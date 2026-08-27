proposed structure

graphdb/
├─ pyproject.toml                     # dependency Python, tooling (pytest, ruff, mypy), entrypoint app
├─ .env.example                       # template env: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, OPENAI_API_KEY, dll
├─ README.md                          # overview arsitektur, cara run, cara migration, alur end-to-end
├─ .gitignore                         # ignore venv, cache, .env, artifacts

├─ src/
│  └─ poultry_graphrag/
│     ├─ __init__.py                  # package marker + versi app
│
│     ├─ config/
│     │  ├─ settings.py               # loader konfigurasi (pydantic settings), validasi env
│     │  └─ logging.py                # format logging, level, correlation/case id
│
│     ├─ domain/
│     │  ├─ entities/
│     │  │  ├─ case.py                # model inti case (status, alert_count, evidence, timestamps)
│     │  │  ├─ cage.py                # model cage + exclusion/cooldown state
│     │  │  └─ confirmation.py        # model konfirmasi user: sakit/tidak_sakit/sehat
│     │  ├─ value_objects/
│     │  │  ├─ enums.py               # enum status case/cage/session
│     │  │  └─ severity.py            # severity + onset multiplier rule
│     │  ├─ state_machine/
│     │  │  └─ case_state_machine.py  # transisi status + guard (TTL, merge evidence, skip sesi ke-2)
│     │  └─ policies/
│     │     ├─ cooldown_policy.py     # aturan cooldown N siklus
│     │     ├─ safety_net_policy.py   # eskalasi jika anomali berulang >=3
│     │     └─ ttl_policy.py          # rule unconfirmed -> escalated
│
│     ├─ application/
│     │  ├─ dto/
│     │  │  ├─ intake_dto.py          # payload dari edge
│     │  │  └─ response_dto.py        # response terstruktur ke UI
│     │  └─ use_cases/
│     │     ├─ ingest_detection.py    # intake + dedup/merge case
│     │     ├─ process_case_pipeline.py # orkestrasi Modul A -> B -> C -> fallback
│     │     ├─ confirm_case.py        # handle tombol konfirmasi user
│     │     ├─ mark_recovered.py      # tandai sembuh/reset monitoring cage
│     │     └─ chat_case_context.py   # chat follow-up dengan retrieval ulang graph
│
│     ├─ pipelines/
│     │  ├─ module_a_semantic_mapping/
│     │  │  ├─ vlm_extractor.py       # ekstraksi fitur visual multi-frame
│     │  │  ├─ frame_aggregator.py    # majority vote + confidence aggregation
│     │  │  ├─ canonical_mapper.py    # map istilah ke ontology canonical
│     │  │  ├─ sensor_normalizer.py   # raw sensor -> status semantik
│     │  │  └─ mapping_validator.py   # cek unmapped ratio >50% => manual review
│     │  ├─ module_b_graph_retrieval/
│     │  │  ├─ retriever.py           # eksekusi query template ke Neo4j
│     │  │  ├─ query_params_builder.py # susun parameter query
│     │  │  └─ boundary_check.py      # hasil kosong -> fallback path
│     │  └─ module_c_reasoning/
│     │     ├─ prompt_constraints.py  # hard constraints anti-hallucination
│     │     ├─ reasoner.py            # call LLM terkontrol + parsing output
│     │     └─ fallback_template.py   # response non-generatif insufficient_data
│
│     ├─ infrastructure/
│     │  ├─ neo4j/
│     │  │  ├─ driver.py              # singleton driver/session neo4j
│     │  │  ├─ cypher_runner.py       # util execute read/write transaction
│     │  │  └─ repositories/
│     │  │     ├─ disease_repository.py # akses Disease & relasi terkait
│     │  │     └─ ontology_repository.py # validasi entity allowlist
│     │  ├─ llm/
│     │  │  └─ client.py              # adapter provider LLM (OpenAI/dll)
│     │  └─ persistence/
│     │     ├─ case_store.py          # simpan case operasional (non-graph)
│     │     ├─ exclusion_store.py     # status exclusion/cooldown cage
│     │     └─ feedback_store.py      # simpan data feedback loop
│
│     ├─ interfaces/
│     │  ├─ api/
│     │  │  ├─ app.py                 # bootstrap API server
│     │  │  ├─ dependencies.py        # dependency injection (settings, driver, usecase)
│     │  │  ├─ routers/
│     │  │  │  ├─ detection_router.py # endpoint intake deteksi edge
│     │  │  │  ├─ cases_router.py     # list/detail case + konfirmasi
│     │  │  │  └─ chat_router.py      # endpoint chat case
│     │  │  └─ schemas/
│     │  │     ├─ detection_schema.py # request/response contract deteksi
│     │  │     └─ case_schema.py      # contract case detail, confirmation payload
│     │  └─ schedulers/
│     │     ├─ detection_schedule.py  # scheduler 2x/hari
│     │     └─ ttl_escalation_job.py  # job akhir hari untuk unconfirmed escalation
│
│     └─ knowledge_graph/
│        ├─ ontology/
│        │  ├─ node_definitions.yaml  # definisi node (Disease, VisualFeature, dst)
│        │  └─ relationship_definitions.yaml # definisi relasi + properti
│        ├─ cypher/
│        │  ├─ constraints/
│        │  │  └─ 001_constraints.cypher # uniqueness/mandatory constraints
│        │  ├─ indexes/
│        │  │  └─ 001_indexes.cypher   # index untuk label/property penting
│        │  ├─ templates/
│        │  │  └─ retrieve_disease_context.cypher # template retrieval utama modul B
│        │  └─ seeds/
│        │     └─ 001_seed_ontology.cypher # data awal ontologi
│        └─ dictionaries/
│           ├─ canonical_terms.yaml    # canonical feature/symptom/environment names
│           └─ synonym_dictionary.yaml # sinonim/fuzzy mapping terms

