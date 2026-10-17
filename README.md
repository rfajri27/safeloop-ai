# SafeLoop AI

SafeLoop AI is an AI-assisted process safety platform. It links live equipment health to the HAZOP risk register. As sensor data shows an asset getting worse, SafeLoop re-scores the HAZOP scenarios that depend on it and flags safeguards that can no longer be credited. Engineers can ask questions about the plant's documents and get cited answers, and an AI "Red Team" proposes new or worsened hazard scenarios for human review.

The MVP runs on **Unit 100**, a fictional solvent recovery unit. Its sensor signals are replayed from open datasets (NASA IMS bearing data and the Tennessee Eastman Process), and all of its documents are synthetic.

## Key features

- **Asset health monitoring** (`hi.v1`): computes a Health Index for each asset and sorts it into a Healthy, Degraded or Critical band, with hysteresis.
- **Dynamic risk scoring** (rule set `v1`): re-scores HAZOP rows from asset health and removes credit from safeguards that depend on degraded equipment.
- **Replay scenarios**: S1 (P-101 pump bearing failure) and S2 (E-301 cooling water fault), streamed to the UI over SSE.
- **Knowledge assistant**: answers questions from SOPs, manuals, incident reports and the HAZOP study. It uses hybrid retrieval (Chroma vectors + BM25 fused with RRF) and cites a source for every claim.
- **HAZOP Red Team agent**: a LangGraph agent proposes new or worsened scenarios. A rule-based Judge checks each one before it goes to the approval queue.
- **Safety by design**: guardrails block prompt injection and any request to operate equipment. The AI is advisory only, and every number and safety decision is computed by deterministic engines, not the LLM.
- **Evaluation and audit**: golden datasets measure QA, HAZOP, guardrail and RCA quality, and every action is written to an audit log.

## Tech stack

- **Backend**: FastAPI, SQLAlchemy + Alembic (PostgreSQL), Redis
- **AI**: Google Gemini (`google-genai`), LangChain / LangGraph, ChromaDB
- **Frontend**: single-page web UI in vanilla JS, served from `/`

## Project structure

```text
app/
  agents/        Knowledge and Red Team agents (LangGraph)
  engines/       Deterministic engines: health, risk, replay, guardrail, judge, corpus
  models/        SQLAlchemy models
  repositories/  Data access layer
  services/      Business logic
config/          Settings, databases, AI clients, middleware
routes/v1/       API endpoints
web/             Web UI
safeloop-demo-data/  Seed data, replay files, document corpus, golden sets
alembic/         Database migrations
tests/           Engine tests
```

## Getting started

```bash
pip install -r requirements.txt
cp example.env .env                 # fill in DB, Redis, JWT and Gemini settings
alembic upgrade head                # create the schema
python -m scripts.seed_demo_data    # load the Unit 100 demo data
python main.py                      # http://localhost:8001
```

Set `LLM_ENABLED=false` to run without Gemini. The assistant then shows only the cited passages.

## Team DoubleF

| Name | Role |
| --- | --- |
| **Rahmat Fajri** | Lead & AI Engineer |
| **Fahira Nurul Ichazza** | Data Scientist |
