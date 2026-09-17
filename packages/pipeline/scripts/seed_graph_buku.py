"""
Seeding graph data buku (JSON "Tahap 4") ke Neo4j 5.26 Community, dari host lewat Bolt.

Target default adalah container KEDUA `poultry-neo4j-buku` (bolt://localhost:7688),
BUKAN graph utama pipeline (7687). Menulis ke port 7687 ditolak kecuali flag
--izinkan-graph-utama diberikan, karena data buku belum mengikuti kontrak
pipeline (nama VisualFeature bebas, label Treatment/BiosecurityMeasure, dll).

Keputusan:
- Seluruh isi database DIHAPUS sebelum seeding hanya bila --hapus-semua diberikan
  (node & relasi; constraint/index tidak dihapus).
- Uniqueness constraint pada `id` untuk setiap label node.
- --dry-run: hanya menampilkan rencana, tanpa koneksi ke database.
- Setiap seeding dicatat sebagai node `_SeedRun` (sumber file, waktu, jumlah).

Konfigurasi (dibaca dari .env root repo atau environment):
    NEO4J_BUKU_URI       (default: bolt://localhost:7688)
    NEO4J_BUKU_USERNAME  (default: neo4j)
    NEO4J_BUKU_PASSWORD  (wajib, kecuali --dry-run)
    NEO4J_BUKU_DATABASE  (default: neo4j)

Pemakaian (dari root repo):
    python packages/pipeline/scripts/seed_graph_buku.py --dry-run
    python packages/pipeline/scripts/seed_graph_buku.py --hapus-semua
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRAF = (
    ROOT / "src" / "futechi_graphrag" / "pipelines" / "knowledge_graph"
    / "cypher" / "seeds" / "004_seed_data_penyakit_buku.json"
)
BATCH = 500

# Kunci MERGE per tipe relasi: hanya properti yang SELALU ada (MERGE gagal bila kunci null).
KUNCI_RELASI = {
    "HAS_SYMPTOM": ["sumber_blok", "sumber_urutan_entri", "urutan"],
    "HAS_VISUAL_FEATURE": ["sumber_blok", "sumber_urutan_entri", "urutan"],
    "TREATED_WITH": ["field_asal", "sumber_blok", "sumber_urutan_entri", "urutan"],
    "MITIGATED_BY": ["sumber_blok", "sumber_urutan_entri", "urutan"],
    "RELATED_TO": ["sumber_blok", "sumber_urutan_entri"],
}


def _muat_env() -> None:
    """`.env` tunggal ada di root repo (monorepo), bukan di root package."""
    for folder in (ROOT, *ROOT.parents):
        kandidat = folder / ".env"
        if kandidat.is_file():
            load_dotenv(kandidat)
            return


def potong(daftar, n=BATCH):
    for i in range(0, len(daftar), n):
        yield daftar[i:i + n]


def siapkan(g):
    """Kelompokkan relasi per (tipe, label asal, label tujuan) dan cek kelengkapan data."""
    label_of = {n["id"]: lbl for lbl, ds in g["nodes"].items() for n in ds}
    grup = {}
    for tipe, daftar in g["relationships"].items():
        if tipe not in KUNCI_RELASI:
            raise ValueError(f"Tipe relasi tanpa kunci MERGE: {tipe}")
        for r in daftar:
            for ujung in ("from", "to"):
                if r[ujung] not in label_of:
                    raise ValueError(f"Relasi {tipe} menunjuk id '{r[ujung]}' yang tidak ada di nodes")
            for k in KUNCI_RELASI[tipe]:
                if r["props"].get(k) is None:
                    raise ValueError(f"Kunci {k} kosong pada relasi {tipe}: {r}")
            la, lb = label_of[r["from"]], label_of[r["to"]]
            grup.setdefault((tipe, la, lb), []).append(r)
    return grup


def cypher_node(label):
    return (f"UNWIND $rows AS row "
            f"MERGE (n:`{label}` {{id: row.id}}) "
            f"SET n = row "
            f"RETURN count(n) AS jumlah")


def cypher_relasi(tipe, la, lb):
    kunci = ", ".join(f"{k}: row.props.{k}" for k in KUNCI_RELASI[tipe])
    return (f"UNWIND $rows AS row "
            f"MATCH (a:`{la}` {{id: row.from}}) "
            f"MATCH (b:`{lb}` {{id: row.to}}) "
            f"MERGE (a)-[r:`{tipe}` {{{kunci}}}]->(b) "
            f"SET r = row.props "
            f"RETURN count(r) AS jumlah")


def tulis_batch(session, query, rows):
    def kerja(tx):
        return tx.run(query, rows=rows).single()["jumlah"]
    jumlah = session.execute_write(kerja)
    if jumlah != len(rows):
        raise RuntimeError(f"Hanya {jumlah} dari {len(rows)} baris tertulis "
                           f"(node ujung tidak ditemukan?). Query: {query[:80]}...")
    return jumlah


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("graf", nargs="?", type=Path, default=DEFAULT_GRAF)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--hapus-semua", action="store_true",
                    help="Hapus SELURUH node & relasi di database target sebelum seeding")
    ap.add_argument("--izinkan-graph-utama", action="store_true",
                    help="Izinkan menulis ke port 7687 (graph utama pipeline). Hindari.")
    args = ap.parse_args()

    with open(args.graf, encoding="utf-8") as f:
        g = json.load(f)
    grup = siapkan(g)

    print(f"Sumber: {args.graf}")
    print("Rencana:")
    print("  hapus semua isi database :", "YA" if args.hapus_semua else "TIDAK")
    for lbl, ds in g["nodes"].items():
        print(f"  node {lbl:<20}: {len(ds)}")
    for (tipe, la, lb), rs in grup.items():
        print(f"  relasi {tipe:<18} {la} -> {lb}: {len(rs)}")

    if args.dry_run:
        print("\n[dry-run] Contoh query:")
        print(" ", cypher_node("Disease"))
        k = next(iter(grup))
        print(" ", cypher_relasi(*k))
        print("[dry-run] Tidak ada yang ditulis.")
        return

    from neo4j import GraphDatabase  # import di sini agar --dry-run tidak butuh driver

    _muat_env()
    uri = os.environ.get("NEO4J_BUKU_URI", "bolt://localhost:7688")
    user = os.environ.get("NEO4J_BUKU_USERNAME", "neo4j")
    pwd = os.environ.get("NEO4J_BUKU_PASSWORD")
    db = os.environ.get("NEO4J_BUKU_DATABASE", "neo4j")
    if not pwd:
        sys.exit("NEO4J_BUKU_PASSWORD belum di-set (.env root).")
    if urlparse(uri).port in (None, 7687) and not args.izinkan_graph_utama:
        sys.exit(f"Target {uri} adalah port graph utama (7687). "
                 "Gunakan container buku (7688) atau tambahkan --izinkan-graph-utama.")

    with GraphDatabase.driver(uri, auth=(user, pwd)) as driver:
        driver.verify_connectivity()
        with driver.session(database=db) as s:
            n_awal = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            print(f"\nTerhubung ke {uri} (database '{db}'), node saat ini: {n_awal}")

            if args.hapus_semua:
                # Auto-commit transaction (wajib untuk CALL ... IN TRANSACTIONS)
                s.run("MATCH (n) CALL (n) { DETACH DELETE n } "
                      "IN TRANSACTIONS OF 1000 ROWS").consume()
                sisa = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                print(f"Hapus semua: {n_awal} node dihapus, sisa {sisa}")
                if sisa:
                    sys.exit("Penghapusan tidak tuntas, seeding dibatalkan.")
            elif n_awal:
                print("PERINGATAN: database tidak kosong dan --hapus-semua tidak diberikan; "
                      "data lama tetap ada.")

            for lbl in g["nodes"]:
                s.run(f"CREATE CONSTRAINT `uniq_{lbl.lower()}_id` IF NOT EXISTS "
                      f"FOR (n:`{lbl}`) REQUIRE n.id IS UNIQUE").consume()
            s.run("CALL db.awaitIndexes(300)").consume()
            print("Constraint uniqueness siap.")

            for lbl, ds in g["nodes"].items():
                q = cypher_node(lbl)
                total = sum(tulis_batch(s, q, b) for b in potong(ds))
                print(f"  node   {lbl:<20}: {total}")

            for (tipe, la, lb), rs in grup.items():
                q = cypher_relasi(tipe, la, lb)
                total = sum(tulis_batch(s, q, b) for b in potong(rs))
                print(f"  relasi {tipe:<18} {la} -> {lb}: {total}")

            n_akhir = s.run("MATCH (n) WHERE NOT n:_SeedRun RETURN count(n) AS c").single()["c"]
            r_akhir = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            s.run("MERGE (m:_SeedRun {sumber: $sumber}) "
                  "SET m.applied_at = datetime(), m.jumlah_node = $n, m.jumlah_relasi = $r",
                  sumber=args.graf.name, n=n_akhir, r=r_akhir).consume()
            print(f"\nSelesai. Isi database: {n_akhir} node, {r_akhir} relasi.")


if __name__ == "__main__":
    main()
