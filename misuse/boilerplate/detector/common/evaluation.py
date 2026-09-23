"""
detector/common/evaluation.py
===============================
Metrik evaluasi standar dipakai untuk MODEL APAPUN (via
model_interface.BaseDetector) dan overhead measurement untuk KOMPONEN
K8S APAPUN (daemon_scorer, webhook_server, controller).
"""

import time

import numpy as np
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc,
)


def evaluate_detection(y_true: np.ndarray, y_pred: np.ndarray,
                        y_score: np.ndarray = None) -> dict:
    """
    Metrik deteksi standar: precision, recall, F1, dan (opsional)
    ROC-AUC/PR-AUC dari skor kontinu.

    TODO (mahasiswa):
      - Tentukan threshold optimal (mis. dari PR-curve) SEBELUM
        memanggil fungsi ini dengan y_pred final.
      - Tambahkan false_positive_rate() di bawah ke output jika
        skenario riset butuh sorotan khusus soal false alarm
        (mis. job benign yang salah ditandai misuse).
    """
    result = {
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }
    if y_score is not None:
        result["roc_auc"] = roc_auc_score(y_true, y_score)
        prec, rec, _ = precision_recall_curve(y_true, y_score)
        result["pr_auc"] = auc(rec, prec)
    return result


def false_positive_rate(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """FPR = FP / (FP + TN) -- job benign yang salah ditandai misuse."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    benign_mask = (y_true == 0)
    if benign_mask.sum() == 0:
        return 0.0
    return float((y_pred[benign_mask] == 1).sum() / benign_mask.sum())


def find_threshold_for_target_fpr(y_true: np.ndarray, y_score: np.ndarray,
                                    target_fpr: float = 0.05) -> float:
    """
    Mencari threshold skor anomali yang menghasilkan FPR mendekati
    `target_fpr` pada data benign -- alternatif dari sekadar memilih
    persentil skor secara membabi buta. Berguna karena keputusan
    threshold berdampak langsung ke berapa banyak job benign yang
    salah ditandai (relevan terutama untuk komponen yang menolak/
    memblokir, seperti webhook_server atau controller berbasis eviction).

    TODO (mahasiswa):
      - Validasi threshold hasil fungsi ini terhadap recall yang
        didapat -- FPR rendah biasanya berarti recall ikut turun,
        laporkan trade-off-nya secara eksplisit.
    """
    y_true, y_score = np.asarray(y_true), np.asarray(y_score)
    benign_scores = np.sort(y_score[y_true == 0])
    if len(benign_scores) == 0:
        raise ValueError("Tidak ada sampel benign di y_true untuk mencari threshold.")
    idx = int((1 - target_fpr) * len(benign_scores))
    idx = min(idx, len(benign_scores) - 1)
    return float(benign_scores[idx])


class OverheadTimer:
    """
    Context manager untuk mengukur overhead waktu wall-clock satu
    pemanggilan (mis. satu siklus scoring/inference).

    Contoh:
        with OverheadTimer() as t:
            score = model.score(features)
        print(t.elapsed_sec)

    TODO (mahasiswa):
      - Untuk overhead LEVEL CLUSTER (bukan cuma inferensi model),
        ukur juga resource request/limit container detektor
        (`kubectl top pod`) dan bandingkan dengan baseline scheduler
        tanpa komponen deteksi aktif.
    """

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed_sec = time.perf_counter() - self._start
        return False
