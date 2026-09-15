# Track Implementasi — GraphRAG & LangGraph

> Acuan desain: [alur_sistem_terpadu.md](alur_sistem_terpadu.md) (Phase 4 diagnostic graph, Phase 5.3 chat graph).
> Cakupan dokumen ini: **sisi server** (GraphRAG + orkestrasi LangGraph + domain & persistence pendukungnya).
> Edge (FCOS-Lite, Pi) di luar cakupan.

## Snapshot

| | |
|---|---|
| Tanggal audit terakhir | 2026-09-15 |
| Branch / commit dasar | `langgraph` @ `5c36887` + perubahan belum di-commit (seed, Modul A/B/C, client LLM) |
| Cara verifikasi | `venv/Scripts/python.exe -m pytest`, `scripts/validate_seed_consistency.py` |
| Hasil test | **116 lulus, 0 gagal** |
| Neo4j live | Belum diuji — Docker tidak aktif; sintaks seed & template Cypher belum dijalankan di Neo4j sungguhan |
| LLM/MLLM live | Belum diuji — semua test memakai fake client |

### Legenda status
| Simbol | Arti |
|---|---|
| ✅ | Selesai, ada test, sesuai desain |
| 🟢 | Logika selesai & ada unit test, belum diuji live (Neo4j/LLM sungguhan) |
| 🟡 | Parsial: ada kode, tapi ada gap terhadap desain atau bug |
| 🔴 | Skeleton / placeholder, belum berfungsi |
| ⬜ | Belum ada sama sekali |
| ⏸️ | Menunggu keputusan `K#` di alur_sistem_terpadu.md |

---

## 1. Ringkasan per Komponen

| Komponen | Status | Catatan singkat |
|---|---|---|
| Domain: `Case`, `Cage`, state machine, policies, severity | 🟡 | Severity kini menerima onset kosong (multiplier 1.0). Typo field & threshold tidak konsisten masih ada (B6, B7) |
| Knowledge graph: ontologi YAML | ✅ | Ditambah `condition_type`, `data_status`, `observation_target`, catatan validasi/diagnostik, `clinical_note` |
| Knowledge graph: **seed data** | 🟢 | 17 penyakit/kondisi dari tabel literatur (`draft_literature`) + draft mitigasi & faktor lingkungan terpisah (`draft_general_knowledge`). Belum direview dokter hewan |
| Validator seed | ✅ | Cek skema (enum, wajib, pola id), referensi id, relasi inline, sinkron kosakata |
| Neo4j infra (driver, runner, repositories) | 🟢 | `DiseaseRepository` mengembalikan satu tipe `GraphContext`; tanpa integration test |
| Modul A — ekstraksi MLLM + semantic mapping | 🟢 | VLM terpisah dihapus; MLLM dengan kosakata tertutup, agregasi mayoritas, manual review bila tidak ada fitur |
| Modul B — graph retrieval | 🟢 | Tipe tunggal, parameter pengecualian penyakit, retry remap label mentah |
| Modul C — reasoning | 🟢 | Bug `zone_id` & evidence gejala diperbaiki; prompt memuat catatan validasi/diagnostik; fallback actionable |
| LLM client | 🟢 | `OpenAICompatibleLLMClient` (teks + multimodal + structured JSON + repair 1×), konfigurasi `LLM_*` |
| **Orkestrasi `diagnostic_graph`** | 🔴 | Masih 4 node lambda identitas — belum dirangkai ke fungsi Modul A/B/C |
| **Orkestrasi `chat_graph`** | 🟡 | `NameError` sudah diperbaiki; `retrieve`/`respond` masih placeholder |
| State LangGraph (`state.py`) | 🟡 | `PipelineState` baru sebagian field desain |
| Checkpointer | 🟡 | `InMemorySaver` baru dibuat tiap `build_chat_graph()` (B10) |
| CaseStore | 🟡 | In-memory; casing status tidak konsisten (B5) |
| Audit trail store | ⬜ | File ada tapi kosong |
| Exclusion store, feedback store | ⬜ | Belum ada |
| Application layer (use cases) | ⬜ | Belum ada folder `application/` |
| API (FastAPI), scheduler (sesi deteksi, TTL job) | ⬜ | Belum ada folder `interfaces/` |

