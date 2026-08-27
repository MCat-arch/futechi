# Knowledge Base & Decisions Log
## Poultry GraphRAG-Vet Project

Last updated: 2026-08-27

---

## 📋 Project Overview

**Goal:** Build a Neo4j-based GraphRAG system for poultry health screening using Computer Vision + VLM + Knowledge Graph.

**Architecture:** 3-module pipeline (A/B/C) with constrained LLM reasoning, state machine for case lifecycle, and user feedback loop.

**Reference:** [flow-sistem-poultry-graphrag-vet.md](./flow-sistem-poultry-graphrag-vet.md)

---

## 🛠️ Tech Stack Decisions

### Infrastructure
| Component | Choice | Why | Status |
|-----------|--------|-----|--------|
| Database | Neo4j 5.26 (Community) | Native graph storage, APOC plugin support | ✅ Docker setup done |
| Python env | venv (local) | Simple, no extra container layer for MVP | ✅ Configured |
| App framework | (TBD) FastAPI or LangGraph | API endpoint exposure | ⏳ Pending |
| LLM provider | (TBD) OpenAI/Anthropic | Modul C constrained reasoning | ⏳ Pending |
| VLM provider | (TBD) OpenAI Vision or Claude | Modul A visual feature extraction | ⏳ Pending |

---

## 🏗️ Folder Structure Decision

**Final structure approved:**
```
graphdb/
  ├─ src/futechi_graphrag/
  │   ├─ domain/           # Pure logic (entities, state machine, policies)
  │   ├─ application/      # Use cases (orchestration)
  │   ├─ pipelines/        # Modul A/B/C + orchestration graphs
  │   ├─ infrastructure/   # Neo4j, LLM, persistence
  │   ├─ interfaces/       # API, schedulers
  │   └─ knowledge_graph/  # Ontology YAML, Cypher templates, dictionaries
  ├─ tests/                # unit, integration, e2e
  ├─ ops/docker/           # Docker Compose for Neo4j dev
  ├─ scripts/              # Bootstrap, migrations
  └─ examples/             # Sample payloads
```

**Key insight:** Pipelines folder now includes:
- `orchestration/` → LangGraph workflow graphs
- `module_a_semantic_mapping/` → VLM + sensor mapping
- `module_b_graph_retrieval/` → Neo4j template queries
- `module_c_reasoning/` → LLM reasoning + fallback

---

## 🐳 Docker Implementation (Phase 1)

### Decision: Neo4j in Docker, Python app in venv

**Status:** ⏳ Blocked by virtualization support (see troubleshooting)

### Files added
- `ops/docker/docker-compose.neo4j.yml` → Neo4j 5.26 + APOC
- `.env.example` → Template for credentials
- `.gitignore` → Ignore venv, .env, cache
- `README.md` → Basic local dev instructions

### Why this separation
| Layer | Container | Why |
|-------|-----------|-----|
| Database | ✅ Docker | Consistent version, reproducible, easy reset |
| Python app | ❌ venv | Faster iteration, easier debugging, no rebuild |

### Known issues & troubleshooting

#### Issue 1: "Virtualization support not detected"
**Error:** Docker Desktop fails to start, shows "virtualisation support wasn't detected"
**Cause:** Hyper-V or WSL2 not enabled on Windows
**Fix (3 options):**

**Option A: Enable Hyper-V (Windows Pro/Enterprise only)**
1. Win + R → `optionalfeatures` → Enter
2. Check ✅ **Hyper-V**
3. Click OK, restart Windows
4. Try Docker Desktop again

**Option B: Enable WSL 2 (Windows Home or any edition)**
1. Open PowerShell as Administrator
2. Run: `wsl --install`
3. Restart Windows
4. Try Docker Desktop again

**Option C: Enable Virtualization in BIOS (Advanced)**
1. Restart computer, enter BIOS (F2, F10, or Del during boot)
2. Find **Virtualization**, **VT-x**, or **AMD-V** option
3. Enable it
4. Save and restart

**Fallback: Use Neo4j Aura instead**
- Skip Docker entirely for MVP
- Use cloud Neo4j at https://neo4j.com/cloud/aura/
- Free tier available, just get URI + credentials
- Update `.env` with cloud URI instead of `bolt://localhost:7687`

---

#### Issue 2: "cannot find the file specified" at `//./pipe/docker_engine`
**Cause:** Docker Desktop daemon not running
**Fix:** Start Docker Desktop from Windows Start menu

### Future: Phase 2 (optional)
- Dockerize Python app when scaling to production
- Use Docker network to connect app container ↔ Neo4j container
- Separate `docker-compose.app.yml` for FastAPI/LangGraph app

---

## 📊 Flow Mapping to Code

From [flow-sistem-poultry-graphrag-vet.md](./flow-sistem-poultry-graphrag-vet.md):

