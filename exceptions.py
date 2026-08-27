"""
Custom exception untuk domain layer.

Prinsip: exception dari infrastruktur (Neo4jError, HTTPError, dll) TIDAK BOLEH
bocor sampai ke domain layer. Kalau use case/infra menangkap error eksternal,
mereka harus menerjemahkannya ke salah satu exception di sini (atau exception
domain lain yang relevan) sebelum diteruskan ke atas.
"""


class DomainError(Exception):
    """Base exception untuk seluruh domain layer."""


class InvalidTransitionError(DomainError):
    """
    Dilempar saat state machine menerima event yang tidak valid
    untuk status Case saat ini (mis. mencoba konfirmasi ulang case
    yang sudah CONFIRMED_SICK).
    """

    def __init__(self, current_status: str, attempted_event: str):
        self.current_status = current_status
        self.attempted_event = attempted_event
        super().__init__(
            f"Transisi tidak valid: tidak bisa memproses event "
            f"'{attempted_event}' dari status '{current_status}'"
        )


class CaseAlreadyResolvedError(DomainError):
    """
    Dilempar saat mencoba menggabungkan (merge) deteksi baru ke case
    yang sudah resolved di hari yang sama. Sesuai kesepakatan desain:
    jika case sudah dikonfirmasi user sebelum sesi deteksi ke-2,
    sesi ke-2 untuk cage tersebut seharusnya di-skip di use case layer
    SEBELUM sampai memanggil method ini -- exception ini adalah guard
    kedua supaya domain tidak pernah berada di state yang tidak valid.
    """

    def __init__(self, case_id: str):
        self.case_id = case_id
        super().__init__(
            f"Case {case_id} sudah resolved untuk hari ini, "
            f"tidak bisa digabungkan dengan deteksi baru"
        )