├─ tests/
│  ├─ unit/                             # test unit per module (A/B/C, state machine, policy)
│  ├─ integration/                      # test integrasi Neo4j + pipeline
│  └─ e2e/                              # test alur end-to-end dari intake sampai output UI payload

├─ scripts/
│  ├─ bootstrap_neo4j.ps1               # setup awal db + apply constraints/indexes/seeds
│  ├─ run_migrations.py                 # eksekusi cypher migration berurutan
│  └─ replay_sample_case.py             # jalankan 1 sample case untuk validasi cepat

├─ examples/
│  ├─ sample_payloads/
│  │  ├─ case_intake_high_quality.json  # contoh payload normal
│  │  └─ case_intake_low_quality.json   # contoh payload low capture quality
│  └─ api_collection/                   # koleksi request (Postman/Bruno) untuk uji manual

└─ ops/
   ├─ docker/
   │  └─ docker-compose.neo4j.yml       # service Neo4j lokal dev
   └─ monitoring/
      └─ health_checks.md               # daftar health check operasional minimum
# Poultry GraphRAG-Vet

## Local dev with Docker

Use Docker for Neo4j only. The Python app can stay in `venv` for now.

### Why
- Neo4j runs with the same version/config on every machine.
- Data survives container restarts via named volumes.
- APOC is enabled once in compose, instead of manual setup.

### How it works
- `ops/docker/docker-compose.neo4j.yml` starts one Neo4j container.
- Port `7474` exposes Neo4j Browser.
- Port `7687` exposes Bolt for the Python driver.
- `NEO4J_AUTH` creates the first admin user.
- Named volumes keep database files, logs, import files, and plugins outside your code.

### Run
From repo root:

```powershell
Copy-Item .env.example .env
docker compose -f ops\docker\docker-compose.neo4j.yml up -d
```

Then open:
- http://localhost:7474

### Stop

```powershell
docker compose -f ops\docker\docker-compose.neo4j.yml down
```
