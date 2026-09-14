# Track Implementasi — GraphRAG & LangGraph

> Acuan desain: [alur_sistem_terpadu.md](alur_sistem_terpadu.md) (Phase 4 diagnostic graph, Phase 5.3 chat graph).
> Cakupan dokumen ini: **sisi server** (GraphRAG + orkestrasi LangGraph + domain & persistence pendukungnya).
> Edge (FCOS-Lite, Pi) di luar cakupan.

## Snapshot

| | |
|---|---|
| Tanggal audit | 2026-09-14 |
| Branch / commit | `langgraph` @ `bbd5fd6` + 1 perubahan belum di-commit (`prompt_constraints.py`) |
| Cara verifikasi | Membaca kode, import check semua modul, `venv/Scripts/python.exe -m pytest` |
| Hasil test | **63 lulus, 4 gagal** (semua di `tests/unit/chat/`) |
| Neo4j live | Tidak diuji (tidak ada integration test) |
| LLM live | Tidak diuji (tidak ada client yang pernah dipanggil) |

### Legenda status
| Simbol | Arti |
|---|---|
| ✅ | Selesai, ada test, sesuai desain |
| 🟢 | Logika selesai, tapi belum ada test / belum diuji live |
| 🟡 | Parsial: ada kode, tapi ada gap terhadap desain atau bug |
| 🔴 | Skeleton / placeholder, belum berfungsi |
| ⬜ | Belum ada sama sekali |
| ⏸️ | Menunggu keputusan `K#` di alur_sistem_terpadu.md |

---

## 1. Ringkasan per Komponen

| Komponen | Status | Catatan singkat |
|---|---|---|
| Domain: `Case`, `Cage`, state machine, policies, severity | 🟡 | Test lulus; ada typo field & threshold tidak konsisten (lihat B6, B7) |
| Knowledge graph: ontologi YAML, constraints, indexes | ✅ | `notifiable` sudah ada di `node_definitions.yaml` |
| Knowledge graph: **seed data** | 🔴 | Hanya 1 penyakit, 2 fitur visual, 1 kondisi lingkungan, 0 Symptom, tanpa `notifiable` |
| Neo4j infra (driver, runner, repositories) | 🟢 | Tidak ada integration test ke Neo4j sungguhan |
| Modul A — semantic mapping | 🟡 | Pipeline & test ada; client VLM masih generik, agregasi pakai max bukan majority |
| Modul B — graph retrieval | 🟡 | Test ada; **tipe output tidak cocok dengan Modul C** (B1); retry tidak efektif (B4) |
| Modul C — reasoning | 🟡 | Logika lengkap, **0 test**, bug `zone_id` (B3) |
| LLM client | 🔴 | Hanya `AnthropicLLMClient` (belum pernah dijalankan, package tidak ada di dependencies); belum ada client GLM |
| **Orkestrasi `diagnostic_graph`** | 🔴 | 4 node lambda identitas, tanpa conditional edge, node fallback tidak terjangkau |
| **Orkestrasi `chat_graph`** | 🟡 | `sync_case_state` & `load_cage_history` jalan; `retrieve`/`respond` placeholder; `NameError` di scope filter |
| State LangGraph (`state.py`) | 🟡 | `PipelineState` baru sebagian field desain |
| Checkpointer | 🟡 | `InMemorySaver` baru dibuat tiap `build_chat_graph()` → riwayat chat hilang |
| CaseStore | 🟡 | In-memory; casing status tidak konsisten (B5) |
| Audit trail store | ⬜ | File ada tapi kosong |
| Exclusion store, feedback store | ⬜ | Belum ada |
| Application layer (use cases) | ⬜ | Belum ada folder `application/` |
| API (FastAPI), scheduler (sesi deteksi, TTL job) | ⬜ | Belum ada folder `interfaces/` |

---

## 2. Diagnostic Graph — Track per Node

Desain: [alur_sistem_terpadu.md §4.2](alur_sistem_terpadu.md). Implementasi saat ini: [diagnostic_graph.py](../src/futechi_graphrag/pipelines/orchestration/diagnostic_graph.py) — **semua node masih `lambda state: state`**, alur `module_a → module_b → module_c → END`.

