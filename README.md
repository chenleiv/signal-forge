# SignalForge

A real-time Security Operations Center (SOC) dashboard built with Angular 19 and FastAPI. Simulates live threat intelligence with animated attack maps, analytics charts, incident management, and alert feeds.

---

## Features

- **Live SOC Stream** — real-time threat event feed over WebSocket with severity color coding
- **Analytics Charts** — severity distribution, attack types, events-per-minute, and top attacking IPs (Apache ECharts)
- **Threat Map** — animated D3.js world map showing attack origin → target lines in real time
- **Threat Intelligence** — IP table with per-IP history drawer, MITRE ATT&CK tags, and region tracking
- **Incidents** — auto-generated incident log with status, assigned analyst, and detail drawer
- **Alerts** — live alert feed with severity filters and dismiss functionality
- **Settings** — configurable WebSocket URL, reconnect delay, buffer size, alert thresholds, and analyst profile
- **WebSocket auto-reconnect** — automatic reconnection with status indicator in the topbar

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Angular 19, standalone components, Signals |
| Charts | Apache ECharts via ngx-echarts |
| Map | D3.js v7 + topojson-client |
| Backend | FastAPI, WebSockets, uvicorn |
| Styling | SCSS, Palo Alto XSIAM design language |

---

## Project Structure

```
signalforge/
├── backend/
│   └── main.py          # FastAPI app — WebSocket, REST endpoints, in-memory store
└── frontend/
    └── src/app/
        ├── core/
        │   └── services/ # ThreatStore, Threats, Settings, Notification
        ├── shared/
        │   └── models/   # TypeScript interfaces
        ├── layout/       # AppLayout shell with sidebar and topbar
        └── features/
            ├── dashboard/     # Main dashboard with charts and stream
            ├── threat-map/    # D3 animated world map
            ├── threats/       # IP threat intelligence table + drawer
            ├── alerts/        # Live alert feed
            ├── incidents/     # Incident management
            └── settings/      # App configuration
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.9+
- Angular CLI (`npm install -g @angular/cli`)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip3 install fastapi uvicorn websockets
uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
ng serve
```

App runs on `http://localhost:4200`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| WS | `/ws/threats` | Live threat event stream |
| GET | `/api/stats` | Aggregated chart data |
| GET | `/api/incidents` | Incident list |
| GET | `/api/ip/{ip}/history` | Per-IP event history |
| GET | `/health` | Health check |

---

## Architecture

```
Browser
  └── Angular 19 (port 4200)
        ├── WebSocket → ws://localhost:8000/ws/threats   (live events)
        └── HTTP      → /api/*                           (stats, incidents, history)

FastAPI (port 8000)
  ├── WebSocket handler  → generates ~1 threat/sec, writes to in-memory store
  ├── GET /api/stats     → aggregates ip_store into chart data
  ├── GET /api/incidents → returns last 50 auto-generated incidents
  └── GET /api/ip/{ip}   → per-IP event history with MITRE tags
```

The frontend uses a central `ThreatStoreService` (Angular signals) as the single source of truth. WebSocket events are pushed into the store, and all components react to signal changes without direct component-to-component communication.
