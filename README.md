# SHL Conversational Assessment Recommender

> **AI Intern Take-Home Assignment — SHL Labs 2026**  
> A production-ready conversational AI agent that guides hiring managers from a vague role description to a grounded shortlist of SHL assessments through natural dialogue.

---

## What This Does

Hiring managers often don't know the exact assessment they need until they describe the role out loud. Traditional catalog interfaces force keyword search — which assumes you already know the right vocabulary.

This agent flips that: you describe the role in plain English, the agent clarifies what it needs, and returns a precision shortlist drawn **exclusively** from the live SHL catalog. No hallucinated products. No made-up URLs. Every recommendation is grounded.

```
User:      "I need an assessment for a software engineer"
Agent:     "What skills or technology are you evaluating?"
User:      "Java backend, mid-level, 4 years experience"
Agent:     "Here are 3 assessments for a mid-level Java backend developer:"
           → Core Java (Advanced Level) (New)  [K]  shl.com/...
           → Core Java (Entry Level) (New)      [K]  shl.com/...
           → Enterprise Java Beans (New)        [K]  shl.com/...
```

---

## Live Demo

```bash
# Health check
curl https://your-service.onrender.com/health
# → {"status": "ok"}

# Chat
curl -X POST https://your-service.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user",      "content": "Hiring a mid-level Java developer"},
      {"role": "assistant", "content": "What specific skills should be assessed?"},
      {"role": "user",      "content": "Core Java and backend API development"}
    ]
  }'
```

**Response:**
```json
{
  "reply": "Here are 3 assessments for a mid-level Java backend developer:",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url": "https://www.shl.com/solutions/products/product-catalog/view/core-java-advanced-level-new/",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     POST /chat (FastAPI)                         │
│                    Stateless — full history each call            │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Agentic Orchestrator (agent.py)               │
│                                                                  │
│  Step 1 ── Hard Refusal Filter (Python, pre-LLM)               │
│            Blocks: prompt injection, legal Qs, competitors       │
│                                                                  │
│  Step 2 ── Intent Classification (Groq Llama-3.3-70b)          │
│            → VAGUE / SPECIFIC / REFINE / COMPARE / OFF_TOPIC    │
│                                                                  │
│  Step 3 ── Context Extraction (Groq Llama-3.3-70b)             │
│            → {role, seniority, skills, test_types_preferred}     │
│                                                                  │
│  Step 4 ── FAISS Semantic Retrieval (Gemini Embedding-2)        │
│            → Top-15 candidates by cosine similarity             │
│                                                                  │
│  Step 5 ── LLM Re-ranking & Response Generation                 │
│            Catalog context injected in system prompt             │
│                                                                  │
│  Step 6 ── URL Post-filter (Python, post-LLM)                  │
│            Drops any URL not in catalog.json — zero hallucination│
└──────────────────────────────────────────────────────────────────┘
```

### Four Conversational Behaviors

| Behavior | Trigger | What Happens |
|---|---|---|
| **Clarify** | `VAGUE` — fewer than 2 attributes known | Asks exactly ONE clarifying question. No retrieval yet. |
| **Recommend** | `SPECIFIC` — role + at least 1 attribute | Embeds accumulated context → FAISS → LLM re-rank → 1–10 recs |
| **Refine** | `REFINE` — user updates a constraint | Re-retrieves with merged context. Explicitly acknowledges the change. |
| **Compare** | `COMPARE` — "difference between X and Y" | Loads named catalog entries by keyword match, injects raw data into LLM. No model prior used. |

---

## Tech Stack

| Component | Choice | Why |
|---|---|---|
| **API Framework** | FastAPI | Async, auto-OpenAPI, required by spec |
| **LLM (generation)** | Groq `llama-3.3-70b-versatile` | Sub-1s latency, generous free tier, large context window |
| **Embeddings** | Gemini `gemini-embedding-2` | No local model download, 3072-dim, free API |
| **Vector Store** | FAISS `IndexFlatIP` | Zero infrastructure, file-serializable, exact cosine search |
| **Schema Validation** | Pydantic v2 | Strict request/response enforcement, auto-422 on bad input |
| **Scraping** | `requests` + BeautifulSoup4 | Catalog data is in server-rendered HTML — no headless browser needed |
| **Deployment** | Render.com | Free tier, always-on Python web service |

---

## Project Structure