| Node desain | Logika modul (sudah ada?) | Terpasang di graph? | Status | Gap / yang harus dikerjakan |
|---|---|---|---|---|
| **N1 image_extraction** | [vlm_extractor.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/vlm_extractor.py) — memanggil `vision_client.analyze(frame)` per frame | ❌ | 🟡 ⏸️K12 K13 | Belum ada client GLM-5.3-Flash + prompt ekstraksi; kontrak `{"detections":[{label, confidence}]}` belum terdokumentasi; flag `capture_quality` belum diteruskan |
| **N2 semantic_mapping** | [frame_aggregator.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/frame_aggregator.py), [confidence_filter.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/confidence_filter.py), [canonical_mapper.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/canonical_mapper.py), [mapping_validator.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/mapping_validator.py) | ❌ | 🟡 ⏸️K6 | Agregasi memakai **confidence maksimum**, desain: majority vote / rata-rata (B8). `alias_map` harus di-load dari `synonym_dictionary.yaml` oleh pemanggil |
| **N3 environment_fusion** | [sensor_normalizer.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/sensor_normalizer.py) (threshold suhu >30, RH >75, NH₃ >20) | ❌ | 🟡 ⏸️K10 | `pipeline.py` wajib `raw_environment` dict (gagal jika `None`); `EnvironmentSnapshot` wajib 3 float; kanonik hanya punya `humidity_attention` → `temperature_attention`/`ammonia_attention` akan **ditolak** `DiseaseRepository` (B9) |
| Cond: fitur kosong / unmapped >50% → FB | `validate_mapping()` menghasilkan `manual_review_required` | ❌ | 🟡 | Kondisi "visual_features kosong setelah filter" belum dicek; conditional edge belum dibuat |
| **N4 graph_retrieval** | [query_params_builder.py](../src/futechi_graphrag/pipelines/module_b_graph_retrieval/query_params_builder.py), [retriever.py](../src/futechi_graphrag/pipelines/module_b_graph_retrieval/retriever.py), [disease_repository.py](../src/futechi_graphrag/infrastructure/neo4j/repositories/disease_repository.py), [retrieve_disease_context.cypher](../src/futechi_graphrag/pipelines/knowledge_graph/cypher/templates/retrieve_disease_context.cypher) | ❌ | 🟡 | Output `list[domain GraphContext]` ≠ input Modul C `neo4j.dto.GraphContext(candidates=…)` (B1). `$recently_excluded_diseases` belum ada di template |
| Cond: graph kosong → retry 1× → FB | [boundary_check.py](../src/futechi_graphrag/pipelines/module_b_graph_retrieval/boundary_check.py) `is_context_empty`, `retry_with_fuzzy_expansion` | ❌ | 🟡 | Retry memperluas kanonik→kanonik, jadi query ulang **identik** (B4); `retrieval_retry_count` belum ada di state |
| **N5 differential_reasoning** | [reasoner.py](../src/futechi_graphrag/pipelines/module_c_reasoning/reasoner.py) `reason()` + `DIAGNOSTIC_SYSTEM_PROMPT` | ❌ | 🟡 ⏸️K9 K13 | Bug `case_context.zone_id` (B3); tidak ada test; `overall_uncertainty` masih teks bebas (belum level kategorikal) |
| **N6 recommendation_builder** | [deterministic_builders.py](../src/futechi_graphrag/pipelines/module_c_reasoning/deterministic_builders.py), [severity_selector.py](../src/futechi_graphrag/pipelines/module_c_reasoning/severity_selector.py) | ❌ (masih di dalam `reason()`) | 🟢 ⏸️K7 | Logika siap tapi belum dipisah jadi node; tidak ada test |
| **FB fallback_template** | [fallback_template.py](../src/futechi_graphrag/pipelines/module_c_reasoning/fallback_template.py) | node ada, **tanpa edge masuk** | 🟡 | `recommended_checks` kosong, desain: `general_visual_check`, `monitor_24h`; belum set `requires_manual_review` |
| **N7 persist_case** | `Case.attach_reasoning_result` / `mark_insufficient_data` + `transition()` | ❌ | ⬜ | Butuh use case + CaseStore berbasis entitas `Case` + notifikasi |

