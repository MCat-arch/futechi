# Panduan Implementasi: Isi File & Urutan Pengerjaan
## Poultry GraphRAG-Vet

Prinsip urutan: **bangun dari lapisan yang tidak punya dependensi ke luar dulu** (domain logic murni), baru naik ke lapisan yang bergantung padanya. Ini juga memudahkan unit testing sejak awal — `domain/` bisa 100% diuji tanpa Neo4j/LLM/API menyala sama sekali.

---

## TAHAP 1 — Fondasi Proyek

### `pyproject.toml`
Daftar dependency inti yang perlu masuk: `pydantic`/`pydantic-settings`, `neo4j` (driver resmi), `langgraph`, `langchain-core` (untuk message types), client LLM (mis. `openai` atau `anthropic`), `fastapi` + `uvicorn` (kalau pakai FastAPI untuk `interfaces/api`), `pytest`, `ruff`, `mypy`. Definisikan entrypoint script (mis. `poultry-api = "poultry_graphrag.interfaces.api.app:main"`).

### `.env.example`
Isi kunci minimal: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `LLM_API_KEY`, `LLM_MODEL_NAME`, `VLM_API_KEY`, `CONFIDENCE_THRESHOLD=0.6`, `COOLDOWN_CYCLES=3`, `SAFETY_NET_ANOMALY_COUNT=3`, `CASE_TTL_HOURS=24`. Menaruh threshold sebagai env (bukan hardcode) penting karena ini yang akan Anda kalibrasi ulang setelah pilot.

### `README.md`
Cukup kerangka dulu: diagram arsitektur (boleh tempel ASCII diagram dari dokumen flow sebelumnya), cara run lokal, cara migrasi Neo4j, link ke dokumen flow & timeline yang sudah dibuat. Lengkapi isinya progresif seiring development, jangan tunda sampai akhir.

### `.gitignore`
Standar Python + tambahan: `.env`, `*.db` (kalau checkpointer LangGraph pakai SQLite lokal), folder cache image/frame sementara.

### `ops/docker/docker-compose.neo4j.yml`
Service Neo4j dengan APOC plugin diaktifkan (dibutuhkan untuk fuzzy matching/string functions di Cypher nanti). Expose port bolt & browser, mount volume data agar tidak hilang saat restart.

**✅ Checkpoint Tahap 1:** `docker compose up` bisa jalan, Neo4j browser bisa diakses, `pyproject.toml` bisa di-install (`pip install -e .`).

---

## TAHAP 2 — Domain Layer (Logika Murni, Tanpa Dependensi Eksternal)

Ini paling penting dikerjakan duluan karena **tidak butuh Neo4j/LLM/API menyala** untuk ditest — cocok untuk membangun kepercayaan diri di awal proyek solo.

### `domain/value_objects/enums.py`
Semua enum status:
```python
class CaseStatus(str, Enum):
    DETECTED = "detected"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED_SICK = "confirmed_sick"
    CONFIRMED_NOT_SICK = "confirmed_not_sick"
    CONFIRMED_HEALTHY = "confirmed_healthy"
    UNCONFIRMED_ESCALATED = "unconfirmed_escalated"

class CageStatus(str, Enum):
    ELIGIBLE = "eligible"
    EXCLUDED_SICK = "excluded_sick"
    COOLDOWN = "cooldown"

class ConfirmationType(str, Enum):
    SICK = "sakit"
    NOT_SICK = "tidak_sakit"
    HEALTHY = "sehat"

class DetectionSession(str, Enum):
    MORNING = "morning"
    EVENING = "evening"
```

### `domain/value_objects/severity.py`
Fungsi murni, tidak ada I/O:
```python
def compute_severity(base_severity: str, onset_stage: str) -> SeverityResult:
    # multiplier: early=1.0, middle=1.5, late=2.0
    # return level (low/medium/high/critical) + breakdown perhitungan
```
Sertakan juga tabel mapping severity level agar mudah dikalibrasi ulang tanpa ubah logic.

