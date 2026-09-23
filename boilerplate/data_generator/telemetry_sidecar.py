"""
data_generator/telemetry_sidecar.py
=====================================
Berjalan sebagai SIDECAR CONTAINER di dalam Pod yang sama dengan job
container, memanfaatkan `shareProcessNamespace: true` pada Pod spec
supaya sidecar bisa melihat proses job lewat psutil walau beda
container. Versi ini dipakai untuk CLUSTER TANPA GPU -- kolom GPU
akan bernilai None (nvidia-smi tidak ada), TIDAK menyebabkan error,
tapi juga tidak memberi sinyal. Sinyal misuse tetap terekam lewat
CPU/memori/IO, karena torch.device("cuda" if ... else "cpu") pada
skenario otomatis fallback ke CPU -- alokasi "GPU memory" pada
misuse_idle_hoarding, misuse_zombie_job, dsb otomatis menjadi alokasi
RAM biasa, sehingga tetap tertangkap oleh kolom mem_rss_mb.

Environment variables (diisi dari Pod spec):
  SESSION_ID, LABEL, JOB_TYPE, JOB_CMD_MATCH, INTERVAL_SEC,
  EXTRA_META_JSON (lihat k8s_job_runner.py)
"""

import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import psutil

OUT_PATH = "/data/telemetry.csv"
POLL_FOR_TARGET_SEC = 30


def _run(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def get_gpu_device_stats():
    """Tanpa GPU: nvidia-smi tidak ada di PATH -> _run() gagal senyap,
    seluruh kolom GPU bernilai None. Tidak menyebabkan error di baris
    manapun -- ini SENGAJA didesain graceful degradation."""
    out = _run(["nvidia-smi",
                 "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total",
                 "--format=csv,noheader,nounits"])
    if not out:
        return {"gpu_util_pct": None, "gpu_mem_util_pct": None,
                 "gpu_mem_used_mb": None, "gpu_mem_total_mb": None}
    parts = [p.strip() for p in out.split(",")]
    return {"gpu_util_pct": float(parts[0]), "gpu_mem_util_pct": float(parts[1]),
             "gpu_mem_used_mb": float(parts[2]), "gpu_mem_total_mb": float(parts[3])}


def get_process_gpu_memory_mb(pids):
    out = _run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                 "--format=csv,noheader,nounits"])
    if not out:
        return 0.0
    total, pid_set = 0.0, set(pids)
    for line in out.splitlines():
        try:
            pid_str, mem_str = [x.strip() for x in line.split(",")]
            if int(pid_str) in pid_set:
                total += float(mem_str)
        except Exception:
            continue
    return total


def find_target_root_pid(cmd_match):
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(p.info["cmdline"] or [])
            if cmd_match in cmdline:
                return p.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def collect_pid_tree(root_pid):
    pids = [root_pid]
    try:
        root = psutil.Process(root_pid)
        pids += [c.pid for c in root.children(recursive=True)]
    except psutil.NoSuchProcess:
        pass
    return pids


def get_process_cpu_mem_io(pids):
    cpu_pct = mem_rss_mb = io_read_mb = io_write_mb = 0.0
    alive = 0
    for pid in pids:
        try:
            p = psutil.Process(pid)
            cpu_pct += p.cpu_percent(interval=None)
            mem_rss_mb += p.memory_info().rss / (1024 ** 2)
            io = p.io_counters()
            io_read_mb += io.read_bytes / (1024 ** 2)
            io_write_mb += io.write_bytes / (1024 ** 2)
            alive += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"cpu_pct": cpu_pct, "mem_rss_mb": mem_rss_mb,
             "io_read_mb": io_read_mb, "io_write_mb": io_write_mb,
             "num_alive_processes": alive}


def main():
    session_id = os.environ["SESSION_ID"]
    label = os.environ["LABEL"]
    job_type = os.environ["JOB_TYPE"]
    cmd_match = os.environ["JOB_CMD_MATCH"]
    interval_sec = float(os.environ.get("INTERVAL_SEC", "5"))
    extra_meta = json.loads(os.environ.get("EXTRA_META_JSON", "{}"))

    print(f"[telemetry_sidecar] menunggu proses target (match='{cmd_match}')...",
          flush=True)
    start_wait = time.time()
    root_pid = None
    while time.time() - start_wait < POLL_FOR_TARGET_SEC:
        root_pid = find_target_root_pid(cmd_match)
        if root_pid is not None:
            break
        time.sleep(1)

    if root_pid is None:
        print("[telemetry_sidecar] proses target tidak ditemukan, keluar.", flush=True)
        sys.exit(1)

    print(f"[telemetry_sidecar] target ditemukan pid={root_pid}, mulai rekam.",
          flush=True)

    fieldnames = [
        "timestamp", "session_id", "label", "job_type",
        "cpu_pct", "mem_rss_mb", "io_read_mb", "io_write_mb",
        "num_alive_processes", "gpu_util_pct", "gpu_mem_util_pct",
        "gpu_mem_used_mb_device", "gpu_mem_used_mb_process",
    ] + list(extra_meta.keys())

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for pid in collect_pid_tree(root_pid):
            try:
                psutil.Process(pid).cpu_percent(interval=None)
            except Exception:
                pass

        while True:
            pids = collect_pid_tree(root_pid)
            if not pids or not psutil.pid_exists(root_pid):
                print("[telemetry_sidecar] proses target selesai, berhenti.",
                      flush=True)
                break

            proc_stats = get_process_cpu_mem_io(pids)
            gpu_dev = get_gpu_device_stats()
            gpu_proc_mem = get_process_gpu_memory_mb(pids)

            row = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id, "label": label, "job_type": job_type,
                "cpu_pct": round(proc_stats["cpu_pct"], 3),
                "mem_rss_mb": round(proc_stats["mem_rss_mb"], 3),
                "io_read_mb": round(proc_stats["io_read_mb"], 3),
                "io_write_mb": round(proc_stats["io_write_mb"], 3),
                "num_alive_processes": proc_stats["num_alive_processes"],
                "gpu_util_pct": gpu_dev["gpu_util_pct"],
                "gpu_mem_util_pct": gpu_dev["gpu_mem_util_pct"],
                "gpu_mem_used_mb_device": gpu_dev["gpu_mem_used_mb"],
                "gpu_mem_used_mb_process": round(gpu_proc_mem, 3),
            }
            row.update(extra_meta)
            writer.writerow(row)
            f.flush()
            time.sleep(interval_sec)

    with open("/data/DONE", "w") as f:
        f.write("done")


if __name__ == "__main__":
    main()
