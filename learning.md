# Learning Progress & Mentor Notes

## 1. Status sesi saat ini

Kami berada di fase transisi dari fondasi sistem ke integrasi orchestration yang benar. Fokus utama bukan menambah fitur baru, melainkan memastikan kontrak state, history, dan retrieval sudah konsisten sebelum lanjut ke pengembangan yang lebih luas.

Poin yang sudah masuk ke arah yang benar:
- Rule #11 sudah tertulis di `CHAT_SYSTEM_PROMPT`.
- `CaseStore` dan `CageHistoryEntry` sudah ada dalam bentuk kontrak minimal.
- `ChatState` sudah mendefinisikan field yang dibutuhkan untuk chat runtime.
- `sync_case_state` dan `load_cage_history` sudah menjadi bagian dari arsitektur yang diasumsikan.
- Import legacy `poultry_graphrag` sudah dibersihkan dari area Modul C yang sedang aktif.

Poin yang masih belum final dan perlu difokuskan:
- sinkronisasi `case_status` dan `confirmed_disease` ke `ChatState` secara nyata
- conditional retrieval berdasarkan status case
- `thread_id = case_id` pada checkpointer
- persistence nyata untuk `CaseStore`, bukan hanya in-memory
- end-to-end testing untuk riwayat kandang dan konfirmasi

## 2. Prinsip arsitektur yang wajib dijaga

### A. Pemisahan jelas antara checkpointer dan case store

Ini adalah keputusan utama yang tidak boleh dilanggar:
- LangGraph checkpointer menyimpan `messages` berdasarkan `thread_id = case_id`.
- CaseStore menyimpan status resmi case dan data konfirmasi, seperti `status`, `confirmed_condition`, `cage_id`, serta `resolved_at`.

Tujuannya:
- riwayat percakapan tetap terpisah dari status domain
- status case tidak boleh tergantung pada isi chat saja
- setiap thread chat tetap bisa di-query dengan cara yang deterministik

### B. Urutan eksekusi chat harus konsisten

Urutan yang benar adalah:
1. `sync_case_state`
2. `load_cage_history`
3. `retrieve`
4. `respond`

Jika urutannya dibalik, sistem berisiko:
- retrieval memakai state yang tidak terbarui
- cage history ikut dipakai sebagai bukti utama padahal harus bersifat informasional
- konfirmasi penyakit aktif tidak tercermin pada prompt saat ini

### C. Riwayat kandang adalah konteks, bukan bukti utama

Ini adalah aturan kunci untuk diagnosis:
- `cage_history` boleh dijadikan catatan contextual
- tetapi `graph_context` saat ini tetap menjadi sumber utama
- jika graph context kosong, sistem harus secara jujur mengatakan bahwa data terverifikasi tidak tersedia, bukan mengarang diagnosis dari memori lama

### D. Status case harus memengaruhi retrieval

Retrieval harus bersifat conditional:
- `PENDING_CONFIRMATION`: retrieval normal, multi-kandidat masih diperbolehkan
- `CONFIRMED_SICK`: retrieval harus difokuskan ke `confirmed_disease` saja

Ini penting agar keputusan chat tidak kembali mengajukan kandidat yang sudah tidak relevan.

## 3. Pengaturan kontrak state yang disarankan

### `ChatState` harus berisi elemen berikut
- `case_id`
- `cage_id`
- `case_status`
- `confirmed_disease`
- `messages`
- `graph_context`
- `cage_history`

Catatan penting:
- `messages` boleh dipersist di checkpointer
- `case_status` dan `confirmed_disease` sebaiknya dipulihkan dari `CaseStore` di awal turn
- `cage_history` harus dibatasi pada `limit=5` dan `since_days=90`

### `CaseStore` harus menjaga domain truth

CaseStore bukan hanya untuk chat. Ia berperan sebagai sumber kebenaran untuk:
- status case
- keputusan konfirmasi
- data kondisi yang sudah dikonfirmasi
- riwayat resolved case per cage

Jika nanti ada persistence DB, pastikan indeks seperti:
- `cage_id`
- `resolved_at`
- `status`

## 4. Panduan desain implementasi yang harus diikuti

### Prioritas 1: sinkronisasi status nyata

Sebelum retrieval atau response, lakukan pembaruan state dari `CaseStore` ke `ChatState`.

Tujuannya:
- case status selalu konsisten dengan record resmi
- `confirmed_disease` tidak bertahan pada state lama
- `graph_context` bisa diperlakukan sesuai status yang aktif

