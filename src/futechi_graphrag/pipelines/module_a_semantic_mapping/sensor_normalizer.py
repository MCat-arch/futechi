from __future__ import annotations


# ---------------------------------------------------------------------------
# Modul A: sensor normalization
# ---------------------------------------------------------------------------
# Data sensor sering datang dalam bentuk numeric yang belum siap dipakai sebagai
# input query. File ini mengubah angka suhu, kelembaban, dan amonia menjadi
# istilah semantic canonical seperti "temperature_attention" atau
# "humidity_attention" agar konsisten dengan ontology dan query graph.
# ---------------------------------------------------------------------------


def normalize_environment(
    temperature_c: float | None = None,
    humidity_percent: float | None = None,
    ammonia_ppm: float | None = None,
) -> list[str]:
    """Normalize raw environmental readouts into canonical conditions."""
    conditions: list[str] = []

    if temperature_c is not None and temperature_c > 30.0:
        conditions.append("temperature_attention")

    if humidity_percent is not None and humidity_percent > 75.0:
        conditions.append("humidity_attention")

    if ammonia_ppm is not None and ammonia_ppm > 20.0:
        conditions.append("ammonia_attention")

    return list(dict.fromkeys(conditions))
