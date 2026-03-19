# CLAUDE.md

## Project Overview

React + Vite frontend for the ATC Transcript Analyzer. Supervisors use this dashboard to upload shift audio, trigger transcription and AI analysis, and review findings against FAA AIM procedures.

## Project Structure

```
web-ui/
├── src/
│   ├── main.jsx          # Entry point; wraps app in BrowserRouter
│   ├── App.jsx           # Top-level layout and routes
│   ├── index.css         # Global dark theme; CSS custom properties
│   ├── api.js            # Fetch-based client for atc-api
│   └── pages/
│       ├── ShiftList.jsx     # Main shift list with filters, pagination, batch analyze
│       ├── UploadShift.jsx   # Audio file upload form
│       └── ShiftDetail.jsx   # Analysis results + transcript viewer (tabbed)
├── index.html
├── vite.config.js        # Dev proxy to atc-api; build config
├── nginx.conf            # SPA fallback; served on port 8080
├── Dockerfile            # Multi-stage: Node build → nginx serve
├── openshift.yaml        # Deployment + Service + Route
└── README.md
```

## Key Design Decisions

- **Single-file pages** — each screen is one file in `src/pages/`. Do not break into sub-components unless the file grows substantially.
- **No UI framework** — styling is done with plain CSS variables in `index.css`. Do not add Tailwind, MUI, or similar.
- **Fetch only** — `api.js` uses the native `fetch` API. Do not add axios or react-query.
- **No global state** — each page manages its own state with `useState`/`useEffect`. Do not add Redux or Zustand.
- **API URL at build time** — `VITE_API_URL` is baked in by Vite. In dev, Vite proxies `/api` to the backend; in production, set the env var at `docker build` time or via an `oc start-build` build arg.
- **Port 8080** — nginx listens on 8080 for OpenShift compatibility.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `/api` (proxied in dev) | Backend base URL, baked in at build time |

## Running Locally

```bash
npm install
npm run dev   # http://localhost:3000
```

Requires `atc-api` running at `http://localhost:8000` (configured in `vite.config.js` proxy).

## What to Avoid

- Do not add a CSS framework or component library.
- Do not add client-side routing beyond the three existing pages without a clear user need.
- Do not store auth tokens or sensitive data in `localStorage`.
- Do not change the nginx port away from 8080.
