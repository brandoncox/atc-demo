# CLAUDE.md

## Project Overview

Lightweight FastAPI service that wraps a remote Whisper speech-to-text model behind a single `POST /transcribe` endpoint. Uses the `openai` Python library to talk to any OpenAI-compatible audio API (Ollama by default).

## Project Structure

```
transcribe-api/
├── main.py           # FastAPI application — all app logic lives here
├── requirements.txt  # Pinned Python dependencies
├── Dockerfile        # Container image; runs on port 8080 (OpenShift non-root convention)
├── openshift.yaml    # Deployment + Service + Route for OpenShift
└── README.md         # Setup and usage guide
```

## Key Design Decisions

- **Single-file app** — `main.py` is intentionally kept as one file. Do not split into modules unless the file grows substantially.
- **OpenAI-compatible client** — uses `openai.OpenAI` pointed at a configurable base URL. This means no vendor-specific SDK; the same code works against Ollama, OpenAI, or any compatible server.
- **Port 8080** — OpenShift drops root privileges, so privileged ports (<1024) are unavailable. Always use 8080.
- **No auth layer** — authentication is intentionally out of scope; the expectation is that the Route or an API gateway handles it.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `WHISPER_BASE_URL` | `http://localhost:11434/v1` | Whisper endpoint base URL |
| `WHISPER_MODEL` | `whisper` | Model name to request |
| `WHISPER_API_KEY` | `ollama` | API key (Ollama ignores it) |

## Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Common Tasks

**Test a transcription:**
```bash
curl -X POST http://localhost:8000/transcribe -F "file=@audio.mp3"
```

**Build and run in Docker:**
```bash
docker build -t transcribe-api:latest .
docker run -p 8080:8080 -e WHISPER_BASE_URL=http://host.docker.internal:11434/v1 transcribe-api:latest
```

**Deploy to OpenShift:**
```bash
oc apply -f openshift.yaml
oc get route transcribe-api   # get the public URL
```

## Dependencies

- `fastapi` — web framework
- `uvicorn` — ASGI server
- `openai` — OpenAI-compatible client used to call the Whisper endpoint
- `python-multipart` — required by FastAPI for multipart file uploads

## What to Avoid

- Do not add an ORM or database — this service is stateless by design.
- Do not buffer or store uploaded audio files to disk; keep processing in memory.
- Do not change the default port away from 8080.
