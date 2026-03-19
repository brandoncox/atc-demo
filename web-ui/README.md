# ATC Web UI

React dashboard for the ATC Transcript Analyzer. Supervisors can upload shift audio, trigger transcription and AI analysis, and review findings.

## Screens

| Screen | Path | Description |
|---|---|---|
| Shift List | `/` | Browse, filter, and batch-analyze shifts |
| Upload Audio | `/upload` | Upload an audio file and attach shift metadata |
| Shift Detail | `/shift/:shift_id` | View analysis results and full transcript |

## Running Locally

### Prerequisites

- Node.js 20+
- `atc-api` running at `http://localhost:8000`

### Steps

```bash
cd web-ui
npm install
npm run dev
```

The app will be available at `http://localhost:3000`. API calls are proxied to `http://localhost:8000` via Vite's dev server proxy.

To point at a different backend:

```bash
VITE_API_URL=http://my-api-server:8000 npm run dev
```

## Building for Production

The API URL is baked in at build time:

```bash
VITE_API_URL=https://atc-api.example.com npm run build
# Output is in dist/
```

## Docker

```bash
docker build \
  --build-arg VITE_API_URL=https://atc-api.example.com \
  -t atc-web-ui:latest .

docker run -p 8080:8080 atc-web-ui:latest
```

## OpenShift

```bash
# Build the image in-cluster (run from the web-ui/ directory)
oc new-build --binary --strategy=docker --name=atc-web-ui \
  --build-arg VITE_API_URL=https://atc-api-route.example.com
oc start-build atc-web-ui --from-dir=. --follow

# Apply manifests
oc apply -f openshift.yaml
oc get route atc-web-ui
```

Re-run `oc start-build` whenever you want to deploy a new version.

## Backend API

The UI talks directly to [atc-api](../atc-api/README.md). Endpoints used:

| Endpoint | Purpose |
|---|---|
| `GET /shifts` | List shifts (paginated, filtered) |
| `GET /shift/:id` | Load a single shift |
| `DELETE /shift/:id` | Delete a shift |
| `POST /transcribe` | Upload audio and transcribe |
| `POST /analyze_transcript` | Run RAG analysis on a shift |
