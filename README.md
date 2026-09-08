# TerrierLife AI

A campus assistant for BU students. Ask it a question in plain English and it figures out where to look.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=next.js)
![LangGraph](https://img.shields.io/badge/LangGraph-1.1-brightgreen?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?style=flat-square&logo=postgresql)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=flat-square&logo=openai)

Finding anything at BU means digging through maps, the student portal, and a few dozen department sites. I wanted one box you could type into instead:

- *"I have 25 mins near CDS, where can I eat?"*
- *"Find me a quiet study spot near CAS with outlets"*
- *"How do I apply for OPT as an F-1 student?"*
- *"Any AI or startup events this week?"*

Behind that box is a GPT-4o agent with three tools. It picks which ones to call, pulls real data, and answers with sources.

## How it works

```
┌─────────────────┐
│  Next.js 14     │  query + optional location / time available
└────────┬────────┘
         │  POST /api/query
┌────────▼────────┐
│  FastAPI        │  rate limited, 10 req/day per IP
└────────┬────────┘
         │
┌────────▼──────────────────────────┐
│  LangGraph ReAct Agent (GPT-4o)   │  plans + sequences tool calls
└────┬──────────────┬───────────────┘
     │              │              │
┌────▼─────┐  ┌─────▼──────┐  ┌────▼─────────────────┐
│ places   │  │ events     │  │ BU resources (RAG)   │
│ (zone-   │  │ (interest- │  │ BM25 + pgvector      │
│  aware)  │  │  ranked)   │  │ ensemble, 40/60      │
└────┬─────┘  └─────┬──────┘  └────┬─────────────────┘
     └──────────────┴──────────────┘
                    │
        ┌───────────▼──────────┐
        │ PostgreSQL + pgvector│
        └──────────────────────┘
```

There's no intent classifier. The model decides which tools to call, so a question that mentions both a place and an event just calls both in one loop.

| Tool | What it does | Data |
|---|---|---|
| `get_nearby_places` | Study spots, dining, printers, libraries near a campus zone | `places` table, 25 locations |
| `get_events` | Upcoming events ranked by interest tags | `events` table, 12 events |
| `search_bu_resource` | Policy and service questions, with citations | 43 scraped BU pages, hybrid retrieval |

A few things worth explaining:

**Places search knows about campus zones.** BU's campus runs along Comm Ave rather than around a quad, so "near CDS" should also turn up Questrom and GSU. There's a zone adjacency map for that. Location strings get normalized first, because the model likes to say "Questrom School of Business" when the database just says "Questrom".

**Retrieval is hybrid.** BM25 keyword search at 40%, pgvector semantic search at 60%. Plain vector search kept missing short acronym queries like OPT, CPT and FAFSA, where matching the literal string works better.

**Follow-up questions work.** Send a `session_id` and the last few turns get replayed to the agent, so "what about closer to Questrom?" still knows you were asking about quiet study spots. History is capped at 6 messages, 1500 characters each. Those caps matter: everything you keep gets re-sent on the next request, so an unbounded window quietly runs up the bill. Leave out `session_id` and it behaves like it did before, one question at a time.

## Stack

| Layer | What I used |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind |
| Backend | FastAPI 0.111, Python 3.12, SQLAlchemy 2.0 |
| Agent | LangGraph `create_react_agent`, GPT-4o |
| Retrieval | LangChain PGVector + BM25 `EnsembleRetriever`, `text-embedding-3-small` |
| Database | PostgreSQL + pgvector (1536-dim) |
| Evals | RAGAS 0.4, plus a tool-selection harness I wrote |
| Hosting | Render (API), Vercel (web), Neon (database) |
| Rate limiting | slowapi, 10 requests/day per IP |

## Evaluation

I evaluate this in two places, because RAG metrics tell you nothing about whether the agent called the right tool.

### Retrieval (RAGAS)

20 BU-specific questions. I ran it twice with nothing changed, to see how much the score moves on its own:

| Metric | Run 1 | Run 2 |
|---|---|---|
| Faithfulness | 0.92 | 0.97 |
| Answer Relevance | 0.47 | 0.51 |
| Context Precision | 0.44 | 0.50 |
| Context Recall | 0.42 | 0.39 |

Same corpus, same code, same questions. The gap is just the LLM judge being nondeterministic, and it works out to about ±0.05. That number ended up mattering more than any single score, because it tells you which of my "improvements" were real and which were noise.

### Tool selection

25 labeled queries against the live agent. Five are multi-turn, where the question being scored makes no sense on its own ("what about closer to Questrom instead?") and only passes if the agent carried context forward.

| Metric | Result |
|---|---|
| Exact tool-set match | 23/25 (92%) |
| Any correct tool used | 24/25 (96%) |
| Parameter accuracy | 7/7 (100%) |

Errors are counted separately from wrong answers. An earlier version of this harness scored rate-limited requests as bad tool choices, which made the agent look worse than it was. It now retries on 429 and leaves real failures out of the denominator.

```bash
cd backend
python eval/run_eval.py        # RAGAS
python eval/run_tool_eval.py   # tool selection
```

Both cost money to run since they hit the API. The unit tests don't:

```bash
pip install -r requirements-dev.txt
python -m pytest      # 64 tests, ~5s, no API calls, no database
ruff check app scripts eval tests
```

Those cover the deterministic parts where bugs actually turned up: zone normalization and whether it's wired into the query, chunk dedup, context assembly, history limits, token counting, input validation. CI runs both on every push.

### What the evals found

The tool-selection harness caught the agent sending `location: "Questrom School of Business"`, which matched no zone in the database and returned zero rows. No error, no warning, just a confident answer built on nothing. RAGAS can't see that, since it never touches the places tool.

Then I went looking for why context precision was stuck around 0.15, and found two problems. Only one was in the app.

| Change | Ctx Precision | Real? |
|---|---|---|
| What I originally reported | 0.15 | — |
| After fixing the eval | 0.30 | No, just measuring correctly |
| After fixing the scraper | ~0.47 | Yes |
| Chunking | 0.28 | No, within noise |

The eval had been scoring answers against the same 500-character snippet repeated once per source, while the answer itself was generated from the full context. So the score was capped by construction and had nothing to do with retrieval quality.

The scraper problem was worse. It never checked `status_code`, so BU's "Page not found" page got parsed and stored as a legitimate document. 15 of 51 pages were 404s. That wiped out tutoring and financial aid completely, and the word "fafsa" appeared nowhere in the corpus despite four financial aid pages supposedly being scraped. Fixing it moved answer relevance from 0.27 to about 0.49, mostly because the answers stopped correctly telling people the context didn't have what they asked for.

Chunking was my first theory and it was wrong. Splitting pages into 800-character chunks scored slightly worse. The pages average about 4.2k characters and are already roughly the right size, so chunking mostly just cut answers in half. It's off by default, and `RAG_CHUNK_SIZE` turns it back on if you want to rerun the comparison.

The pattern I'd flag: three of the four bugs I found were in how I was measuring, not in what I built.

One multi-turn miss is arguable rather than broken. Asked "where is it located?" right after "what is the ERC?", the agent answered from the conversation instead of searching again. Cheaper, but it skips re-grounding, so a thin first answer would carry forward.

### Known limitations

- With 20 questions and a ±0.05 judge spread, anything under about 0.05 isn't a real difference. Only the corpus fix and the eval fix clear that bar. Chunking and corpus dedup don't.
- The ground truth answers were written separately from the corpus rather than pulled out of it, so recall is limited by what got scraped. A few questions can't be answered from the pages at all, like housing lottery mechanics or exact library hours (that page renders client-side, so the scraper only sees navigation).
- The RAGAS harness calls the retriever directly. It never runs the actual agent path that production uses.
- Conversation history never expires. It sits there until a client calls the delete endpoint. Real deployment needs a retention policy.
- Rebuilding embeddings drops the collection first, so there's a short window during a refresh where resource questions return nothing.

## API

| Endpoint | Method | What it does |
|---|---|---|
| `/api/query` | POST | Ask the agent something (rate limited) |
| `/api/query/history/{session_id}` | DELETE | Wipe a conversation |
| `/api/places` | GET | Place search: `location`, `place_type`, `features` |
| `/api/events` | GET | Event search: `interests`, `days_ahead` |
| `/api/resources` | GET | Straight RAG lookup: `q` |
| `/health` | GET | Process is alive |
| `/ready` | GET | Checks the database too, 503 if something's down |

```bash
curl -X POST localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"message": "quiet study spot with outlets", "location": "CAS", "time_available": 45}'

# reuse the session id and the follow-up knows what you meant
curl -X POST localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"message": "what about closer to Questrom?", "session_id": "abc-123"}'
```

You get back the answer, a rough `type` the frontend uses for styling, which tools ran, and the token count for the request.

## Running it locally

You'll need Python 3.12, Node 18+, PostgreSQL 15+ with pgvector, and an OpenAI key.

Database:
```bash
psql postgres -c "CREATE DATABASE terrierlife;"
psql terrierlife -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql terrierlife < backend/app/db/schema.sql
```

Backend:
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your OPENAI_API_KEY

python -m app.db.seed_data              # places + events
python scripts/scrape_bu_resources.py   # builds data/bu_resources.json
python scripts/build_embeddings.py      # embeds it into pgvector

uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Then open `http://localhost:3000`.

The scraped corpus is gitignored, so you have to build it yourself. Same goes for deploying: embeddings live in the database, not the repo, so run the scraper and `build_embeddings.py` against whatever `DATABASE_URL` you're deploying to.

## Layout

```
backend/
  app/
    main.py               FastAPI app, CORS, rate limiting
    routes/               query, places, events, resources
    services/
      openai_service.py   the agent and its tools
      rag_service.py      hybrid retrieval, chunking config
      places_service.py   zone map + normalization
      events_service.py   interest-tag ranking
      memory_service.py   conversation history
    limiter.py            shared rate limiter
    models/db_models.py   SQLAlchemy models
    db/                   connection, schema.sql, seed data
  scripts/
    scrape_bu_resources.py   scraper, validates what it stores
    build_embeddings.py      corpus -> pgvector
  eval/
    run_eval.py                  RAGAS
    run_tool_eval.py             tool selection
    test_questions.py            20 labeled RAG questions
    tool_selection_questions.py  labeled tool-choice cases
  tests/                  unit tests, no API calls
frontend/
  app/                    Next.js app router
  components/             QueryBar, RecommendationCard
  lib/api.ts              typed API client
data/                     places, events, scraped corpus
```

## Configuration

| Variable | What it's for |
|---|---|
| `OPENAI_API_KEY` | GPT-4o and embeddings |
| `DATABASE_URL` | Postgres connection (SSL turns on automatically for Neon) |
| `ALLOWED_ORIGINS` | Comma-separated CORS allowlist |
| `RAG_CHUNK_SIZE` | Chunk size for retrieval. `0` (default) indexes whole pages |
| `MAX_HISTORY_MESSAGES` | Turns replayed per request (default 6) |
| `MAX_HISTORY_MESSAGE_CHARS` | Per-message cap on that history (default 1500) |
| `NEXT_PUBLIC_API_URL` | Where the frontend looks for the API |
| `REDIS_URL` | Rate-limit storage. Without it limits live in process memory, reset on restart, and apply per instance. Set it if you run more than one. |
| `QUERY_RATE_LIMIT` | Per-IP quota on `/api/query` (default `10/day`) |
| `AGENT_RECURSION_LIMIT` | Max ReAct steps per request (default 8). Every step is a billable call. |
| `AGENT_TIMEOUT_SECONDS` | Ceiling on a whole agent run (default 90) |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | Per-call timeout and retry count |
| `LOG_LEVEL` | Default `INFO` |
