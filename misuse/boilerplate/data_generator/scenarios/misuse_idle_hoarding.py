"""
scenarios/misuse_idle_hoarding.py
====================================
Job MISUSE: GPU idle-hoarding. Mengalokasikan memori GPU lalu idle
dalam waktu lama tanpa komputasi nyata. Signature: GPU memory tinggi
konstan, GPU utilization mendekati 0%.
"""
import argparse
import time

import torch

from scenario_base import Scenario
from registry import register


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration-sec", type=int, default=600)
    ap.add_argument("--hold-mem-mb", type=int, default=2048)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    n_floats = int(args.hold_mem_mb * 1024 * 1024 / 4)
    _held = torch.empty(n_floats, device=device)

    start = time.time()
    while time.time() - start < args.duration_sec:
        time.sleep(5)

    print("[misuse_idle_hoarding] selesai (GPU ditahan tanpa komputasi).")


register(Scenario(
    name="misuse_idle_hoarding",
    label="misuse",
    script_path="scenarios/misuse_idle_hoarding.py",
    default_args=["--duration-sec", "600"],
    timeout_sec=620,  # tidak berhenti sendiri lebih awal dari durasi -> beri toleransi
    description="GPU memory tinggi konstan, utilization ~0% sepanjang sesi.",
))


if __name__ == "__main__":
    main()
