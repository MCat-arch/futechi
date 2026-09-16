# packages/api — Backend FastAPI

Menyambungkan edge (FCOS-Lite) dengan pipeline GraphRAG di `packages/pipeline`,
menyimpan siklus hidup case, dan melayani chat lanjutan.

API ini **tidak punya logika diagnosis sendiri**. Semua ekstraksi, retrieval,
dan reasoning dijalankan oleh `futechi_graphrag`; API hanya mengurus HTTP,
database, antrean, dan penyimpanan gambar.

## Alur

```
Edge (host Pi)              API (FastAPI)                    Worker (Celery)
──────────────              ─────────────                    ───────────────
POST /cases      ────────►  1. keputusan intake:
(crop + metadata)              duplicate / excluded /
                               cooldown / merged / new
                            2. simpan crop (resize saja)
                            3. antrekan task ───────────────► diagnostic_graph:
                            4. balas case_id + outcome          N1 ekstraksi MLLM
                               (non-blocking)                   N2 semantic mapping
                                                                N4 retrieval Neo4j
GET  /cases             ──► daftar alert                        N5 reasoning LLM
GET  /cases/{id}        ──► detail (Tahap 1 reveal)             N6 rekomendasi
POST /cases/{id}/confirm──► Sakit/Tidak Sakit/Sehat             simpan ke Postgres
                            (Tahap 2 reveal: mitigasi+obat)
POST /cases/{id}/chat   ──► chat_graph (retrieval ulang tiap giliran)
POST /cages/{id}/recover──► Tandai Sembuh (manual)
```

## Keputusan yang tertanam di kode

- **Intake diputuskan di server** (K5-A). Edge selalu mengirim event; server yang
  memutuskan skip/gabung/buat baru, sehingga anomali saat cooldown tetap tercatat
  dan safety-net bisa dihitung.
- **Two-stage reveal.** `disease_actions` disimpan sejak awal tapi tidak pernah
  ikut response. Mitigasi & referensi obat baru terisi setelah tombol "Sakit"
  ditekan, dan hanya untuk penyakit yang dikonfirmasi.
- **Enum status di-import dari domain**, bukan didefinisikan ulang, supaya nilai
  di DB tidak pernah menyimpang dari state machine.
- **Postgres sumber kebenaran chat.** Riwayat dimuat dari DB tiap giliran lalu
  dikirim ke `chat_graph`; checkpointer LangGraph hanya penampung sementara.
- **Preprocessing tanpa autocontrast** (K14): warna jengger/pial adalah bukti
  diagnostik, jadi tidak boleh digeser sebelum MLLM melihatnya.
- **Session khusus Celery.** Tiap task memakai event loop baru, jadi task memakai
  engine sendiri (NullPool); memakai pool bersama menyebabkan error
  "attached to a different loop" pada task kedua.

## Menjalankan (dev)

```powershell
# 1. Infrastruktur. Neo4j di compose ini SAMA dengan ops/docker; jalankan salah satu.
docker compose -f packages/api/docker-compose.yml up -d postgres redis neo4j

# 2. Seed knowledge graph (sekali, dari package pipeline)
python packages/pipeline/scripts/bootstrap_neo4j.py --reset --yes

# 3. Dependency (editable, dua package)
pip install -e packages/pipeline -e packages/api

# 4. API
uvicorn app.main:app --reload --app-dir packages/api

# 5. Worker (terminal terpisah, dari folder packages/api)
celery -A app.tasks.worker.celery_app worker --loglevel=info --pool=solo
```

`--pool=solo` dipakai di Windows; di Linux boleh default (prefork).

## Endpoint

| Method | Path | Fungsi |
|---|---|---|
| POST | `/cases` | Ingestion event dari edge (multipart: `metadata` + `images`) |
| GET | `/cases` | Daftar alert (filter `status`, `cage_id`) |
| GET | `/cases/{id}` | Detail case |
| POST | `/cases/{id}/confirm` | Tombol Sakit / Tidak Sakit / Sehat |
| POST | `/cases/{id}/chat` | Chat lanjutan (grounded ke knowledge graph) |
| GET | `/cases/{id}/chat` | Riwayat chat |
| GET | `/cages`, `/cages/{id}` | Status monitoring kandang |
| POST | `/cages/{id}/recover` | Tandai Sembuh |
| POST | `/cages/{id}/reset` | Reset Monitoring (ayam diganti/dipindah) |
| GET | `/health` | Liveness + ringkasan konfigurasi |

## Status implementasi

| Komponen | Status |
|---|---|
| Ingestion + keputusan intake (dedup, exclusion, cooldown, safety-net) | Selesai, teruji smoke |
| Preprocessing crop | Selesai |
| Two-stage reveal saat konfirmasi | Selesai, teruji smoke |
| Siklus hidup cage (exclusion, cooldown, recover, reset) | Selesai, teruji smoke |
| Celery task memanggil diagnostic_graph | Terpasang, **belum diuji dengan worker sungguhan** |
| Chat via chat_graph | Terpasang, **belum diuji live** |
| TTL job (case tak dikonfirmasi -> UNCONFIRMED_ESCALATED) | Belum ada |
| Tick cooldown per siklus deteksi | Belum ada (butuh scheduler) |
| Feedback loop (Phase 7) | Belum ada |
| Auth / multi-user | Belum ada |
| Migrasi Alembic | Belum ada (dev memakai create_all) |
