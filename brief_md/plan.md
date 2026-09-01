# Plan audit kesesuaian file baru terhadap sistem aktif

## Masalah dan pendekatan

Beberapa file yang baru ditambahkan pada pipeline Modul C tampak masih mewarisi konvensi lama dan belum sepenuhnya selaras dengan struktur aktif di `src/futechi_graphrag`. Audit ini akan fokus pada konsistensi arsitektur: path, import, DTO, dan kontrak domain, bukan menambah fungsi baru.

Masalah yang sudah teridentifikasi:
- impor masih mengarah ke `poultry_graphrag`
- nama file/objek masih lama (`observations` vs `observation`)
- beberapa DTO belum diverifikasi apakah benar-benar sesuai dengan tipe yang dipakai di domain dan pipeline B
- perlu memastikan tidak terjadi shadowing terhadap package aktif yang sudah berjalan

## Todo

1. Audit struktur file baru terhadap `src/futechi_graphrag`
   - cek apakah file masuk ke folder yang benar, nama modul sesuai arsitektur
   - pastikan tidak ada duplikasi/legacy file yang mengganggu importing

2. Validasi import path dan naming
   - ganti semua `poultry_graphrag` ke `futechi_graphrag`
   - sesuaikan referensi ke `observation`, `severity`, `exceptions`, `enums`, dsb.
   - buang/abaikan referensi ke file atau nama lama yang sudah tidak dipakai

3. Check kontrak domain/DTO
   - bandingkan `CaseContextInput`, `ReasoningOutput`, `DifferentialNoteItem` dengan `GraphContext` dan `VisualFeatureObservation`
   - pastikan `severity`, `related_conditions`, `disease_actions`, dan `inspection_actions` konsisten dengan objek domain yang aktif

4. Verifikasi integrasi dengan Modul A/B
   - pastikan output Modul A dan input Modul B masih cocok
   - pastikan payload Modul C siap diterima oleh `Case.attach_reasoning_result` dan pipeline berikutnya

5. Jalankan validasi fokus
   - test domain dan modul B yang sudah ada
   - tambahkan/cek test yang menutup kontrak DTO baru bila dibutuhkan

## Catatan dan keputusan

- Fokus utama adalah konsistensi arsitektur, bukan menambah fitur baru.
- Package aktif yang valid adalah `futechi_graphrag`, bukan legacy `poultry_graphrag`.
- Semua perbaikan harus menjaga kompatibilitas terhadap domain contract yang sudah dibuat sebelumnya.
- Setelah audit ini selesai, implementasi Modul C bisa dilanjutkan dengan struktur yang lebih stabil dan akuntabel.

## Design Addendum: Chat Persistence & Riwayat Kandang

Audit tambahan yang perlu dipenuhi sebelum implementasi Tahap 7/8/10:

1. `LangGraph Checkpointer` dan `Case Store` harus dipisahkan secara eksplisit.
   - checkpointer menyimpan `messages` berdasarkan `thread_id = case_id`
   - case store menyimpan `status`, `related_conditions`, `confirmed_condition` berdasarkan `case_id` dan `cage_id`

2. `sync_case_state` wajib dipanggil di awal `chat_graph` sebelum retrieval atau respond.
   - urutan: `sync_case_state -> load_cage_history -> retrieve -> respond`

3. Riwayat cage hanya berlaku untuk chat, bukan Tier 1 `diagnostic_graph`.
   - `CaseStore.find_resolved_cases_by_cage(cage_id, exclude_case_id, limit=5, since_days=90)`
   - DTO `CageHistoryEntry` harus dibuat dan dibatasi 90 hari / 5 item

4. Rule #11 wajib masuk ke `CHAT_SYSTEM_PROMPT` dalam `prompt_constraints.py`.
   - riwayat kandang hanya catatan informasional, BUKAN bukti utama diagnosis