```
SHL/
├── main.py              # FastAPI entrypoint — GET /health, POST /chat
├── agent.py             # Orchestrator: intent → route → retrieve → respond
├── retrieval.py         # FAISS vector store + Gemini embedding
├── catalog.py           # catalog.json loader + context formatter
├── prompts.py           # System / intent / extraction prompt templates
├── models.py            # Pydantic: Message, ChatRequest, ChatResponse
├── eval.py              # Evaluation: Recall@10, Precision@10, Groundedness, Relevance
├── run_tests.py         # Quick end-to-end behavioral test (7 probes)
├── app.py               # Optional Streamlit UI
│
├── scraper/
│   ├── scrape.py        # Scrapes SHL catalog → catalog.json (144 Individual Tests)
│   └── enrich.py        # Generates LLM descriptions to replace scraper cookie text
│
├── catalog.json         # 144 real SHL Individual Test Solutions (committed)
├── catalog.index        # FAISS binary index (auto-built at startup, gitignored)
├── catalog.pkl          # Parallel catalog list (auto-built at startup, gitignored)
│
├── tests/
│   ├── test_api.py      # Schema compliance + HTTP contract tests
│   ├── test_agent.py    # Behavior probe tests (pytest)
│   └── traces/          # 5 conversation traces for Recall@10 eval
│       ├── trace_01.json — trace_05.json
│
├── render.yaml          # Render.com deployment config
├── requirements.txt     # Python dependencies
└── .env                 # API keys (never committed)
```

---

## API Contract

### `GET /health`
```json
{"status": "ok"}
```
Returns HTTP 200. Responds within 200ms (catalog pre-loaded at startup).

### `POST /chat`

**Request:**
```json
{
  "messages": [
    {"role": "user",      "content": "string"},
    {"role": "assistant", "content": "string"}
  ]
}
```
Full conversation history on every call. The API is **completely stateless** — no server-side session.

**Response:**
```json
{
  "reply": "Natural language response",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url":  "https://www.shl.com/solutions/products/product-catalog/view/core-java-advanced-level-new/",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
```

| Field | Type | Notes |
|---|---|---|
| `reply` | `string` | Always non-empty |
| `recommendations` | `array` | `[]` when clarifying/refusing. 1–10 items when recommending. |
| `end_of_conversation` | `boolean` | `true` when task complete |
| `test_type` | `string` | One of: `A B C D E K O P S` |

### Test Type Codes

| Code | Label |
|---|---|
| `A` | Ability & Aptitude |
| `B` | Biodata & Situational Judgement |
| `C` | Competencies |
| `D` | Development & 360 |
| `E` | Assessment Exercises |
| `K` | Knowledge & Skills |
| `O` | Occupational Personality |
| `P` | Personality & Behavior |
| `S` | Simulations |

---

## Evaluation Results

```
============================================================
  SHL ASSESSMENT RECOMMENDER -- EVALUATION REPORT
============================================================

HARD EVALS (must be 100%)
  Schema compliance :  5/5
  Test type validity:  5/5
  URL groundedness  :  5/5  (0 hallucinated URLs)
  Turn cap honored  :  5/5
  -> Overall hard   :  5/5  PASS

SOFT METRICS
  Mean Recall@10    :  0.40
  Mean Precision@10 :  0.30
  Mean Groundedness :  1.00  (all URLs from catalog)
  Mean Relevance    :  0.30  (Jaccard)

BEHAVIORAL PROBES (run_tests.py)
  [PASS] Health check
  [PASS] Vague → returns [] and asks clarifying question
  [PASS] Specific → returns 1–3 relevant recommendations
  [PASS] Refine → updates shortlist, acknowledges change
  [PASS] Compare → grounded catalog comparison
  [PASS] Off-topic → polite refusal, empty recs
  [PASS] Prompt injection → hard refusal, empty recs
  7/7 PASSED
============================================================
```

---

## Evaluation Metrics Explained

| Metric | Definition | Our Score |
|---|---|---|
| **Recall@10** | Fraction of expected assessments appearing in top-10 | 0.40 (5 local traces) |
| **Precision@10** | Fraction of returned recs that are relevant | 0.30 |
| **Groundedness** | Fraction of URLs present verbatim in catalog.json | **1.00** |
| **Relevance (Jaccard)** | Overlap between predicted and expected names | 0.30 |
| **Schema Compliance** | Pydantic parse success rate | **100%** |

> Groundedness is the critical hard eval — 1.00 means zero hallucinated URLs across all traces.

---

## Running Locally

