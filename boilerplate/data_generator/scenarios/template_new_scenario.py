"""
scenarios/template_new_scenario.py
=====================================
TEMPLATE untuk menambah skenario benign/misuse BARU. Salin file ini,
ganti nama file & isi sesuai kebutuhan, dan skenario Anda otomatis
terdeteksi oleh registry.discover_scenarios() -- TIDAK ADA file lain
yang perlu diubah.

Langkah:
  1. Salin file ini -> scenarios/misuse_nama_skenario_anda.py
  2. Ganti fungsi main() dengan logika job yang merepresentasikan
     pola resource yang ingin Anda simulasikan.
  3. Sesuaikan argparse sesuai parameter yang relevan (durasi,
     intensitas, dsb).
  4. Isi register(Scenario(...)) di bagian bawah dengan metadata yang
     BENAR -- terutama `label` dan `timeout_sec` (lihat penjelasan di
     scenario_base.py).
  5. Uji jalankan standalone dulu: `python scenarios/misuse_nama_anda.py --help`
  6. Jalankan run_experiment.py -- skenario baru otomatis ikut
     terpanggil tanpa konfigurasi tambahan.

Contoh ide skenario misuse lain yang BELUM ada di boilerplate ini,
sebagai referensi (hapus/ganti sesuai kebutuhan riset Anda):
  - Multi-GPU fragmentation: job yang sengaja meminta banyak GPU kecil-
    kecil (bukan 1 GPU penuh) untuk menghindari deteksi threshold per-GPU.
  - Bursty/intermittent abuse: job yang aktif sangat singkat (mis. 5
    detik) lalu idle lama berulang-ulang, mencoba tetap di bawah radar
    rata-rata window waktu tertentu.
  - Network exfiltration proxy: job dengan I/O (bukan GPU) yang
    mencurigakan -- transfer data besar terus-menerus tanpa pola
    training yang jelas (butuh tambahan kolom telemetri jaringan jika
    ingin direpresentasikan akurat -- lihat catatan NUMERIC_TELEMETRY_COLUMNS
    di detector/common/feature_engineering.py, kolom baru perlu
    ditambahkan di kedua tempat).
"""
import argparse
import time

# import torch  # jika skenario Anda perlu GPU

from scenario_base import Scenario
from registry import register


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration-sec", type=int, default=600)
    # TODO: tambahkan argumen lain sesuai kebutuhan skenario Anda
    args = ap.parse_args()

    start = time.time()
    while time.time() - start < args.duration_sec:
        # TODO: implementasikan pola resource yang ingin disimulasikan
        # di sini -- ini bagian INTI yang menentukan signature
        # telemetri skenario Anda (lihat contoh-contoh skenario lain
        # di folder ini untuk pola: konstan, siklik, idle, dsb).
        time.sleep(1)

    print("[template_new_scenario] selesai.")


register(Scenario(
    name="TODO_ganti_nama_unik",       # WAJIB unik di antara semua skenario
    label="misuse",                     # "benign" atau "misuse"
    script_path="scenarios/TODO_nama_file_ini.py",
    default_args=["--duration-sec", "600"],
    timeout_sec=620,                    # None jika skenario berhenti sendiri
    description="TODO: jelaskan pola telemetri yang diharapkan dari skenario ini.",
))


if __name__ == "__main__":
    main()
