# Template Dockerfile — komponen detector/k8s_integration/*

Semua komponen (`daemon_scorer`, `webhook_server`, `controller`)
memakai pola yang sama. Build context HARUS root `detector/` (bukan
folder komponennya), karena tiap komponen mengimpor `common/` dan
`model_interface.py`.

```dockerfile
# detector/k8s_integration/daemon_scorer/Dockerfile (contoh)
FROM python:3.11-slim
WORKDIR /app

# TODO: sesuaikan dependency sesuai kebutuhan model Anda, contoh dasar:
RUN pip install --no-cache-dir kubernetes joblib scikit-learn numpy pandas
# tambahkan torch/dsb jika model Anda butuh

COPY common/ /app/common/
COPY model_interface.py /app/
COPY YOUR_MODEL_MODULE.py /app/   # file berisi subclass BaseDetector Anda
COPY k8s_integration/daemon_scorer/main.py /app/

CMD ["python", "main.py"]
```

Build & load ke kind:
```bash
docker build -f k8s_integration/daemon_scorer/Dockerfile \
  -t REPLACE_ME/detector-daemon-scorer:latest .   # context = root detector/
kind load docker-image REPLACE_ME/detector-daemon-scorer:latest --name <nama-cluster>
```

Ulangi pola yang sama untuk `webhook_server/Dockerfile` dan
`controller/Dockerfile` — hanya `COPY .../main.py` terakhir yang
berbeda, dan `controller/` tidak perlu meng-COPY model sama sekali
(controller hanya baca label/annotation, tidak memanggil model
langsung).