### Prioritas 2: retrieval conditional

Implementasikan logika berikut:
- jika `case_status == "CONFIRMED_SICK"`: batasi hasil retrieval hanya ke `confirmed_disease`
- jika `case_status == "PENDING_CONFIRMATION"`: tetap gunakan konteks kandidat yang relevan dengan case aktif
- jika tidak ada `graph_context`: tangani sebagai kondisi data tidak tersedia, bukan fallback umum

### Prioritas 3: pembatasan riwayat kandang

Ketika mengisi `cage_history`:
- gunakan `find_resolved_cases_by_cage(cage_id, exclude_case_id, limit=5, since_days=90)`
- hanya ambil kasus yang sudah resolved
- jangan masukkan kasus yang sedang aktif atau belum resolved
- jangan gunakan historical data sebagai satu-satunya alasan diagnosa

### Prioritas 4: test yang menutup bug nyata

Uji yang harus ada:
1. `PENDING_CONFIRMATION` + cage history present + graph context valid
2. `CONFIRMED_SICK` + confirmed disease active
3. graph context kosong + cage history present
4. prompt menyatakan riwayat kandang bersifat informational saja
5. sync state mengambil status terbaru dari `CaseStore`
6. retrieval conditional untuk confirmed disease

## 5. Kesalahan umum yang harus dihindari

- Menganggap riwayat lama sebagai sumber bukti utama.
- Menyimpan status case di chat state tanpa sinkronisasi ke CaseStore.
- Menggunakan `thread_id` acak atau tidak konsisten.
- Menggabungkan `messages` dan `case_status` dalam satu store tanpa pemisahan domain.
- Memasukkan import legacy ke path active.
- Mengubah nama field domain secara tidak konsisten tanpa update kontrak graph/prompt.

## 6. Fokus pengembangan berikutnya

### Milestone berikutnya
- Selesaikan wiring `sync_case_state -> load_cage_history -> retrieve -> respond`.
- Pastikan `ChatState` dibangun dari data case yang benar.
- Buat retrieval conditional yang memanfaatkan `case_status`.
- Validasi behavior prompt dengan `case_status` dan `confirmed_disease`.
- Ubah store menjadi DB-backed bila ekspektasi produk sudah siap.

### Pedoman kualitas
- coverage harus menutup edge case chat state, prompt constraints, dan retrieval conditional
- semua fungsi harus memiliki fallback bila data tidak lengkap
- setiap hasil yang dikembalikan ke user harus mengandung jelas sumber data: graph context vs historical note
- semua error handling harus berakhir pada pesan yang aman dan tidak mengarang diagnosis

## 7. Mentor guidance singkat

Sistem ini sudah memiliki fondasi arsitektur yang kuat: domain model, graph retrieval, semantic mapping, dan prompt constraint utama sudah ada. Kelemahan utama sekarang bukan pada model data, melainkan pada koneksi runtime antara state, history, dan retrieval.

Jangan lanjut ke fitur baru sebelum alur berikut benar-benar mapan:
- state live dari CaseStore
- history cage terpisah dan terbatas
- retrieval sesuai status case
- prompt selalu menjaga perbedaan antara data saat ini dan riwayat lama

Jika ingin melanjutkan ke implementation, maka urutan yang paling masuk akal adalah:
1. perbaiki contract ChatState dan sync logic
2. implementasikan conditional retrieval
3. lalu lanjut ke prompt/integrasi runtime
4. baru setelah itu fokus ke persistence DB-backed dan end-to-end test

## 8. Catatan pembelajaran

Poin pembelajaran yang paling penting dari fase ini adalah bahwa dalam sistem seperti ini, "status resmi" harus memiliki pemilik yang jelas. Jika status case dan memori percakapan dicampur, semua keputusan akan berantakan. Model yang sehat adalah:
- state live di CaseStore
- chat history di checkpointer
- evidence utama di graph context
- historical cage notes sebagai catatan tambahan yang dibatasi

Ini adalah fondasi yang tepat untuk pengembangan lanjutan yang aman dan terdokumentasi.

---

## 9. Runbook infrastruktur: Postgres & Neo4j di Docker

> Bagian 1–8 mencatat fase sebelum backend dibuat. Bagian ini mencatat kondisi
> setelah repo menjadi monorepo (`packages/pipeline` + `packages/api`) dan
> database dijalankan di Docker.

### 9.1 Siapa menyimpan apa