5. File yang masih kosong dan harus diimplementasikan untuk memenuhi addendum:
   - [src/futechi_graphrag/pipelines/orchestration/chat_graph.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/orchestration/chat_graph.py)
   - [src/futechi_graphrag/pipelines/orchestration/state.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/orchestration/state.py)
   - [src/futechi_graphrag/pipelines/orchestration/diagnostic_graph.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/orchestration/diagnostic_graph.py)

6. Audit cepat terhadap file aktif:
   - [src/futechi_graphrag/pipelines/module_c_reasoning/prompt_constraints.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/module_c_reasoning/prompt_constraints.py) sudah berisi rule #11
   - [src/futechi_graphrag/pipelines/module_c_reasoning/reasoner.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/module_c_reasoning/reasoner.py) masih mengandung import legacy `poultry_graphrag` dan perlu disesuaikan ke `futechi_graphrag`
   - `CaseStore` / `CageHistoryEntry` belum ada sama sekali di repo aktif

## Gap Audit Lengkap: Tahap 7 / 8 / 10

### 1) Tahap 7 — Modul C & prompt constraint

Status: sebagian selesai, tetapi belum final karena belum ada integrasi penuh dengan `case_status` dan `cage_history`.

Sesuai addendum, gap utama:
- [src/futechi_graphrag/pipelines/module_c_reasoning/prompt_constraints.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/module_c_reasoning/prompt_constraints.py)
  - Rule #11 sudah ada dan sudah benar secara semantik.
  - Namun kebutuhan addendum menuntut juga bahwa `case_status` dan `confirmed_disease` ikut masuk ke prompt konteks chat, bukan hanya `messages` dan `graph_context`.
- [src/futechi_graphrag/pipelines/module_c_reasoning/reasoner.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/module_c_reasoning/reasoner.py)
  - `build_chat_prompt()` sudah membedakan riwayat vs evidence saat ini.
  - Namun belum ada wiring yang mengirim `case_status` dan `confirmed_disease` dari `CaseStore` ke `reason_chat_turn()` secara otomatis.
- Belum ada test khusus untuk skenario:
  - `PENDING_CONFIRMATION` + history cage dari kasus lama
  - `CONFIRMED_SICK` + `confirmed_disease` aktif
  - still-empty graph context + cage history present

Kesimpulan:
- Rule #11 sudah ada: READY.
- Integrasi runtime dari state ke prompt: NOT READY.

### 2) Tahap 8 — Orchestration chat dan retrieval conditional

Status: masih skeleton, belum final.

Gap utama:
- [src/futechi_graphrag/pipelines/orchestration/chat_graph.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/orchestration/chat_graph.py)
  - sudah dibuat skeleton, tetapi belum punya node retrieval aktual yang memanfaatkan `case_status`.
  - `sync_case_state` harus dipanggil dulu sebelum retrieval; ini sudah sesuai rencana, tapi belum dihubungkan ke workflow aplikasi nyata.
- [src/futechi_graphrag/pipelines/orchestration/state.py](C:/Users/User/graphdb/src/futechi_graphrag/pipelines/orchestration/state.py)
  - `ChatState` sudah ada minimal, tetapi belum dipakai secara penuh oleh graph runtime.
  - `messages` harus tetap disimpan via checkpoint, sementara `case_status`/`confirmed_disease` harus dipulihkan dari Case Store setiap turn.
- Belum ada logic conditional retrieval berdasarkan status:
  - `PENDING_CONFIRMATION` => multi-kandidat seperti biasa
  - `CONFIRMED_SICK` => hanya kandidat `confirmed_disease`
- Belum ada `thread_id = case_id` integration yang deterministik di checkpointer configuration.
- `load_cage_history` masih sebagai contract, belum dihubungkan ke `reason_chat_turn()` dalam satu alur utuh.

Kesimpulan:
- Flow orchestration chat: partial implementation, not production-ready.
- Retrieval conditional by status: missing.

### 3) Tahap 10 — Persistence & Case Store

Status: in-memory foundation exists, but not complete production persistence.

