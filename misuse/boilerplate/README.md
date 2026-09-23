# Boilerplate — Deteksi Resource Misuse GPU Cluster (General-Purpose)

Dua bagian independen, masing-masing tidak terikat pada topik/model
riset tertentu:

```
boilerplate/
├── data_generator/   # menghasilkan dataset telemetri berlabel,
│                     # lewat sistem PLUGIN skenario (benign & misuse)
└── detector/         # melatih & mengevaluasi model deteksi + integrasi
                       # K8s, lewat satu KONTRAK model (BaseDetector)
```

## Kenapa dipisah begini

- **`data_generator/`** menjawab "data seperti apa yang tersedia" --
  independen dari model/pendekatan deteksi apapun yang nanti dipakai.
  Menambah jenis misuse baru = tambah 1 file di `scenarios/`.
- **`detector/`** menjawab "bagaimana model dipakai" -- independen
  dari skenario/dataset spesifik. Ganti model = ganti 1 file yang
  mengimplementasikan `BaseDetector`, seluruh training/evaluasi/
  integrasi K8s di sekitarnya tetap sama.

Kedua bagian terhubung lewat SATU KONTRAK: kolom-kolom di
`data_generator/telemetry_logger.py` (`FIELDNAMES`) harus konsisten
dengan `NUMERIC_TELEMETRY_COLUMNS` di
`detector/common/feature_engineering.py`. Keduanya sudah didefinisikan
sinkron di boilerplate ini -- kalau menambah kolom telemetri baru
(mis. metrik jaringan), update DUA tempat ini bersamaan.

## Alur kerja end-to-end

```bash
# 1. Hasilkan dataset (lihat data_generator/README.md)
cd data_generator
python run_experiment.py --repeats 10 --out-dir data

# 2. Implementasikan model Anda (lihat detector/README.md)
cd ../detector
cat model_interface.py   # baca kontrak + contoh kerangka
# -> buat my_model.py berisi subclass BaseDetector

# 3. Latih & evaluasi
python train.py --dataset-csv ../data_generator/data/dataset.csv \
  --detector-class my_model.MyDetector --model-out model_artifacts/model.bin

python evaluate.py --dataset-csv ../data_generator/data/dataset.csv \
  --detector-class my_model.MyDetector --model-path model_artifacts/model.bin

# 4. Pilih pola integrasi K8s yang relevan (lihat detector/README.md)
#    -> daemon_scorer/ dan/atau webhook_server/ dan/atau controller/
```

## Yang perlu diisi sendiri vs yang sudah siap pakai

| Sudah siap pakai (generik) | Perlu diisi (spesifik riset) |
|---|---|
| `scenario_base.py`, `registry.py` | Logika `main()` tiap skenario baru |
| `job_runner.py`, `telemetry_logger.py` | -- |
| `feature_engineering.py`, `evaluation.py` | -- |
| `train.py`, `evaluate.py` (detector) | Implementasi `BaseDetector` Anda |
| Kerangka `daemon_scorer`/`webhook_server`/`controller` | `fetch_pod_features()`, `decide_admission()`, `decide_remediation_level()`, dsb (bagian yang memang bergantung API K8s & keputusan riset) |

Lihat README di masing-masing folder (`data_generator/README.md`,
`detector/README.md`) untuk detail lebih lanjut.
