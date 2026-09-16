"""Unit test untuk scripts/validate_seed_consistency.py (tanpa Neo4j)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
import validate_seed_consistency as validator  # noqa: E402

NODE_DEFS = validator._load_yaml(validator.KG_ROOT / "ontology" / "node_definitions.yaml")
REL_DEFS = validator._load_yaml(validator.KG_ROOT / "ontology" / "relationship_definitions.yaml")
EMPTY_CANONICAL = {"visual_features": [], "symptoms": [], "environment_conditions": []}

VALID_DISEASE = (
    'MERGE (d:Disease {id: "DIS-001"}) SET d.name = "X", d.desc = "x", '
    'd.condition_type = "infectious_viral", d.base_severity = "high", '
    'd.notifiable = false, d.data_status = "draft_literature";\n'
)


def _validate(seed_text: str, canonical=None) -> list[str]:
    return validator.validate_seed_texts(
        {"test.cypher": seed_text}, NODE_DEFS, REL_DEFS, canonical or EMPTY_CANONICAL
    )


def test_repository_seed_files_pass_validation() -> None:
    assert validator.main() == 0


def test_invalid_enum_value_is_reported() -> None:
    errors = _validate(VALID_DISEASE.replace("infectious_viral", "alien"))
    assert any("condition_type='alien'" in error for error in errors)


def test_missing_required_node_property_is_reported() -> None:
    errors = _validate(VALID_DISEASE.replace(', d.data_status = "draft_literature"', ""))
    assert any("property wajib 'data_status'" in error for error in errors)


def test_unknown_reference_and_missing_relationship_property_are_reported() -> None:
    seed = VALID_DISEASE + (
        'MATCH (d:Disease {id: "DIS-001"}), (t:VisualFeature {id: "VF-999"}) '
        'MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.onset_stage = "early";\n'
    )
    errors = _validate(seed)
    assert any("VisualFeature VF-999" in error for error in errors)
    assert any("property wajib 'specificity'" in error for error in errors)


def test_inline_relationship_properties_are_rejected() -> None:
    seed = VALID_DISEASE + (
        'MERGE (i:InspectionAction {id: "IA-001"}) SET i.name = "a", i.instruction = "b", '
        'i.performed_by = "farmer";\n'
        'MATCH (d:Disease {id: "DIS-001"}), (t:InspectionAction {id: "IA-001"}) '
        'MERGE (d)-[:REQUIRES_INSPECTION {note: "x"}]->(t);\n'
    )
    errors = _validate(seed)
    assert any("property inline" in error for error in errors)


def test_canonical_field_mismatch_is_reported() -> None:
    seed = (
        'MERGE (n:VisualFeature {id: "VF-001"}) SET n.name = "pale_comb", '
        'n.observation_target = "egg", n.description = "Jengger pucat";\n'
    )
    canonical = {
        **EMPTY_CANONICAL,
        "visual_features": [{"name": "pale_comb", "target": "bird", "description": "Jengger pucat"}],
    }
    errors = _validate(seed, canonical)
    assert any("target" in error and "pale_comb" in error for error in errors)


def test_create_statement_is_rejected() -> None:
    errors = _validate('CREATE (d:Disease {id: "DIS-001"});\n')
    assert any("CREATE" in error for error in errors)