### `domain/entities/case.py`
Model inti (pakai `pydantic.BaseModel` atau `dataclass`, bukan ORM — domain entity harus bebas dari infra):
```python
class Case:
    case_id: str
    cage_id: str
    status: CaseStatus
    alert_count: int
    detection_sessions: list[DetectionSession]  # bisa >1 jika accumulate
    visual_features: list[VisualFeatureObservation]
    environment_snapshot: EnvironmentSnapshot
    related_conditions: list[RelatedCondition] | None
    severity: SeverityResult | None
    created_at: datetime
    last_detected_at: datetime
    resolved_at: datetime | None
```
Method domain penting yang harus ada di sini (bukan di use case!): `merge_new_detection(evidence)`, `is_ttl_expired(ttl_hours)`, `mark_resolved(confirmation)`.

### `domain/entities/cage.py`
```python
class Cage:
    cage_id: str
    status: CageStatus
    cooldown_reason: str | None
    cooldown_cycles_remaining: int
    anomaly_count_during_cooldown: int  # untuk safety-net
    active_case_id: str | None
```
Method: `should_skip_detection() -> bool`, `register_anomaly_during_cooldown()`, `needs_safety_net_escalation() -> bool` (cek jika count ≥3).

### `domain/entities/confirmation.py`
```python
class Confirmation:
    case_id: str
    type: ConfirmationType
    confirmed_by: str  # user/petugas id
    confirmed_condition: str | None  # diisi jika type=SICK
    confirmed_at: datetime
```

### `domain/state_machine/case_state_machine.py`
Ini jantung logika bisnis. Implementasikan sebagai fungsi transisi eksplisit, bukan magic string:
```python
def transition(case: Case, event: StateEvent) -> Case:
    # guard: skip sesi ke-2 jika sudah resolved hari yang sama
    # guard: TTL check sebelum accept event apapun
    # transisi valid: DETECTED -> PENDING_CONFIRMATION
    #                 PENDING_CONFIRMATION -> CONFIRMED_* (dari tombol user)
    #                 PENDING_CONFIRMATION -> UNCONFIRMED_ESCALATED (dari TTL job)
    # raise InvalidTransitionError jika transisi tidak valid
```
Tulis ini sebagai **pure function** (input Case + event, output Case baru) — jangan simpan state di sini, itu tugas `infrastructure/persistence`.

### `domain/policies/cooldown_policy.py`, `safety_net_policy.py`, `ttl_policy.py`
Masing-masing berisi 1 fungsi/rule kecil, murni kalkulasi:
```python
# cooldown_policy.py
def calculate_cooldown_end(cycles: int, current_cycle: int) -> bool  # eligible_again?

# safety_net_policy.py
def should_force_escalate(anomaly_count: int, threshold: int = 3) -> bool

# ttl_policy.py
def is_expired(detected_at: datetime, ttl_hours: int, now: datetime) -> bool
```

**✅ Checkpoint Tahap 2:** Tulis `tests/unit/domain/` paralel dengan tiap file di atas. Target: 100% domain logic tercover unit test SEBELUM lanjut ke Tahap 3. Ini tahap termurah untuk dapat test coverage tinggi, jangan dilewati.

---

## TAHAP 3 — Knowledge Graph (Data & Schema, Bukan Kode Aplikasi)

Ini bisa dikerjakan **paralel** dengan Tahap 2 kalau Anda ingin selang-seling (riset konten penyakit itu melelahkan secara mental, beda jenis kerja dari coding — baik untuk variasi solo dev), tapi harus **selesai sebelum Tahap 5** (Modul B butuh data ini untuk ditest).

### `knowledge_graph/ontology/node_definitions.yaml`
Definisikan tiap node type + properti wajib/opsional — ini dokumentasi hidup, dipakai juga oleh `ontology_repository.py` untuk validasi:
```yaml
Disease:
  properties:
    id: {type: string, required: true}
    name: {type: string, required: true}
    desc: {type: string, required: true}
    base_severity: {type: enum, values: [low, medium, high, critical]}
VisualFeature:
  properties:
    id: {type: string, required: true}
    name: {type: string, required: true}
# ... dst untuk Symptom, EnvironmentalCondition, InspectionAction, MitigationAction, MedicalTreatment
```

