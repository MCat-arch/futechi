"""
Preprocessing crop dari edge (Phase 3.3).

Crop sudah di-RoI + padding di host Pi, jadi di sini TIDAK ada crop ulang.

SENGAJA tanpa autocontrast/normalisasi warna (keputusan K14): warna jengger
dan pial adalah fitur diagnostik (mis. sianosis pada HPAI, pucat pada
koksidiosis). Mengubah kontras/warna berisiko menggeser bukti sebelum MLLM
melihatnya. Yang dilakukan hanya: koreksi orientasi EXIF, resize proporsional,
dan simpan sebagai JPEG.
"""

import uuid
from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import get_settings

settings = get_settings()

# Sisi terpanjang untuk input MLLM: kompromi antara detail tekstur & ukuran payload.
_MAX_SIDE = 1024


def save_and_preprocess(raw_bytes: bytes, case_id: str, order_index: int) -> str:
    """Simpan crop dari edge, resize bila perlu, kembalikan path final."""
    storage_dir = Path(settings.image_storage_dir) / case_id
    storage_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = storage_dir / f"raw_{order_index}_{uuid.uuid4().hex[:8]}.bin"
    tmp_path.write_bytes(raw_bytes)

    try:
        with Image.open(tmp_path) as opened:
            img = ImageOps.exif_transpose(opened).convert("RGB")

            width, height = img.size
            longest = max(width, height)
            if longest > _MAX_SIDE:
                scale = _MAX_SIDE / longest
                img = img.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

            final_path = storage_dir / f"frame_{order_index}.jpg"
            img.save(final_path, format="JPEG", quality=92)
    finally:
        tmp_path.unlink(missing_ok=True)

    return str(final_path)