| Flow Phase | Code Location | Status |
|------------|---------------|--------|
| Phase 1: Deteksi Anomali (Edge) | `interfaces/api/routers/detection_router.py` | ⏳ TODO |
| Phase 2.1: VLM Semantic Mapping | `pipelines/module_a_semantic_mapping/` | ⏳ TODO |
| Phase 2.2: Graph Retrieval | `pipelines/module_b_graph_retrieval/retriever.py` | ⏳ TODO |
| Phase 2.3: LLM Reasoning | `pipelines/module_c_reasoning/reasoner.py` | ⏳ TODO |
| Phase 3: Output to UI | `interfaces/api/routers/cases_router.py` | ⏳ TODO |
| Case State Machine | `domain/state_machine/case_state_machine.py` | ⏳ TODO |
| Cooldown/TTL Policies | `domain/policies/` | ⏳ TODO |

---

## 🎯 Milestones Completed

- [x] Project folder structure designed
- [x] Docker Neo4j setup created
- [x] `.env.example` template
- [x] `.gitignore` rules
- [x] GitHub repo initialized (mentioned: MCat-arch/futechi)

---

## ⏳ Next Steps (Immediate)

### Step 1: Verify Docker is working
```powershell
# Start Docker Desktop
# Then verify:
docker ps

# Start Neo4j
docker compose -f ops\docker\docker-compose.neo4j.yml up -d

# Check it's running
docker compose -f ops\docker\docker-compose.neo4j.yml ps

# Open browser
# http://localhost:7474
```

**Owner:** You  
**Blocker:** Docker Desktop must be running  
**Expected outcome:** Neo4j Browser loads, login succeeds

---

### Step 2: Create `pyproject.toml` with core dependencies
- `neo4j` (driver)
- `pydantic` (config, DTO)
- `fastapi` + `uvicorn` (API)
- `langgraph` + `langchain-core` (workflow orchestration)
- `pytest` (testing)
- `ruff` + `mypy` (linting)

**Owner:** You or next session  
**Expected outcome:** `pip install -e .` works

---

### Step 3: Build Domain Layer (Phase 2)
Start with pure Python, no Neo4j/LLM yet:
1. `domain/value_objects/enums.py` → Status enums
2. `domain/value_objects/severity.py` → Severity calculation
3. `domain/entities/case.py`, `cage.py`, `confirmation.py`
4. `domain/state_machine/case_state_machine.py`
5. `domain/policies/` → Cooldown, safety-net, TTL rules

**Owner:** You  
**Blocker:** None (domain is purely logic)  
**Expected outcome:** 100% unit test coverage for domain layer

---

## 📝 Q&A History

### Q1: Do we need Docker for this project?
**A:** Docker for Neo4j only (database consistency + APOC). Python app stays in venv for MVP (faster iteration). Later: optionally containerize the app.

### Q2: What does Docker do here vs. AI workflow?
**A:** Docker ≠ AI-specific. It's containerization for ANY service. We use it for database (Neo4j), not the AI pipeline. AI workflow runs as pure Python in venv.

### Q3: Why separate files in `ops/docker/` and `src/`?
**A:** Clean separation of concerns:
- `ops/` = infrastructure (Docker, monitoring, deployment)
- `src/` = application code (business logic, domain, API)

This makes it easy to swap out infra later without touching app code.

---

## 🔗 Important Links

- Flow document: [flow-sistem-poultry-graphrag-vet.md](./flow-sistem-poultry-graphrag-vet.md)
- Implementation guide: [brief_md/panduan-implementasi-per-file.md](./brief_md/panduan-implementasi-per-file.md)
- GitHub repo: https://github.com/MCat-arch/futechi
- Reference (Neo4j GraphRAG): https://github.com/neo4j/neo4j-graphrag-python

---

## 📌 Reminders

- [ ] **Docker:** Virtualization (Hyper-V or WSL2) must be enabled on Windows (see troubleshooting)
- [ ] **Alt:** If virtualization is locked, use Neo4j Aura cloud instead
- [ ] `.env` file is in `.gitignore` — copy from `.env.example` for local dev
- [ ] Named volumes in Docker Compose survive container restarts (data is persistent)
- [ ] APOC plugin is auto-enabled in compose file (no manual install needed)
- [ ] When app needs Neo4j data, connect via `bolt://localhost:7687` (local) or cloud URI (Aura)

---

## 🚀 Commands Quick Reference

```powershell
# Start Neo4j
docker compose -f ops\docker\docker-compose.neo4j.yml up -d

# Stop Neo4j
docker compose -f ops\docker\docker-compose.neo4j.yml down

# View Neo4j logs
docker compose -f ops\docker\docker-compose.neo4j.yml logs -f neo4j

# Access Neo4j Browser
# http://localhost:7474

# Reset database (wipe all data)
docker compose -f ops\docker\docker-compose.neo4j.yml down -v
docker compose -f ops\docker\docker-compose.neo4j.yml up -d
```

---

## 📜 Document Versions

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-08-27 | Initial setup: Docker + folder structure + Q&A |
