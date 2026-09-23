"""
detector/k8s_integration/webhook_server/main.py
==================================================
Pola integrasi: ADMISSION TIME (sebelum Pod dijadwalkan). Kubernetes
API server memanggil endpoint HTTPS ini secara SINKRON setiap ada
permintaan create/update Pod yang cocok dengan aturan di
ValidatingWebhookConfiguration -- keputusan di sini bisa menolak
permintaan sebelum Pod bahkan mulai berjalan.

GENERIK terhadap model: sama seperti daemon_scorer/, model dimuat
lewat BaseDetector.load(). Perbedaan pola integrasi ada di SUMBER
FITUR: di admission time TIDAK ADA metrik runtime (GPU util, dst)
karena Pod belum berjalan -- fitur yang tersedia terbatas pada
METADATA request (resource requests/limits, label, ServiceAccount).

PENTING: model yang dilatih dari data RUNTIME (dataset data_generator/)
punya fitur berbeda dari yang tersedia di admission time -- ini
keterbatasan mendasar yang WAJIB didiskusikan di laporan, bukan
disembunyikan. Salah satu solusi: latih detector KEDUA khusus untuk
fitur admission-time saja (mis. rasio resource yang diminta terhadap
riwayat kuota), tetap lewat BaseDetector yang sama.
"""

import importlib
import json
import os
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer

DETECTOR_CLASS_PATH = os.environ["DETECTOR_CLASS_PATH"]
MODEL_PATH = os.environ.get("MODEL_PATH", "/model/model.bin")
THRESHOLD = float(os.environ.get("ANOMALY_THRESHOLD", "0.0"))
TLS_CERT_PATH = os.environ.get("TLS_CERT_PATH", "/certs/tls.crt")
TLS_KEY_PATH = os.environ.get("TLS_KEY_PATH", "/certs/tls.key")


def load_model():
    module_path, class_name = DETECTOR_CLASS_PATH.rsplit(".", 1)
    DetectorClass = getattr(importlib.import_module(module_path), class_name)
    return DetectorClass.load(MODEL_PATH)


def extract_admission_time_features(admission_review: dict):
    """
    TODO (mahasiswa):
      - Ambil objek Pod yang DIMINTA dari
        `admission_review["request"]["object"]`.
      - Susun fitur dari METADATA request saja: resource
        requests/limits (`spec.containers[].resources`), label/
        annotation identitas, namespace, ServiceAccount pemohon.
      - Bandingkan terhadap ResourceQuota resmi namespace (query K8s
        API) jika relevan untuk skenario yang dipakai.
    """
    raise NotImplementedError


def decide_admission(features, model) -> dict:
    """
    TODO (mahasiswa):
      - score = model.score(features.reshape(1, -1))[0]
      - allowed = score <= THRESHOLD
      - Kembalikan {"allowed": bool, "status": {"message": "..."}}.
      - Pertimbangkan mode dry-run (selalu allowed=True, hanya log)
        di awal pengembangan sebelum benar-benar menolak request.
    """
    raise NotImplementedError


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))

        try:
            features = extract_admission_time_features(body)
            decision = decide_admission(features, self.server.model)
        except NotImplementedError:
            # TODO: fail-open sementara -- HAPUS setelah implementasi
            # decide_admission() selesai, supaya cluster tidak macet
            # akibat webhook belum lengkap.
            decision = {"allowed": True,
                         "status": {"message": "webhook belum diimplementasikan"}}

        response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": body["request"]["uid"],
                "allowed": decision["allowed"],
                "status": decision.get("status", {}),
            },
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())


def main():
    model = load_model()
    server = HTTPServer(("0.0.0.0", 8443), WebhookHandler)
    server.model = model

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=TLS_CERT_PATH, keyfile=TLS_KEY_PATH)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print(f"[webhook_server] model dimuat ({DETECTOR_CLASS_PATH}), listening :8443")
    server.serve_forever()


if __name__ == "__main__":
    main()