---

## 2. Diagnostic Graph — Track per Node

Desain: [alur_sistem_terpadu.md §4.2](alur_sistem_terpadu.md). Implementasi graph: [diagnostic_graph.py](../src/futechi_graphrag/pipelines/orchestration/diagnostic_graph.py) — **semua node masih `lambda state: state`**. Logika modul di bawah sudah siap dipanggil sebagai node.

| Node desain | Fungsi modul | Terpasang di graph? | Status | Catatan |
|---|---|---|---|---|
| **N1 image_extraction** | [mllm_extractor.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/mllm_extractor.py) `extract_frame_features` | ❌ | 🟢 ⏸️K12 | 1 panggilan MLLM per crop (opsi A di K12). Kosakata dari `canonical_terms.yaml` dengan target `bird` + `feces_litter`. `capture_quality=low` membuat prompt konservatif |
| **N2 semantic_mapping** | [canonical_mapper.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/canonical_mapper.py) → [frame_aggregator.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/frame_aggregator.py) → [confidence_filter.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/confidence_filter.py) → [mapping_validator.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/mapping_validator.py), dirangkai di [pipeline.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/pipeline.py) | ❌ | 🟢 ⏸️K6 | Mapping per frame **sebelum** agregasi (sinonim berbeda antar frame dihitung sama). Label harus muncul di >50% frame valid |
| **N3 environment_fusion** | [sensor_normalizer.py](../src/futechi_graphrag/pipelines/module_a_semantic_mapping/sensor_normalizer.py) | ❌ | 🟢 ⏸️K10 | Lingkungan opsional (`raw_environment=None` aman). Ketiga kondisi sensor kini ada di kosakata |
| Cond: fitur kosong / unmapped >50% → FB | `validate_mapping()` + cek frame valid | ❌ | 🟢 | Manual review jika: tidak ada frame valid, tidak ada fitur canonical, atau unmapped dominan |
| **N4 graph_retrieval** | [query_params_builder.py](../src/futechi_graphrag/pipelines/module_b_graph_retrieval/query_params_builder.py), [retriever.py](../src/futechi_graphrag/pipelines/module_b_graph_retrieval/retriever.py), [disease_repository.py](../src/futechi_graphrag/infrastructure/neo4j/repositories/disease_repository.py), [retrieve_disease_context.cypher](../src/futechi_graphrag/pipelines/knowledge_graph/cypher/templates/retrieve_disease_context.cypher) | ❌ | 🟢 | Output `GraphContext(candidates=…)`. `$excluded_disease_ids` tersedia |
| Cond: graph kosong → retry 1× → FB | [boundary_check.py](../src/futechi_graphrag/pipelines/module_b_graph_retrieval/boundary_check.py) `retry_with_synonym_remap` | ❌ | 🟢 | Remap `unmapped_visuals` dengan fuzzy (cutoff 0.85); query ulang hanya jika ada fitur baru |
| **N5 differential_reasoning** | [reasoner.py](../src/futechi_graphrag/pipelines/module_c_reasoning/reasoner.py) `reason()` | ❌ | 🟢 ⏸️K9 | `overall_uncertainty` masih teks bebas (belum level kategorikal) |
| **N6 recommendation_builder** | [deterministic_builders.py](../src/futechi_graphrag/pipelines/module_c_reasoning/deterministic_builders.py), [severity_selector.py](../src/futechi_graphrag/pipelines/module_c_reasoning/severity_selector.py) | ❌ (masih di dalam `reason()`) | 🟢 ⏸️K7 | Evidence hanya fitur & lingkungan yang cocok |
| **FB fallback_template** | [fallback_template.py](../src/futechi_graphrag/pipelines/module_c_reasoning/fallback_template.py) | node ada, **tanpa edge masuk** | 🟢 | `general_visual_check` + `monitor_24h` |
| **N7 persist_case** | `Case.attach_reasoning_result` / `mark_insufficient_data` + `transition()` | ❌ | ⬜ | Butuh use case + CaseStore berbasis entitas `Case` + notifikasi |