### Checklist diagnostic graph
- [ ] Satukan tipe `GraphContext` (B1) — **blocker utama**, semua node setelah N4 bergantung padanya
- [ ] Lengkapi `PipelineState` sesuai [§4.1](alur_sistem_terpadu.md) (`cage_id`, `blok_id`, `crops`, `capture_quality`, `unmapped_features`, `retrieval_retry_count`, `requires_manual_review`, dst.)
- [ ] Wrapper node N1–N7 + FB yang memanggil fungsi modul (tanpa memindahkan logika domain ke graph)
- [ ] Conditional edge: setelah N3 (manual review), setelah N4 (empty → retry → FB)
- [ ] Dependency injection (vision client, LLM client, repository) lewat factory `build_diagnostic_graph(deps)`, bukan global
- [ ] Compile graph sekali, jangan di tiap `run_diagnostic_graph()`
- [ ] Test graph end-to-end dengan fake vision client, fake LLM, fake repository: jalur normal, jalur manual review, jalur empty→retry→fallback

---

## 3. Chat Graph — Track per Node

Desain: [alur_sistem_terpadu.md §5.3](alur_sistem_terpadu.md). Implementasi: [chat_graph.py](../src/futechi_graphrag/pipelines/orchestration/chat_graph.py).
Urutan edge sudah sesuai: `sync_case_state → load_cage_history → retrieve → respond`.

| Node | Status | Keterangan |
|---|---|---|
| `sync_case_state` | 🟡 | Berfungsi & teruji. Default `case_store=None` membuat `CaseStore()` baru yang kosong → di graph sungguhan tidak pernah menemukan case |
| `load_cage_history` | 🟡 | Berfungsi & teruji (limit 5 / 90 hari). Terkena B5: status huruf besar tidak dianggap resolved |
| `retrieve` | 🔴 | Placeholder. `apply_retrieval_scope` / `retrieve_conditional` ada tapi **tidak dipasang** dan `NameError` karena `GraphContext` tidak di-import (B2). Belum ada panggilan retrieval Neo4j sungguhan per giliran |
| `respond` | 🔴 | Placeholder. `reason_chat_turn()` + `CHAT_SYSTEM_PROMPT` ada di Modul C tapi belum dipanggil; ringkasan `cage_history` → teks belum dibuat |
| Checkpointer (`thread_id = case_id`) | 🟡 | Smoke test lulus; `InMemorySaver` baru tiap build (B10) |

### Checklist chat graph
- [ ] Import `GraphContext` di `chat_graph.py` + import di 4 file test (B2)
- [ ] Node `retrieve`: ambil fitur case dari CaseStore → `build_params` → `DiseaseRepository` → `apply_retrieval_scope`
- [ ] Node `respond`: bentuk `cage_history_summary`, panggil `reason_chat_turn`, append `ChatMessage` ke `messages`
- [ ] Samakan tipe `messages` (`ChatMessage` di state vs dict di test)
- [ ] Inject `CaseStore` & checkpointer tunggal dari luar
- [ ] Test: graph kosong + riwayat ada; `CONFIRMED_SICK` tanpa `confirmed_disease`; prompt menyatakan riwayat hanya informasional

---

## 4. Lapisan Pendukung

### 4.1 Knowledge graph
| Item | Status | Catatan |
|---|---|---|
| [node_definitions.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/ontology/node_definitions.yaml), [relationship_definitions.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/ontology/relationship_definitions.yaml) | ✅ | Termasuk `notifiable` |
| Constraints & indexes | ✅ | |
| [Seed](../src/futechi_graphrag/pipelines/knowledge_graph/cypher/seeds/001_seed_ontology.cypher) | 🔴 | 1 Disease (Newcastle), 2 VisualFeature, 1 EnvironmentalCondition, 1 Inspection, 1 Mitigation, 1 Treatment, **0 Symptom**, tanpa `notifiable`. Differential reasoning multi-kandidat **tidak bisa diuji** dengan 1 penyakit |
| [canonical_terms.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/dictionaries/canonical_terms.yaml) / [synonym_dictionary.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/dictionaries/synonym_dictionary.yaml) | 🟡 | 2 fitur visual, 1 kondisi lingkungan; sinonim masih contoh |
| Bootstrap & validasi seed (`scripts/`) | ✅ | 9 test lulus |
| Validasi isi KG oleh pakar vet | ⬜ | Belum ada |

