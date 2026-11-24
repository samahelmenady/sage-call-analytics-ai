# STT + Generative AI Customer Support Intelligence Platform
## Implementation Roadmap — Sage v2.0

> **Status:** Planning only. No code modified. Awaiting your approval to begin.
> **Prepared:** 2026-11-24 | **Saved to:** `docs/platform-roadmap.md`

---

## Project Understanding (Audit Summary)

The existing **Sage** project is a fully-implemented bilingual (Arabic/English) FastAPI application with:

| Component | State | Decision |
|---|---|---|
| Cohere STT (`cohere-transcribe-arabic-07-2026`) | ✅ Production-ready | **Keep verbatim** |
| Transcription router (`POST /api/transcribe`) | ✅ Clean, validated | **Keep verbatim** |
| Provider-interface pattern (`STTProvider` ABC) | ✅ Excellent abstraction | **Mirror for GenAI** |
| Arabic ANN sentiment model (`best_sentiment_ann.keras`) | ⚠️ 3-class hotel-review classifier | **Archive + Remove** |
| `sentiment_model.py` + `preprocessor.py` | ⚠️ TF 2.21.0 + CountVectorizer | **Remove** |
| Sentiment router (`POST /api/sentiment`) | ⚠️ ANN-only, no insights | **Replace** |
| Frontend (3-screen consumer SPA) | ⚠️ Single-review focus | **Replace with dashboard** |
| Tests (4 test files, good coverage) | ✅ Pattern is reusable | **Extend** |

**Why the ANN must be replaced:** The `best_sentiment_ann.keras` model (Dense 8000→128→64→3, macro-F1=0.797) is a hotel-review bag-of-words classifier. It cannot understand conversation structure, identify speakers, extract problem categories, score agent performance, or generate insights. These require a Generative AI model.

---

## Target Architecture

```
Audio Upload
     │
     ▼ POST /api/transcribe (unchanged)
Cohere STT ──► Raw Transcript
     │
     ▼ POST /api/analyze (new)
GenAI Analysis Engine
  ├─ Prompt Builder (rubric from models_config.yaml)
  ├─ Cohere Command-R+ (default)
  ├─ OpenAI GPT-4o   (Phase 4, benchmarking)
  └─ Gemini 1.5 Pro  (Phase 4, benchmarking)
     │
     ▼ Pydantic schema validation
CallAnalysisResult (validated JSON)
     │
     ├──► Call Repository  (data/calls/{id}.json)
     │
     └──► Management Dashboard
              ├─ View 1: Upload & Analyze
              ├─ View 2: Call Detail Report
              ├─ View 3: Analytics Dashboard
              └─ View 4: Call History
```

---

## What Gets Removed / Retained / Added

### ❌ Remove

| Component | Why |
|---|---|
| `backend/services/sentiment_model.py` | Replaced by GenAI |
| `backend/services/preprocessor.py` | LLMs handle preprocessing internally |
| `backend/routers/sentiment.py` | Replaced by `/api/analyze` |
| `models/*.keras` (4 files) | **Archived** to `archive/models_dl/` — not deleted |
| `tensorflow==2.21.0` | Removes ~2.6 GB from install; cold-start drops from ~3s to <1s |
| `scikit-learn`, `joblib`, `numpy`, `scipy` | No longer needed at runtime |

### ✅ Keep Verbatim

`backend/services/stt/interface.py` · `backend/services/stt/cohere_stt.py` · `backend/routers/transcription.py`

### ✨ Add New

GenAI engine + providers · 3 new API routers · Pydantic analysis schema · Call repository · Management dashboard · Benchmark suite · `models_config.yaml`

---

## Phase 0 — Housekeeping & Repository Restructure
**Est. 0.5 days**

```
archive/
  models_dl/      ← move models/*.keras (4 files)
  data_processed/ ← move data/processed/count_vectorizer.joblib
  notebooks/      ← copy notebooks/ for portfolio reference
  results_dl/     ← move results_dl/ content
  README.md       ← document: architecture, metrics (86.9% acc, F1=0.797), reason for evolution
data/calls/       ← NEW empty store for call records
```

