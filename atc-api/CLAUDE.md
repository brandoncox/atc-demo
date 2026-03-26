# CLAUDE.md

## Project Overview

Combined FastAPI service that:
1. Wraps a Whisper speech-to-text model behind `POST /transcribe`, persisting results to MongoDB.
2. Ingests FAA AIM reference pages into a LlamaStack vector store and runs a RAG agent to analyze ATC shift transcripts for procedural compliance and communication quality via `POST /analyze_transcript`.

Merged from `shift-api` and `transcribe-api`.

## Project Structure

```
atc-api/
├── main.py           # App factory — wires FastAPI, middleware, lifespan, and router
├── config.py         # Env vars, constants (FAA URLs, query template), shared client instances
├── models.py         # Pydantic request/response models
├── rag.py            # RAG helpers: clean_text, build_llm_model, ingest_urls, run_rag_query
├── routes.py         # APIRouter with all route handlers (/health, /transcribe, /shifts, /analyze_transcript)
├── requirements.txt  # Python dependencies
├── Dockerfile        # Container image; runs on port 8080 (OpenShift non-root convention)
├── openshift.yaml    # Deployment + Service + Route for OpenShift
└── README.md         # Setup and usage guide
```

## Key Design Decisions
- **FAA AIM URLs are hardcoded** — the AIM chapter URLs are the canonical knowledge base. Add to the list if coverage needs to expand; do not make them a runtime parameter.
- **Vector store at startup** — the vector store is created once at startup and reused across requests. This is faster than per-request ingestion.
- **LlamaStack client** — uses `llama-stack-client` directly (not the OpenAI-compatible layer). The `LLAMA_STACK_URL` env var points at the server.
- **OpenAI-compatible Whisper client** — uses `openai.OpenAI` pointed at a configurable base URL. Works against Ollama, OpenAI, or any compatible server.
- **Port 8080** — OpenShift drops root privileges, so privileged ports (<1024) are unavailable. Always use 8080.
- **No auth layer** — authentication is intentionally out of scope.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `LLAMA_STACK_URL` | `http://localhost:8321` | Llama Stack server base URL |
| `WHISPER_BASE_URL` | `http://localhost:11434/v1` | Whisper endpoint base URL |
| `WHISPER_MODEL` | `whisper-large-v3-turbo-quantized` | Model name to request |
| `WHISPER_API_KEY` | `ollama` | API key (Ollama ignores it) |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |

## Running Locally

```bash
# Install dependencies
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Start with hot reload
uvicorn main:app --reload
```

## Common Tasks

**Test a transcription:**
```bash
curl -X POST http://localhost:8000/transcribe -F "file=@audio.mp3"
```

**Test with the example transcript:**
```bash
curl -X POST http://localhost:8000/analyze_transcript \
  -H "Content-Type: application/json" \
  -d '{"transcription": "United one two, cleared to land runway one six..."}'
```

**Check health:**
```bash
curl http://localhost:8000/health
```

**Build and run in Docker:**
```bash
docker build -t atc-api:latest .
docker run -p 8080:8080 \
  -e LLAMA_STACK_URL=http://host.docker.internal:8321 \
  -e WHISPER_BASE_URL=http://host.docker.internal:11434/v1 \
  -e MONGO_URI=mongodb://host.docker.internal:27017 \
  atc-api:latest
```

## Dependencies

- `fastapi` — web framework
- `uvicorn` — ASGI server
- `llama-stack-client` — client SDK for Llama Stack (agent, vector store, RAG APIs)
- `openai` — OpenAI-compatible client for Whisper endpoint
- `motor` — async MongoDB driver
- `python-multipart` — required by FastAPI for multipart file uploads
- `requests` — fetches FAA AIM HTML pages
- `pydantic` — request/response models (bundled with FastAPI)

## What to Avoid

- Do not add an additional database abstraction layer — MongoDB access is intentional and direct.
- Do not buffer or store uploaded audio files to disk; keep processing in memory.
- Do not change the default port away from 8080.
- Do not move FAA URL configuration to a database or external config service; keep it in `main.py`.