### 4.2 Domain
| Item | Status | Catatan |
|---|---|---|
| `Case` + state machine | 🟡 | Test lulus; typo `recomended_checks` (B6); merge belum memicu reasoning ulang |
| `Cage` | 🟡 | Default safety-net 4 ≠ policy 3 (B7) |
| Policies cooldown/safety-net/TTL | 🟡 | Cooldown default 4 siklus, desain "misal 3" & komentar "~1.5 hari" (4 siklus = 2 hari) |
| Severity | ✅ | 7 test |

### 4.3 Infrastruktur
| Item | Status | Catatan |
|---|---|---|
| Neo4j driver/runner/repository | 🟢 | Unit test dengan fake; belum ada integration test |
| [llm/client.py](../src/futechi_graphrag/infrastructure/llm/client.py) | 🔴 ⏸️K13 | Protocol bagus; implementasi Anthropic belum pernah dijalankan, `anthropic` tidak ada di `pyproject.toml` (yang ada `openai`); tidak ada client multimodal/GLM; `settings.py` belum punya konfigurasi LLM |
| [checkpointer.py](../src/futechi_graphrag/infrastructure/checkpointer.py) | 🟡 | In-memory |
| [case_store.py](../src/futechi_graphrag/infrastructure/persistence/case_store.py) | 🟡 | In-memory dict, bukan entitas `Case`; tidak DB-backed |
| [audit_trail_store.py](../src/futechi_graphrag/infrastructure/persistence/audit_trail_store.py) | ⬜ | Kosong |

---

## 5. Temuan Bug & Blocker Integrasi

Diurutkan dari yang paling memblokir.