**Files to modify:** `backend/config.py`, `backend/main.py`, `requirements.txt`, `.env.example`

---

## Phase 1 — GenAI Analysis Engine
**Est. 2–3 days**

### Output Schema (`backend/schemas/call_analysis.py`)

The core engineering artifact — every GenAI output is validated against this before storage:

```python
class CallAnalysisResult(BaseModel):
    call_id: str
    analyzed_at: str                    # ISO datetime
    transcript_language: Literal["ar", "en", "mixed", "other"]
    speakers: list[SpeakerTurn]         # diarized turns (prompt-inferred)

    sentiment: SentimentAnalysis        # overall, score (0–10), trajectory, evidence[]
    problem: ProblemClassification      # summary, category, priority, rationale, keywords[]
    agent_evaluation: AgentEvaluation   # 4 scores (0–10), strengths[], improvements[], evidence[]
    resolution: ResolutionStatus        # resolved, type, follow_up_actions[]

    call_summary: str                   # 2–4 sentence factual summary
    key_insights: list[str]             # 3–5 actionable observations
    recommendations: list[str]         # specific recommended actions

    confidence_score: float             # 0.0–1.0
    low_confidence_flags: list[str]    # fields where evidence was insufficient
```

**8 problem categories:** `billing` · `technical` · `shipping` · `account` · `product_quality` · `returns` · `general_inquiry` · `other`

**4 agent dimensions:** Empathy · Clarity · Resolution Effectiveness · Professionalism (all 0–10, rubric configurable in `models_config.yaml`)

### Provider Interface (`backend/services/genai/interface.py`)

Mirrors the existing `STTProvider` ABC pattern exactly:

```python
class GenAIProvider(ABC):
    @abstractmethod
    async def analyze_transcript(
        self, transcript: str, call_id: str, language: str = "ar"
    ) -> CallAnalysisResult: ...
```

### Prompt Engineering (`backend/services/genai/prompts/`)

- `system_prompt.py` — template with role, task, rubric, schema, evidence mandate, low-confidence instructions
- `prompt_builder.py` — injects transcript + language + rubric from config

**Critical prompt requirements:**
1. ALL scoring claims must cite direct transcript quotes
2. Insufficient-evidence fields must go in `low_confidence_flags` (not hallucinated)
3. Output ONLY valid JSON — no preamble or markdown
4. JSON-mode enforced at API level (`response_format={"type": "json_object"}`)

### Cohere GenAI Provider (`backend/services/genai/cohere_genai.py`)

- **Model:** `command-r-plus-08-2024` (128k context, strong Arabic)
- **JSON mode:** `ClientV2.chat()` with `response_format={"type": "json_object"}`
- **Retry:** Schema validation failure → one correction-prompt retry → `AnalysisError`

### Orchestrator (`backend/services/genai/analyzer.py`)

Selects provider from config, calls `analyze_transcript()`, validates schema, handles retries with exponential backoff.

---

## Phase 2 — Enhanced Backend API
**Est. 1–2 days**

### New Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/analyze` | Transcript → validated `CallAnalysisResult` JSON |
| `GET` | `/api/calls` | List all calls (paginated, filterable by sentiment/category/priority/date) |
| `GET` | `/api/calls/{id}` | Single call record |
| `DELETE` | `/api/calls/{id}` | Delete call record |
| `GET` | `/api/analytics` | Aggregated metrics across all calls |
| `GET` | `/api/health` | External provider health check |

### Analytics Response Shape

```json
{
  "total_calls": 142,
  "avg_satisfaction_score": 7.4,
  "resolution_rate": 0.74,
  "sentiment_distribution": {"positive": 68, "neutral": 42, "negative": 32},
  "category_breakdown": {"billing": 38, "technical": 29, ...},
  "avg_agent_scores": {"empathy": 7.1, "clarity": 6.8, ...},
  "top_issues": ["billing_dispute", "delayed_shipment"],
  "trend_7d": {"satisfaction": [7.1, 7.3, 7.0, 7.5, 7.6, 7.4, 7.4]}
}
```

### Call Repository (`backend/services/call_repository.py`)

Abstract interface (storage-backend swappable):

