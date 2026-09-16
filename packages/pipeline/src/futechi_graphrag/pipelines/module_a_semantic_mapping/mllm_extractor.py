"""
Modul A -- ekstraksi fitur visual dengan MLLM (node image_extraction di
workflow agentic). Tidak ada lagi layanan VLM terpisah: model multimodal
dipanggil lewat client yang sama dengan reasoning (infrastructure/llm).

Output MLLM dibatasi ke kosakata tertutup dari ontologi (canonical_terms.yaml)
supaya hasil ekstraksi langsung bisa dipakai sebagai parameter query graph.
Tanda di luar kosakata masuk `other_observations` -- dipetakan lewat sinonim
atau dihitung sebagai unmapped (memicu manual review bila dominan).

Pengaman halusinasi: model WAJIB menyatakan `bird_visible` lebih dulu.
Frame dengan bird_visible=false dibuang seluruhnya, apa pun fitur yang
dilaporkan (uji live: gambar merah polos sempat dilaporkan sebagai
bloody_feces tanpa pengaman ini).
"""
from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from futechi_graphrag.infrastructure.llm.client import ImageInput, MultimodalLLMClient
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    VocabularyTerm,
)

from .types import FrameExtractionResult, RawVisualCandidate

# Crop RoI dari edge berisi individu ayam dan kadang feses/litter di sekitarnya.
DEFAULT_OBSERVATION_TARGETS: tuple[str, ...] = ("bird", "feces_litter")


class ExtractedFeature(BaseModel):
    name: str = Field(description="Nama fitur, WAJIB persis salah satu nama dari daftar fitur.")
    confidence: float = Field(ge=0.0, le=1.0, description="Keyakinan tanda benar-benar terlihat.")
    evidence: str = Field(default="", description="Deskripsi singkat bagian gambar yang menunjukkan tanda.")


class OtherObservation(BaseModel):
    label: str = Field(description="Label deskriptif singkat untuk tanda abnormal di luar daftar.")
    confidence: float = Field(ge=0.0, le=1.0)


class FrameExtractionResponse(BaseModel):
    bird_visible: bool = Field(
        description="Diisi PERTAMA. True HANYA jika seekor ayam benar-benar terlihat pada gambar."
    )
    image_usable: bool = Field(description="False jika gambar tidak dapat dinilai.")
    unusable_reason: str | None = None
    features: list[ExtractedFeature] = Field(default_factory=list)
    other_observations: list[OtherObservation] = Field(default_factory=list)


EXTRACTION_SYSTEM_PROMPT = """\
Anda adalah modul ekstraksi fitur visual untuk screening kesehatan ayam petelur.
Tugas Anda HANYA mendeskripsikan tanda visual yang terlihat pada gambar, BUKAN mendiagnosis penyakit.

Aturan:
1. Langkah PERTAMA: tentukan apakah seekor ayam benar-benar terlihat (`bird_visible`). Jika tidak ada ayam
   yang terlihat, set `bird_visible` = false dan `image_usable` = false, dan JANGAN melaporkan fitur apa pun --
   termasuk warna, bercak, atau pola yang hanya mirip darah, feses, atau bagian tubuh ayam.
2. Masukkan tanda ke `features` HANYA jika terlihat jelas pada gambar, dan `name` WAJIB persis salah satu nama dari daftar fitur yang diberikan.
3. Tanda abnormal yang terlihat tetapi tidak ada padanannya di daftar dimasukkan ke `other_observations` dengan label deskriptif singkat.
4. `confidence` (0.0-1.0) menyatakan seberapa yakin tanda itu benar-benar terlihat, BUKAN seberapa parah.
5. `evidence` berisi deskripsi singkat bagian gambar yang menunjukkan tanda tersebut.
6. Jangan menyebut nama penyakit di field mana pun.
7. Jangan menebak tanda pada area yang tidak terlihat (tertutup, di luar frame). Jika tidak ada tanda abnormal, kembalikan daftar kosong.
8. Jika gambar tidak dapat dinilai (terlalu buram atau gelap), set `image_usable` = false dan isi `unusable_reason`.
"""


def build_extraction_user_prompt(
    vocabulary: Sequence[VocabularyTerm], capture_quality: str = "high"
) -> str:
    lines = ["Daftar fitur yang boleh dilaporkan (nama: deskripsi):"]
    lines += [f"- {term.name}: {term.description}" for term in vocabulary]
    lines.append("")
    if capture_quality == "low":
        lines.append(
            "Kualitas capture RENDAH (sebagian frame tidak valid di edge). "
            "Bersikap konservatif: laporkan hanya tanda yang sangat jelas."
        )
    else:
        lines.append(f"Kualitas capture: {capture_quality}.")
    lines.append("Analisis gambar berikut.")
    return "\n".join(lines)


def extract_frame_features(
    frames: Sequence[ImageInput],
    mllm_client: MultimodalLLMClient,
    vocabulary: Sequence[VocabularyTerm],
    capture_quality: str = "high",
) -> FrameExtractionResult:
    """Panggil MLLM sekali per frame dan kumpulkan label mentah beserta frame asalnya."""
    if not vocabulary:
        raise ValueError("vocabulary must not be empty")

    user_prompt = build_extraction_user_prompt(vocabulary, capture_quality)
    candidates: list[RawVisualCandidate] = []
    notes: list[str] = []
    frames_usable = 0

    for index, frame in enumerate(frames):
        frame_id = f"frame-{index}"
        response = mllm_client.generate_structured_with_images(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            images=[frame],
            schema=FrameExtractionResponse,
        )
        if not response.bird_visible or not response.image_usable:
            reason = response.unusable_reason or (
                "ayam tidak terlihat" if not response.bird_visible else "tanpa alasan"
            )
            notes.append(f"{frame_id} tidak dapat dinilai: {reason}")
            continue

        frames_usable += 1
        candidates += [
            RawVisualCandidate(
                label=feature.name,
                confidence=feature.confidence,
                source_frame=frame_id,
                evidence=feature.evidence or None,
            )
            for feature in response.features
        ]
        candidates += [
            RawVisualCandidate(
                label=observation.label,
                confidence=observation.confidence,
                source_frame=frame_id,
            )
            for observation in response.other_observations
        ]

    return FrameExtractionResult(
        candidates=candidates,
        frames_total=len(frames),
        frames_usable=frames_usable,
        notes=notes,
    )
