# data_generator — Boilerplate Generator Dataset (Plugin Skenario)

Menghasilkan dataset telemetri berlabel (benign vs berbagai jenis
misuse) lewat sistem skenario yang bisa DIPERLUAS tanpa mengubah kode
inti (`job_runner.py`, `run_experiment.py`, `registry.py`).

## Struktur

```
data_generator/
├── scenario_base.py          # kontrak (dataclass) Scenario
├── registry.py                # plugin registry + auto-discovery
├── telemetry_logger.py        # perekam CPU/mem/GPU/IO -> CSV
├── job_runner.py              # jalankan 1 sesi dari Scenario + rekam
├── run_experiment.py          # orchestrator config-driven
└── scenarios/
    ├── benign_cnn_training.py
    ├── benign_eda_notebook.py
    ├── misuse_idle_hoarding.py
    ├── misuse_synthetic_load.py
    ├── misuse_zombie_job.py
    ├── misuse_disguised_pattern.py
    ├── misuse_quota_exceed.py
    └── template_new_scenario.py   # <- salin file ini untuk misuse baru
```

## Cara kerja sistem plugin

1. Tiap file di `scenarios/` berisi fungsi `main()` (job yang
   dijalankan sebagai proses) DAN satu baris `register(Scenario(...))`
   di bagian bawah file, dieksekusi saat modulnya di-import.
2. `registry.discover_scenarios()` meng-import SEMUA modul di
   `scenarios/` secara otomatis (pakai `pkgutil.iter_modules`), memicu
   efek samping `register()` di tiap file.
3. `run_experiment.py` memanggil `discover_scenarios()` lalu
   `all_scenarios()` untuk mendapat daftar lengkap — **tidak ada
   daftar skenario yang di-hardcode di file manapun**.

**Menambah jenis misuse baru = 1 langkah:** salin
`scenarios/template_new_scenario.py`, isi logika `main()` dan metadata
`register(Scenario(...))`, selesai. `run_experiment.py` langsung
mengikutsertakannya di run berikutnya.

## Instalasi

```bash
pip install torch psutil pandas numpy
```

## Menjalankan

```bash
# Jalankan SEMUA skenario terdaftar, 10 putaran
python run_experiment.py --repeats 10 --out-dir data

# Hanya skenario tertentu (mis. untuk uji cepat 1 skenario baru)
python run_experiment.py --repeats 2 --scenarios misuse_idle_hoarding

# Uji 1 skenario secara standalone (tanpa runner/telemetry)
python scenarios/misuse_idle_hoarding.py --duration-sec 30
```

Output: `data/<session_id>.csv` per sesi, digabung otomatis jadi
`data/dataset.csv` di akhir proses.

## Menangani skenario dengan metadata tambahan (mis. kuota)

Skenario seperti `misuse_quota_exceed.py` butuh kolom tambahan di CSV
(`claimed_quota_mb`) yang tidak ada di skenario lain. Oper lewat
`extra_meta` saat memanggil `run_labeled_job()` langsung (bukan lewat
`run_experiment.py` generik, yang tidak tahu skenario mana butuh
metadata apa):

```python
from registry import discover_scenarios, get
from job_runner import run_labeled_job

discover_scenarios()
scenario = get("misuse_quota_exceed")
run_labeled_job(
    scenario, session_id="custom_001", out_dir="data",
    extra_meta={"claimed_quota_mb": 1024},
)
```

TODO (mahasiswa): jika BANYAK skenario butuh extra_meta yang berbeda-
beda, pertimbangkan menambah field `extra_meta_template: dict` di
`Scenario` (scenario_base.py) supaya `run_experiment.py` generik bisa
otomatis mengopernya tanpa kode khusus per skenario.

## Menjalankan di Kubernetes/kind (bukan lokal)

Boilerplate ini menjalankan skenario sebagai `subprocess` lokal
(`job_runner.py`). Untuk menjalankan di cluster kind, ganti
`job_runner.py` dengan versi yang submit Kubernetes Pod (2 container:
job + telemetry sidecar dengan `shareProcessNamespace: true`) — pola
lengkapnya sudah pernah didiskusikan sebelumnya di percakapan ini;
struktur `Scenario`/`registry.py` di boilerplate ini TIDAK PERLU
berubah sama sekali untuk pindah ke K8s, karena keduanya sudah
independen dari cara job dieksekusi (lihat `scenario.script_path` yang
sengaja generik, bisa diartikan sebagai path lokal maupun path di
dalam container image).
