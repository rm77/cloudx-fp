"""
detector/k8s_integration/daemon_scorer/main.py
=================================================
Pola integrasi: POLLING PERIODIK. Berjalan sebagai DaemonSet (1
instance per node) atau Deployment (terpusat) -- pilih sesuai
kebutuhan riset. Secara berkala membaca metrik Pod dan memberi skor
anomali, lalu menulis hasilnya sebagai label/annotation pada Pod
tersebut.

GENERIK terhadap model: model dimuat lewat BaseDetector.load(), skor
dihitung lewat model.score() -- kode ini tidak berubah apapun model
yang dipakai (Isolation Forest, LSTM-AE, clustering, ensemble, dst),
selama subclass BaseDetector diimplementasikan dengan benar.

Cocok dipakai untuk: deteksi real-time dengan latensi longgar (siklus
polling detik-menit), TIDAK memblokir penjadwalan pod (beda dari pola
webhook_server/).
"""

import importlib
import os
import time

DETECTOR_CLASS_PATH = os.environ["DETECTOR_CLASS_PATH"]  # mis. "my_model.MyDetector"
MODEL_PATH = os.environ.get("MODEL_PATH", "/model/model.bin")
FEATURE_MODE = os.environ.get("FEATURE_MODE", "aggregate")  # "aggregate" | "sequence"
THRESHOLD = float(os.environ.get("ANOMALY_THRESHOLD", "0.0"))
TARGET_NAMESPACE = os.environ.get("TARGET_NAMESPACE", "default")
NODE_NAME = os.environ.get("NODE_NAME")  # diisi Downward API jika mode DaemonSet
POLL_INTERVAL_SEC = float(os.environ.get("POLL_INTERVAL_SEC", "15"))

ANOMALY_SCORE_ANNOTATION = "testbed.io/anomaly-score"
ANOMALY_FLAG_LABEL = "testbed.io/anomaly-flag"


def load_model():
    module_path, class_name = DETECTOR_CLASS_PATH.rsplit(".", 1)
    DetectorClass = getattr(importlib.import_module(module_path), class_name)
    return DetectorClass.load(MODEL_PATH)


def get_target_pods():
    """
    TODO (mahasiswa):
      - Query Kubernetes API (kubernetes python client,
        `config.load_incluster_config()`) untuk Pod di
        `TARGET_NAMESPACE`.
      - Jika mode DaemonSet (per-node): filter
        `spec.nodeName == NODE_NAME`. Jika mode Deployment terpusat:
        tidak perlu filter node.
      - Kembalikan list objek Pod (atau minimal nama + metadata yang
        dibutuhkan fetch_pod_features()).
    """
    raise NotImplementedError


def fetch_pod_features(pod):
    """
    TODO (mahasiswa) -- INI BAGIAN YANG PALING SPESIFIK-PROYEK, karena
    bergantung pada dari mana metrik pod diambil:
      - Snapshot sesaat: Metrics Server (`metrics.k8s.io/v1beta1`) untuk
        CPU/mem, DCGM-exporter (via query langsung atau lewat
        Prometheus) untuk GPU.
      - Window waktu (FEATURE_MODE="sequence"): query Prometheus HTTP
        API `/api/v1/query_range` untuk rentang waktu tertentu.
      - Susun jadi vektor/array fitur dengan URUTAN KOLOM SAMA PERSIS
        seperti saat training (lihat artefak `feature_cols` /
        `scaler` yang disimpan model.save() -- pastikan detector Anda
        MENYIMPAN metadata ini, bukan cuma parameter model, supaya
        bisa dipakai ulang di sini).
    """
    raise NotImplementedError


def label_pod(pod, score: float, is_anomaly: bool):
    """
    TODO (mahasiswa):
      - Patch Pod (kubernetes python client
        `patch_namespaced_pod`) untuk menambah:
          annotations[ANOMALY_SCORE_ANNOTATION] = str(score)
          labels[ANOMALY_FLAG_LABEL] = "true"/"false"
      - Label/annotation inilah yang dibaca komponen controller/
        untuk memutuskan tindakan remediasi.
    """
    raise NotImplementedError


def main_loop():
    model = load_model()
    print(f"[daemon_scorer] model dimuat ({DETECTOR_CLASS_PATH}), "
          f"feature_mode={FEATURE_MODE}, namespace={TARGET_NAMESPACE}, "
          f"node={NODE_NAME or '(semua node)'}")

    while True:
        try:
            pods = get_target_pods()
            for pod in pods:
                features = fetch_pod_features(pod)
                score = float(model.score(features.reshape(1, -1))[0])
                is_anomaly = score > THRESHOLD
                label_pod(pod, score, is_anomaly)
        except NotImplementedError:
            raise
        except Exception as e:
            print(f"[daemon_scorer] error pada siklus polling: {e}")
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main_loop()