### `knowledge_graph/ontology/relationship_definitions.yaml`
```yaml
HAS_VISUAL_FEATURE:
  from: Disease
  to: VisualFeature
  properties:
    specificity: {type: enum, values: [high, medium, low]}
    onset_stage: {type: enum, values: [early, middle, late]}
    mechanism: {type: string}
TREATED_WITH:
  from: Disease
  to: MedicalTreatment
  properties:
    dosage: {type: string}
    withdrawal_period: {type: string, required: true}  # wajib, jangan sampai kosong
# ... dst
```

### `knowledge_graph/cypher/constraints/001_constraints.cypher`
```cypher
CREATE CONSTRAINT disease_id_unique IF NOT EXISTS FOR (d:Disease) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT visualfeature_id_unique IF NOT EXISTS FOR (vf:VisualFeature) REQUIRE vf.id IS UNIQUE;
-- ulangi untuk semua node type
```

### `knowledge_graph/cypher/indexes/001_indexes.cypher`
```cypher
CREATE INDEX visualfeature_name_idx IF NOT EXISTS FOR (vf:VisualFeature) ON (vf.name);
CREATE INDEX environmentalcondition_name_idx IF NOT EXISTS FOR (ec:EnvironmentalCondition) ON (ec.name);
-- index di kolom yang dipakai WHERE di query retrieval
```

### `knowledge_graph/cypher/templates/retrieve_disease_context.cypher`
Persis query final yang sudah kita desain (full query, tanpa gating TREATED_WITH):
```cypher
MATCH (d:Disease)-[hf:HAS_VISUAL_FEATURE]->(vf:VisualFeature)
WHERE vf.name IN $visual_features
OPTIONAL MATCH (d)-[hs:HAS_SYMPTOM]->(s:Symptom)
OPTIONAL MATCH (d)-[ae:ASSOCIATED_WITH_ENVIRONMENT]->(ec:EnvironmentalCondition)
  WHERE ec.name IN $environment_conditions
OPTIONAL MATCH (d)-[:REQUIRES_INSPECTION]->(ia:InspectionAction)
OPTIONAL MATCH (d)-[:MITIGATED_BY]->(ma:MitigationAction)
OPTIONAL MATCH (d)-[:TREATED_WITH]->(mt:MedicalTreatment)
RETURN d, hf, vf, hs, s, ae, ec, ia, ma, mt
LIMIT 20
```
Simpan sebagai file `.cypher` mentah (bukan string di Python) supaya bisa direview/diedit tanpa sentuh kode — penting untuk audit oleh vet nanti.

### `knowledge_graph/cypher/seeds/001_seed_ontology.cypher`
Data 15–30 penyakit prioritas (sesuai batasan realistis di timeline). Tulis manual dulu untuk 3–5 penyakit sebagai contoh pola, baru scale up.

### `knowledge_graph/dictionaries/canonical_terms.yaml` & `synonym_dictionary.yaml`
```yaml
# canonical_terms.yaml — daftar istilah resmi yang diakui ontologi
visual_features:
  - lowered_head_posture
  - irregular_feather_appearance
```
```yaml
# synonym_dictionary.yaml — mapping variasi istilah ke canonical
lowered_head_posture:
  - "head down"
  - "drooping head"
  - "lowered neck"
```

**✅ Checkpoint Tahap 3:** Jalankan `scripts/bootstrap_neo4j.ps1` (lihat Tahap 10), buka Neo4j browser, pastikan minimal 3–5 Disease dengan relasi lengkap bisa di-query manual dan hasilnya masuk akal.

---

## TAHAP 4 — Infrastructure: Akses Neo4j

### `infrastructure/neo4j/driver.py`
Singleton driver, baca config dari `config/settings.py`:
```python
def get_driver() -> Driver:
    # cache instance, reuse connection pool
```

### `infrastructure/neo4j/cypher_runner.py`
Util generik jalankan query + handle exception Neo4j (jadi satu tempat untuk log semua query yang jalan — berguna untuk audit trail nanti):
```python
def run_read_query(query: str, params: dict) -> list[Record]
def run_write_query(query: str, params: dict) -> None
```