| # | Tingkat | Lokasi | Masalah | Dampak |
|---|---|---|---|---|
| **B1** | 🔴 Blocker | [domain/value_objects/graph_context.py](../src/futechi_graphrag/domain/value_objects/graph_context.py) vs [infrastructure/neo4j/dto.py:79](../src/futechi_graphrag/infrastructure/neo4j/dto.py#L79) | Ada **dua kelas `GraphContext`**. Modul B (`DiseaseRepository`, `retriever`, `boundary_check`) mengembalikan `list[GraphContext]` versi domain (satu objek per penyakit, field dict). Modul C, `severity_selector`, `state.py`, `chat_graph` memakai versi `neo4j.dto` (`GraphContext(candidates=[DiseaseCandidate])`). `map_record_to_candidate()` di dto tidak dipakai di mana pun | Output N4 tidak bisa masuk N5/N6; graph tidak bisa dirangkai tanpa adapter / penyatuan tipe |
| **B2** | 🔴 | [chat_graph.py:63-84](../src/futechi_graphrag/pipelines/orchestration/chat_graph.py#L63-L84) + 4 file di `tests/unit/chat/` | `GraphContext` dipakai tanpa import di `chat_graph.py`; 4 file test tidak punya import sama sekali | 4 test gagal; `apply_retrieval_scope` akan `NameError` saat runtime |
| **B3** | 🔴 | [reasoner.py:49](../src/futechi_graphrag/pipelines/module_c_reasoning/reasoner.py#L49) vs [dto.py:31](../src/futechi_graphrag/pipelines/module_c_reasoning/dto.py#L31) | `build_diagnostic_prompt` membaca `case_context.zone_id`, sedangkan `CaseContextInput` hanya punya `blok_id` (terkait K16) | `reason()` selalu `AttributeError`; tidak tertangkap karena Modul C tanpa test |
| **B4** | 🟡 | [boundary_check.py:30-40](../src/futechi_graphrag/pipelines/module_b_graph_retrieval/boundary_check.py#L30-L40) | Retry memetakan input yang **sudah kanonik** ke kanonik lagi, sehingga parameter query sama persis. Istilah non-kanonik tidak pernah sampai ke sini karena ditolak `DiseaseRepository` | Retry 1× tidak pernah menghasilkan hasil berbeda. Menurut desain, retry seharusnya mengulang canonical mapping atas **label mentah** (`unmapped_features`) |
| **B5** | 🟡 | [case_store.py:47,86](../src/futechi_graphrag/infrastructure/persistence/case_store.py#L86), [state.py:29](../src/futechi_graphrag/pipelines/orchestration/state.py#L29) | CaseStore membandingkan status huruf kecil (`confirmed_sick`, nilai enum), sementara default `ChatState` & test memakai huruf besar (`CONFIRMED_SICK`); status disimpan sebagai string, bukan `CaseStatus` | Case yang disimpan dengan huruf besar tidak muncul di riwayat kandang; test `>= 1` masih lulus karena satu entri huruf kecil |
| **B6** | 🟡 | [case.py:68](../src/futechi_graphrag/domain/entities/case.py#L68) | Field dataclass bernama `recomended_checks`, tapi `attach_reasoning_result` mengisi `recommended_checks` | Field resmi selalu kosong; serialisasi (`asdict`) kehilangan checks |
| **B7** | 🟡 | [cage.py:35](../src/futechi_graphrag/domain/entities/cage.py#L35) vs [safety_net_policy.py:8](../src/futechi_graphrag/domain/policies/safety_net_policy.py#L8) | Default threshold 4 di `Cage`, 3 di policy (desain: ≥3) | Perilaku bergantung jalur mana yang dipanggil |
| **B8** | 🟡 | [frame_aggregator.py:16-27](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/frame_aggregator.py#L16-L27) | Agregasi mengambil confidence **tertinggi**, bukan majority vote / rata-rata | Fitur yang muncul di 1 dari 3 frame tetap lolos → false positive fitur naik |
| **B9** | 🟡 | [sensor_normalizer.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/sensor_normalizer.py) vs [canonical_terms.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/dictionaries/canonical_terms.yaml) | Normalizer bisa menghasilkan `temperature_attention` & `ammonia_attention`, tapi kanonik hanya `humidity_attention` | `build_params`/`DiseaseRepository` raise `ValueError` saat suhu >30°C atau amonia >20ppm |
| **B10** | 🟡 | [checkpointer.py:13](../src/futechi_graphrag/infrastructure/checkpointer.py#L13), [chat_graph.py:24,51](../src/futechi_graphrag/pipelines/orchestration/chat_graph.py#L24) | Checkpointer & CaseStore dibuat baru saat default | Riwayat chat & status case tidak persisten antar-build |
| **B11** | 🟡 | [fallback_template.py](../src/futechi_graphrag/pipelines/module_c_reasoning/fallback_template.py) | `recommended_checks` kosong | Tidak sesuai desain "fallback actionable" (`general_visual_check`, `monitor_24h`) |
| **B12** | 🟡 | Seed KG | Tidak ada property `notifiable` | `build_notifiable_notice()` selalu `None` |
| B13 | ⚪ Minor | [prompt_constraints.py](../src/futechi_graphrag/pipelines/module_c_reasoning/prompt_constraints.py) | Perubahan belum di-commit: menghapus aturan chat (#9–#11) yang sebelumnya **terduplikasi** ke `DIAGNOSTIC_SYSTEM_PROMPT` | Perubahannya benar; perlu di-commit |
| B14 | ⚪ Minor | `case_store.py`, test chat | `datetime.utcnow()` deprecated | Warning; sebaiknya pakai waktu timezone-aware |

---

## 6. Cakupan Test

| File test | Jumlah | Hasil |
|---|---:|---|
| `tests/unit/domain/test_cage.py` | 10 | ✅ |
| `tests/unit/domain/test_case_state_machine.py` | 9 | ✅ |
| `tests/unit/domain/test_confirmation.py` | 3 | ✅ |
| `tests/unit/domain/test_policies.py` | 8 | ✅ |
| `tests/unit/domain/test_severity.py` | 7 | ✅ |
| `tests/unit/scripts/test_bootstrap_neo4j.py` | 9 | ✅ |
| `tests/unit/test_module_a_semantic_mapping.py` | 7 | ✅ |
| `tests/unit/test_module_b_graph_retrieval.py` | 5 | ✅ |
| `tests/unit/chat/test_chat_graph_sync.py` | 5 | ✅ |
| `tests/unit/chat/test_confirmed_not_sick_return_empty.py` | 1 | ❌ NameError |
| `tests/unit/chat/test_confirmed_sick_filters_graph_context_to_confirmed_disease.py` | 1 | ❌ NameError |
| `tests/unit/chat/test_empty_graph_stays_empty.py` | 1 | ❌ NameError |
| `tests/unit/chat/test_pending_confirmation_keeps_multi_candidate_result.py` | 1 | ❌ NameError |
| **Total** | **67** | **63 ✅ / 4 ❌** |

Belum ada test untuk: Modul C (`reasoner`, `deterministic_builders`, `severity_selector`, `fallback_template`, `prompt_constraints`), `diagnostic_graph`, `CaseStore` (terpisah dari chat), integration Neo4j, dan end-to-end.

---

## 7. Urutan Kerja Berikutnya

Tanpa menunggu keputusan desain:

1. [ ] **Perbaiki B2** (import) → suite test hijau lagi
2. [ ] **Putuskan & satukan `GraphContext` (B1)**. Opsi: (a) `DiseaseRepository` langsung mengembalikan `neo4j.dto.GraphContext` via `map_record_to_candidate` dan hapus versi domain; (b) sebaliknya. Saran: (a), karena Modul C, state, chat sudah memakai versi dto
3. [ ] Perbaiki B3, B6, B7 + test Modul C dengan `FakeLLMClient`
4. [ ] Commit perubahan `prompt_constraints.py` (B13)
5. [ ] Perbaiki B9 (samakan normalizer ↔ kanonik ↔ seed) dan B4 (retry atas label mentah)
6. [ ] Lengkapi `PipelineState` → rangkai `diagnostic_graph` dengan node wrapper + conditional edge + test jalur normal/manual review/fallback
7. [ ] Rangkai node `retrieve` & `respond` di `chat_graph`, inject CaseStore & checkpointer tunggal (B10)
8. [ ] Perluas seed KG: minimal 3–5 penyakit dengan fitur tumpang tindih, Symptom, `notifiable` (B12) — agar differential reasoning bisa diuji
9. [ ] Integration test Neo4j (docker-compose yang sudah ada)

Menunggu keputusan desain (lihat [alur_sistem_terpadu.md §0.2](alur_sistem_terpadu.md)):

| Pekerjaan | Menunggu |
|---|---|
| Client ekstraksi GLM-5.3-Flash + format panggilan (per crop / multi-image) | K12, K13 |
| LLM client reasoning & konfigurasi di `settings.py` | K13 |
| Pisah N2 mapping jadi node sendiri vs gabung N1 | K6 |
| N3 lingkungan opsional & sumber data | K10 |
| N6 deterministik vs generatif | K7 |
| Bentuk `overall_uncertainty` (level kategorikal) | K9 |
| Two-stage reveal di output & API | K8 |
| Agregasi majority vs rata-rata (B8) | K12 |
| Nama `blok_id` / `zone_id` (B3) | K16 |
| Perilaku eskalasi saat ambigu | K11 |

Belum dimulai (setelah graph jalan): application layer (`ingest_detection`, `process_case_pipeline`, `confirm_case`, `mark_recovered`, `chat_case_context`), exclusion/feedback/audit store DB-backed, API FastAPI, scheduler sesi deteksi & TTL job.

---

## 8. Log Pembaruan

| Tanggal | Commit | Perubahan status |
|---|---|---|
| 2026-09-14 | `bbd5fd6` (+ uncommitted) | Audit awal: 63/67 test lulus; diagnostic graph skeleton; chat graph parsial; 12 temuan bug utama (B1–B12) |