### Checklist diagnostic graph
- [x] Satukan tipe `GraphContext` (B1)
- [x] Client MLLM/LLM untuk N1 & N5
- [ ] Lengkapi `PipelineState` sesuai [§4.1](alur_sistem_terpadu.md) (`cage_id`, `blok_id`, `crops`, `capture_quality`, `unmapped_visuals`, `retrieval_retry_count`, `requires_manual_review`, dst.)
- [ ] Wrapper node N1–N7 + FB yang memanggil fungsi modul
- [ ] Conditional edge: setelah N2/N3 (manual review), setelah N4 (empty → retry → FB)
- [ ] Dependency injection (MLLM/LLM client, repository) lewat factory `build_diagnostic_graph(deps)`
- [ ] Compile graph sekali, jangan di tiap `run_diagnostic_graph()`
- [ ] Test graph end-to-end dengan fake client & fake repository: jalur normal, manual review, empty→retry→fallback

---

## 3. Chat Graph — Track per Node

Desain: [alur_sistem_terpadu.md §5.3](alur_sistem_terpadu.md). Implementasi: [chat_graph.py](../src/futechi_graphrag/pipelines/orchestration/chat_graph.py).

| Node | Status | Keterangan |
|---|---|---|
| `sync_case_state` | 🟡 | Berfungsi & teruji. Default `case_store=None` membuat `CaseStore()` baru yang kosong |
| `load_cage_history` | 🟡 | Berfungsi & teruji. Terkena B5 |
| `retrieve` | 🔴 | `apply_retrieval_scope` sudah bisa dipakai (B2 diperbaiki) tapi node masih placeholder; belum ada retrieval Neo4j per giliran |
| `respond` | 🔴 | `reason_chat_turn()` siap & teruji, belum dipanggil dari graph |
| Checkpointer (`thread_id = case_id`) | 🟡 | `InMemorySaver` baru tiap build (B10) |

### Checklist chat graph
- [x] Import `GraphContext` di `chat_graph.py` + 4 file test (B2)
- [ ] Node `retrieve`: fitur case dari CaseStore → `build_params` → `DiseaseRepository` → `apply_retrieval_scope`
- [ ] Node `respond`: bentuk `cage_history_summary`, panggil `reason_chat_turn`, append `ChatMessage`
- [ ] Samakan tipe `messages` (`ChatMessage` di state vs dict di test)
- [ ] Inject `CaseStore`, checkpointer, dan LLM client tunggal dari luar

---

## 4. Lapisan Pendukung

### 4.1 Knowledge graph
| Item | Status | Catatan |
|---|---|---|
| [node_definitions.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/ontology/node_definitions.yaml), [relationship_definitions.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/ontology/relationship_definitions.yaml) | ✅ | Aturan pengisian `specificity` terdokumentasi di relationship_definitions |
| [001_seed_ontology.cypher](../src/futechi_graphrag/pipelines/knowledge_graph/cypher/seeds/001_seed_ontology.cypher) | 🟢 | Dari tabel literatur: 17 Disease, 41 VisualFeature, 8 Symptom, 8 EnvironmentalCondition, 16 InspectionAction, 67 HAS_VISUAL_FEATURE, 15 HAS_SYMPTOM, 3 ASSOCIATED_WITH_ENVIRONMENT, 49 REQUIRES_INSPECTION |
| [002_seed_draft_general_knowledge.cypher](../src/futechi_graphrag/pipelines/knowledge_graph/cypher/seeds/002_seed_draft_general_knowledge.cypher) | 🟡 | **Di luar tabel sumber**: 9 MitigationAction, 44 MITIGATED_BY, 8 ASSOCIATED_WITH_ENVIRONMENT. Perlu review sebelum dipakai |
| MedicalTreatment | ⬜ | Sengaja kosong — tabel tidak memuat obat/dosis. Data lama (Amoxicillin untuk ND, dosis karangan) dihapus |
| [canonical_terms.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/dictionaries/canonical_terms.yaml) / [synonym_dictionary.yaml](../src/futechi_graphrag/pipelines/knowledge_graph/dictionaries/synonym_dictionary.yaml) | ✅ | Kosakata + deskripsi untuk prompt MLLM; sinonim ID/EN; test memastikan tidak ada alias ambigu |
| Bootstrap & validasi seed (`scripts/`) | ✅ | 16 test lulus |
| Validasi isi KG oleh pakar vet | ⬜ | Semua data berstatus draft |

