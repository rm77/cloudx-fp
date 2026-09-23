"""
detector/evaluate.py
======================
Script evaluasi GENERIK, pasangan dari train.py -- memuat model APAPUN
lewat BaseDetector.load(), menghitung skor, menentukan threshold, dan
melaporkan precision/recall/F1/FPR/overhead. Tidak tahu dan tidak
peduli model spesifik apa yang dimuat.
"""

import argparse
import importlib
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "common"))
from feature_engineering import (  # noqa: E402
    aggregate_sessions, build_sequences, NUMERIC_TELEMETRY_COLUMNS,
)
from evaluation import (  # noqa: E402
    evaluate_detection, false_positive_rate,
    find_threshold_for_target_fpr, OverheadTimer,
)


def import_detector_class(dotted_path: str):
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def evaluate(dataset_csv: str, detector_class_path: str, model_path: str,
             feature_mode: str = "aggregate", max_len: int = 60,
             target_fpr: float = 0.05, scaler=None):
    """
    TODO (mahasiswa):
      - Pastikan dataset_csv di sini adalah HOLD-OUT set (sesi yang
        tidak dipakai train.py), bukan dataset yang sama persis.
      - Untuk feature_mode="sequence", `scaler` WAJIB diisi dengan
        scaler yang sama persis dipakai saat training (simpan/muat
        sesuai catatan di common/feature_engineering.py).
      - Threshold dipilih di sini lewat find_threshold_for_target_fpr()
        sebagai DEFAULT yang aman (FPR rendah) -- eksperimen dengan
        target_fpr berbeda dan laporkan trade-off precision/recall,
        jangan berhenti di satu angka threshold tunggal.
    """
    DetectorClass = import_detector_class(detector_class_path)
    model = DetectorClass.load(model_path)

    raw_df = pd.read_csv(dataset_csv)

    if feature_mode == "aggregate":
        features_df = aggregate_sessions(raw_df, NUMERIC_TELEMETRY_COLUMNS)
        feature_cols = [c for c in features_df.columns
                         if c not in ("session_id", "label")]
        X = features_df[feature_cols].fillna(0).to_numpy()
        y_true = (features_df["label"] == "misuse").astype(int).to_numpy()
    elif feature_mode == "sequence":
        X, mask, session_ids, labels, _ = build_sequences(
            raw_df, max_len=max_len, scaler=scaler,
        )
        y_true = (np.array(labels) == "misuse").astype(int)
    else:
        raise ValueError(f"feature_mode tidak dikenal: {feature_mode}")

    with OverheadTimer() as t:
        y_score = model.score(X)

    threshold = find_threshold_for_target_fpr(y_true, y_score, target_fpr)
    y_pred = model.predict(X, threshold)

    metrics = evaluate_detection(y_true, y_pred, y_score=y_score)
    metrics["false_positive_rate"] = false_positive_rate(y_true, y_pred)
    metrics["threshold_used"] = threshold
    metrics["target_fpr"] = target_fpr
    metrics["inference_time_sec_total"] = t.elapsed_sec
    metrics["inference_time_sec_per_session"] = t.elapsed_sec / max(len(X), 1)

    print(metrics)
    return metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-csv", required=True)
    ap.add_argument("--detector-class", required=True)
    ap.add_argument("--model-path", default="model_artifacts/model.bin")
    ap.add_argument("--feature-mode", choices=["aggregate", "sequence"],
                     default="aggregate")
    ap.add_argument("--max-len", type=int, default=60)
    ap.add_argument("--target-fpr", type=float, default=0.05)
    args = ap.parse_args()
    evaluate(args.dataset_csv, args.detector_class, args.model_path,
              args.feature_mode, args.max_len, args.target_fpr)