### Prerequisites
- Python 3.11+
- Groq API key (free at [console.groq.com](https://console.groq.com))
- Gemini API key (free at [aistudio.google.com](https://aistudio.google.com))

### Setup
```bash
# 1. Clone and install
git clone https://github.com/your-username/shl-recommender
cd shl-recommender
pip install -r requirements.txt

# 2. Set API keys
echo 'GEMINI_API_KEY="your-key-here"' >> .env
echo 'GROQ_API_KEY="your-key-here"'   >> .env

# 3. Start the API (catalog.index auto-builds on first run, ~2 min)
uvicorn main:app --reload

# 4. Test it (new terminal, PowerShell)
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/chat' `
  -ContentType 'application/json' `
  -Body '{"messages":[{"role":"user","content":"Java backend developer, mid level"}]}'
```

### Run Evaluations
```bash
# Full evaluation report
python eval.py

# Quick 7-probe behavioral test
python run_tests.py

# Pytest behavior probes
pytest tests/ -v
```

### Optional Streamlit UI
```bash
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Data Pipeline

### 1. Catalog Scraping (`scraper/scrape.py`)
- Hits `shl.com/solutions/products/product-catalog/?type=1` (Individual Tests only)
- Paginates 32 pages × 12 items = **384 items** (current catalog: 144 scraped)
- Extracts: name, URL, test type codes, remote/adaptive flags
- No headless browser — data is in server-rendered HTML

### 2. Description Enrichment (`scraper/enrich.py`)
- The scraper's detail pages return a cookie-consent banner instead of descriptions
- Enrichment calls Groq LLM to generate accurate 1–2 sentence descriptions from name + type + tags
- Saves checkpoints every 20 items to avoid data loss

### 3. FAISS Index Build (`retrieval.py`)
- Each catalog entry embedded as: `name | description | test_type_label | job_levels | tags`
- 144 entries × 3072-dim Gemini vectors → `IndexFlatIP` (cosine similarity)
- Persisted to `catalog.index` + `catalog.pkl` — rebuilt only when missing
- Query time: ~200ms (1 Gemini embedding call)

---

## Design Decisions & Tradeoffs

### Why Groq over Gemini for generation?
Gemini 2.5 Flash free tier caps at 20 requests/day — hit during development. Groq's Llama-3.3-70b offers 30 RPM and much higher daily limits on the free tier, with sub-1s inference latency.

### Why FAISS over Chroma/pgvector?
At ~200 catalog items, FAISS `IndexFlatIP` is exact (not approximate), zero-infrastructure, and serializes to a single binary file. Chroma requires a running server; pgvector requires PostgreSQL — both add cold-start risk for the 30s timeout constraint.

### Why three separate LLM calls per turn?
Intent classification, context extraction, and response generation each have single, focused responsibilities. A monolithic prompt degrades at all three tasks and makes JSON parsing failure more likely. The cost: 2–3 calls per turn, but Groq's latency keeps total response time under 5s.

### Why embed accumulated context, not the raw user message?
A message like "What about Python too?" produces a meaningless embedding. The context extractor first builds `{role, seniority, skills}` from the full conversation history, then we embed that structured context. This is the primary driver of Recall@10.

### Why a Python URL post-filter in addition to prompt instructions?
Defense in depth. The prompt says "only use URLs from catalog context." The Python filter drops any URL not in `catalog.json` before the response reaches the client. If the LLM hallucinates despite instructions, Python catches it. Groundedness = 1.00 across all tests.

### Why stateless?
The evaluator replays conversation traces without maintaining session state. Statelessness also eliminates stale-context bugs and makes horizontal scaling trivial. The cost: context re-extraction from full history on every turn (2 extra LLM calls), acceptable given Groq's latency.

---

## What Didn't Work (and How It Was Fixed)

| Problem | Root Cause | Fix |
|---|---|---|
| FAISS returning irrelevant results | Batch embedding API silently returned 1 vector for 144 inputs | Changed to per-item embedding loop |
| All descriptions were cookie-banner text | SHL detail pages return consent modal before content | Wrote `enrich.py` to generate descriptions via LLM |
| `500 Internal Server Error` on `/chat` | LLM returned `null` for list fields; `.join(None)` crashed | Added `or []` / `or ""` guards in `build_query()` |
| COMPARE intent not triggering | Intent prompt lacked examples; keyword match too strict | Added examples to prompt; implemented fuzzy keyword matching |
| Gemini quota exceeded (20 req/day) | Development testing hit free-tier limit | Migrated generation to Groq; kept Gemini for embeddings only |
| `curl` failing on PowerShell | PowerShell aliases `curl` to `Invoke-WebRequest` | Documented `Invoke-RestMethod` as the correct PowerShell equivalent |

---

## Security & Constraints

- **Prompt injection** — hard-coded keyword blocklist runs before any LLM call
- **Out-of-scope** — "salary", "legal", "hogan", "korn ferry", "talent+" trigger immediate refusal
- **URL hallucination** — Python post-filter enforces `url ∈ catalog.json` on every recommendation
- **Turn cap** — forces recommendation at turn 6 if not yet recommended; sets `end_of_conversation=true` at turn 8
- **Secrets** — `.env` in `.gitignore`; API keys set as Render environment variables

---

## Author

Built By Sahil Arora for the SHL Labs AI Intern Take-Home Assignment 2026.  
Stack: FastAPI · Groq Llama-3.3-70b · Gemini Embedding-2 · FAISS · Pydantic v2 · Python 3.11
