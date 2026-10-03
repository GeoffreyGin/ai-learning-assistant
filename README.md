# AI Personal Knowledge Engineer

An evidence-based learning system that turns personal learning materials into a traceable knowledge model. This initial MVP slice supports document ingestion, source chunks, normalized concepts, and a local API.

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

## Current endpoints

- `POST /documents/upload` — upload PDF, Markdown, or TXT material.
- `GET /documents` and `GET /documents/{id}` — inspect documents and source chunks.
- `GET /concepts` and `GET /concepts/{id}` — inspect normalized, source-grounded concepts.
- `POST /documents/{id}/knowledge-summary` — generate a source-grounded overview and key concepts.

The default extractor is deterministic and local. It is intentionally isolated behind an extraction interface so an OpenAI-compatible structured extractor can replace it later without changing persistence or API contracts.