### `infrastructure/neo4j/repositories/disease_repository.py`
```python
class DiseaseRepository:
    def retrieve_context(self, visual_features: list[str], environment_conditions: list[str]) -> GraphContext:
        # load query dari file .cypher (JANGAN hardcode string di sini)
        # jalankan via cypher_runner, mapping hasil raw ke domain object GraphContext
```

### `infrastructure/neo4j/repositories/ontology_repository.py`
```python
class OntologyRepository:
    def is_valid_visual_feature(self, name: str) -> bool
    def is_valid_environment_condition(self, name: str) -> bool
    # load allowlist dari canonical_terms.yaml, cache di memory
```

**✅ Checkpoint Tahap 4:** `tests/integration/` — test `DiseaseRepository.retrieve_context()` terhadap Neo4j nyata (pakai testcontainer atau instance dev), pastikan hasil match seed data Tahap 3.

---

## TAHAP 5 — Pipeline Modul B (Graph Retrieval)

Dikerjakan duluan sebelum A & C karena paling sedikit dependensi eksternal (cuma butuh Neo4j yang sudah siap dari Tahap 3–4) dan paling mudah divalidasi benar/salahnya (query result vs seed data yang Anda tahu isinya).

### `pipelines/module_b_graph_retrieval/query_params_builder.py`
```python
def build_params(visual_features: list[FeatureObservation], environment_conditions: list[str]) -> dict:
    # filter hanya nama yang sudah lolos threshold confidence (dari Modul A)
    # validasi via OntologyRepository sebelum masuk parameter
```

### `pipelines/module_b_graph_retrieval/retriever.py`
```python
def retrieve(params: dict, disease_repo: DiseaseRepository) -> GraphContext | None
```

### `pipelines/module_b_graph_retrieval/boundary_check.py`
```python
def is_context_empty(context: GraphContext | None) -> bool
def retry_with_fuzzy_expansion(params: dict, ...) -> GraphContext | None
    # sekali retry: cek ulang synonym_dictionary, perluas parameter, retrieve lagi
```

**✅ Checkpoint Tahap 5:** Test Modul B end-to-end dengan `examples/sample_payloads/` — pastikan payload yang match seed data menghasilkan context benar, payload acak menghasilkan `None` (trigger fallback).

---

## TAHAP 6 — Pipeline Modul A (VLM + Sensor)

### `pipelines/module_a_semantic_mapping/vlm_extractor.py`
```python
def extract_features(frames: list[ImageRef]) -> list[RawFeatureObservation]:
    # panggil infrastructure/llm/client.py (VLM call), per frame
```

### `pipelines/module_a_semantic_mapping/frame_aggregator.py`
```python
def aggregate(observations: list[RawFeatureObservation]) -> list[FeatureObservation]:
    # majority vote antar frame, rata-rata confidence
```

### `pipelines/module_a_semantic_mapping/confidence_filter.py` *(file baru yang disarankan sebelumnya)*
```python
def filter_by_threshold(observations: list[FeatureObservation], threshold: float = 0.6) -> list[FeatureObservation]
```

### `pipelines/module_a_semantic_mapping/canonical_mapper.py`
```python
def map_to_canonical(raw_term: str, ontology_repo: OntologyRepository) -> str | None:
    # cek exact match -> synonym dictionary -> fuzzy match -> None jika gagal
```

### `pipelines/module_a_semantic_mapping/sensor_normalizer.py`
```python
def normalize(raw_environment: RawEnvironment) -> list[str]:
    # threshold-based: temperature 30.5 -> "temperature_attention"
```

### `pipelines/module_a_semantic_mapping/mapping_validator.py`
```python
def check_unmapped_ratio(mapped: list, total_extracted: int) -> bool:
    # True jika unmapped > 50% -> trigger bypass ke manual review
```

**✅ Checkpoint Tahap 6:** Test dengan gambar sample nyata (ambil beberapa foto ayam, bukan cuma data sintetis) — VLM API sungguhan sudah harus terhubung di tahap ini.

---