| Database | Container | Isi | Dipakai oleh |
|---|---|---|---|
| **PostgreSQL 16** | `futechi-postgres` | Data operasional: case, cage, frame, event dari edge, riwayat chat | `packages/api` |
| **Neo4j 5.26** | `poultry-neo4j` | Knowledge graph: penyakit, fitur visual, gejala, pemeriksaan, mitigasi, obat | `packages/pipeline` (Modul B) |
| **Redis 7** | `futechi-redis` | Antrean task Celery (bukan penyimpanan data) | API + worker |

Aturannya: **Postgres = apa yang terjadi di kandang**, **Neo4j = pengetahuan penyakit**.
Keduanya tidak saling menyalin data.

PostgreSQL 17 native di `C:\Program Files\PostgreSQL\17` **tidak dipakai**. Service
`postgresql-x64-17` sudah disetel `Manual` supaya tidak merebut port 5432 dari Docker.

### 9.2 Di mana setup-nya

| Yang ingin diubah | File |
|---|---|
| Kredensial & URL koneksi (satu untuk semua) | `.env` di root repo |
| Container Postgres + Redis | `packages/api/docker-compose.yml` |
| Container Neo4j yang sedang dipakai | `ops/docker/docker-compose.neo4j.yml` |
| URL Postgres default & setting API | `packages/api/app/core/config.py` (`database_url`) |
| Engine/session Postgres | `packages/api/app/core/database.py` (`get_db` untuk request, `task_session` untuk Celery) |
| Struktur tabel Postgres | `packages/api/app/models/case.py` |
| Kapan tabel dibuat | `packages/api/app/main.py` → `lifespan` menjalankan `create_all` saat API start |
| Koneksi Neo4j & LLM | `packages/pipeline/src/futechi_graphrag/config/settings.py`, `infrastructure/neo4j/driver.py` |
| Skema knowledge graph | `packages/pipeline/src/futechi_graphrag/pipelines/knowledge_graph/ontology/*.yaml` |
| Constraint & index Neo4j | `.../knowledge_graph/cypher/constraints/`, `.../cypher/indexes/` |
| Isi knowledge graph | `.../knowledge_graph/cypher/seeds/001–003_*.cypher` |
| Pemuat seed | `packages/pipeline/scripts/bootstrap_neo4j.py` (+ `validate_seed_consistency.py`) |

Variabel `.env` yang relevan:

```env
# Postgres (boleh tidak diisi; default-nya sudah cocok dengan compose)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/futechi
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
```

**Jebakan penting soal password:**
- `POSTGRES_PASSWORD` dan `NEO4J_AUTH` di compose **hanya dipakai saat volume masih kosong**
  (pertama kali container dibuat). Mengubah `.env` setelahnya **tidak** mengganti password
  di database — ganti lewat SQL/Cypher, atau hapus volume (data ikut hilang).
- `docker compose` membaca `.env` dari folder file compose, **bukan** root repo. Kalau ingin
  compose memakai `.env` root, tambahkan `--env-file .env`. Tanpa itu, compose memakai nilai
  default (`postgres/postgres`, `neo4j/change-me`).

### 9.3 Menyalakan, menghentikan, memeriksa

Dari root repo (`C:\Users\User\graphdb`):

```powershell
# nyalakan
docker compose -f ops/docker/docker-compose.neo4j.yml up -d          # Neo4j
docker compose -f packages/api/docker-compose.yml up -d postgres redis

# status (Neo4j "unhealthy" boleh diabaikan: healthcheck-nya memakai curl
# yang tidak ada di image Neo4j, padahal servernya jalan normal)
docker ps

# log
docker logs futechi-postgres --tail 50
docker logs poultry-neo4j --tail 50

# hentikan (data TETAP ada di volume)
docker compose -f packages/api/docker-compose.yml stop
docker compose -f ops/docker/docker-compose.neo4j.yml stop
```

Jangan menjalankan service `neo4j` dari `packages/api/docker-compose.yml` selama
`poultry-neo4j` dari `ops/docker` masih ada: nama container dan port 7687 sama.

### 9.4 Melihat isi PostgreSQL

**Cara 1 — `psql` di dalam container (tanpa instal apa pun):**

```powershell
docker exec -it futechi-postgres psql -U postgres -d futechi
```

Perintah dasar di dalam `psql`:

| Perintah | Fungsi |
|---|---|
| `\dt` | daftar tabel |
| `\d cases` | struktur satu tabel |
| `\x` | tampilan per-kolom (enak untuk kolom JSON panjang) |
| `\q` | keluar |

Query yang sering dipakai:

```sql
-- daftar alert terbaru
SELECT id, cage_id, status, severity_level, alert_count, requires_manual_review, last_detected_at
FROM cases ORDER BY last_detected_at DESC LIMIT 10;

-- detail hasil diagnosis satu case (kolom JSON dirapikan)
SELECT jsonb_pretty(visual_features::jsonb)    AS fitur,
       jsonb_pretty(related_conditions::jsonb) AS kandidat,
       jsonb_pretty(recommended_checks::jsonb) AS pemeriksaan,
       pipeline_status, pipeline_notes, error
FROM cases WHERE id = '<case_id>';

-- status monitoring kandang (exclusion / cooldown / safety-net)
SELECT cage_id, status, cooldown_reason, cooldown_cycles_remaining,
       anomaly_count_during_cooldown, active_case_id
FROM cages ORDER BY updated_at DESC;

-- semua event dari edge, termasuk yang di-skip
SELECT event_id, cage_id, outcome, case_id, created_at
FROM detection_events ORDER BY created_at DESC LIMIT 20;

-- riwayat chat satu case + kandidat yang dipakai sebagai dasar jawaban
SELECT role, left(content, 100) AS isi, graph_scope, created_at
FROM chat_messages WHERE case_id = '<case_id>' ORDER BY created_at;
```

Sekali jalan tanpa masuk ke `psql`:

```powershell
docker exec futechi-postgres psql -U postgres -d futechi -c "select status, count(*) from cases group by status"
```

**Cara 2 — pgAdmin 4 (GUI, sudah terpasang bersama PostgreSQL native):**

Register → Server, lalu isi:

| Tab | Isian |
|---|---|
| General → Name | `futechi-docker` |
| Connection → Host | `localhost` |
| Port | `5432` |
| Maintenance database | `futechi` |
| Username / Password | `postgres` / `postgres` |

Tabel ada di **Servers → futechi-docker → Databases → futechi → Schemas → public → Tables**.
Klik kanan tabel → **View/Edit Data → All Rows**.
pgAdmin hanya dipakai sebagai penampil; server yang terhubung tetap Postgres di Docker.

**Membersihkan data uji** (struktur tabel tetap ada):

```powershell
docker exec futechi-postgres psql -U postgres -d futechi -c "TRUNCATE chat_messages, frames, detection_events, cases, cages CASCADE;"
```

Saat runbook ini ditulis, Postgres masih berisi 2 case sisa smoke test (cage `SMOKE-1`).
Hindari `docker compose down -v` kecuali memang ingin menghapus volume beserta seluruh data.

### 9.5 Melihat isi Neo4j

**Cara 1 — Neo4j Browser (GUI, paling informatif karena bisa melihat bentuk graph):**

1. Buka **http://localhost:7474**
2. Connect URL: `neo4j://localhost:7687`
3. Username / password: sesuai `NEO4J_USERNAME` / `NEO4J_PASSWORD` di `.env`

Query yang berguna (ketik di kotak atas lalu Ctrl+Enter):

```cypher
// jumlah node per label
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS jumlah ORDER BY label;

// satu penyakit beserta semua relasinya (tampil sebagai graph)
MATCH (d:Disease {id: "DIS-001"})-[r]->(x) RETURN d, r, x;

// penyakit apa saja yang punya fitur tertentu, urut dari yang paling khas
MATCH (d:Disease)-[r:HAS_VISUAL_FEATURE]->(:VisualFeature {name: "conjunctivitis"})
RETURN d.name, r.specificity, r.clinical_note
ORDER BY CASE r.specificity WHEN "high" THEN 0 WHEN "medium" THEN 1 ELSE 2 END;

// penyakit wajib lapor
MATCH (d:Disease {notifiable: true}) RETURN d.id, d.name;

// data dummy yang harus diganti sebelum dipakai di lapangan
MATCH (n) WHERE n.data_status = "dummy" RETURN labels(n)[0] AS label, n.id, n.name;

// file seed yang sudah diterapkan
MATCH (m:_SchemaMigration) RETURN m.filename, m.applied_at ORDER BY m.filename;

// gambaran keseluruhan (dibatasi supaya browser tidak berat)
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 150;
```

**Cara 2 — `cypher-shell` di dalam container (terminal):**

```powershell
docker exec -it poultry-neo4j cypher-shell -u neo4j -p "<NEO4J_PASSWORD>"
```

Keluar dengan `:exit`. Contoh sekali jalan:

```powershell
docker exec poultry-neo4j cypher-shell -u neo4j -p "<NEO4J_PASSWORD>" "MATCH (d:Disease) RETURN count(d)"
```