### 4.2 Domain
| Item | Status | Catatan |
|---|---|---|
| `Case` + state machine | 🟡 | Typo `recomended_checks` (B6); merge belum memicu reasoning ulang |
| `Cage` | 🟡 | Default safety-net 4 ≠ policy 3 (B7) |
| Policies cooldown/safety-net/TTL | 🟡 | Cooldown default 4 siklus vs desain "misal 3" |
| Severity | ✅ | Onset kosong → multiplier 1.0 (8 test) |

### 4.3 Infrastruktur
| Item | Status | Catatan |
|---|---|---|
| Neo4j driver/runner/repository | 🟢 | Belum ada integration test |
| [llm/client.py](../src/futechi_graphrag/infrastructure/llm/client.py) | 🟢 | OpenAI-compatible; endpoint diarahkan lewat `LLM_BASE_URL` (OpenCode/Z.ai/vLLM). 11 test dengan fake SDK |
| [config/settings.py](../src/futechi_graphrag/config/settings.py) | ✅ | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `MLLM_MODEL`, suhu, max token, timeout, JSON mode |
| [checkpointer.py](../src/futechi_graphrag/infrastructure/checkpointer.py) | 🟡 | In-memory |
| [case_store.py](../src/futechi_graphrag/infrastructure/persistence/case_store.py) | 🟡 | In-memory dict, bukan entitas `Case` |
| [audit_trail_store.py](../src/futechi_graphrag/infrastructure/persistence/audit_trail_store.py) | ⬜ | Kosong |

---

## 5. Temuan Bug & Blocker

