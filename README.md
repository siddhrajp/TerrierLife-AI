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
