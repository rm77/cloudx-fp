"""
detector/model_interface.py
=============================
Kontrak (abstract base class) yang harus diimplementasikan oleh MODEL
APAPUN yang dipilih -- Isolation Forest, LSTM-Autoencoder, DBSCAN, GMM,
ensemble gabungan, atau pendekatan lain. Selama subclass mengikuti
interface ini, seluruh boilerplate lain di folder ini (train.py,
evaluate.py, k8s_integration/*) berfungsi TANPA PERLU diubah.

Alasan desain: keputusan riset ("model mana yang dipakai") dan
keputusan integrasi sistem ("bagaimana model dipanggil di cluster")
adalah dua hal terpisah. Interface ini adalah batas (boundary) di
antara keduanya.
"""

from abc import ABC, abstractmethod

import numpy as np


class BaseDetector(ABC):
    """
    Implementasikan subclass ini untuk model unsupervised pilihan Anda.
    Lihat contoh kerangka implementasi di bagian bawah file ini.
    """

    @abstractmethod
    def fit(self, X: np.ndarray) -> "BaseDetector":
        """
        Latih model dari data (biasanya HANYA data job benign, karena
        model bersifat unsupervised/semi-supervised -- lihat train.py).

        Parameters
        ----------
        X : np.ndarray
            Untuk model non-temporal: shape (n_sesi, n_fitur), hasil
            `common.feature_engineering.aggregate_sessions()`.
            Untuk model temporal: shape (n_sesi, max_len, n_fitur),
            hasil `common.feature_engineering.build_sequences()`.

        Returns
        -------
        self (untuk method chaining, konsisten dengan konvensi sklearn)
        """
        raise NotImplementedError

    @abstractmethod
    def score(self, X: np.ndarray) -> np.ndarray:
        """
        Hitung skor anomali kontinu untuk tiap sesi/baris di X.
        KONVENSI WAJIB: skor lebih TINGGI = lebih anomali (lebih
        mencurigakan sebagai misuse). Jika model dasar Anda memakai
        konvensi terbalik (mis. sklearn.IsolationForest.decision_function
        yang skornya lebih RENDAH = lebih anomali), balik tandanya di
        sini (`return -raw_score`) supaya seluruh boilerplate lain
        (threshold selection, evaluate_detection, dsb) konsisten.

        Returns
        -------
        np.ndarray, shape (n_sesi,)
        """
        raise NotImplementedError

    def predict(self, X: np.ndarray, threshold: float) -> np.ndarray:
        """
        Keputusan biner dari skor kontinu. Sudah diimplementasikan
        secara generik -- biasanya TIDAK PERLU di-override, cukup
        pastikan score() sudah benar konvensi arahnya.

        Returns
        -------
        np.ndarray of int (0/1), shape (n_sesi,) -- 1 = misuse.
        """
        return (self.score(X) > threshold).astype(int)

    @abstractmethod
    def save(self, path: str) -> None:
        """
        Simpan seluruh state yang dibutuhkan untuk memuat ulang model
        secara identik: parameter model terlatih, DAN artefak
        preprocessing terkait (scaler, daftar nama fitur, max_len untuk
        model sequence, dsb) -- semua harus ikut tersimpan di sini,
        supaya save()/load() adalah satu-satunya jalur konsisten antara
        train.py dan komponen inference (evaluate.py, k8s_integration/*).
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "BaseDetector":
        """Muat kembali model dari path hasil save()."""
        raise NotImplementedError


# ============================================================================
# CONTOH KERANGKA IMPLEMENTASI (hapus/ganti sesuai model pilihan Anda)
# ============================================================================
#
# import joblib
# from sklearn.ensemble import IsolationForest
#
# class IsolationForestDetector(BaseDetector):
#     def __init__(self, **isolation_forest_kwargs):
#         self.model = IsolationForest(**isolation_forest_kwargs)
#
#     def fit(self, X):
#         self.model.fit(X)
#         return self
#
#     def score(self, X):
#         # decision_function: makin RENDAH = makin anomali -> balik tanda
#         return -self.model.decision_function(X)
#
#     def save(self, path):
#         joblib.dump(self.model, path)
#
#     @classmethod
#     def load(cls, path):
#         instance = cls()
#         instance.model = joblib.load(path)
#         return instance
#
# Untuk model temporal (LSTM-Autoencoder dkk), score() biasanya
# menghitung reconstruction error per sesi -- lihat catatan masked
# loss di common/feature_engineering.py untuk penanganan padding.
#
# Untuk model ensemble, fit() bisa memanggil fit() beberapa
# BaseDetector lain sekaligus, dan score() menggabungkan skor
# masing-masing (voting/stacking) -- BaseDetector yang di-ensemble pun
# tetap BaseDetector, sehingga ensemble ITU SENDIRI juga valid dipakai
# oleh train.py/evaluate.py/k8s_integration/* tanpa perubahan.
# ============================================================================
