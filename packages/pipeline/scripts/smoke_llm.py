"""
Smoke test LIVE endpoint LLM/MLLM (memakai konfigurasi LLM_* di .env).

Menguji 3 kemampuan yang dibutuhkan workflow:
  1. generate()                         -- teks bebas (chat Modul C)
  2. generate_structured()              -- JSON sesuai schema (reasoning Modul C)
  3. generate_structured_with_images()  -- citra + JSON (ekstraksi Modul A)

Setiap langkah memanggil API sungguhan (memakai kredit). API key TIDAK dicetak.

Usage:
    python scripts/smoke_llm.py                    # gambar sintetis (uji format, bukan akurasi)
    python scripts/smoke_llm.py --image crop.jpg   # crop ayam sungguhan
    python scripts/smoke_llm.py --skip-image
"""
from __future__ import annotations

import argparse
import struct
import sys
import time
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from futechi_graphrag.config.settings import get_settings
from futechi_graphrag.infrastructure.llm.client import build_llm_client
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.mllm_extractor import (
    DEFAULT_OBSERVATION_TARGETS,
    EXTRACTION_SYSTEM_PROMPT,
    FrameExtractionResponse,
    build_extraction_user_prompt,
)


class Ping(BaseModel):
    status: str
    answer: int


def synthetic_png(width: int = 96, height: int = 96, rgb: tuple[int, int, int] = (200, 40, 40)) -> bytes:
    """PNG polos tanpa dependensi (hanya untuk menguji jalur input gambar)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    row = b"\x00" + bytes(rgb) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def run_step(name: str, action: Callable[[], Any]) -> bool:
    started = time.perf_counter()
    try:
        result = action()
    except Exception as exc:  # noqa: BLE001 -- smoke test melaporkan semua jenis error
        elapsed = (time.perf_counter() - started) * 1000
        print(f"[FAIL] {name} ({elapsed:.0f} ms): {type(exc).__name__}: {str(exc)[:300]}")
        return False
    elapsed = (time.perf_counter() - started) * 1000
    text = result.model_dump_json() if isinstance(result, BaseModel) else str(result)
    print(f"[PASS] {name} ({elapsed:.0f} ms): {text[:300]}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", type=Path, help="Path crop ayam untuk uji multimodal")
    parser.add_argument("--skip-image", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    client = build_llm_client(settings)
    print(f"Endpoint : {client.base_url}")
    print(f"Model    : teks={client.model}, multimodal={client.multimodal_model}, json_mode={settings.llm_json_mode}\n")

    results = [
        run_step("teks", lambda: client.generate("Jawab sangat singkat.", "Balas dengan satu kata: siap")),
        run_step(
            "structured JSON",
            lambda: client.generate_structured(
                "Anda asisten yang menjawab dalam JSON.",
                "Isi status dengan 'ok' dan answer dengan hasil 2+3.",
                Ping,
            ),
        ),
    ]

    if not args.skip_image:
        image = args.image if args.image else synthetic_png()
        vocabulary = OntologyRepository().visual_feature_catalog(DEFAULT_OBSERVATION_TARGETS)
        results.append(
            run_step(
                "multimodal ekstraksi",
                lambda: client.generate_structured_with_images(
                    EXTRACTION_SYSTEM_PROMPT,
                    build_extraction_user_prompt(vocabulary),
                    [image],
                    FrameExtractionResponse,
                ),
            )
        )

    passed = sum(results)
    print(f"\n{passed}/{len(results)} langkah lolos")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
