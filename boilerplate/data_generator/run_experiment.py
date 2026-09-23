"""
data_generator/run_experiment.py
===================================
Orchestrator GENERIK -- tidak menyebut satu pun nama skenario secara
eksplisit di file ini. Daftar skenario yang dijalankan diambil dari
registry.discover_scenarios() (otomatis menemukan seluruh file di
scenarios/), sehingga menambah/menghapus skenario di folder scenarios/
langsung mengubah dataset yang dihasilkan tanpa menyentuh file ini.

Contoh pemakaian:
    python run_experiment.py --repeats 10 --out-dir data
    python run_experiment.py --repeats 5 --scenarios benign_cnn_training,misuse_idle_hoarding
"""

import argparse
import glob
import os
import random

import pandas as pd

from registry import discover_scenarios, all_scenarios, get


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=10,
                     help="berapa kali seluruh set skenario diulang")
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--interval-sec", type=float, default=5.0)
    ap.add_argument("--scenarios", default=None,
                     help="daftar nama skenario dipisah koma (default: SEMUA "
                          "skenario yang terdaftar di scenarios/)")
    ap.add_argument("--executor", choices=["local", "k8s"], default="local",
                     help="'local': subprocess di mesin ini (job_runner.py). "
                          "'k8s': submit Pod ke cluster kind aktif "
                          "(k8s_job_runner.py) -- kubeconfig harus sudah "
                          "menunjuk ke cluster yang benar.")
    args = ap.parse_args()

    if args.executor == "local":
        from job_runner import run_labeled_job
    else:
        from k8s_job_runner import run_labeled_job

    discover_scenarios()  # import semua modul di scenarios/ -> trigger register()

    if args.scenarios:
        names = [s.strip() for s in args.scenarios.split(",")]
        scenarios = [get(name) for name in names]
    else:
        scenarios = all_scenarios()

    if not scenarios:
        raise RuntimeError(
            "Tidak ada skenario terdaftar -- pastikan folder scenarios/ "
            "berisi file skenario yang memanggil registry.register()."
        )

    print(f"[run_experiment] {len(scenarios)} skenario ditemukan: "
          f"{[s.name for s in scenarios]}")

    os.makedirs(args.out_dir, exist_ok=True)
    run_idx = 0

    for repeat in range(args.repeats):
        order = scenarios[:]
        random.shuffle(order)  # acak urutan tiap putaran, hindari bias waktu
        for scenario in order:
            run_idx += 1
            session_id = f"{scenario.name}_{run_idx:04d}"
            run_labeled_job(
                scenario=scenario,
                session_id=session_id,
                out_dir=args.out_dir,
                interval_sec=args.interval_sec,
            )

    all_csvs = glob.glob(os.path.join(args.out_dir, "*.csv"))
    all_csvs = [f for f in all_csvs if os.path.getsize(f) > 0]
    if not all_csvs:
        print("[run_experiment] tidak ada CSV dihasilkan, dataset gabungan dilewati.")
        return

    df = pd.concat([pd.read_csv(f) for f in all_csvs], ignore_index=True)
    out_path = os.path.join(args.out_dir, "dataset.csv")
    df.to_csv(out_path, index=False)
    print(f"[run_experiment] dataset final: {out_path} ({len(df)} baris, "
          f"{df['session_id'].nunique()} sesi, "
          f"{df.groupby('job_type')['session_id'].nunique().to_dict()})")


if __name__ == "__main__":
    main()
