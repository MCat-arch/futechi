"""
Kosakata ontologi (canonical terms + sinonim) -- satu sumber untuk:
  - validasi parameter query Modul B
  - daftar fitur tertutup untuk prompt ekstraksi MLLM di Modul A
  - resolusi label mentah -> nama canonical (Modul A mapping & retry Modul B)

Dibaca dari pipelines/knowledge_graph/dictionaries/*.yaml, TIDAK dari Neo4j,
supaya Modul A bisa berjalan tanpa koneksi graph.
"""
from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_DICTIONARY_DIR = (
    Path(__file__).parents[3] / "pipelines" / "knowledge_graph" / "dictionaries"
)
DEFAULT_CANONICAL_TERMS_PATH = _DICTIONARY_DIR / "canonical_terms.yaml"
DEFAULT_SYNONYM_PATH = _DICTIONARY_DIR / "synonym_dictionary.yaml"


@dataclass(frozen=True)
class VocabularyTerm:
    """Satu istilah canonical. `category` = target (visual), mode (symptom), atau source (lingkungan)."""

    name: str
    category: str
    description: str


def normalize_term(label: str) -> str:
    """Huruf kecil, '_' dan '-' jadi spasi, spasi berlebih dirapikan."""
    return re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", label.strip().lower())).strip()


def resolve_term(
    label: str,
    alias_map: Mapping[str, Sequence[str]],
    fuzzy_cutoff: float | None = None,
) -> str | None:
    """
    Petakan label mentah ke nama canonical: cocok persis (setelah normalisasi)
    dengan nama canonical atau salah satu aliasnya. Jika `fuzzy_cutoff` diisi
    dan tidak ada yang cocok persis, pakai kemiripan string (difflib) >= cutoff.
    """
    normalized = normalize_term(label)
    if not normalized:
        return None

    lookup: dict[str, str] = {}
    for canonical, aliases in alias_map.items():
        lookup.setdefault(normalize_term(canonical), canonical)
        for alias in aliases:
            lookup.setdefault(normalize_term(alias), canonical)

    if normalized in lookup:
        return lookup[normalized]
    if fuzzy_cutoff is None:
        return None

    matches = difflib.get_close_matches(normalized, list(lookup), n=1, cutoff=fuzzy_cutoff)
    return lookup[matches[0]] if matches else None


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _terms(entries: Iterable[Any] | None, category_key: str) -> dict[str, VocabularyTerm]:
    terms: dict[str, VocabularyTerm] = {}
    for entry in entries or []:
        if isinstance(entry, str):
            terms[entry] = VocabularyTerm(entry, "", "")
        else:
            terms[entry["name"]] = VocabularyTerm(
                name=entry["name"],
                category=str(entry.get(category_key, "")),
                description=str(entry.get("description", "")),
            )
    return terms


class OntologyRepository:
    """Read and cache canonical terms used to validate and resolve ontology vocabulary."""

    def __init__(
        self,
        canonical_terms_path: Path | None = None,
        synonym_path: Path | None = None,
    ) -> None:
        data = _load_yaml(canonical_terms_path or DEFAULT_CANONICAL_TERMS_PATH)
        self._visual_features = _terms(data.get("visual_features"), "target")
        self._symptoms = _terms(data.get("symptoms"), "mode")
        self._environment_conditions = _terms(data.get("environment_conditions"), "source")
        self._synonym_path = synonym_path or DEFAULT_SYNONYM_PATH
        self._synonyms: dict[str, list[str]] | None = None

    def is_valid_visual_feature(self, name: str) -> bool:
        """Return whether a visual feature is a canonical ontology term."""
        return name in self._visual_features

    def is_valid_symptom(self, name: str) -> bool:
        return name in self._symptoms

    def is_valid_environment_condition(self, name: str) -> bool:
        """Return whether an environment condition is canonical."""
        return name in self._environment_conditions

    def visual_feature_catalog(
        self, targets: Iterable[str] | None = None
    ) -> list[VocabularyTerm]:
        """Daftar fitur visual canonical, opsional dibatasi observation_target tertentu."""
        allowed = set(targets) if targets is not None else None
        return [
            term
            for term in self._visual_features.values()
            if allowed is None or term.category in allowed
        ]

    def alias_map(self, names: Iterable[str] | None = None) -> dict[str, list[str]]:
        """
        {nama canonical: [alias...]} untuk fitur visual. Entri sinonim yang
        bukan istilah canonical diabaikan. `names` membatasi ke subset istilah.
        """
        if self._synonyms is None:
            raw = _load_yaml(self._synonym_path)
            self._synonyms = {
                str(key): [str(alias) for alias in (aliases or [])]
                for key, aliases in raw.items()
            }
        selected = self._visual_features if names is None else [
            name for name in names if name in self._visual_features
        ]
        return {name: list(self._synonyms.get(name, [])) for name in selected}

    def resolve_visual_feature(
        self, label: str, fuzzy_cutoff: float | None = None
    ) -> str | None:
        return resolve_term(label, self.alias_map(), fuzzy_cutoff)