## TAHAP 7 — Infrastructure: LLM Client & Pipeline Modul C

### `infrastructure/llm/client.py`
```python
class LLMClient:
    def generate(self, system_prompt: str, context: str, user_query: str) -> LLMRawResponse
    def generate_structured(self, ..., schema: type[BaseModel]) -> BaseModel  # pakai structured output/function calling
```

### `pipelines/module_c_reasoning/prompt_constraints.py`
Simpan hard constraint sebagai **template string terpisah** (bukan f-string tercampur logic), supaya mudah diiterasi tanpa sentuh kode:
```python
SYSTEM_PROMPT_TEMPLATE = """
Role: Anda adalah asisten screening kesehatan unggas.
Aturan:
1. Gunakan HANYA case data dan graph context yang diberikan.
...
"""
```

### `pipelines/module_c_reasoning/reasoner.py`
```python
def reason(case_context: CaseContext, graph_context: GraphContext, llm_client: LLMClient) -> ReasoningOutput:
    # assembly prompt, call llm_client.generate_structured()
    # parsing & validasi output schema (severity, related_conditions, medical_reference, dst)
```

### `pipelines/module_c_reasoning/fallback_template.py`
```python
def build_insufficient_data_response(case_id: str) -> ReasoningOutput:
    # response statis, TIDAK panggil LLM sama sekali
```

**✅ Checkpoint Tahap 7:** Ini tahap paling butuh iterasi (sesuai flag risiko di timeline) — uji dengan minimal 5–10 kombinasi kasus (single disease jelas, overlap gejala, graph kosong) sebelum lanjut.

---

## TAHAP 8 — Orchestration (LangGraph)

Sekarang seluruh "bahan" (Modul A, B, C) sudah teruji terpisah — tahap ini murni **wiring**, bukan menulis logic baru.

### `orchestration/state.py`
```python
class PipelineState(TypedDict):
    case_id: str
    raw_frames: list[ImageRef]
    raw_environment: RawEnvironment
    visual_features: list[FeatureObservation] | None
    environment_conditions: list[str] | None
    unmapped_ratio_exceeded: bool
    graph_context: GraphContext | None
    reasoning_output: ReasoningOutput | None
    status: Literal["processing", "insufficient_data", "manual_review", "done"]
```

### `orchestration/diagnostic_graph.py`
```python
graph = StateGraph(PipelineState)

graph.add_node("module_a", run_module_a)          # wrap pipelines/module_a/*
graph.add_node("module_b", run_module_b)          # wrap pipelines/module_b/*
graph.add_node("module_c", run_module_c)          # wrap pipelines/module_c/reasoner
graph.add_node("fallback", run_fallback)          # wrap pipelines/module_c/fallback_template

graph.add_conditional_edges(
    "module_a", check_unmapped_ratio,
    {"proceed": "module_b", "manual_review": END}
)
graph.add_conditional_edges(
    "module_b", check_boundary,
    {"has_context": "module_c", "empty": "fallback"}
)
graph.add_edge("module_c", END)
graph.add_edge("fallback", END)
graph.set_entry_point("module_a")

diagnostic_graph = graph.compile()
```

### `orchestration/chat_graph.py`
Graph terpisah untuk sesi chat lanjutan — **penting**: node retrieval (Modul B) tetap dipanggil ulang tiap invoke, bukan cuma mengandalkan message history:
```python
chat_graph = StateGraph(ChatState)
chat_graph.add_node("retrieve", run_module_b)   # selalu jalan tiap turn
chat_graph.add_node("respond", run_module_c_chat_variant)
chat_graph.add_edge("retrieve", "respond")
chat_graph.set_entry_point("retrieve")
compiled_chat_graph = chat_graph.compile(checkpointer=get_checkpointer())
```

### `orchestration/checkpointer.py`
```python
def get_checkpointer() -> BaseCheckpointSaver:
    # SqliteSaver untuk dev, upgrade ke PostgresSaver untuk produksi
    # thread_id = case_id, supaya histori chat terikat per case
```

