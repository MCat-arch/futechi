"""
Validasi konsistensi seed data TANPA perlu Neo4j menyala.

Ini bukan pengganti eksekusi Cypher sungguhan (sintaks Cypher tetap
harus diverifikasi dengan menjalankannya di Neo4j asli) -- tapi
menangkap kelas error yang paling sering terjadi saat menulis seed data
manual: nama entity yang typo/tidak sinkron antara canonical_terms.yaml
dan seed cypher, atau relasi yang merujuk id node yang tidak pernah
didefinisikan di file yang sama.

Usage:
    python scripts/validate_seed_consistency.py
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
KG_ROOT = (
    ROOT
    / "src"
    / "futechi_graphrag"
    / "pipelines"
    / "knowledge_graph"
)


def load_canonical_terms() -> dict[str, set[str]]:
    with open(KG_ROOT / "dictionaries" / "canonical_terms.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {
        "visual_features": set(data.get("visual_features", [])),
        "symptoms": set(data.get("symptoms", [])),
        "environment_conditions": set(data.get("environment_conditions", [])),
    }


def extract_node_definitions(seed_text: str) -> dict[str, dict[str, str]]:
    """
    Ekstrak semua node yang di-MERGE beserta variabel Cypher-nya dan
    property `name` (jika ada), dikelompokkan per label.

    Contoh yang ditangkap:
        MERGE (vf1:VisualFeature {id: "VF-001"}) SET vf1.name = "lowered_head_posture";

    Return: {"VisualFeature": {"vf1": "lowered_head_posture", ...}, ...}
    """
    nodes: dict[str, dict[str, str]] = {}

    merge_pattern = re.compile(
        r'MERGE\s*\((\w+):(\w+)\s*\{id:\s*"([^"]+)"\}\)'
    )
    name_pattern = re.compile(r'(\w+)\.name\s*=\s*"([^"]+)"')

    var_to_label: dict[str, str] = {}
    for match in merge_pattern.finditer(seed_text):
        var, label, node_id = match.groups()
        var_to_label[var] = label
        nodes.setdefault(label, {})

    for match in name_pattern.finditer(seed_text):
        var, name_value = match.groups()
        label = var_to_label.get(var)
        if label:
            nodes[label][var] = name_value

    return nodes


def validate_canonical_consistency(
    nodes: dict[str, dict[str, str]], canonical: dict[str, set[str]]
) -> list[str]:
    """
    Cek: semua `name` di seed data untuk VisualFeature/Symptom/
    EnvironmentalCondition WAJIB ada di canonical_terms.yaml, dan
    sebaliknya -- semua entri di canonical_terms.yaml WAJIB muncul
    sebagai node di seed data (supaya tidak ada istilah "hantu" yang
    didaftarkan tapi tidak pernah benar-benar dipakai di graph).
    """
    errors: list[str] = []

    label_to_canonical_key = {
        "VisualFeature": "visual_features",
        "Symptom": "symptoms",
        "EnvironmentalCondition": "environment_conditions",
    }

    for label, canonical_key in label_to_canonical_key.items():
        seed_names = set(nodes.get(label, {}).values())
        canonical_names = canonical[canonical_key]

        missing_from_canonical = seed_names - canonical_names
        for name in sorted(missing_from_canonical):
            errors.append(
                f"[{label}] '{name}' ada di seed data tapi TIDAK terdaftar "
                f"di canonical_terms.yaml -- tambahkan ke dictionary."
            )

        missing_from_seed = canonical_names - seed_names
        for name in sorted(missing_from_seed):
            errors.append(
                f"[{label}] '{name}' terdaftar di canonical_terms.yaml tapi "
                f"TIDAK ada node-nya di seed data -- entri tidak terpakai "
                f"(hapus dari dictionary atau tambahkan node-nya)."
            )

    return errors


def validate_relationship_targets(seed_text: str) -> list[str]:
    """
    Cek: setiap relasi (mis. MERGE (d1)-[:HAS_VISUAL_FEATURE ...]->(vf1))
    merujuk variabel yang benar-benar pernah di-MERGE sebagai node di
    file yang sama. Menangkap typo variabel (mis. nulis (vf10) padahal
    yang didefinisikan (vf1)).
    """
    errors: list[str] = []

    defined_vars: set[str] = set()
    for match in re.finditer(r'MERGE\s*\((\w+):\w+\s*\{id:', seed_text):
        defined_vars.add(match.group(1))

    relationship_pattern = re.compile(
        r'MERGE\s*\((\w+)\)-\[[^\]]*\]->\((\w+)\)'
    )
    for match in relationship_pattern.finditer(seed_text):
        source_var, target_var = match.groups()
        if source_var not in defined_vars:
            errors.append(
                f"Relasi merujuk variabel sumber '{source_var}' yang tidak "
                f"pernah di-MERGE sebagai node di file ini."
            )
        if target_var not in defined_vars:
            errors.append(
                f"Relasi merujuk variabel target '{target_var}' yang tidak "
                f"pernah di-MERGE sebagai node di file ini."
            )

    return errors


def validate_no_create_statements(seed_text: str) -> list[str]:
    """
    Cek: seed file TIDAK boleh pakai CREATE untuk node/relationship --
    wajib MERGE supaya idempotent. Deteksi kata "CREATE" yang bukan
    bagian dari "CREATE CONSTRAINT"/"CREATE INDEX" (yang memang boleh
    dan hanya ada di file constraints/indexes, bukan file seed).
    """
    errors: list[str] = []
    create_pattern = re.compile(r'\bCREATE\s+\(')
    if create_pattern.search(seed_text):
        errors.append(
            "Ditemukan 'CREATE (' di seed file -- seed data WAJIB pakai "
            "MERGE supaya idempotent (aman dijalankan berulang)."
        )
    return errors


def validate_withdrawal_period_not_empty(seed_text: str) -> list[str]:
    """
    Cek tambahan spesifik domain: setiap withdrawal_period di TREATED_WITH
    tidak boleh string kosong -- sesuai aturan MedicalReference di domain
    layer (Tahap 2) yang menolak withdrawal_period kosong.
    """
    errors: list[str] = []
    pattern = re.compile(r'withdrawal_period:\s*"([^"]*)"')
    for match in pattern.finditer(seed_text):
        if not match.group(1).strip():
            errors.append("Ditemukan withdrawal_period kosong ('') di seed data -- wajib diisi.")
    return errors


def main() -> int:
    seed_dir = KG_ROOT / "cypher" / "seeds"
    seed_files = sorted(seed_dir.glob("*.cypher"))

    if not seed_files:
        print("Tidak ada file seed ditemukan.")
        return 1

    canonical = load_canonical_terms()
    all_errors: list[str] = []

    for seed_file in seed_files:
        print(f"Memvalidasi: {seed_file.relative_to(ROOT)}")
        seed_text = seed_file.read_text(encoding="utf-8")

        nodes = extract_node_definitions(seed_text)
        all_errors += [f"  {e}" for e in validate_canonical_consistency(nodes, canonical)]
        all_errors += [f"  {e}" for e in validate_relationship_targets(seed_text)]
        all_errors += [f"  {e}" for e in validate_no_create_statements(seed_text)]
        all_errors += [f"  {e}" for e in validate_withdrawal_period_not_empty(seed_text)]

    if all_errors:
        print(f"\n{len(all_errors)} masalah ditemukan:\n")
        for error in all_errors:
            print(error)
        return 1

    print("\nSemua validasi konsistensi LOLOS.")
    print(
        "\nCATATAN: validasi ini TIDAK menjalankan Cypher sungguhan --"
        "\nsintaks Cypher tetap wajib diverifikasi dengan Neo4j asli"
        "\n(jalankan scripts/bootstrap_neo4j.py setelah Neo4j via Docker aktif)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
