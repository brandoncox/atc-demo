# Shift Analysis API

FastAPI service that analyzes ATC shift transcripts against FAA AIM procedures using a LlamaStack RAG agent.

## How it works

1. On each request, the service downloads FAA AIM reference pages and uploads them to a LlamaStack vector store.
2. A RAG agent with file-search is created and queried with the submitted transcript.
3. The agent returns a structured assessment of procedural compliance and communication quality.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) package manager
- A running [Llama Stack](https://github.com/meta-llama/llama-stack) server (default: `http://localhost:8321`)

## Running Locally

```bash
# Install dependencies
uv sync

# Start the server
uv run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `LLAMA_STACK_URL` | `http://localhost:8321` | Llama Stack server URL |

## API

### `POST /analyze_transcript`

Analyzes a shift transcript against FAA AIM procedures.

**Request body:**

```json
{
  "shift_id": "shift_20250624_0800",
  "controller_id": "CTR_823",
  "facility": "KLAX",
  "transcription": "United one two, cleared to land runway one six...",
  "query": "(optional) override the default analysis prompt"
}
```

**Response:**

```json
{
  "shift_id": "shift_20250624_0800",
  "vector_store_id": "aim_docs_a1b2c3d4",
  "analysis": "..."
}
```

Only `transcription` is required. When `query` is omitted, the service uses a default prompt that evaluates phraseology, procedural compliance, and communication quality.

### `GET /health`

Returns `{"status": "ok"}`.

## OpenShift

```bash
oc apply -f openshift.yaml
oc get route shift-api   # get the public URL
```

Set `LLAMA_STACK_URL` in `openshift.yaml` to point at your Llama Stack server before deploying.

## Docker

```bash
docker build -t shift-api:latest .
docker run -p 8080:8080 \
  -e LLAMA_STACK_URL=http://host.docker.internal:8321 \
  shift-api:latest
```