```python
class CallRepository(ABC):
    async def save(self, result: CallAnalysisResult) -> None: ...
    async def get(self, call_id: str) -> Optional[CallAnalysisResult]: ...
    async def list_all(self, filters: dict) -> list[CallAnalysisResult]: ...
    async def delete(self, call_id: str) -> bool: ...
```

**Phase 1–3:** JSON files (`data/calls/{call_id}.json`) — zero dependencies  
**Phase 3+ upgrade path:** SQLite (`aiosqlite`), documented in `docs/deployment.md`

---

## Phase 3 — Management Dashboard
**Est. 3–4 days**

**4 views, Vanilla JS + Chart.js (CDN, no build step):**

### View 1 — Upload & Analyze
Drag-and-drop audio OR paste transcript · Optional metadata (Agent ID, Queue, Language) · "Transcribe & Analyze" with progress states

### View 2 — Call Detail Report
```
┌─ HEADER ──────────────────────────────────────────┐
│ ID: CALL-001 │ Date │ Category: BILLING │ HIGH    │
├─ SENTIMENT ────────┐  ├─ RESOLUTION ─────────────┐│
│ ● Negative 3.2/10  │  │ ✗ Unresolved             ││
│ Trajectory: ↘      │  │ Follow-up: Required      ││
├─ PROBLEM ─────────────────────────────────────────┤
│ Customer charged twice for order #4421.           │
├─ AGENT EVALUATION ────────────────────────────────┤
│ Empathy        [████████░░] 7.8/10                │
│ Clarity        [██████░░░░] 6.2/10                │
│ Resolution     [████░░░░░░] 4.5/10                │
│ Professionalism[█████████░] 8.9/10                │
│ Overall:  6.9/10                                  │
├─ SUMMARY / INSIGHTS / RECOMMENDATIONS ────────────┤
│ Call summary paragraph...                         │
│ Insights: • Evidence quote from transcript        │
│ Recommendations: • Specific action                │
├─ TRANSCRIPT ──────────────────────────────────────┤
│ [Agent] I understand your concern about...        │
│ [Customer] I was charged twice for...             │
└───────────────────────────────────────────────────┘
```

### View 3 — Analytics Dashboard
KPI cards · Sentiment donut chart · Category bar chart · 7-day trend line · Agent performance table

### View 4 — Call History
Filterable table (sentiment, category, priority, date, resolution) · Sort · Row click → Detail · CSV export

**Design:** Extend existing CSS token system with semantic colors (`--score-high`, `--priority-critical`, etc.)

---

## Phase 4 — Configurable Model Architecture
**Est. 1 day**

### `models_config.yaml`

```yaml
genai:
  active: cohere          # change this to switch providers — no code change needed
  providers:
    cohere:
      model: command-r-plus-08-2024
      temperature: 0.1
      max_tokens: 4096
      timeout_seconds: 60
      retry_attempts: 2
    openai:
      model: gpt-4o
      ...
    gemini:
      model: gemini-1.5-pro
      ...

evaluation_rubric:
  empathy:
    weight: 0.25
    description: "Agent acknowledges customer feelings"
    indicators:
      positive: ["I understand", "I'm sorry"]
      negative: ["That's not my problem"]
  clarity:  { weight: 0.25, ... }
  resolution_effectiveness: { weight: 0.30, ... }
  professionalism: { weight: 0.20, ... }
```

Switching `genai.active: openai` swaps the provider at startup — zero code changes. Rubric is injected into the prompt at build time.

---

## Phase 5 — Testing & Benchmarking
**Est. 2–3 days**

### Unit Tests (7 new files)

| File | Key Scenarios |
|---|---|
| `test_analysis_schema.py` | Valid schema passes, invalid scores/literals rejected |
| `test_prompt_builder.py` | Transcript injection, rubric inclusion, language instruction |
| `test_analysis_router.py` | 200 (mocked), 400 empty, 400 short, 502 provider error |
| `test_calls_router.py` | List, get, 404, delete, filter params |
| `test_analytics_router.py` | Zero calls, N calls, correct aggregation math |
| `test_call_repository.py` | Save/load/list/delete, concurrent write safety |
| `tests/integration/test_cohere_live.py` | Real API (skipped unless `INTEGRATION_TESTS=true`) |

