"""
Demo alur sistem end-to-end dengan Neo4j & LLM SUNGGUHAN (memakai kredit API).

  1. diagnostic_graph : ekstraksi -> mapping -> retrieval -> reasoning
  2. CaseStore        : simpan case (pending_confirmation) + fitur case
  3. chat_graph       : pertanyaan lanjutan (retrieval ulang + LLM)
  4. --confirm        : simulasi tombol "Sakit" + pertanyaan lanjutan kedua

Mode ekstraksi (pilih salah satu):
  --image crop1.jpg --image crop2.jpg   MLLM sungguhan membaca crop
  --features conjunctivitis nasal_discharge
                                        MLLM diganti stub yang melaporkan fitur tsb
                                        di setiap frame (uji retrieval + reasoning live
                                        tanpa foto)

Contoh:
  python scripts/demo_flow.py --features conjunctivitis nasal_discharge --ammonia 25 \\
      --temperature 29 --humidity 70 --confirm "CRD (Mycoplasma gallisepticum)"
"""
from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import replace
from pathlib import Path

from futechi_graphrag.infrastructure.neo4j.driver import close_driver
from futechi_graphrag.infrastructure.persistence.case_store import CaseStore
from futechi_graphrag.pipelines.module_a_semantic_mapping.mllm_extractor import (
    ExtractedFeature,
    FrameExtractionResponse,
)
from futechi_graphrag.pipelines.module_c_reasoning.dto import ChatMessage
from futechi_graphrag.pipelines.orchestration.chat_graph import build_chat_graph, chat_config
from futechi_graphrag.pipelines.orchestration.diagnostic_graph import (
    build_diagnostic_dependencies,
    build_diagnostic_graph,
    initial_diagnostic_state,
)


class StaticFeatureMLLM:
    """Pengganti MLLM: melaporkan fitur yang sama di setiap frame."""

    def __init__(self, features: list[str], confidence: float) -> None:
        self.features = features
        self.confidence = confidence

    def generate_structured_with_images(self, system_prompt, user_prompt, images, schema):
        return FrameExtractionResponse(
            bird_visible=True,
            image_usable=True,
            features=[
                ExtractedFeature(name=name, confidence=self.confidence, evidence="stub demo")
                for name in self.features
            ],
        )


def print_diagnostic(result: dict) -> None:
    print("=" * 72)
    print(f"STATUS DIAGNOSTIC : {result['status']}")
    print(f"Fitur visual      : {[(f.name, round(f.confidence, 2)) for f in result.get('visual_features', [])]}")
    print(f"Lingkungan        : {result.get('environment_conditions', [])}")
    print(f"Unmapped          : {result.get('unmapped_visuals', [])}  retry={result.get('retrieval_retry_count', 0)}")
    for note in result.get("notes", []):
        print(f"Catatan           : {note}")

    output = result["reasoning_output"]
    severity = output.severity
    if severity:
        print(f"Severity          : {severity.level.value} (base={severity.base_severity}, onset={severity.onset_stage}, x{severity.multiplier})")
    print(f"Ketidakpastian    : {output.overall_uncertainty}")
    if output.notifiable_notice:
        print(f"WAJIB LAPOR       : {output.notifiable_notice}")

    print("\nKandidat kondisi:")
    for condition in output.related_conditions:
        print(f"- {condition.disease_name}")
        print(f"    evidence : {list(condition.evidence)}")
        print(f"    catatan  : {condition.differential_note}")
    print("\nPemeriksaan yang disarankan:")
    for check in output.recommended_checks:
        print(f"- {check.name}: {check.instruction}")
    print("\nAksi per penyakit (dibuka setelah konfirmasi 'Sakit'):")
    for name, bundle in output.disease_actions.items():
        treatments = [f"{m.treatment_name} / WD {m.withdrawal_period}" for m in bundle.medical_references]
        print(f"- {name}: {len(bundle.mitigations)} mitigasi, obat={treatments}")
    print("=" * 72)


def ask(chat, case_id: str, cage_id: str, question: str) -> None:
    state = chat.invoke(
        {"case_id": case_id, "cage_id": cage_id, "messages": [ChatMessage("user", question)]},
        config=chat_config(case_id),
    )
    scope = [candidate.disease_name for candidate in state["graph_context"].candidates]
    print(f"\n[chat] status={state['case_status']} konfirmasi={state['confirmed_disease']}")
    print(f"[chat] cakupan kandidat: {scope}")
    print(f"[user] {question}")
    print(f"[asisten] {state['messages'][-1].content}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, action="append", help="Path crop (boleh berulang)")
    source.add_argument("--features", nargs="+", help="Nama fitur canonical untuk stub MLLM")
    parser.add_argument("--frames", type=int, default=3, help="Jumlah frame stub (mode --features)")
    parser.add_argument("--confidence", type=float, default=0.85)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--humidity", type=float)
    parser.add_argument("--ammonia", type=float)
    parser.add_argument("--cage", default="B40")
    parser.add_argument("--blok", default="Z3")
    parser.add_argument("--capture-quality", default="high")
    parser.add_argument("--question", default="Apa yang perlu saya periksa dulu pada ayam ini?")
    parser.add_argument("--confirm", help="Nama penyakit untuk simulasi tombol 'Sakit'")
    parser.add_argument("--followup", default="Apa langkah penanganan untuk penyakit yang dikonfirmasi?")
    args = parser.parse_args()

    deps = build_diagnostic_dependencies()
    if args.features:
        deps = replace(deps, mllm_client=StaticFeatureMLLM(args.features, args.confidence))
        crops: list = [b"stub"] * args.frames
    else:
        crops = list(args.image)

    environment = {
        "temperature_c": args.temperature,
        "humidity_percent": args.humidity,
        "ammonia_ppm": args.ammonia,
    }
    case_id = f"CASE-DEMO-{uuid.uuid4().hex[:8]}"

    try:
        diagnostic = build_diagnostic_graph(deps)
        result = diagnostic.invoke(
            initial_diagnostic_state(
                case_id=case_id,
                cage_id=args.cage,
                blok_id=args.blok,
                crops=crops,
                capture_quality=args.capture_quality,
                raw_environment=environment if any(v is not None for v in environment.values()) else None,
            )
        )
        print_diagnostic(result)

        store = CaseStore()
        store.upsert_case(
            case_id=case_id,
            cage_id=args.cage,
            status="pending_confirmation",
            visual_features=[feature.name for feature in result.get("visual_features", [])],
            environment_conditions=result.get("environment_conditions", []),
        )
        chat = build_chat_graph(store, disease_repository=deps.disease_repository, llm_client=deps.llm_client)
        ask(chat, case_id, args.cage, args.question)

        if args.confirm:
            store.upsert_case(case_id=case_id, cage_id=args.cage, status="confirmed_sick", confirmed_condition=args.confirm)
            ask(chat, case_id, args.cage, args.followup)
    finally:
        close_driver()
    return 0


if __name__ == "__main__":
    sys.exit(main())
