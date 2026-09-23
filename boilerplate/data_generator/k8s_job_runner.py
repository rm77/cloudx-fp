"""
data_generator/k8s_job_runner.py
===================================
Pengganti job_runner.py untuk eksekusi di Kubernetes/kind -- menerima
objek Scenario yang SAMA PERSIS dari registry (scenario_base.py TIDAK
BERUBAH). Submit Pod 2-container (job + sidecar telemetri, berbagi PID
namespace), tunggu selesai, tarik CSV keluar via `kubectl cp`, hapus Pod.

VERSI TANPA GPU: `request_gpu` default False, dan TIDAK PERNAH
menambahkan `resources.limits: {"nvidia.com/gpu": ...}` ke Pod manifest.
Cluster kind tanpa NVIDIA device plugin tidak mengiklankan resource
tersebut sebagai allocatable -- Pod yang memintanya akan macet status
Pending selamanya (tidak ada node yang match). JANGAN set request_gpu=True
kecuali device plugin sudah dipasang & diverifikasi (lihat catatan di
instruksi pipeline).

Prasyarat: pip install kubernetes
           kubeconfig sudah menunjuk ke cluster kind aktif
"""

import json
import os
import subprocess
import time

from kubernetes import client, config

from scenario_base import Scenario

NAMESPACE = os.environ.get("K8S_NAMESPACE", "testbed-jobs")
JOB_IMAGE = os.environ.get("JOB_IMAGE", "local/data-generator-job:latest")

_config_loaded = False


def _ensure_kube_config():
    global _config_loaded
    if not _config_loaded:
        config.load_kube_config()
        _config_loaded = True


def _kubectl_cp(pod_name, container, src_in_pod, dst_local):
    subprocess.check_call([
        "kubectl", "cp", f"{NAMESPACE}/{pod_name}:{src_in_pod}", dst_local,
        "-c", container,
    ])


def _pod_name_from_session(session_id: str) -> str:
    # Nama Pod harus DNS-1123: lowercase, "_" tidak diizinkan -> ganti "-"
    return f"session-{session_id}".replace("_", "-").lower()


def build_pod_manifest(scenario: Scenario, session_id: str, args: list,
                        interval_sec: float, extra_meta: dict,
                        request_gpu: bool = False):
    job_cmd_match = os.path.basename(scenario.script_path)

    job_resources = {}
    if request_gpu:
        # Hanya aktif jika device plugin GPU sudah terpasang -- lihat
        # docstring modul ini. Default False untuk cluster tanpa GPU.
        job_resources = {"limits": {"nvidia.com/gpu": "1"}}

    job_container = {
        "name": "job",
        "image": JOB_IMAGE,
        "command": ["python", scenario.script_path] + args,
        "volumeMounts": [{"name": "shared-data", "mountPath": "/data"}],
        "resources": job_resources,
    }

    telemetry_container = {
        "name": "telemetry",
        "image": JOB_IMAGE,
        "command": ["python", "/app/telemetry_sidecar.py"],
        "env": [
            {"name": "SESSION_ID", "value": session_id},
            {"name": "LABEL", "value": scenario.label},
            {"name": "JOB_TYPE", "value": scenario.name},
            {"name": "JOB_CMD_MATCH", "value": job_cmd_match},
            {"name": "INTERVAL_SEC", "value": str(interval_sec)},
            {"name": "EXTRA_META_JSON", "value": json.dumps(extra_meta or {})},
        ],
        "volumeMounts": [{"name": "shared-data", "mountPath": "/data"}],
    }

    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": _pod_name_from_session(session_id),
            "namespace": NAMESPACE,
            "labels": {"session_id": session_id, "label": scenario.label,
                        "job_type": scenario.name},
        },
        "spec": {
            "shareProcessNamespace": True,
            "restartPolicy": "Never",
            "containers": [job_container, telemetry_container],
            "volumes": [{"name": "shared-data", "emptyDir": {}}],
        },
    }


def run_labeled_job(scenario: Scenario, session_id: str, out_dir="data",
                     interval_sec=5.0, args_override=None, extra_meta=None,
                     request_gpu=False):
    """
    Signature SAMA PERSIS dengan job_runner.run_labeled_job() (versi
    subprocess lokal) -- run_experiment.py bisa memakai salah satu
    tanpa mengubah cara pemanggilan, hanya beda modul yang di-import.
    """
    _ensure_kube_config()
    v1 = client.CoreV1Api()

    args = args_override if args_override is not None else scenario.default_args
    timeout_sec = scenario.timeout_sec or 600

    pod_manifest = build_pod_manifest(
        scenario, session_id, args, interval_sec, extra_meta, request_gpu,
    )
    pod_name = pod_manifest["metadata"]["name"]

    v1.create_namespaced_pod(namespace=NAMESPACE, body=pod_manifest)
    print(f"[k8s_job_runner] Pod {pod_name} dibuat (scenario={scenario.name}), "
          f"menunggu job selesai (timeout={timeout_sec}s)...")

    start = time.time()
    job_done = False
    while time.time() - start < timeout_sec + 30:  # +30s toleransi start-up image
        try:
            pod = v1.read_namespaced_pod_status(pod_name, NAMESPACE)
        except client.ApiException as e:
            print(f"[k8s_job_runner] gagal baca status Pod: {e}")
            break
        statuses = {c.name: c.state for c in (pod.status.container_statuses or [])}
        job_state = statuses.get("job")
        if job_state and job_state.terminated is not None:
            job_done = True
            break
        time.sleep(3)

    if not job_done:
        print(f"[k8s_job_runner] TIMEOUT/gagal -- job {session_id} tidak "
              f"selesai dalam batas waktu.")

    # Tunggu sidecar menulis penanda /data/DONE (tanda CSV siap diambil)
    done_deadline = time.time() + max(interval_sec * 3, 15)
    while time.time() < done_deadline:
        check = subprocess.run(
            ["kubectl", "exec", "-n", NAMESPACE, pod_name, "-c", "telemetry",
             "--", "test", "-f", "/data/DONE"],
            capture_output=True,
        )
        if check.returncode == 0:
            break
        time.sleep(2)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{session_id}.csv")
    try:
        _kubectl_cp(pod_name, "telemetry", "/data/telemetry.csv", out_path)
    except subprocess.CalledProcessError:
        print(f"[k8s_job_runner] WARNING: gagal mengambil CSV dari {pod_name}")
        out_path = None

    try:
        v1.delete_namespaced_pod(pod_name, NAMESPACE, grace_period_seconds=0)
    except client.ApiException:
        pass

    print(f"[k8s_job_runner] session={session_id} scenario={scenario.name} "
          f"label={scenario.label} -> {out_path}")
    return out_path