Gap utama:
- [src/futechi_graphrag/infrastructure/persistence/case_store.py](C:/Users/User/graphdb/src/futechi_graphrag/infrastructure/persistence/case_store.py)
  - `CaseStore` minimal sudah ada.
  - `find_resolved_cases_by_cage()` sudah ada dengan limit dan since_days, sesuai addendum.
  - `CageHistoryEntry` juga sudah ada.
  - Namun ini masih in-memory, bukan persistence layer yang benar-benar terikat ke DB / repository.
- Belum ada schema/index yang merepresentasikan kebutuhan riwayat kandang di DB riil:
  - index `cage_id`
  - index `resolved_at`
  - query `find_resolved_cases_by_cage` idealnya ter-optimized dan dipisahkan dari in-memory dictionary.
- Belum ada sinkronisasi eksplisit dari tombol konfirmasi UI ke `CaseStore` dan dari `CaseStore` ke chat state.
- Belum ada use case/adapter yang menghubungkan `CaseStore` ke domain `Case` entity dan `CaseStatus` enum secara konsisten.

Kesimpulan:
- Contract persistence: implemented as scaffold only.
- Production persistence and indexing: not yet done.

### 4) Checklist kelayakan sebelum lanjut ke tahap berikutnya

Yang sudah siap:
- [x] Rule #11 pada prompt constraint
- [x] `CageHistoryEntry` minimal
- [x] `CaseStore` minimal contract
- [x] `sync_case_state` + `load_cage_history` skeleton
- [x] `ChatState` initial schema
- [x] import legacy cleanup di Modul C

Yang masih belum siap untuk implementasi penuh:
- [ ] aktual retrieval conditional di `chat_graph`
- [ ] sinkronisasi `CaseStore` ke chat state per turn
- [ ] pengikatan `thread_id = case_id` di checkpointer hidup
- [ ] DB-backed persistence untuk `CaseStore`
- [ ] end-to-end test untuk kasus riwayat kandang & konfirmasi tombol
- [ ] validasi prompt terhadap `case_status` + `confirmed_disease` pada chat

### 5) Rekomendasi prioritas berikutnya

Prioritas 1: sambungkan alur `sync_case_state -> load_cage_history -> retrieve -> respond` dengan state nyata dan use case yang mengakses `CaseStore`.
Prioritas 2: dibuatkan `CaseStore` versi DB-backed dengan query `find_resolved_cases_by_cage` dan index yang sesuai.
Prioritas 3: uji skenario ChatState `CONFIRMED_SICK` vs `PENDING_CONFIRMATION`.
Prioritas 4: tambahkan tests unit untuk prompt chat dan state sync.

Ringkasnya: addendum ini secara konsep sudah mengarahkan arsitektur ke arah yang benar, tetapi implementasinya masih berada di level scaffold. Level berikutnya adalah koneksi nyata antara state store, checkpointer, dan chat retrieval secara end-to-end.

## Progress Tracker (status saat ini)

### Stage-by-stage status menurut panduan implementasi

| Stage | Item | Status | Catatan |
|---|---|---:|---|
| 1 | Project foundation & dependencies | Done | `pyproject.toml`, Docker Neo4j, `.env` template, bootstrap, venv aktif |
| 2 | Domain layer | Done | `Case`, `Cage`, enums, severity, domain rules dan entity model sudah map |
| 3 | Knowledge graph schema + seed | Done | Graph seed and ontology structure aligned with active package |
| 4 | Neo4j infra & repo access | Done | driver, cypher runner, disease repository, ontology repo ready |
| 5 | Modul B retrieval boundary & fallback | Done | builder, retriever, boundary check, tests passing |
| 6 | Modul A semantic mapping | Done | extractor, mapper, validator, aggregator, tests passing |
| 7 | Modul C reasoning & prompt constraints | Partial | rule #11 and prompt logic exist; runtime state sync still missing |
| 8 | Chat orchestration / LangGraph chat | Partial | skeleton exists; retrieval conditional and real message flow not yet complete |
| 9 | Use case / application flow | Pending | no full use-case layer wiring around chat/case confirmation yet |
| 10 | Case persistence + history store | Partial | `CaseStore` and `CageHistoryEntry` exist in-memory, not DB-backed |

