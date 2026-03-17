# CLAUDE.md

## Project Overview

FastAPI service that accepts an ATC shift transcript, ingests FAA AIM reference pages into a LlamaStack vector store, and runs a RAG agent to analyze the transcript for procedural compliance and communication quality.

## Project Structure

```
shift-api/
├── main.py           # FastAPI application — all app logic lives here
├── rag_agent.py      # Standalone script used as reference during development
├── requirements.txt  # Python dependencies (used by uv)
├── Dockerfile        # Container image; runs on port 8080 (OpenShift non-root convention)
└── README.md         # Setup and usage guide
```

## Key Design Decisions

- **Single-file app** — `main.py` is intentionally kept as one file. Do not split into modules unless the file grows substantially.
- **FAA AIM URLs are hardcoded** — the seven AIM chapter URLs are the canonical knowledge base. Add to the list if coverage needs to expand; do not make them a runtime parameter.
- **Vector store per request** — a new vector store is created on every `POST /analyze_transcript` call. This keeps the service stateless but is slow. If performance matters, consider caching the store ID at startup.
- **LlamaStack client** — uses `llama-stack-client` directly (not the OpenAI-compatible layer). The `LLAMA_STACK_URL` env var points at the server.
- **Port 8080** — OpenShift drops root privileges, so privileged ports (<1024) are unavailable. Always use 8080.
- **No auth layer** — authentication is intentionally out of scope.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `LLAMA_STACK_URL` | `http://localhost:8321` | Llama Stack server base URL |

## Running Locally

```bash
# Install dependencies
uv sync

# Start with hot reload
uv run uvicorn main:app --reload
```

## Common Tasks

**Test with the example transcript:**
```bash
curl -X POST http://localhost:8000/analyze_transcript \
  -H "Content-Type: application/json" \
  -d @../transcribe-api/example.json
```

**Check health:**
```bash
curl http://localhost:8000/health
```

**Build and run in Docker:**
```bash
docker build -t shift-api:latest .
docker run -p 8080:8080 \
  -e LLAMA_STACK_URL=http://host.docker.internal:8321 \
  shift-api:latest
```

## Dependencies

- `fastapi` — web framework
- `uvicorn` — ASGI server
- `llama-stack-client` — client SDK for Llama Stack (agent, vector store, file APIs)
- `requests` — fetches FAA AIM HTML pages
- `pydantic` — request/response models (bundled with FastAPI)

## What to Avoid

- Do not add an ORM or database — this service is stateless by design.
- Do not change the default port away from 8080.
- Do not move FAA URL configuration to a database or external config service; keep it in `main.py`.
