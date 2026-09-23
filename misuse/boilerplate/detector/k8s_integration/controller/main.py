"""
detector/k8s_integration/controller/main.py
==============================================
Pola integrasi: WATCH + REMEDIASI. Mengawasi Pod yang sudah diberi
label/annotation anomali (hasil daemon_scorer/), dan memicu tindakan
saat kondisi tertentu terpenuhi. Berbeda dari webhook_server (blocking,
admission time) -- controller ini REAKTIF terhadap Pod yang SUDAH
berjalan, cocok untuk remediasi bertingkat (throttle -> notify ->
evict) berdasarkan tingkat keyakinan.

GENERIK terhadap model DAN terhadap jenis remediasi: logika keputusan
"tindakan apa yang diambil" dipisah dari "bagaimana tindakan itu
dieksekusi" (lihat REMEDIATION_ACTIONS), supaya menambah level
remediasi baru tidak perlu mengubah alur watch utama.
"""

import os

from kubernetes import client, config, watch

NAMESPACE = os.environ.get("TARGET_NAMESPACE", "default")
ANOMALY_FLAG_LABEL = "testbed.io/anomaly-flag"
ANOMALY_SCORE_ANNOTATION = "testbed.io/anomaly-score"


def decide_remediation_level(pod) -> str:
    """
    TODO (mahasiswa):
      - Baca skor dari annotation ANOMALY_SCORE_ANNOTATION (ditulis
        daemon_scorer/), tentukan level remediasi.
      - Contoh kerangka ambang bertingkat (sesuaikan angka & jumlah
        level dengan kebutuhan riset -- bisa cuma 1 level "evict" saja
        untuk pendekatan sederhana):
            score < T1                -> "none"
            T1 <= score < T2          -> "throttle"
            T2 <= score < T3          -> "notify"
            score >= T3               -> "evict"
      - Pertimbangkan histori (butuh N deteksi berturut-turut sebelum
        eskalasi) untuk mengurangi dampak false positive dari satu
        snapshot skor yang kebetulan menyimpang.

    Returns
    -------
    str  salah satu key di REMEDIATION_ACTIONS (termasuk "none").
    """
    raise NotImplementedError


def action_none(pod, v1_api):
    pass  # tidak melakukan apapun


def action_notify(pod, v1_api):
    """
    TODO (mahasiswa):
      - Buat Kubernetes Event terkait pod
        (`v1_api.create_namespaced_event` atau
        `CoreV1Event`/`EventsV1Event` tergantung versi API) supaya
        tercatat di `kubectl describe pod` dan/atau
        `kubectl get events`.
      - Opsional: kirim notifikasi eksternal (webhook Slack, dst).
    """
    raise NotImplementedError


def action_throttle(pod, v1_api):
    """
    TODO (mahasiswa):
      - K8s tidak native mendukung update SEMUA jenis resource limit
        pada Pod yang sedang berjalan (in-place pod resize masih
        terbatas per versi K8s) -- riset opsi yang tersedia di versi
        cluster Anda, atau alternatif: turunkan prioritas/QoS,
        atau gunakan pendekatan cgroup langsung via privileged sidecar
        (dokumentasikan keterbatasannya di laporan jika dipakai).
    """
    raise NotImplementedError


def action_evict(pod, v1_api):
    """
    TODO (mahasiswa):
      - Pakai Kubernetes Eviction API
        (`v1_api.create_namespaced_pod_eviction`), BUKAN
        delete_namespaced_pod langsung, supaya PodDisruptionBudget
        (jika ada) dihormati.
      - Catat log/metric setiap eviction (nama pod, skor anomali,
        timestamp) -- data ini jadi bukti evaluasi recall/FPR di
        laporan TA.
    """
    raise NotImplementedError


REMEDIATION_ACTIONS = {
    "none": action_none,
    "notify": action_notify,
    "throttle": action_throttle,
    "evict": action_evict,
}


def watch_pods():
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    w = watch.Watch()

    print(f"[controller] memantau namespace={NAMESPACE}, "
          f"level remediasi tersedia: {list(REMEDIATION_ACTIONS)}")

    for event in w.stream(v1.list_namespaced_pod, namespace=NAMESPACE,
                            label_selector=f"{ANOMALY_FLAG_LABEL}=true"):
        pod = event["object"]
        try:
            level = decide_remediation_level(pod)
            action_fn = REMEDIATION_ACTIONS.get(level)
            if action_fn is None:
                print(f"[controller] level remediasi tidak dikenal: {level}")
                continue
            action_fn(pod, v1)
        except NotImplementedError:
            raise
        except Exception as e:
            print(f"[controller] error pada pod {pod.metadata.name}: {e}")


if __name__ == "__main__":
    watch_pods()
