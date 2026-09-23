# detector — Boilerplate Deteksi (Model-Agnostic)

Boilerplate ini TIDAK terikat pada model atau topik tertentu. Batas
(boundary) antara "model apa yang dipakai" dan "bagaimana model
dipanggil di cluster" dijaga lewat satu kontrak: `model_interface.BaseDetector`.

## Struktur

```
detector/
├── common/
│   ├── feature_engineering.py   # aggregate_sessions() & build_sequences()
│   └── evaluation.py             # precision/recall/F1/FPR/overhead
├── model_interface.py            # BaseDetector -- KONTRAK UTAMA
├── train.py                      # generik, load model via dotted path
├── evaluate.py                   # generik, idem
├── k8s_integration/
│   ├── daemon_scorer/main.py     # pola: polling periodik (DaemonSet/Deployment)
│   ├── webhook_server/main.py    # pola: admission time (blocking)
│   ├── controller/main.py        # pola: watch + remediasi bertingkat
│   └── k8s/*.yaml                 # manifest template (isi REPLACE_ME)
└── DOCKERFILE_TEMPLATE.md
```

## Langkah pemakaian

### 1. Implementasikan model Anda

Buat file baru (mis. `my_model.py`) berisi subclass `BaseDetector`
(lihat kerangka contoh di bagian bawah `model_interface.py`):

```python
from model_interface import BaseDetector

class MyDetector(BaseDetector):
    def fit(self, X): ...      # X: hasil aggregate_sessions() atau build_sequences()
    def score(self, X): ...    # WAJIB: skor lebih tinggi = lebih anomali
    def save(self, path): ...
    @classmethod
    def load(cls, path): ...
```

Ini berlaku untuk model APAPUN: Isolation Forest, LSTM-Autoencoder,
DBSCAN, GMM, atau ensemble gabungan beberapa `BaseDetector` lain
(ensemble itu sendiri juga valid sebagai `BaseDetector`).

### 2. Training & evaluasi — tidak perlu ditulis ulang

```bash
python train.py \
  --dataset-csv ../data_generator/data/dataset.csv \
  --detector-class my_model.MyDetector \
  --model-out model_artifacts/model.bin \
  --feature-mode aggregate   # atau "sequence" untuk model temporal

python evaluate.py \
  --dataset-csv ../data_generator/data/holdout_dataset.csv \
  --detector-class my_model.MyDetector \
  --model-path model_artifacts/model.bin \
  --feature-mode aggregate \
  --target-fpr 0.05
```

### 3. Pilih pola integrasi K8s sesuai kebutuhan riset

Tiga pola sudah disediakan generik di `k8s_integration/` — pilih satu
atau kombinasikan, sesuai apa yang ingin dibuktikan di rumusan masalah:

| Pola | Kapan dipakai | Karakteristik |
|---|---|---|
| `daemon_scorer/` | Deteksi berkelanjutan pada Pod yang sudah berjalan | Non-blocking, siklus polling detik-menit |
| `webhook_server/` | Mencegah Pod bermasalah TERJADWAL sama sekali | Blocking (sinkron), fitur terbatas metadata admission-time |
| `controller/` | Tindak lanjut otomatis atas Pod yang ditandai anomali | Watch-based, remediasi bertingkat (none/notify/throttle/evict) |

Ketiganya memuat model lewat `DETECTOR_CLASS_PATH` (env var, dotted
path yang sama seperti argumen `--detector-class` di atas) — tidak
perlu kode berbeda untuk model berbeda.

### 4. Build & deploy

Lihat `DOCKERFILE_TEMPLATE.md` untuk pola build context (harus dari
root `detector/`, karena tiap komponen mengimpor `common/` dan
`model_interface.py`).

## Bagian yang WAJIB diisi sendiri (tidak generik, spesifik proyek)

- `fetch_pod_features()` di `daemon_scorer/main.py` — cara mengambil
  metrik pod dari Metrics Server/Prometheus/DCGM-exporter.
- `extract_admission_time_features()` di `webhook_server/main.py` —
  fitur apa yang tersedia SEBELUM pod berjalan (beda dari fitur
  runtime dataset training).
- `decide_remediation_level()` + isi `action_*()` di
  `controller/main.py` — kebijakan remediasi spesifik riset Anda.
- Implementasi `BaseDetector` itu sendiri (`my_model.py`) — ini
  memang bagian riset inti yang tidak seharusnya di-generic-kan.

Bagian di atas sengaja dibiarkan `TODO`/`NotImplementedError` karena
memang tempat riset Anda berada — boilerplate ini hanya menjamin
bagian di SEKITARNYA (loading, saving, evaluasi, alur data) sudah
konsisten dan tidak perlu ditulis ulang tiap kali ganti pendekatan.