### Benchmarking Framework

**Dataset:** `benchmarks/data/test_calls.json` — 30+ synthetic call transcripts covering all 8 categories, 4 sentiment levels, AR + EN, with ground-truth labels.

**Metrics per provider/model:**

| Metric | Description |
|---|---|
| Schema validity rate | % of outputs that parse as valid `CallAnalysisResult` |
| Sentiment accuracy | Agreement with ground-truth label |
| Category accuracy | Agreement with ground-truth category |
| Priority accuracy | Agreement with ground-truth priority |
| Resolution accuracy | Agreement with resolved/unresolved ground truth |
| Agent score MAE | Mean absolute error vs. human-annotated score range |
| Latency p50 / p95 | End-to-end request time (ms) |
| Cost per call | Tokens in + out × provider pricing (USD) |
| Retry rate | % requiring schema-correction retry |

**Providers compared:**
`cohere/command-r-plus-08-2024` · `cohere/command-r-08-2024` · `openai/gpt-4o` · `openai/gpt-4o-mini` · `gemini/gemini-1.5-pro` · `gemini/gemini-1.5-flash`

**Output:** `results/benchmarks/{timestamp}_benchmark_report.md` — comparison table + recommendation, suitable for GitHub README inclusion.

**STT benchmark** (`benchmarks/stt_benchmark.py`): WER + CER using `jiwer` on 5–10 reference audio clips.

---

## Phase 6 — Documentation & Portfolio Polish
**Est. 1–2 days**

| File | Content |
|---|---|
| `README.md` | Architecture diagram, quick start, API table, benchmark results, tech badges |
| `docs/api-reference.md` | Full endpoint reference with curl examples |
| `docs/schema-reference.md` | `CallAnalysisResult` field documentation |
| `docs/prompt-engineering.md` | Prompt design decisions, versioning log |
| `docs/benchmarks.md` | Methodology, dataset description, latest results |
| `docs/deployment.md` | Environment setup, production notes |

**Portfolio callouts for README:**
- *"End-to-end AI pipeline:"* STT → GenAI → Validated JSON → Dashboard
- *"Provider-agnostic:"* swap Cohere, OpenAI, Gemini via config file
- *"Evidence-based:"* every claim backed by transcript quotes
- *"Benchmarked:"* quantified comparison of 5+ models on 8 metrics
- *"Production patterns:"* retry logic, schema validation, error boundaries, repository abstraction

---

## Complete Target File Tree

```
ANN_01 - Copy/
├── archive/                           ← NEW
│   ├── models_dl/  (*.keras × 4)
│   ├── data_processed/  (*.joblib)
│   ├── notebooks/
│   └── README.md
├── backend/
│   ├── main.py                        ← MODIFY
│   ├── config.py                      ← MODIFY
│   ├── schemas/
│   │   └── call_analysis.py           ← NEW
│   ├── routers/
│   │   ├── transcription.py           ← UNCHANGED
│   │   ├── sentiment.py               ← REMOVE
│   │   ├── analysis.py                ← NEW
│   │   ├── calls.py                   ← NEW
│   │   └── analytics.py               ← NEW
│   └── services/
│       ├── preprocessor.py            ← REMOVE
│       ├── sentiment_model.py         ← REMOVE
│       ├── call_repository.py         ← NEW
│       ├── model_config.py            ← NEW
│       ├── stt/  (interface + cohere) ← UNCHANGED
│       └── genai/                     ← NEW
│           ├── interface.py
│           ├── analyzer.py
│           ├── cohere_genai.py
│           ├── openai_genai.py        ← Phase 4
│           ├── gemini_genai.py        ← Phase 4
│           └── prompts/
│               ├── system_prompt.py
│               └── prompt_builder.py
├── frontend/                          ← REPLACE
│   ├── index.html
│   ├── app.js
│   ├── views/  (upload / call-detail / analytics / call-history)
│   ├── components/  (score-bar / sentiment-chip)
│   └── styles/  (main / dashboard / report)
├── data/calls/                        ← NEW (call record store)
├── benchmarks/                        ← NEW
│   ├── run_benchmark.py
│   ├── stt_benchmark.py
│   ├── benchmark_config.yaml
│   └── data/test_calls.json
├── tests/
│   ├── test_transcription_api.py      ← KEEP
│   ├── test_preprocessor.py           ← REMOVE
│   ├── test_sentiment_model.py        ← REMOVE
│   ├── test_sentiment_api.py          ← REMOVE
│   ├── test_analysis_schema.py        ← NEW
│   ├── test_prompt_builder.py         ← NEW
│   ├── test_analysis_router.py        ← NEW
│   ├── test_calls_router.py           ← NEW
│   ├── test_analytics_router.py       ← NEW
│   ├── test_call_repository.py        ← NEW
│   └── integration/
│       └── test_cohere_live.py        ← NEW
├── docs/
│   ├── platform-roadmap.md            ← THIS FILE
│   ├── api-reference.md               ← NEW
│   ├── schema-reference.md            ← NEW
│   ├── prompt-engineering.md          ← NEW
│   ├── benchmarks.md                  ← NEW
│   └── deployment.md                  ← NEW
├── results/benchmarks/                ← NEW
├── models_config.yaml                 ← NEW
├── .env                               ← MODIFY
├── .env.example                       ← MODIFY
├── requirements.txt                   ← MODIFY
└── README.md                          ← REPLACE
```