**Mengisi ulang knowledge graph** (hanya bila file seed berubah; file yang sudah tercatat
di `_SchemaMigration` tidak dijalankan ulang tanpa `--reset`):

```powershell
python packages/pipeline/scripts/validate_seed_consistency.py
python packages/pipeline/scripts/bootstrap_neo4j.py --reset --yes
```

`--reset` menghapus **seluruh** node Neo4j (constraint & index tetap).

### 9.6 Cek cepat semua koneksi

```powershell
docker ps
docker exec futechi-postgres pg_isready -U postgres
docker exec futechi-redis redis-cli ping
curl.exe -s -o NUL -w "Neo4j Browser HTTP %{http_code}`n" http://localhost:7474
```

Hasil yang diharapkan: tiga container `Up`, `accepting connections`, `PONG`, dan `HTTP 200`.

### 9.7 Masalah yang sering muncul

| Gejala | Penyebab | Solusi |
|---|---|---|
| API gagal start: `connection refused` ke 5432 | Postgres container mati | `docker compose -f packages/api/docker-compose.yml up -d postgres` |
| Data di pgAdmin berbeda dari yang dilihat API | pgAdmin terhubung ke Postgres native | Pastikan service `postgresql-x64-17` berhenti; cek host/port di pgAdmin |
| `password authentication failed` padahal `.env` sudah diubah | Password hanya di-set saat volume pertama dibuat | Ubah via `ALTER USER`, atau pakai password lama |
| Neo4j Browser menolak login | Sama: `NEO4J_AUTH` hanya berlaku saat volume pertama dibuat | Pakai password awal, atau ubah lewat `ALTER CURRENT USER SET PASSWORD` |
| Retrieval selalu kosong | Neo4j belum di-seed / seed sebagian | Jalankan query "jumlah node per label", lalu `bootstrap_neo4j.py --reset --yes` |
| Neo4j `unhealthy` | Healthcheck image memakai `curl` yang tidak tersedia | Abaikan selama port 7474/7687 merespons |

### 9.8 Graph kedua: data buku (`poultry-neo4j-buku`)

| | Graph utama | Graph buku |
|---|---|---|
| Container | `poultry-neo4j` | `poultry-neo4j-buku` |
| Compose | `ops/docker/docker-compose.neo4j.yml` | `ops/docker/docker-compose.neo4j-buku.yml` |
| Browser | http://localhost:7474 | http://localhost:7475 (Connect URL `neo4j://localhost:7688`) |
| Bolt | `bolt://localhost:7687` | `bolt://localhost:7688` |
| Isi | seed 001–003 (kontrak pipeline) | `004_seed_data_penyakit_buku.json`: 826 node, 887 relasi |
| Diisi oleh | `scripts/bootstrap_neo4j.py` | `scripts/seed_graph_buku.py` |
| Kredensial | `NEO4J_PASSWORD` (baris `# [GRAPH UTAMA]`) | `NEO4J_BUKU_PASSWORD` |

```powershell
# dari root repo
docker compose --env-file .env -f ops/docker/docker-compose.neo4j-buku.yml up -d
python packages/pipeline/scripts/seed_graph_buku.py --dry-run
python packages/pipeline/scripts/seed_graph_buku.py --hapus-semua   # isi ulang dari nol
```

Program (pipeline & API) memilih graph lewat `NEO4J_*` di `.env` root. Saat ini
nilainya menunjuk **graph buku**. Untuk kembali ke graph utama: hapus empat baris
`NEO4J_*` yang aktif dan buka komentar baris `# [GRAPH UTAMA]`.

Hal yang perlu diperhatikan selama program terhubung ke graph buku:
- Jangan jalankan `bootstrap_neo4j.py` karena perintah itu akan menulis seed 001–003
  ke graph buku (atau menghapusnya bila memakai `--reset`).
- Diagnosis selalu mengembalikan 0 kandidat. Validasi ontologi hanya menerima nama
  kanonik (`bloody_feces`), sedangkan VisualFeature di buku berupa kalimat bebas
  ("Kulit tidak terlalu memerah"), sehingga tidak ada yang cocok.
- Integration test pipeline (`tests/integration`) mengharapkan data seed 001–003,
  jadi test itu akan gagal.
- Buku memakai label `Treatment`/`BiosecurityMeasure` dengan properti `teks`. Pipeline
  membaca `Medication`/`MitigationAction` dengan properti `name`, jadi obat dan
  mitigasi tidak ikut terbaca.
