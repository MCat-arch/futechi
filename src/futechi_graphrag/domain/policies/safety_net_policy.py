"""
Aturan safety-net: eskalasi paksa ke petugas jika anomali terjadi
berulang kali selama cage masih dalam masa cooldown -- supaya penyakit
baru yang muncul segera setelah false-alarm sebelumnya tidak terlewat.
"""

# Nilai awal -- WAJIB dikalibrasi ulang setelah pilot deployment.
DEFAULT_SAFETY_NET_THRESHOLD = 3


def should_force_escalate(
    anomaly_count_during_cooldown: int, threshold: int | None = None
) -> bool:
    """
    True jika jumlah anomali yang tercatat selama cooldown sudah
    mencapai/melewati threshold.
    """
    effective_threshold = (
        threshold if threshold is not None else DEFAULT_SAFETY_NET_THRESHOLD
    )
    return anomaly_count_during_cooldown >= effective_threshold