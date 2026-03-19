# ATC API

Combined FastAPI service that transcribes ATC audio via Whisper and analyzes shift transcripts against FAA AIM procedures using a LlamaStack RAG agent.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/transcribe` | Transcribe an audio file and persist the result |
| `GET` | `/shift/{shift_id}` | Retrieve a shift record by ID |
| `DELETE` | `/shift/{shift_id}` | Delete a shift record by ID |
| `POST` | `/analyze_transcript` | Analyze a transcript against FAA AIM procedures |

## How it works

**Transcription** — audio is forwarded to a Whisper-compatible endpoint (Ollama by default). The resulting transcript and shift metadata are stored in MongoDB.

**Analysis** — on each `POST /analyze_transcript` request, FAA AIM reference pages are ingested into a LlamaStack vector store and a RAG agent evaluates the transcript for procedural compliance and communication quality.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `LLAMA_STACK_URL` | `http://localhost:8321` | Llama Stack server URL |
| `WHISPER_BASE_URL` | `http://localhost:11434/v1` | Whisper-compatible endpoint base URL |
| `WHISPER_MODEL` | `whisper-large-v3-turbo-quantized` | Whisper model name |
| `WHISPER_API_KEY` | `ollama` | API key (Ollama ignores it) |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |

## Running Locally

### Prerequisites

- Python 3.12+
- A running Whisper endpoint (e.g. Ollama with `ollama pull whisper`)
- A running [Llama Stack](https://github.com/meta-llama/llama-stack) server
- A running MongoDB instance

### Steps

```bash
# Install dependencies (uv recommended)
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Start with hot reload
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## API Reference

### POST /transcribe

**Form fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | Yes | Audio file (mp3, wav, m4a, ogg, flac, etc.) |
| `language` | string | No | ISO-639-1 language code (e.g. `en`) |
| `prompt` | string | No | Optional context to guide transcription |
| `shift_id` | string | No | Shift identifier |
| `controller_id` | string | No | Controller identifier |
| `facility` | string | No | Facility code |
| `status` | string | No | Shift status |
| `start_time` | string | No | Shift start time |
| `end_time` | string | No | Shift end time |
| `position` | string | No | Controller position |
| `schedule_type` | string | No | Schedule type |
| `traffic_count_avg` | int | No | Average traffic count |
| `original_file` | string | No | Original filename |

**Example:**

```bash
curl -X POST http://localhost:8000/transcribe \
  -F "file=@audio.mp3" \
  -F "language=en" \
  -F "shift_id=shift_20250624_0800" \
  -F "controller_id=CTR_823" \
  -F "facility=KLAX"
```

### POST /analyze_transcript

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

Only `transcription` is required. When `query` is omitted, the service uses a default prompt that evaluates phraseology, procedural compliance, and communication quality.

**Response:**

```json
{
  "shift_id": "shift_20250624_0800",
  "vector_store_id": "aim_docs_a1b2c3d4",
  "analysis": "..."
}
```

## Docker

```bash
docker build -t atc-api:latest .
docker run -p 8080:8080 \
  -e LLAMA_STACK_URL=http://host.docker.internal:8321 \
  -e WHISPER_BASE_URL=http://host.docker.internal:11434/v1 \
  -e MONGO_URI=mongodb://host.docker.internal:27017 \
  atc-api:latest
```

## OpenShift

```bash
# Build the image in-cluster
oc new-build --binary --strategy=docker --name=atc-api
oc start-build atc-api --from-dir=. --follow

# Update openshift.yaml to reference the internal image stream, then:
oc apply -f openshift.yaml
oc get route atc-api   # get the public URL
```

Override env vars after deploying:

```bash
oc set env deployment/atc-api LLAMA_STACK_URL=http://llamastack-server.llama-serve.svc.cluster.local:8321
oc set env deployment/atc-api WHISPER_BASE_URL=http://my-whisper-server:8000/v1
oc set env deployment/atc-api MONGO_URI=mongodb://mongodb:27017
```