| # | Status | Lokasi | Masalah | Penyelesaian / sisa |
|---|---|---|---|---|
| B1 | ✅ Selesai | `domain/value_objects/graph_context.py` vs `neo4j/dto.py` | Dua kelas `GraphContext` | Versi domain dihapus; repository memakai `map_record_to_candidate` |
| B2 | ✅ Selesai | `chat_graph.py`, 4 test chat | `NameError` | Import ditambahkan |
| B3 | ✅ Selesai | `reasoner.py` | `case_context.zone_id` | Pakai `blok_id` (penamaan final tetap K16) |
| B4 | ✅ Selesai | `boundary_check.py` | Retry mengirim query identik | Remap label unmapped (fuzzy), skip query jika tidak ada fitur baru |
| **B5** | 🟡 Terbuka | [case_store.py:47,86](../src/futechi_graphrag/infrastructure/persistence/case_store.py#L86), [state.py:29](../src/futechi_graphrag/pipelines/orchestration/state.py#L29) | Casing status tidak konsisten | Belum dikerjakan |
| **B6** | 🟡 Terbuka | [case.py:68](../src/futechi_graphrag/domain/entities/case.py#L68) | Field `recomended_checks` typo | Belum dikerjakan |
| **B7** | 🟡 Terbuka | [cage.py:35](../src/futechi_graphrag/domain/entities/cage.py#L35) vs [safety_net_policy.py:8](../src/futechi_graphrag/domain/policies/safety_net_policy.py#L8) | Threshold 4 vs 3 | Belum dikerjakan |
| B8 | ✅ Selesai | `frame_aggregator.py` | Agregasi pakai max | Mayoritas frame + rata-rata confidence |
| B9 | ✅ Selesai | `sensor_normalizer` vs kosakata | `temperature_attention`/`ammonia_attention` ditolak | Ketiga kondisi sensor ada di kosakata & seed |
| **B10** | 🟡 Terbuka | [checkpointer.py:13](../src/futechi_graphrag/infrastructure/checkpointer.py#L13), [chat_graph.py](../src/futechi_graphrag/pipelines/orchestration/chat_graph.py) | Checkpointer & CaseStore dibuat baru | Belum dikerjakan |
| B11 | ✅ Selesai | `fallback_template.py` | `recommended_checks` kosong | Dua pemeriksaan statis |
| B12 | ✅ Selesai | Seed KG | Tanpa `notifiable` | Wajib di skema; ND & HPAI `true` |
| B13 | ✅ Selesai | `prompt_constraints.py` | Aturan chat terduplikasi ke prompt diagnosis | Sudah di-commit (`5c36887`) |
| B14 | ⚪ Terbuka | `case_store.py`, test chat | `datetime.utcnow()` deprecated | Minor |
| B15 | ✅ Selesai | `deterministic_builders.py` | `related_symptoms` (belum teramati) dimasukkan sebagai evidence | Evidence hanya fitur visual & lingkungan yang cocok; prompt memberi label "BELUM teramati" |

---

## 6. Cakupan Test

| File test | Jumlah | Hasil |
|---|---:|---|
| `tests/unit/domain/*` (cage, state machine, confirmation, policies, severity) | 38 | ✅ |
| `tests/unit/scripts/test_bootstrap_neo4j.py` | 9 | ✅ |
| `tests/unit/scripts/test_validate_seed_consistency.py` | 7 | ✅ |
| `tests/unit/test_ontology_repository.py` | 7 | ✅ |
| `tests/unit/test_module_a_semantic_mapping.py` | 16 | ✅ |
| `tests/unit/test_module_b_graph_retrieval.py` | 12 | ✅ |
| `tests/unit/test_module_c_reasoning.py` | 7 | ✅ |
| `tests/unit/test_llm_client.py` | 11 | ✅ |
| `tests/unit/chat/*` | 9 | ✅ |
| **Total** | **116** | **116 ✅** |

Belum ada test untuk: `diagnostic_graph`, `CaseStore` terpisah, integration Neo4j (seed + template), panggilan LLM/MLLM sungguhan, end-to-end.

---

## 7. Urutan Kerja Berikutnya

Tanpa menunggu keputusan desain:

1. [ ] **Reset & bootstrap Neo4j** dengan seed baru, lalu jalankan template retrieval secara manual. Seed lama `seeds/001_seed_ontology.cypher` sudah tercatat di `_SchemaMigration` sehingga tidak dijalankan ulang otomatis
2. [ ] Uji live client: satu panggilan teks & satu panggilan multimodal ke endpoint yang dipilih (cek dukungan `response_format` dan input gambar)
3. [ ] Integration test Neo4j (docker-compose yang sudah ada)
4. [ ] Lengkapi `PipelineState` → rangkai `diagnostic_graph` + conditional edge + test jalur
5. [ ] Rangkai node `retrieve` & `respond` di `chat_graph`, inject dependency tunggal (B10)
6. [ ] Perbaiki B5, B6, B7

Menunggu keputusan:

| Pekerjaan | Menunggu |
|---|---|
| Review isi seed oleh dokter hewan (specificity, base_severity, notifiable) | Pakar vet |
| Pakai atau buang draft `002` (mitigasi & faktor lingkungan di luar tabel) | Anda / pakar vet |
| Sumber data obat & dosis (MedicalTreatment) | Pakar vet / label obat terdaftar |
| `notifiable` untuk AI H9 (saat ini `false`) | Regulasi yang diacu |
| Sumber citra untuk fitur `egg`, `feed`, `flock` (crop edge hanya `bird`/`feces_litter`) | Desain edge |
| Jalur input faktor manajemen (`overcrowding`, `wet_litter`, dll.) — belum ada pengisinya | Desain aplikasi |
| 1 panggilan per crop vs multi-image | K12 |
| Pisah N2 mapping jadi node sendiri vs gabung N1 | K6 |
| N6 deterministik vs generatif | K7 |
| Bentuk `overall_uncertainty` (level kategorikal) | K9 |
| Nama `blok_id` / `zone_id` | K16 |

---

## 8. Log Pembaruan

| Tanggal | Commit | Perubahan status |
|---|---|---|
| 2026-09-14 | `bbd5fd6` (+ uncommitted) | Audit awal: 63/67 test lulus; diagnostic graph skeleton; chat graph parsial; 14 temuan (B1–B14) |
| 2026-09-15 | `5c36887` (+ uncommitted) | Seed katalog 17 penyakit/kondisi dari tabel literatur + draft 002; validator skema; Modul A VLM → MLLM kosakata tertutup; Modul B tipe tunggal & retry remap; Modul C client OpenAI-compatible + perbaikan evidence/prompt/severity/fallback. B1–B4, B8, B9, B11, B12, B15 selesai. 116/116 test lulus |
