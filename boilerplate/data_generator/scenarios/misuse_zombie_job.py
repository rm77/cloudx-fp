"""
scenarios/misuse_zombie_job.py
=================================
Job MISUSE: zombie job. Proses hidup lama tanpa aktivitas apapun,
merepresentasikan job yang tidak dibersihkan otomatis. Harus dihentikan
paksa lewat timeout_sec eksternal (bukan berhenti sendiri).
"""
import argparse
import time

import torch

from scenario_base import Scenario
from registry import register


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration-sec", type=int, default=1200)
    ap.add_argument("--hold-mem-mb", type=int, default=512)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    n_floats = int(args.hold_mem_mb * 1024 * 1024 / 4)
    _held = torch.empty(n_floats, device=device)

    start = time.time()
    while time.time() - start < args.duration_sec:
        time.sleep(10)

    print("[misuse_zombie_job] selesai.")


register(Scenario(
    name="misuse_zombie_job",
    label="misuse",
    script_path="scenarios/misuse_zombie_job.py",
    default_args=["--duration-sec", "1200"],
    timeout_sec=1220,
    description="Proses hidup lama, benar-benar flat, tidak pernah berhenti sendiri.",
))


if __name__ == "__main__":
    main()
