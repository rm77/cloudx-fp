"""
detector/train.py
===================
Script training GENERIK -- tidak tahu dan tidak peduli model apa yang
dipakai. Model diberikan lewat `--detector-class`, sebuah dotted path
Python (mis. "my_model.IsolationForestDetector") menunjuk ke subclass
BaseDetector. Script ini hanya mengurus: load dataset -> ekstraksi
fitur -> panggil fit() HANYA pada data benign -> save().

Contoh pemakaian:
    python train.py \\
        --dataset-csv ../data_generator/data/dataset.csv \\
        --detector-class my_model.IsolationForestDetector \\
        --model-out model_artifacts/model.bin \\
        --feature-mode aggregate
"""

import argparse
import importlib
import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "common"))
from feature_engineering import (  # noqa: E402
    aggregate_sessions, build_sequences, NUMERIC_TELEMETRY_COLUMNS,
)


def import_detector_class(dotted_path: str):
    """
    Import subclass BaseDetector dari dotted path, mis.
    "my_model.IsolationForestDetector" -> import module "my_model",
    ambil atribut "IsolationForestDetector".

    TODO (mahasiswa): tidak perlu diubah -- cukup pastikan modul model
    Anda ada di PYTHONPATH saat memanggil train.py (mis. taruh file
    model Anda di folder ini, atau tambahkan ke sys.path).
    """
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def load_features(dataset_csv: str, feature_mode: str, max_len: int = 60):
    """
    Menyiapkan X (fitur) sesuai feature_mode, DAN mengembalikan
    label per baris X supaya train() bisa memfilter hanya sesi benign.

    TODO (mahasiswa):
      - feature_mode="aggregate": untuk model non-temporal.
      - feature_mode="sequence": untuk model temporal -- perhatikan
        `fitted_scaler` yang dikembalikan HARUS disimpan bersama model
        (lewat argumen tambahan di detector Anda, atau simpan terpisah
        dan muat manual di evaluate.py/komponen K8s).
    """
    raw_df = pd.read_csv(dataset_csv)

    if feature_mode == "aggregate":
        features_df = aggregate_sessions(raw_df, NUMERIC_TELEMETRY_COLUMNS)
        feature_cols = [c for c in features_df.columns
                         if c not in ("session_id", "label")]
        X = features_df[feature_cols].fillna(0).to_numpy()
        labels = features_df["label"].to_numpy()
        session_ids = features_df["session_id"].to_numpy()
        extra = {"feature_cols": feature_cols}
        return X, labels, session_ids, extra

    elif feature_mode == "sequence":
        X, mask, session_ids, labels, scaler = build_sequences(
            raw_df, max_len=max_len, fit_scaler_on_label="benign",
        )
        extra = {"mask": mask, "scaler": scaler, "max_len": max_len}
        return X, pd.Series(labels).to_numpy(), pd.Series(session_ids).to_numpy(), extra

    else:
        raise ValueError(f"feature_mode tidak dikenal: {feature_mode}")


def train(dataset_csv: str, detector_class_path: str, model_out_path: str,
          feature_mode: str = "aggregate", max_len: int = 60,
          detector_kwargs: dict = None):
    """
    TODO (mahasiswa):
      - Lakukan train/validation split PER SESI sebelum training,
        supaya evaluate.py bisa dipanggil pada hold-out set yang tidak
        pernah dilihat model saat training (hindari data leakage).
      - Jika detector Anda butuh argumen konstruktor (mis. jumlah
        cluster, hidden_size), oper lewat detector_kwargs.
    """
    detector_kwargs = detector_kwargs or {}
    DetectorClass = import_detector_class(detector_class_path)

    X, labels, session_ids, extra = load_features(dataset_csv, feature_mode, max_len)

    # Model unsupervised: latih HANYA dari job benign.
    benign_mask = (labels == "benign")
    X_train = X[benign_mask]

    model = DetectorClass(**detector_kwargs)
    model.fit(X_train)
    os.makedirs(os.path.dirname(model_out_path) or ".", exist_ok=True)
    model.save(model_out_path)

    print(f"[train] model ({DetectorClass.__name__}) tersimpan di "
          f"{model_out_path}, dilatih dari {len(X_train)} sesi benign "
          f"(feature_mode={feature_mode}).")

    if "feature_cols" in extra:
        print(f"[train] jumlah fitur: {len(extra['feature_cols'])}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-csv", required=True)
    ap.add_argument("--detector-class", required=True,
                     help='dotted path ke subclass BaseDetector, '
                          'mis. "my_model.IsolationForestDetector"')
    ap.add_argument("--model-out", default="model_artifacts/model.bin")
    ap.add_argument("--feature-mode", choices=["aggregate", "sequence"],
                     default="aggregate")
    ap.add_argument("--max-len", type=int, default=60,
                     help="hanya dipakai jika --feature-mode sequence")
    args = ap.parse_args()
    train(args.dataset_csv, args.detector_class, args.model_out,
          args.feature_mode, args.max_len)
