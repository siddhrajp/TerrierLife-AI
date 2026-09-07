# TerrierLife AI

> A GenAI-powered campus assistant for Boston University students.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=next.js)
![LangChain](https://img.shields.io/badge/LangChain-1.2-brightgreen?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=flat-square&logo=openai)

---

## What It Does

Instead of digging through maps, portals, and websites — BU students just ask:

- *"I have 25 mins near CDS, where can I eat?"*
- *"Find me a quiet study spot near CAS with outlets"*
- *"How do I apply for OPT as an F-1 student?"*
- *"Any AI or startup events this week?"*

A LangChain ReAct agent powered by GPT-4o classifies the intent, calls the right tool, queries the database, and returns a grounded natural language answer.

---

## Architecture

```
[Next.js Frontend]
        │
        ▼
[FastAPI Backend]
        │
[LangChain ReAct Agent]
        │
   ┌────┴────────────┐
   ▼                 ▼
[PostgreSQL]    [OpenAI GPT-4o]
[+ pgvector]    [+ Embeddings]
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| AI Agent | LangChain, LangGraph, GPT-4o |
| RAG | LangChain PGVector, text-embedding-3-small |
| Database | PostgreSQL 15, pgvector |
| Rate limiting | slowapi (10 req/day per IP) |

---

## RAG Evaluation (RAGAS)

Evaluated over 20 BU-specific questions using [RAGAS](https://github.com/explodinggradients/ragas). Ran a full ablation study to isolate the contribution of each improvement:

| Experiment | Faithfulness | Context Precision | Context Recall |
|---|---|---|---|
| Baseline (vector, 15 pages) | 0.93 | 0.05 | 0.07 |
| Expanded corpus only (vector, 51 pages) | 0.97 | 0.14 | **0.13** |
| Hybrid search only (BM25+vector, 15 pages) | 0.98 | 0.10 | 0.12 |
| Both together (BM25+vector, 51 pages) | 0.93 | **0.15** | 0.09 |

**Key findings:**
- Expanded corpus (15 → 51 pages) drove the biggest gain in **Context Recall** — more pages means more knowledge to retrieve
- Hybrid search (BM25 40% + vector 60%) drove the biggest gain in **Context Precision** — keyword matching helps for acronym-heavy queries like OPT, CPT, FAFSA
- Faithfulness remains high (0.93+) across all experiments — GPT-4o doesn't hallucinate

> Run evals yourself: `cd backend && python eval/run_eval.py`

---

## Agent Evaluation (Tool Selection)

RAGAS only scores the RAG retrieval leg — it says nothing about whether the LangGraph ReAct agent picks the right tool(s) for a query, or extracts correct arguments from it. Built a separate harness for that: 20 labeled test cases (including multi-tool queries) run against the live agent, checking tool selection and parameter extraction.

| Metric | Result |
|---|---|
| Exact tool-set match | 19/20 (95%) |
| Any correct tool used | 20/20 (100%) |
| Parameter accuracy | 5/5 (100%) |

**Key findings:**
- The harness caught a real bug: for queries like *"study spot near Questrom"*, the agent extracted `location: "Questrom School of Business"` instead of the short zone code `"Questrom"`, which silently returned zero results against the DB's zone map. Fixed by normalizing extracted locations against known campus zones (case-insensitive substring match) before querying.
- The one remaining "miss" on exact tool-set match is arguably a mislabeled test case, not an agent error — the agent called both `get_events` and `get_nearby_places` for a query that mentioned a specific location, which is a reasonable interpretation.

> Run it yourself: `cd backend && python eval/run_tool_eval.py`

---

## Running Locally

**1. Database**
```bash
psql postgres -c "CREATE DATABASE terrierlife;"
psql terrierlife -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql terrierlife < backend/app/db/schema.sql
```

**2. Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your OPENAI_API_KEY
python -m app.db.seed_data
uvicorn app.main:app --reload --port 8000
```

**3. Frontend**
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`
