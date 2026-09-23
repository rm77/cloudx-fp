"""
scenarios/misuse_quota_exceed.py
===================================
Job MISUSE: melebihi kuota resmi yang seharusnya dipatuhi. Berbeda
dari skenario lain di folder ini, skenario ini menghasilkan METADATA
TAMBAHAN (claimed_quota_mb) yang perlu ditangkap runner/telemetry
logger di luar kolom numerik standar -- lihat catatan `extra_meta` di
job_runner.py.
"""
import argparse
import time

import torch

from scenario_base import Scenario
from registry import register


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration-sec", type=int, default=300)
    ap.add_argument("--claimed-quota-mb", type=int, default=1024)
    ap.add_argument("--actual-alloc-mb", type=int, default=4096)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # SENGAJA tidak membatasi diri ke claimed_quota_mb -- mensimulasikan
    # proses yang bypass mekanisme quota enforcement.
    n_floats = int(args.actual_alloc_mb * 1024 * 1024 / 4)
    try:
        _held = torch.empty(n_floats, device=device)
        bypass_success = True
    except RuntimeError:
        bypass_success = False

    a = torch.randn(1024, 1024, device=device)
    b = torch.randn(1024, 1024, device=device)
    start = time.time()
    while time.time() - start < args.duration_sec:
        _ = a @ b
        time.sleep(0.5)

    print(f"[misuse_quota_exceed] claimed={args.claimed_quota_mb}MB "
          f"actual={args.actual_alloc_mb}MB bypass_success={bypass_success}")


register(Scenario(
    name="misuse_quota_exceed",
    label="misuse",
    script_path="scenarios/misuse_quota_exceed.py",
    default_args=["--duration-sec", "300", "--claimed-quota-mb", "1024",
                    "--actual-alloc-mb", "4096"],
    timeout_sec=320,
    description="Alokasi GPU memory jauh melebihi claimed_quota_mb -- "
                 "perlu extra_meta claimed_quota_mb saat run via job_runner.",
))


if __name__ == "__main__":
    main()
