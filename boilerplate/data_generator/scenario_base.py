"""
data_generator/scenario_base.py
==================================
Kontrak untuk SATU skenario job (benign ATAU misuse). Setiap skenario
adalah sebuah script Python yang bisa dijalankan berdiri sendiri
(`python nama_file.py --arg ...`) DAN mendaftarkan dirinya ke registry
(lihat registry.py) supaya bisa ditemukan otomatis oleh run_experiment.py.

Menambah jenis misuse baru = membuat satu file baru di scenarios/
mengikuti pola ini -- TIDAK PERLU mengubah registry.py, job_runner.py,
atau run_experiment.py sama sekali. Lihat
scenarios/template_new_scenario.py untuk kerangka siap-pakai.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Scenario:
    name: str
    """Identifier unik skenario, dipakai sebagai job_type di dataset
    output (kolom `job_type`) dan sebagai penanda proses untuk
    telemetry logger. Gunakan snake_case, mis. "misuse_idle_hoarding"."""

    label: str
    """WAJIB salah satu: "benign" atau "misuse"."""

    script_path: str
    """Path ke script Python skenario ini -- relatif terhadap folder
    scenarios/ untuk eksekusi lokal, atau path di dalam image container
    (mis. "/app/scenarios/misuse_idle_hoarding.py") untuk eksekusi K8s."""

    default_args: List[str] = field(default_factory=list)
    """Argumen CLI default saat dijalankan run_experiment.py, mis.
    ["--duration-sec", "600"]. Bisa di-override per pemanggilan."""

    timeout_sec: Optional[int] = None
    """Batas waktu paksa (detik). WAJIB diisi untuk skenario yang tidak
    berhenti sendiri (mis. idle-hoarding, zombie job) -- runner akan
    mem-force-kill proses setelah durasi ini. None = biarkan skenario
    berhenti sendiri (skenario yang memang punya durasi internal)."""

    description: str = ""
    """Penjelasan singkat pola telemetri yang diharapkan dari skenario
    ini -- membantu dokumentasi otomatis & debugging, tidak dipakai
    logika runner."""

    def __post_init__(self):
        if self.label not in ("benign", "misuse"):
            raise ValueError(
                f"Scenario '{self.name}': label harus 'benign' atau "
                f"'misuse', dapat '{self.label}'"
            )
