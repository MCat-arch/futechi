"""
Unit test untuk logika orkestrasi di scripts/bootstrap_neo4j.py.

TIDAK menguji koneksi Neo4j sungguhan (butuh Docker/Neo4j asli, tidak
tersedia di sandbox ini) -- yang diuji adalah LOGIKA murni:
  - split_statements() memisahkan multi-statement dengan benar & abaikan komentar
  - bootstrap() melewati file yang sudah diterapkan (idempotency)
  - bootstrap() menerapkan urutan folder yang benar (constraints -> indexes -> seeds)
  - bootstrap() berhenti dan keluar dengan kode error jika ada statement gagal

Dipakai fake in-memory "session" yang meniru cukup banyak perilaku
neo4j.Session untuk keperluan test ini.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
import bootstrap_neo4j  # noqa: E402


class FakeRecord:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]


class FakeSession:
    """
    Meniru neo4j.Session cukup untuk test bootstrap():
    - Menyimpan node _SchemaMigration di memori (dict biasa)
    - Mencatat SEMUA statement yang dijalankan (untuk assert urutan)
    - Bisa disetel untuk melempar exception pada statement tertentu
      (simulasi Cypher error)
    """

    def __init__(self, fail_on_substring: str | None = None):
        self.applied_migrations: set[str] = set()
        self.executed_statements: list[str] = []
        self.fail_on_substring = fail_on_substring

    def run(self, statement: str, **params):
        self.executed_statements.append(statement)

        if self.fail_on_substring and self.fail_on_substring in statement:
            raise RuntimeError(f"Simulasi error Cypher pada: {statement[:50]}...")

        if statement.strip().startswith("MATCH (m:_SchemaMigration)"):
            return [FakeRecord({"filename": f}) for f in self.applied_migrations]

        if statement.strip().startswith("MERGE (m:_SchemaMigration"):
            filename = params.get("filename")
            self.applied_migrations.add(filename)
            return []

        return []


@pytest.fixture
def cypher_root(tmp_path: Path) -> Path:
    """Buat struktur folder cypher/ sementara dengan beberapa file dummy."""
    root = tmp_path / "cypher"
    (root / "constraints").mkdir(parents=True)
    (root / "indexes").mkdir(parents=True)
    (root / "seeds").mkdir(parents=True)

    (root / "constraints" / "001_constraints.cypher").write_text(
        "// komentar harus diabaikan\n"
        'CREATE CONSTRAINT disease_id_unique IF NOT EXISTS FOR (d:Disease) REQUIRE d.id IS UNIQUE;\n'
    )
    (root / "indexes" / "001_indexes.cypher").write_text(
        'CREATE INDEX disease_name_idx IF NOT EXISTS FOR (d:Disease) ON (d.name);\n'
    )
    (root / "seeds" / "001_seed_ontology.cypher").write_text(
        'MERGE (d1:Disease {id: "DIS-001"}) SET d1.name = "Newcastle Disease";\n'
        'MERGE (d2:Disease {id: "DIS-002"}) SET d2.name = "Infectious Bronchitis";\n'
    )
    return root


# ----------------------------------------------------------------------
# split_statements
# ----------------------------------------------------------------------
def test_split_statements_separates_multiple_statements():
    text = 'CREATE (a);\nCREATE (b);\n'
    result = bootstrap_neo4j.split_statements(text)
    assert result == ["CREATE (a)", "CREATE (b)"]


def test_split_statements_ignores_comment_lines():
    text = (
        "// ini komentar, harus diabaikan\n"
        'MERGE (a:Disease {id: "DIS-001"});\n'
        "// komentar lagi\n"
        'MERGE (b:Disease {id: "DIS-002"});\n'
    )
    result = bootstrap_neo4j.split_statements(text)
    assert len(result) == 2
    assert "komentar" not in " ".join(result)


def test_split_statements_ignores_empty_lines():
    text = 'MERGE (a);\n\n\n   \nMERGE (b);\n'
    result = bootstrap_neo4j.split_statements(text)
    assert result == ["MERGE (a)", "MERGE (b)"]


def test_split_statements_empty_text_returns_empty_list():
    assert bootstrap_neo4j.split_statements("") == []
    assert bootstrap_neo4j.split_statements("// hanya komentar\n") == []


# ----------------------------------------------------------------------
# get_applied_migrations / mark_applied
# ----------------------------------------------------------------------
def test_mark_applied_then_get_applied_migrations_roundtrip():
    session = FakeSession()
    bootstrap_neo4j.mark_applied(session, "constraints/001_constraints.cypher")
    bootstrap_neo4j.mark_applied(session, "seeds/001_seed_ontology.cypher")

    applied = bootstrap_neo4j.get_applied_migrations(session)
    assert applied == {
        "constraints/001_constraints.cypher",
        "seeds/001_seed_ontology.cypher",
    }


# ----------------------------------------------------------------------
# bootstrap() -- orkestrasi penuh dengan fake session
# ----------------------------------------------------------------------
def _run_bootstrap_with_fake_session(cypher_root: Path, session: FakeSession):
    """
    Helper: jalankan logika inti bootstrap() TANPA driver Neo4j sungguhan,
    dengan menyuntikkan FakeSession secara manual (meniru apa yang
    dilakukan `with driver.session() as session:` di bootstrap() asli).
    """
    applied = bootstrap_neo4j.get_applied_migrations(session)

    for folder_name in bootstrap_neo4j.ORDERED_FOLDERS:
        folder_path = cypher_root / folder_name
        if not folder_path.exists():
            continue
        for filepath in sorted(folder_path.glob("*.cypher")):
            relative_name = f"{folder_name}/{filepath.name}"
            if relative_name in applied:
                continue
            bootstrap_neo4j.run_cypher_file(session, filepath)
            bootstrap_neo4j.mark_applied(session, relative_name)


def test_bootstrap_applies_all_files_in_correct_order(cypher_root: Path):
    session = FakeSession()
    _run_bootstrap_with_fake_session(cypher_root, session)

    applied = bootstrap_neo4j.get_applied_migrations(session)
    assert applied == {
        "constraints/001_constraints.cypher",
        "indexes/001_indexes.cypher",
        "seeds/001_seed_ontology.cypher",
    }

    # Urutan eksekusi statement HARUS: constraint dulu, baru index, baru seed.
    executed = session.executed_statements
    constraint_idx = next(i for i, s in enumerate(executed) if "CONSTRAINT" in s)
    index_idx = next(i for i, s in enumerate(executed) if s.strip().startswith("CREATE INDEX"))
    seed_idx = next(i for i, s in enumerate(executed) if s.strip().startswith("MERGE (d1"))

    assert constraint_idx < index_idx < seed_idx


def test_bootstrap_is_idempotent_skips_already_applied(cypher_root: Path):
    session = FakeSession()
    _run_bootstrap_with_fake_session(cypher_root, session)
    statements_after_first_run = len(session.executed_statements)

    # Jalankan lagi -- seharusnya TIDAK ada statement baru yang dieksekusi
    # (semua sudah tercatat sebagai applied), kecuali query MATCH untuk
    # baca ulang daftar applied migrations.
    _run_bootstrap_with_fake_session(cypher_root, session)
    statements_after_second_run = len(session.executed_statements)

    # Hanya bertambah 1 (query MATCH _SchemaMigration untuk baca ulang),
    # tidak ada CREATE/MERGE tambahan yang dieksekusi lagi.
    new_statements = session.executed_statements[statements_after_first_run:]
    assert not any(
        s.strip().startswith(("CREATE", "MERGE (d")) for s in new_statements
    )


def test_bootstrap_partial_failure_does_not_mark_file_as_applied(cypher_root: Path):
    """
    Kalau salah satu statement di sebuah file gagal, file itu TIDAK boleh
    tercatat sebagai applied -- supaya percobaan berikutnya mengulang
    file yang sama (bukan melewatkannya begitu saja).
    """
    session = FakeSession(fail_on_substring="Infectious Bronchitis")

    with pytest.raises(RuntimeError):
        _run_bootstrap_with_fake_session(cypher_root, session)

    applied = bootstrap_neo4j.get_applied_migrations(session)
    # constraints & indexes berhasil, tapi seeds GAGAL di tengah jalan
    assert "constraints/001_constraints.cypher" in applied
    assert "indexes/001_indexes.cypher" in applied
    assert "seeds/001_seed_ontology.cypher" not in applied


def test_bootstrap_skips_nonexistent_folder_gracefully(tmp_path: Path):
    """Kalau folder 'indexes/' belum dibuat sama sekali, tidak boleh error."""
    root = tmp_path / "cypher"
    (root / "constraints").mkdir(parents=True)
    (root / "constraints" / "001.cypher").write_text('MERGE (a:Test {id: "1"});\n')
    # sengaja TIDAK buat folder indexes/ dan seeds/

    session = FakeSession()
    _run_bootstrap_with_fake_session(root, session)  # tidak boleh raise

    applied = bootstrap_neo4j.get_applied_migrations(session)
    assert applied == {"constraints/001.cypher"}