### Design Addendum compliance status

| Addendum item | Status | Catatan |
|---|---:|---|
| Separate checkpointer vs case store | Done (scaffold) | lightweight separation exists, but not fully wired to real app lifecycle |
| `sync_case_state` before chat respond | Partial | function exists and graph order is defined; no full runtime integration yet |
| `load_cage_history` limit 5/90d | Done (scaffold) | implemented in `CaseStore.find_resolved_cases_by_cage()` |
| Rule #11 in `CHAT_SYSTEM_PROMPT` | Done | historical cage context is labeled as informational |
| Conditional retrieval by `case_status` | Pending | not yet implemented in chat workflow |
| DB-backed `CaseStore` + indexing | Pending | in-memory store only |
| End-to-end chat sync with confirmation button | Pending | no full use-case / UI integration yet |

### Current progress summary

- Completed: foundation, domain, ontology, graph access, retrieval, semantic mapping, import cleanup, prompt rule for cage history, initial case-store and chat-state skeleton.
- Partial: Modul C runtime wiring, chat graph orchestration, persistence persistence contract.
- Missing: full status-based retrieval, DB-backed history persistence, use-case wiring, end-to-end tests for chat confirmation + cage history behavior.

### File-by-file implementation checklist (Tahap 7 / 8 / 10)

#### Stage 7 — Modul C reasoning and prompt contract

- [ ] `src/futechi_graphrag/pipelines/module_c_reasoning/prompt_constraints.py`
  - keep `BASE_RULES` and `CHAT_SYSTEM_PROMPT`
  - ensure rule #11 remains: cage history is informational only
  - ensure prompt explicitly prioritizes `graph_context` over historical cage notes
  - add explicit handling for `case_status = CONFIRMED_SICK` and `confirmed_disease`

- [ ] `src/futechi_graphrag/pipelines/module_c_reasoning/reasoner.py`
  - finalize `build_chat_prompt()` to receive live `case_status` and `confirmed_disease`
  - include `cage_history_summary` as a distinct block, never as primary evidence
  - ensure `reason_chat_turn()` consumes the synchronized state from the chat graph
  - validate no direct legacy imports remain

- [ ] `src/futechi_graphrag/pipelines/module_c_reasoning/dto.py`
  - confirm `ChatMessage`, `CaseContextInput`, `ReasoningOutput` remain aligned with current domain objects
  - make sure `ReasoningOutput` remains compatible with `Case.attach_reasoning_result()`

- [ ] `src/futechi_graphrag/pipelines/module_c_reasoning/deterministic_builders.py`
  - verify evidence strings remain deterministic and graph-derived
  - confirm action bundles remain compatible with `DiseaseActionBundle` in `observation.py`

- [ ] `src/futechi_graphrag/pipelines/module_c_reasoning/severity_selector.py`
  - verify severity logic remains based on `base_severity` + `onset_stage`
  - no change needed unless a real-case calibration issue is found

- [ ] `src/futechi_graphrag/pipelines/module_c_reasoning/fallback_template.py`
  - keep fallback as static no-LLM response when graph context is empty
  - confirm it does not cite cage history as diagnostic evidence

- [ ] `tests/unit/test_module_c_reasoning.py` (new or expanded)
  - add case: `PENDING_CONFIRMATION` + cage history present + valid graph context
  - add case: `CONFIRMED_SICK` + `confirmed_disease` active
  - add case: graph context empty + cage history present
  - add test confirming prompt text states history is informational only

#### Stage 8 — Orchestration, LangGraph chat loop, and state sync