**✅ Checkpoint Tahap 8:** Jalankan `diagnostic_graph.invoke()` dengan sample payload dari Tahap 5–6, pastikan hasil akhir identik dengan saat A/B/C dites terpisah — ini murni validasi wiring, bukan validasi logic baru.

---

## TAHAP 9 — Application Layer (Use Cases)

### `application/dto/intake_dto.py`, `response_dto.py`
Kontrak data masuk/keluar use case (beda dari API schema — DTO ini internal, API schema di Tahap 11 boleh identik atau beda tipis).

### `application/use_cases/ingest_detection.py`
```python
def ingest(payload: IntakeDto, cage_repo, case_repo) -> IngestResult:
    # cek cage.status via domain.entities.cage
    # cek ada case PENDING aktif -> merge (domain.entities.case.merge_new_detection)
    # atau buat case baru -> status DETECTED
    # simpan via case_store/exclusion_store
```

### `application/use_cases/process_case_pipeline.py`
```python
def process(case: Case) -> Case:
    result_state = diagnostic_graph.invoke(build_initial_state(case))
    # update case dengan reasoning_output, severity, status -> PENDING_CONFIRMATION
    # simpan via case_store
```

### `application/use_cases/confirm_case.py`
```python
def confirm(case_id: str, confirmation: Confirmation) -> Case:
    # panggil domain.state_machine.transition()
    # update cage (exclusion/cooldown) sesuai tipe konfirmasi
    # simpan ke feedback_store untuk evaluasi nanti
```

### `application/use_cases/mark_recovered.py`
Dua fungsi terpisah: `mark_recovered(cage_id)` dan `reset_monitoring(cage_id)` — jangan digabung satu fungsi meski mirip, karena semantiknya beda (recovery = penyakit selesai, reset = ayam diganti).

### `application/use_cases/chat_case_context.py`
```python
def send_chat_message(case_id: str, user_message: str) -> ChatResponse:
    config = {"configurable": {"thread_id": case_id}}
    result = compiled_chat_graph.invoke({"user_message": user_message, ...}, config)
```

**✅ Checkpoint Tahap 9:** Test use case level (bisa pakai in-memory fake repository dulu, belum perlu API/DB sungguhan) — pastikan orkestrasi antar domain + orchestration + persistence sudah benar secara logic.

---

## TAHAP 10 — Persistence Non-Graph & Scripts Migrasi

### `infrastructure/persistence/case_store.py`, `exclusion_store.py`, `feedback_store.py`
Pilih DB (SQLite untuk dev cepat, upgrade Postgres untuk produksi). Tiap store = repository pattern sederhana (CRUD + query spesifik seperti `find_active_case_by_cage(cage_id)`).

### `infrastructure/persistence/audit_trail_store.py` *(file baru yang disarankan sebelumnya)*
```python
class AuditTrailStore:
    def log_decision(self, case_id: str, subgraph_snapshot: dict, reasoning_output: dict, timestamp: datetime)
    def log_confirmation(self, case_id: str, confirmation: Confirmation)
```

### `scripts/bootstrap_neo4j.ps1`
Jalankan urutan: constraints → indexes → seeds, dengan pengecekan idempotent (aman dijalankan ulang).

### `scripts/run_migrations.py`
Kalau nanti ada perubahan schema Cypher susulan (mis. tambah node type baru), script ini apply file `.cypher` baru secara berurutan dengan tracking versi mana yang sudah jalan (semacam migration table sederhana).

### `scripts/replay_sample_case.py`
Ambil salah satu file dari `examples/sample_payloads/`, jalankan lewat seluruh pipeline (`ingest_detection` → `process_case_pipeline`), print hasil akhir ke terminal — ini alat paling sering Anda pakai untuk debug cepat tanpa perlu jalankan API server.

**✅ Checkpoint Tahap 10:** `python scripts/replay_sample_case.py examples/sample_payloads/case_intake_high_quality.json` menghasilkan output lengkap sampai `ReasoningOutput`, end-to-end tanpa API layer sama sekali.

---

## TAHAP 11 — Interfaces (API)

Sengaja paling akhir — API cuma "kulit" tipis di atas use case yang sudah teruji penuh di Tahap 9–10.

