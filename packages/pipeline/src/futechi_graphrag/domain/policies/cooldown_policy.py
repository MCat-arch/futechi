"""
Aturan cooldown: cage yang dikonfirmasi 'Tidak Sakit' atau 'Sehat'
dikecualikan sementara selama N siklus deteksi sebelum eligible lagi.
"""

# Nilai awal (belum divalidasi vet/data lapangan) -- setara ~1.5 hari
# karena ada 2 sesi deteksi per hari. WAJIB dikalibrasi ulang setelah pilot.
DEFAULT_COOLDOWN_CYCLES = 4


def initial_cooldown_cycles(override: int | None = None) -> int:
    """
    Tentukan jumlah siklus cooldown awal untuk sebuah cage.

    Args:
        override: nilai dari config/env jika sudah dikalibrasi ulang;
            jika None, pakai DEFAULT_COOLDOWN_CYCLES.
    """
    return override if override is not None else DEFAULT_COOLDOWN_CYCLES


def is_cooldown_finished(cycles_remaining: int) -> bool:
    return cycles_remaining <= 0
