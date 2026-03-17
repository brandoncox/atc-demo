# Transcribe API

A lightweight RESTful wrapper around a remote Whisper speech-to-text model. Built with FastAPI and compatible with any OpenAI-compatible audio endpoint (Ollama, OpenAI, or a custom deployment).

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/transcribe` | Transcribe an audio file |
| `GET` | `/transcription/{shift_id}` | Retrieve a transcription by shift ID |
| `DELETE` | `/transcription/{shift_id}` | Delete a transcription by shift ID |

### POST /transcribe

**Form fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | Yes | Audio file (mp3, wav, m4a, ogg, flac, etc.) |
| `language` | string | No | ISO-639-1 language code (e.g. `en`, `fr`) |
| `prompt` | string | No | Optional context to guide transcription |

**Response:**

```json
{
  "transcript": "The transcribed text goes here.",
  "model": "whisper"
}
```

## Configuration

All configuration is via environment variables.

| Variable | Default | Description |
|---|---|---|
| `WHISPER_BASE_URL` | `http://localhost:11434/v1` | Base URL of the Whisper-compatible endpoint |
| `WHISPER_MODEL` | `whisper` | Model name on the remote server |
| `WHISPER_API_KEY` | `ollama` | API key — Ollama ignores this; set it for real endpoints |

## Running Locally

### Prerequisites

- Python 3.12+
- A running Whisper model endpoint (e.g. [Ollama](https://ollama.com) with `ollama pull whisper`)

### Steps

1. **Install dependencies**

   **With uv (recommended):**

   ```bash
   cd transcribe-api
   uv venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```

2. **Start the API**

   ```bash
   uvicorn main:app --reload
   ```

   The API will be available at `http://localhost:8000`.

3. **Test a transcription**

   ```bash
   curl -X POST http://localhost:8000/transcribe \
     -F "file=@/path/to/audio.mp3"
   ```

   With all optional fields:

   ```bash
   curl -X POST http://localhost:8000/transcribe \
     -F "file=@/path/to/audio.mp3" \
     -F "language=en" \
     -F "prompt=Air traffic control communication" \
     -F "shift_id=shift_20250624_0800" \
     -F "controller_id=CTR_823" \
     -F "facility=blowntiresLSZH1" \
     -F "status=completed" \
     -F "start_time=2025-06-24T08:00:00Z" \
     -F "end_time=2025-06-24T16:00:00Z" \
     -F "position=Twr" \
     -F "schedule_type=2-2-1" \
     -F "traffic_count_avg=15" \
     -F "original_file=blowntiresLSZH1-Twr-Jun-24-2025-0800Z.mp3"
   ```

4. **Retrieve a transcription by shift ID**

   ```bash
   curl http://localhost:8000/transcription/shift_20250624_0800
   ```

5. **Delete a transcription by shift ID**

   ```bash
   curl -X DELETE http://localhost:8000/transcription/shift_20250624_0800
   ```

6. **Point to a different Whisper endpoint**

   ```bash
   export WHISPER_BASE_URL=http://my-whisper-server:8000/v1
   export WHISPER_MODEL=whisper-large-v3
   uvicorn main:app --reload
   ```

## Running with Docker

1. **Build the image**

   ```bash
   docker build -t transcribe-api:latest .
   ```

2. **Run the container**

   ```bash
   docker run -p 8080:8080 \
     -e WHISPER_BASE_URL=http://host.docker.internal:11434/v1 \
     transcribe-api:latest
   ```

## Deploying on OpenShift

### Prerequisites

- `oc` CLI installed and logged in to your cluster

### Steps

1. **Create a BuildConfig using OpenShift's Docker build strategy**

   ```bash
   oc new-build --binary --strategy=docker --name=transcribe-api
   ```

2. **Build the image from local source**

   Run this from the `transcribe-api/` directory. OpenShift builds the image using the `Dockerfile` and stores it in the internal registry.

   ```bash
   oc start-build transcribe-api --from-dir=. --follow
   ```

   Re-run this command whenever you want to deploy a new version.

3. **Set your Whisper endpoint URL**

   Edit the `WHISPER_BASE_URL` env var in `openshift.yaml`, or override it after deploying:

   ```bash
   oc set env deployment/transcribe-api WHISPER_BASE_URL=http://my-whisper-service:8000/v1

   oc set env deployment/transcribe-api MONGO_URI=mongodb://mongodb:27017 
   ```

4. **Apply the manifest**

   Update `openshift.yaml` to reference the internal image stream built in step 2:

   ```yaml
   image: image-registry.openshift-image-registry.svc:5000/<your-namespace>/transcribe-api:latest
   ```

   Then apply:

   ```bash
   oc apply -f openshift.yaml
   ```

   This creates a `Deployment`, `Service`, and a TLS-terminated `Route`.

5. **Get the public URL**

   ```bash
   oc get route transcribe-api
   ```

6. **Test the deployment**

   ```bash
   curl -X POST https://<route-host>/transcribe \
     -F "file=@/path/to/audio.mp3"
   ```

### Using an API key (optional)

If your Whisper endpoint requires authentication, create a secret and reference it in the deployment:

```bash
oc create secret generic whisper-secret --from-literal=api-key=<your-key>
```

Then uncomment the `WHISPER_API_KEY` secret reference in `openshift.yaml` and re-apply.
