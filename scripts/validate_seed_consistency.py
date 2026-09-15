"""
Validasi konsistensi seed data TANPA perlu Neo4j menyala.

Bukan pengganti eksekusi Cypher sungguhan (sintaks tetap harus diverifikasi
di Neo4j asli), tapi menangkap kelas error yang paling sering terjadi saat
menulis seed manual:
  - property yang tidak dikenal skema, nilai enum salah, property wajib hilang
  - pola id salah, id node duplikat
  - relasi yang merujuk id/label yang tidak pernah didefinisikan
  - relasi dengan property inline (wajib MERGE tanpa property lalu SET)
  - kosakata seed tidak sinkron dengan canonical_terms.yaml
  - pemakaian CREATE (seed wajib MERGE supaya idempotent)

Skema dibaca dari ontology/node_definitions.yaml & relationship_definitions.yaml.

Usage:
    python scripts/validate_seed_consistency.py
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ontology/node_definitions.yaml

ROOT = Path(__file__).parent.parent
KG_ROOT = ROOT / "src" / "futechi_graphrag" / "pipelines" / "knowledge_graph"

NODE_REF_PATTERN = re.compile(r'\((\w+):(\w+)\s*\{id:\s*"([^"]+)"\}\)')
MERGE_NODE_PATTERN = re.compile(r'MERGE\s*\((\w+):(\w+)\s*\{id:\s*"([^"]+)"\}\)')
REL_PATTERN = re.compile(r"MERGE\s*\((\w+)\)-\[(\w*):(\w+)([^\]]*)\]->\((\w+)\)")
SET_PATTERN = re.compile(
    r'\b(\w+)\.(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|true|false|-?\d+(?:\.\d+)?)'
)

# label node -> (key di canonical_terms.yaml, {field yaml: property node})
CANONICAL_LABELS: dict[str, tuple[str, dict[str, str]]] = {
    "VisualFeature": (
        "visual_features",
        {"target": "observation_target", "description": "description"},
    ),
    "Symptom": ("symptoms", {"mode": "observation_mode", "description": "description"}),
    "EnvironmentalCondition": (
        "environment_conditions",
        {"source": "source", "description": "description"},
    ),
}


@dataclass
class SeedNode:
    label: str
    node_id: str
    location: str
    props: dict[str, Any] = field(default_factory=dict)


def split_statements(cypher_text: str) -> list[str]:
    """Aturan split yang SAMA dengan scripts/bootstrap_neo4j.py."""
    statements: list[str] = []
    current: list[str] = []
    for line in cypher_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or not stripped:
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).rstrip(";"))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


def _parse_value(raw: str) -> Any:
    if raw.startswith('"'):
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    return float(raw) if "." in raw else int(raw)


def _check_property(
    owner: str, prop: str, value: Any, definition: dict[str, Any]
) -> list[str]:
    props = definition.get("properties") or {}
    if prop not in props:
        return [f"{owner}: property '{prop}' tidak dikenal skema"]
    spec = props[prop] or {}
    prop_type = spec.get("type")
    if prop_type == "enum" and value not in spec.get("values", []):
        return [f"{owner}: {prop}={value!r} bukan nilai enum {spec.get('values')}"]
    if prop_type == "boolean" and not isinstance(value, bool):
        return [f"{owner}: {prop} harus boolean"]
    if prop_type == "string":
        if not isinstance(value, str):
            return [f"{owner}: {prop} harus string"]
        if not value.strip():
            return [f"{owner}: {prop} tidak boleh string kosong"]
        pattern = spec.get("pattern")
        if pattern and not re.fullmatch(pattern, value):
            return [f"{owner}: {prop}={value!r} tidak sesuai pola {pattern}"]
    return []


def _missing_required(owner: str, props: dict[str, Any], definition: dict[str, Any]) -> list[str]:
    return [
        f"{owner}: property wajib '{name}' tidak diisi"
        for name, spec in (definition.get("properties") or {}).items()
        if (spec or {}).get("required") and name not in props
    ]


def validate_seed_texts(
    seed_texts: dict[str, str],
    node_defs: dict[str, Any],
    rel_defs: dict[str, Any],
    canonical: dict[str, Any],
) -> list[str]:
    """Validasi seluruh seed (key = nama file) terhadap skema & kosakata."""
    errors: list[str] = []
    nodes: dict[tuple[str, str], SeedNode] = {}
    references: list[tuple[str, str, str]] = []

    for filename, text in seed_texts.items():
        if re.search(r"\bCREATE\s+\(", text):
            errors.append(f"{filename}: ditemukan 'CREATE (' -- seed wajib MERGE (idempotent)")

        for index, statement in enumerate(split_statements(text), start=1):
            location = f"{filename}#{index}"
            var_labels: dict[str, str] = {}
            defined_here: dict[str, SeedNode] = {}

            for var, label, node_id in MERGE_NODE_PATTERN.findall(statement):
                if label not in node_defs:
                    errors.append(f"{location}: label '{label}' tidak ada di node_definitions.yaml")
                    continue
                key = (label, node_id)
                if key in nodes:
                    errors.append(f"{location}: {label} {node_id} didefinisikan ulang (pertama di {nodes[key].location})")
                node = SeedNode(label, node_id, location, {"id": node_id})
                errors += _check_property(f"{location} {label} {node_id}", "id", node_id, node_defs[label])
                nodes[key] = node
                defined_here[var] = node
                var_labels[var] = label

            for var, label, node_id in NODE_REF_PATTERN.findall(statement):
                if var not in defined_here:
                    var_labels[var] = label
                    references.append((label, node_id, location))

            rel_vars: dict[str, str] = {}
            for source, rel_var, rel_type, inline, target in REL_PATTERN.findall(statement):
                if rel_type not in rel_defs:
                    errors.append(f"{location}: relasi '{rel_type}' tidak ada di relationship_definitions.yaml")
                    continue
                if inline.strip():
                    errors.append(f"{location}: {rel_type} memakai property inline -- gunakan MERGE tanpa property lalu SET")
                definition = rel_defs[rel_type]
                for end, expected in ((source, definition["from"]), (target, definition["to"])):
                    if var_labels.get(end) != expected:
                        errors.append(f"{location}: {rel_type} butuh ujung {expected}, variabel '{end}' adalah {var_labels.get(end)}")
                if rel_var:
                    rel_vars[rel_var] = rel_type

            rel_props: dict[str, dict[str, Any]] = {name: {} for name in rel_vars}
            for var, prop, raw in SET_PATTERN.findall(statement):
                value = _parse_value(raw)
                if var in defined_here:
                    node = defined_here[var]
                    errors += _check_property(f"{location} {node.label} {node.node_id}", prop, value, node_defs[node.label])
                    node.props[prop] = value
                elif var in rel_vars:
                    errors += _check_property(f"{location} {rel_vars[var]}", prop, value, rel_defs[rel_vars[var]])
                    rel_props[var][prop] = value
                else:
                    errors.append(f"{location}: SET pada variabel '{var}' yang tidak didefinisikan di statement ini")

            for rel_var, rel_type in rel_vars.items():
                errors += _missing_required(f"{location} {rel_type}", rel_props[rel_var], rel_defs[rel_type])
            for node in defined_here.values():
                errors += _missing_required(f"{location} {node.label} {node.node_id}", node.props, node_defs[node.label])

    for label, node_id, location in references:
        if (label, node_id) not in nodes:
            errors.append(f"{location}: merujuk {label} {node_id} yang tidak pernah di-MERGE di seed mana pun")

    errors += _validate_canonical(nodes, canonical)
    return errors


def _validate_canonical(
    nodes: dict[tuple[str, str], SeedNode], canonical: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    for label, (key, field_map) in CANONICAL_LABELS.items():
        seed_by_name = {
            node.props.get("name"): node for node in nodes.values() if node.label == label
        }
        entries = {entry["name"]: entry for entry in canonical.get(key) or []}

        for name in sorted(set(seed_by_name) - set(entries)):
            errors.append(f"[{label}] '{name}' ada di seed tapi TIDAK terdaftar di canonical_terms.yaml")
        for name in sorted(set(entries) - set(seed_by_name)):
            errors.append(f"[{label}] '{name}' terdaftar di canonical_terms.yaml tapi TIDAK ada node-nya di seed")

        for name in sorted(set(entries) & set(seed_by_name)):
            for yaml_field, node_prop in field_map.items():
                expected = entries[name].get(yaml_field)
                actual = seed_by_name[name].props.get(node_prop)
                if expected != actual:
                    errors.append(f"[{label}] '{name}': {yaml_field} di canonical_terms.yaml ({expected!r}) != {node_prop} di seed ({actual!r})")
    return errors


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main() -> int:
    seed_files = sorted((KG_ROOT / "cypher" / "seeds").glob("*.cypher"))
    if not seed_files:
        print("Tidak ada file seed ditemukan.")
        return 1

    for seed_file in seed_files:
        print(f"Memvalidasi: {seed_file.relative_to(ROOT)}")

    errors = validate_seed_texts(
        {path.name: path.read_text(encoding="utf-8") for path in seed_files},
        _load_yaml(KG_ROOT / "ontology" / "node_definitions.yaml"),
        _load_yaml(KG_ROOT / "ontology" / "relationship_definitions.yaml"),
        _load_yaml(KG_ROOT / "dictionaries" / "canonical_terms.yaml"),
    )

    if errors:
        print(f"\n{len(errors)} masalah ditemukan:\n")
        for error in errors:
            print(f"  {error}")
        return 1

    print("\nSemua validasi konsistensi LOLOS.")
    print(
        "\nCATATAN: validasi ini TIDAK menjalankan Cypher sungguhan --"
        "\nsintaks tetap wajib diverifikasi dengan Neo4j asli"
        "\n(jalankan scripts/bootstrap_neo4j.py setelah Neo4j via Docker aktif)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
