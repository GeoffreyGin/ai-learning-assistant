# AI Personal Knowledge Engineer

An evidence-based learning system that turns personal learning materials into a traceable knowledge model. The system ingests documents, extracts concepts and relationships, builds a knowledge graph, estimates mastery from actual answers, detects prerequisite gaps, and generates targeted learning activities.

> Not "ChatGPT that can read my PDFs." — an agent that maintains a model of what you know, finds what you are missing, and helps you close the gaps. (Spec: `AI_Personal_Knowledge_Engineer_Spec.md`)

## Run locally

Requires Python 3.12 or newer. With a normal Python installation:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

This workspace also has a project-local Python 3.12 runtime for the MVP demo:

```powershell
.\.runtime\python312\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API explorer.

### LLM configuration

Copy `.env.example` to `.env` and fill in any OpenAI-compatible provider
(DeepSeek, OpenAI, local servers, ...). With no provider configured the system
still works end to end, using deterministic extraction, template questions, and
keyword-based evaluation.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_BASE_URL` | — | OpenAI-compatible endpoint, e.g. `https://api.deepseek.com` |
| `LLM_API_KEY` | — | Provider API key |
| `LLM_MODEL` | — | Model name, e.g. `deepseek-chat` |
| `DATA_DIR` | `data` | SQLite database and upload location |
| `MASTERY_MASTERED_THRESHOLD` | `0.80` | Gap status: mastered at or above |
| `MASTERY_WEAK_THRESHOLD` | `0.40` | Gap status: weak between this and mastered |
| `MASTERY_MIN_EVIDENCE` | `3` | Answers needed before a status is trusted |

## The learning loop

```text
Upload material -> extract concepts -> build graph -> choose a target
-> detect prerequisite gaps -> teach the biggest gap -> ask a question
-> grade the answer -> update mastery -> recommend the next step
```

Try the full loop against the real LLM:

```powershell
.\.runtime\python312\python.exe scripts\e2e_smoke.py
```

Or through the chat endpoint:

```json
POST /agent/chat {"message": "help me learn Black-Scholes"}
POST /agent/chat {"message": "true"}   // answer the open question
```

## Endpoints

- `POST /documents/upload` — upload PDF, Markdown, or TXT; extracts concepts and relationships.
- `GET /documents`, `GET /documents/{id}` — inspect documents and source chunks.
- `POST /documents/{id}/knowledge-summary` — source-grounded overview.
- `GET /concepts`, `GET /concepts/{id}` — normalized, source-grounded concepts.
- `GET /concepts/{id}/prerequisites` — transitive prerequisites with graph distance.
- `GET /concepts/{id}/related` — non-prerequisite neighbors.
- `GET /graph` — nodes and edges with mastery, for visualization.
- `POST /concepts`, `PATCH /concepts/{id}` — create or update a concept.
- `POST /relationships` — create a relationship by concept name.
- `GET /learning/gaps/{concept_id}` — prerequisite gap report (MASTERED / WEAK / UNKNOWN).
- `GET /learning/recommendation?concept_id=` — ranked next topics.
- `POST /assessment/generate` — generate one targeted question.
- `POST /assessment/submit` — grade an answer and update mastery.
- `POST /agent/chat` — the conversational learning agent (logged tool calls in `data/agent.log`).

## How it works

- **Extraction.** Each chunk is sent to the LLM for structured concept and
  relationship extraction (validated JSON, retried on invalid output). Without an
  LLM, a deterministic heading/phrase extractor is used instead.
- **Concept resolution.** Names are normalized (diacritics, possessives) and
  near-duplicates are merged through fuzzy similarity plus an LLM confirmation
  check, so "Ito Lemma" and "Itô's lemma" stay one concept while
  "Black-Scholes Model" and "Black-Scholes PDE" stay two.
- **Source grounding.** Every extracted concept links back to its source chunks;
  relationships carry the chunk that evidences them. Concepts suggested by the
  agent without material support remain ungrounded and are flagged as such.
- **Mastery.** A deterministic, bounded algorithm: correct answers add up to
  `0.2 × (1 - mastery)`, weighted by difficulty; incorrect answers subtract
  proportionally (more for repeated mistakes); long gaps decay slightly. No LLM
  guesses — mastery only moves on recorded evidence.
- **Gap detection.** Deterministic traversal of `PREREQUISITE_OF` edges, with
  configurable MASTERED/WEAK/UNKNOWN thresholds.
- **Agent.** `POST /agent/chat` routes intents ("help me learn X", "test me on X",
  "what should I study next?", answering an open question) and runs the learning
  loop in small, observable, logged steps.

## Tests

```powershell
./.runtime/python312/python.exe -m pytest
./.runtime/python312/python.exe -m ruff check app tests
```

> On this workspace, pytest may need a writable temp directory:
> `pytest --basetemp=.tmp_pytest`.