- [ ] `src/futechi_graphrag/pipelines/orchestration/state.py`
  - finalize `ChatState` contract with required fields
  - include `case_status`, `confirmed_disease`, `messages`, `graph_context`, `cage_history`
  - ensure state is serializable to LangGraph checkpoints

- [ ] `src/futechi_graphrag/pipelines/orchestration/chat_graph.py`
  - implement real `sync_case_state` node before retrieval
  - implement `load_cage_history` node with `limit=5` and `since_days=90`
  - add conditional retrieval logic:
    - `PENDING_CONFIRMATION` -> normal multi-candidate retrieval
    - `CONFIRMED_SICK` -> filter to `confirmed_disease`
  - bring `retrieve` and `respond` nodes to actual application logic, not placeholders
  - ensure graph order is exactly: `sync_case_state -> load_cage_history -> retrieve -> respond`

- [ ] `src/futechi_graphrag/infrastructure/checkpointer.py`
  - configure checkpoint with `thread_id = case_id`
  - ensure chat messages persist separately from CaseStore
  - keep this layer independent from official case status storage

- [ ] `src/futechi_graphrag/pipelines/orchestration/diagnostic_graph.py`
  - keep diagnostic graph separate from chat graph
  - keep Tier 1 flow focused on fresh case detection, without cage history injection
  - ensure it does not include historical cage memory as direct evidence

- [ ] `src/futechi_graphrag/pipelines/orchestration/__init__.py` (if added)
  - export main graph builders and state contracts

- [ ] `tests/unit/test_chat_graph.py` (new)
  - test `sync_case_state` reloads latest status from `CaseStore`
  - test `load_cage_history` returns only resolved cases for same cage
  - test `CONFIRMED_SICK` filters retrieval scope to confirmed disease only
  - test `PENDING_CONFIRMATION` still allows multi-candidate context

#### Stage 10 — Persistence and case history store

- [ ] `src/futechi_graphrag/infrastructure/persistence/case_store.py`
  - replace in-memory-only contract with DB-backed persistence when needed
  - define canonical schema for `case_id`, `cage_id`, `status`, `confirmed_condition`, `resolved_at`
  - add query method `find_resolved_cases_by_cage(cage_id, exclude_case_id, limit=5, since_days=90)`
  - ensure returned objects are `CageHistoryEntry` dataclass instances

- [ ] `src/futechi_graphrag/infrastructure/persistence/__init__.py` (if needed)
  - export `CaseStore` and `CageHistoryEntry`

- [ ] database schema / migrations (new or planned)
  - add index on `cage_id`
  - add index on `resolved_at`
  - add composite index on `(cage_id, resolved_at)` if needed
  - add case status enum validation in DB layer if DB supports it

- [ ] application/use-case layer (new)
  - create a service that syncs confirmation button events to `CaseStore`
  - create `chat_case_context()` service to pass `case_id` as `thread_id`
  - ensure `CaseStore` remains the source of truth for case status while checkpointer handles conversation history only

- [ ] `tests/unit/test_case_store.py` (new)
  - test cage history retrieval ordering by `resolved_at` desc
  - test exclusion of current `case_id`
  - test limit and since_days behavior
  - test confirmed vs pending statuses filtering

#### Cross-cutting readiness checks

- [ ] confirm no `poultry_graphrag` references remain in active source tree
- [ ] confirm no stale `observations` import remains in module C or other active package paths
- [ ] confirm all stage outputs are compatible with `Case.attach_reasoning_result()`
- [ ] confirm graph history is informational only and never treated as primary evidence
- [ ] verify all state transitions are traceable from `CaseStore` to `ChatState` to message response

### Immediate next work

1. Connect `sync_case_state -> load_cage_history -> retrieve -> respond` to real state objects.
2. Implement conditional retrieval by `case_status`.
3. Add DB-backed `CaseStore` and index schema for `cage_id` and `resolved_at`.
4. Add chat tests for pending vs confirmed-sick behavior.
5. Validate that prompt text gives `graph_context` priority over cage history.