---

## Dependency Changes

```
ADD:  cohere>=5.0 (already installed — also covers GenAI)
ADD:  openai>=1.40           (Phase 4, optional)
ADD:  google-generativeai>=0.8  (Phase 4, optional)
ADD:  pyyaml>=6.0            (models_config.yaml)
ADD:  pytest-mock>=3.14
ADD:  jiwer>=3.0             (STT benchmarking)

REMOVE: tensorflow==2.21.0   (-2.6 GB, -3s startup)
REMOVE: scikit-learn==1.9.1
REMOVE: joblib==1.6.0
REMOVE: numpy==2.5.5
REMOVE: scipy==1.18.1
```

---

## 6 Open Design Decisions (Need Your Input)

> [!IMPORTANT]
> These decisions affect implementation direction. Please review and decide before I begin coding.

| # | Question | Recommendation | Alternatives |
|---|---|---|---|
| **Q1** | **GenAI provider to implement first?** | Cohere (single API key, matches STT vendor) | OpenAI GPT-4o (highest capability), Gemini 1.5 Pro |
| **Q2** | **Frontend framework?** | Vanilla JS (no build step, fast to ship) | React + Vite (TypeScript, component reuse) |
| **Q3** | **Storage backend?** | JSON files now, SQLite upgrade path documented | SQLite from day 1, PostgreSQL |
| **Q4** | **Dashboard language?** | English-only (enterprise norm, cleaner portfolio) | Bilingual AR/EN (preserves i18n investment) |
| **Q5** | **Speaker diarization?** | Prompt-based inference + `low_confidence_flags` | pyannote.audio (adds complexity), skip entirely |
| **Q6** | **Benchmark dataset creation?** | GenAI-draft 30 synthetic transcripts + human review | Developer writes all from scratch |

---

## Implementation Sequence

```
Phase 0 → Phase 1 → Phase 2 → Phase 5 (unit tests) → Phase 3 → Phase 4 → Phase 5 (benchmarks) → Phase 6
Archive   Schema +  API        Test coverage          Dashboard  Multi-     Benchmark             README
legacy    prompt    routes     for all services                  model      execution              + docs
          engine    + repo                                       config
```

| Phase | Effort |
|---|---|
| 0 — Housekeeping | 0.5 days |
| 1 — GenAI Engine | 2–3 days |
| 2 — Backend API | 1–2 days |
| 3 — Dashboard | 3–4 days |
| 4 — Model Config | 1 day |
| 5 — Tests + Benchmarks | 2–3 days |
| 6 — Docs | 1–2 days |
| **Total** | **10–16 days** |

---

*Roadmap saved to `docs/platform-roadmap.md`. Awaiting approval to begin Phase 0.*
