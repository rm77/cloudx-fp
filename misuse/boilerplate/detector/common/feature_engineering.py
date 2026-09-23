"""
detector/common/feature_engineering.py
========================================
Mengubah dataset telemetri mentah (1 baris = 1 sampel waktu, hasil
data_generator/) menjadi representasi fitur siap pakai -- dipakai oleh
MODEL APAPUN yang diimplementasikan lewat model_interface.py, tanpa
peduli jenis modelnya (non-temporal maupun temporal).
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Kolom telemetri mentah yang tersedia di dataset data_generator/.
# Sesuaikan jika kolom bertambah (mis. skenario custom menambah kolom
# metadata baru -- lihat scenarios/template_new_scenario.py).
NUMERIC_TELEMETRY_COLUMNS = [
    "cpu_pct", "mem_rss_mb", "io_read_mb", "io_write_mb",
    "gpu_util_pct", "gpu_mem_util_pct",
    "gpu_mem_used_mb_device", "gpu_mem_used_mb_process",
]

# Dipakai saat cluster/eksekusi TIDAK punya GPU: kolom GPU di atas akan
# selalu None/NaN (nvidia-smi tidak ditemukan -- lihat
# data_generator/telemetry_sidecar.py) -- ikut-sertakan kolom itu
# sebagai fitur hanya akan menambah kolom konstan (varians nol) yang
# tidak membantu model, jadi kecualikan lewat daftar ini.
NUMERIC_TELEMETRY_COLUMNS_NO_GPU = [
    "cpu_pct", "mem_rss_mb", "io_read_mb", "io_write_mb",
]


def aggregate_sessions(raw_df: pd.DataFrame,
                        numeric_columns=None) -> pd.DataFrame:
    """
    Mengagregasi dataset time-series mentah menjadi 1 baris = 1 sesi,
    dengan statistik mean/std/max/min per kolom numerik. Cocok untuk
    model NON-temporal (mis. Isolation Forest, DBSCAN, GMM -- model
    apapun yang menerima input fitur tetap, bukan sequence).

    TODO (mahasiswa):
      - Tambah fitur turunan sesuai hasil seleksi fitur (mutual
        information / feature importance) pada tahap eksplorasi data,
        mis. rate-of-change, durasi sesi, rasio memory terhadap kuota
        (jika skenario yang dipakai punya metadata kuota).

    Returns
    -------
    pd.DataFrame  1 baris per session_id, kolom fitur ber-suffix
                  _mean/_std/_max/_min, plus kolom `label`.
    """
    numeric_columns = numeric_columns or NUMERIC_TELEMETRY_COLUMNS
    agg_funcs = ["mean", "std", "max", "min"]

    grouped = raw_df.groupby("session_id")
    features = grouped[numeric_columns].agg(agg_funcs)
    features.columns = [f"{col}_{stat}" for col, stat in features.columns]
    features = features.reset_index()

    labels = grouped["label"].first().reset_index()
    features = features.merge(labels, on="session_id")

    return features


def build_sequences(raw_df: pd.DataFrame, max_len: int,
                     numeric_columns=None, scaler: StandardScaler = None,
                     fit_scaler_on_label: str = None) -> tuple:
    """
    Mengubah dataset time-series mentah menjadi array sequence
    ter-padding. Cocok untuk model TEMPORAL (mis. LSTM-Autoencoder,
    atau model sequence apapun).

    Strategi padding: PRE-padding dengan nol (padding di AWAL sequence,
    data asli rata kanan) -- hidden state di akhir forward pass LSTM
    berhenti tepat di timestep data asli terakhir. Sesi lebih panjang
    dari max_len dipotong dengan mengambil `max_len` sampel PALING BARU.

    Penanganan skala (PENTING, hindari data leakage):
      - Training: `scaler=None`, `fit_scaler_on_label="benign"` -> scaler
        baru dibuat & di-fit HANYA dari titik data sesi benign.
      - Evaluasi/inference: oper scaler yang sama (`scaler=fitted_scaler`),
        JANGAN fit ulang.

    Returns
    -------
    (X, mask, session_ids, labels, fitted_scaler)
      X : np.ndarray, shape (n_sessions, max_len, n_features)
      mask : np.ndarray, shape (n_sessions, max_len), dtype bool --
             True = data asli, False = padding. WAJIB dipakai untuk
             masked loss saat training model sequence.
      session_ids, labels : list -- urutan sesuai baris X.
      fitted_scaler : StandardScaler -- simpan bersama model.
    """
    numeric_columns = numeric_columns or NUMERIC_TELEMETRY_COLUMNS

    df = raw_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["session_id", "timestamp"])

    if scaler is None:
        fit_source = df
        if fit_scaler_on_label is not None:
            fit_source = df[df["label"] == fit_scaler_on_label]
        if len(fit_source) == 0:
            raise ValueError(
                f"Tidak ada baris dengan label='{fit_scaler_on_label}' "
                "untuk fit scaler -- periksa nilai fit_scaler_on_label."
            )
        fitted_scaler = StandardScaler()
        fitted_scaler.fit(fit_source[numeric_columns].fillna(0))
    else:
        fitted_scaler = scaler

    scaled_values = fitted_scaler.transform(df[numeric_columns].fillna(0))
    df_scaled = df[["session_id", "label"]].copy()
    for i, col in enumerate(numeric_columns):
        df_scaled[col] = scaled_values[:, i]

    n_features = len(numeric_columns)
    session_ids, labels, sequences = [], [], []
    for session_id, group in df_scaled.groupby("session_id", sort=False):
        session_ids.append(session_id)
        labels.append(group["label"].iloc[0])
        sequences.append(group[numeric_columns].to_numpy())

    n_sessions = len(sequences)
    X = np.zeros((n_sessions, max_len, n_features), dtype=np.float32)
    mask = np.zeros((n_sessions, max_len), dtype=bool)

    for i, seq in enumerate(sequences):
        seq_len = len(seq)
        if seq_len >= max_len:
            X[i, :, :] = seq[-max_len:]
            mask[i, :] = True
        else:
            X[i, max_len - seq_len:, :] = seq
            mask[i, max_len - seq_len:] = True

    return X, mask, session_ids, labels, fitted_scaler