### `interfaces/api/schemas/detection_schema.py`, `case_schema.py`
Pydantic model untuk request/response HTTP (boleh mirroring DTO, tapi tetap file terpisah supaya API contract tidak ikut berubah kalau internal DTO berubah).

### `interfaces/api/routers/detection_router.py`
```python
@router.post("/detections")
def intake_detection(payload: DetectionSchema, use_case = Depends(get_ingest_use_case)):
    result = use_case.ingest(payload)
    # trigger process_case_pipeline (bisa langsung sync dulu, async/queue belakangan)
```

### `interfaces/api/routers/cases_router.py`
Endpoint list alert, detail case, dan `POST /cases/{id}/confirm`, `POST /cages/{id}/recover`, `POST /cages/{id}/reset`.

### `interfaces/api/routers/chat_router.py`
```python
@router.post("/cases/{case_id}/chat")
def chat(case_id: str, message: ChatMessageSchema, use_case = Depends(get_chat_use_case)):
```

### `interfaces/api/dependencies.py`
Wiring dependency injection: settings → driver → repository → use case. Ini titik penyatuan semua layer.

### `interfaces/api/app.py`
Bootstrap FastAPI, register semua router, startup event untuk cek koneksi Neo4j sehat.

### `interfaces/schedulers/detection_schedule.py`, `ttl_escalation_job.py`
Klarifikasi dari diskusi sebelumnya: kalau CV berjalan di edge device, file `detection_schedule.py` di sini fungsinya hanya jika server perlu **mengirim sinyal trigger** ke edge (server-orchestrated) — kalau edge sepenuhnya independen jadwal sendiri, file ini bisa **dihapus** dari repo backend. `ttl_escalation_job.py` tetap relevan di server (job harian cek case yang lewat TTL → escalate).

**✅ Checkpoint Tahap 11:** `examples/api_collection/` — jalankan seluruh koleksi request manual, pastikan alur intake → confirm → chat berjalan via HTTP sungguhan.

---

## TAHAP 12 — Testing Menyeluruh & Ops

### `tests/e2e/`
Skenario penuh: kirim HTTP request intake → cek status case → kirim confirm → cek status cage berubah → cek TTL job. Ini validasi ulang seluruh flow yang sudah didesain di dokumen flow sistem sebelumnya (accumulate alert, cooldown, safety-net, dsb) — jadikan tiap skenario di dokumen itu sebagai 1 test case e2e.

### `ops/monitoring/health_checks.md`
Checklist operasional minimum: endpoint `/health` cek Neo4j, cek LLM API reachable, cek disk space untuk image storage, cek job scheduler jalan.

**✅ Checkpoint Tahap 12 = Selesai Fase 12 di Timeline sebelumnya** ("Integrasi & End-to-End Testing") — lanjut ke Fase 13 (integrasi feedback vet) dan seterusnya sesuai timeline yang sudah dibuat.

---

## Ringkasan Urutan (untuk dicentang progresif)

| Tahap | Folder Utama | Bisa Ditest Tanpa |
|---|---|---|
| 1 | root config, ops/docker | Neo4j, LLM, API |
| 2 | domain/ | Neo4j, LLM, API |
| 3 | knowledge_graph/ | Kode aplikasi (murni data) |
| 4 | infrastructure/neo4j/ | LLM, API |
| 5 | pipelines/module_b/ | LLM, API |
| 6 | pipelines/module_a/ | Neo4j, API |
| 7 | infrastructure/llm/, pipelines/module_c/ | API |
| 8 | orchestration/ | API |
| 9 | application/ | API (pakai fake repo) |
| 10 | infrastructure/persistence/, scripts/ | API |
| 11 | interfaces/ | – (titik penyatuan semua) |
| 12 | tests/e2e/, ops/monitoring/ | – |

Setiap tahap punya "✅ Checkpoint" — **jangan lanjut ke tahap berikutnya sebelum checkpoint itu lolos**, ini mencegah Anda debug banyak layer sekaligus saat sesuatu error (risiko besar untuk solo dev yang bekerja lintas CV/VLM/graph/LLM).
