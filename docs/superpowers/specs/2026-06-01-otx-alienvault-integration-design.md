# OTX AlienVault Integration — Design Spec
Date: 2026-06-01

## Goal

Enrich IP investigation with real threat intelligence from OTX AlienVault — showing pulses,
malware families, and reputation in the existing threat detail drawer and a new full-detail page.

---

## What OTX Adds

OTX (Open Threat Exchange) is a community threat intelligence platform. When given an IP,
it returns:
- **Pulses** — threat intelligence reports written by security researchers who observed this IP
- **Reputation** — automated score: 0 = clean, 1 = suspicious, 2 = malicious
- **Malware families** — malware strains associated with this IP

This is real data, unlike the simulation. It answers "who is this IP?" with actual intelligence.

---

## Part 1 — Backend

### New env var

```
OTX_API_KEY=<key from otx.alienvault.com>
```

Free account required at otx.alienvault.com. No rate limit issues for per-IP lookups.

### Fetch function

```python
OTX_API_KEY = os.getenv("OTX_API_KEY", "")
_otx_cache: dict[str, dict] = {}

async def _fetch_otx(client: httpx.AsyncClient, ip: str) -> dict | None:
    try:
        r = await client.get(
            f"https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/general",
            headers={"X-OTX-API-KEY": OTX_API_KEY},
            timeout=8.0
        )
        r.raise_for_status()
        data = r.json()
        pulse_info = data.get("pulse_info", {})
        pulses_raw = pulse_info.get("pulses", [])
        return {
            "pulse_count": pulse_info.get("count", 0),
            "reputation": data.get("reputation", 0),
            "pulses": [
                {
                    "name":    p.get("name", ""),
                    "tags":    p.get("tags", [])[:5],
                    "author":  p.get("author", {}).get("username", ""),
                    "created": p.get("created", ""),
                }
                for p in pulses_raw[:10]
            ],
            "malware_families": [
                m.get("display_name", m.get("id", ""))
                for m in data.get("malware_families", [])
            ][:5],
        }
    except Exception:
        return None
```

### New endpoint

```
GET /api/ip/{ip}/otx
```

- Requires auth token
- Returns cached result if available
- If `OTX_API_KEY` is empty → returns `{"pulse_count": 0, "pulses": [], "malware_families": [], "reputation": 0}`
- Rate limit: 30/minute (same as other IP endpoints)

### Response shape

```json
{
  "pulse_count": 14,
  "reputation": 2,
  "pulses": [
    {
      "name": "Cobalt Strike C2 Servers",
      "tags": ["c2", "apt", "cobalt-strike"],
      "author": "AlienVault",
      "created": "2024-11-03T12:00:00"
    }
  ],
  "malware_families": ["CobaltStrike", "Emotet"]
}
```

---

## Part 2 — Frontend

### New model

Add to `threat.models.ts`:

```typescript
export interface OtxPulse {
  name: string;
  tags: string[];
  author: string;
  created: string;
}

export interface OtxData {
  pulse_count: number;
  reputation: number;       // 0=clean, 1=suspicious, 2=malicious
  pulses: OtxPulse[];
  malware_families: string[];
}
```

### ThreatStoreService — new method

```typescript
fetchOtxData(ip: string) {
  return this.http.get<OtxData>(`/api/ip/${encodeURIComponent(ip)}/otx`);
}
```

### ThreatDetailDrawerComponent — new accordion

New signal: `otxData = signal<OtxData | null>(null)`

Fetched alongside geo/history in the existing `effect()` when IP changes.

Accordion label: **THREAT INTEL (OTX)**

Content:
- Reputation badge: 🔴 Malicious / 🟡 Suspicious / 🟢 Clean
- Pulse count
- Top 2 pulse names + tags
- "View all →" link → navigates to `/threats/ip/:ip`

If `pulse_count === 0` and no key configured: show "No OTX data available"

### New component: IpDetailComponent

Route: `/threats/ip/:ip`

File: `frontend/src/app/features/threats/ip-detail/ip-detail.component.ts`

Fetches OTX data for the IP from route params. Displays:

**Header:** IP address + reputation badge + pulse count

**Pulses section:** list of all pulses
- Name (bold)
- Tags as chips
- Author + formatted date

**Malware Families section:** horizontal tag list (only if non-empty)

**Back button:** navigates back with `location.back()`

---

## New route

Add to `app.routes.ts`:

```typescript
{ path: 'threats/ip/:ip', component: IpDetailComponent }
```

---

## Fallback behavior

- No `OTX_API_KEY` → endpoint returns zeroed response, drawer shows "No OTX data"
- API error / timeout → same as no key, no crash
- Empty pulses → drawer accordion hidden (not shown if pulse_count === 0)

---

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `OTX_API_KEY` | No | Free at otx.alienvault.com. Without it, feature is silently disabled. |

---

## Out of scope

- Passive DNS data (separate OTX endpoint)
- URL/domain OTX lookups
- Saving OTX data to DB (it's always fetched live + cached in memory)
