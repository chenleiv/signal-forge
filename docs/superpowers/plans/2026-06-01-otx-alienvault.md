# OTX AlienVault Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich IP investigation with real OTX AlienVault threat intelligence — a summary accordion in the existing drawer and a full-detail page at `/threats/ip/:ip`.

**Architecture:** New backend endpoint `GET /api/ip/{ip}/otx` fetches from OTX API (cached in memory). Frontend adds `fetchOtxData()` to `ThreatStoreService`, a new accordion to the drawer, and a new `IpDetailComponent` routed at `threats/ip/:ip`.

**Tech Stack:** Python httpx (backend), Angular 21 signals, standalone components, Angular Router lazy load

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/main.py` | Modify | Add `OTX_API_KEY`, `_otx_cache`, `_fetch_otx()`, `GET /api/ip/{ip}/otx` endpoint |
| `backend/tests/test_otx.py` | Create | Tests for OTX fetch and endpoint fallback |
| `frontend/src/app/shared/models/threat.models.ts` | Modify | Add `OtxPulse`, `OtxData` interfaces |
| `frontend/src/app/core/services/threat-store.service.ts` | Modify | Add `fetchOtxData(ip)` method |
| `frontend/src/app/features/threats/threat-detail-drawer/threat-detail-drawer.component.ts` | Modify | Add `otxData` signal, fetch in effect, `otxOpen` accordion signal |
| `frontend/src/app/features/threats/threat-detail-drawer/threat-detail-drawer.component.html` | Modify | Add OTX accordion section with "View all →" button |
| `frontend/src/app/features/threats/ip-detail/ip-detail.component.ts` | Create | Full OTX detail page |
| `frontend/src/app/features/threats/ip-detail/ip-detail.component.html` | Create | Full OTX detail page template |
| `frontend/src/app/features/threats/ip-detail/ip-detail.component.scss` | Create | Styles for full detail page |
| `frontend/src/app/app.routes.ts` | Modify | Add `threats/ip/:ip` lazy route |

---

## Task 1: Backend — OTX endpoint

**Files:**
- Modify: `backend/main.py`
- Create: `backend/tests/test_otx.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_otx.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_fetch_otx_returns_data(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "OTX_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "pulse_info": {
            "count": 3,
            "pulses": [
                {"name": "APT28 C2", "tags": ["apt", "c2"], "author": {"username": "researcher1"}, "created": "2024-01-01T00:00:00"},
                {"name": "Cobalt Strike", "tags": ["cobalt"], "author": {"username": "researcher2"}, "created": "2024-01-02T00:00:00"},
            ]
        },
        "reputation": 2,
        "malware_families": [{"display_name": "CobaltStrike"}, {"id": "emotet"}],
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    result = await m._fetch_otx(mock_client, "1.2.3.4")

    assert result is not None
    assert result["pulse_count"] == 3
    assert result["reputation"] == 2
    assert len(result["pulses"]) == 2
    assert result["pulses"][0]["name"] == "APT28 C2"
    assert result["pulses"][0]["tags"] == ["apt", "c2"]
    assert "CobaltStrike" in result["malware_families"]


@pytest.mark.asyncio
async def test_fetch_otx_returns_none_on_error(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "OTX_API_KEY", "test-key")

    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("network error")

    result = await m._fetch_otx(mock_client, "1.2.3.4")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_otx_returns_empty_when_no_key(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "OTX_API_KEY", "")

    mock_client = AsyncMock()
    result = await m._fetch_otx(mock_client, "1.2.3.4")

    assert result == {"pulse_count": 0, "reputation": 0, "pulses": [], "malware_families": []}
    mock_client.get.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/chenleiv/threatwatcher/backend && /Users/chenleiv/threatwatcher/backend/venv/bin/python -m pytest tests/test_otx.py -v
```

Expected: FAIL — `AttributeError: module 'main' has no attribute '_fetch_otx'`

- [ ] **Step 3: Add OTX_API_KEY, _otx_cache, _fetch_otx to main.py**

After the existing `GROQ_API_KEY` line (around line 39), add:

```python
OTX_API_KEY = os.environ.get("OTX_API_KEY", "")
_otx_cache: dict[str, dict] = {}
```

After the existing `_fetch_ipinfo` function (around line 79), add:

```python
async def _fetch_otx(client: httpx.AsyncClient, ip: str) -> dict | None:
    if not OTX_API_KEY:
        return {"pulse_count": 0, "reputation": 0, "pulses": [], "malware_families": []}
    try:
        r = await client.get(
            f"https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/general",
            headers={"X-OTX-API-KEY": OTX_API_KEY},
            timeout=8.0,
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

- [ ] **Step 4: Add GET /api/ip/{ip}/otx endpoint to main.py**

After the existing `GET /api/ip/{ip}/geo` endpoint (around line 810), add:

```python
@app.get("/api/ip/{ip}/otx")
@limiter.limit("30/minute")
async def get_ip_otx(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
    if ip in _otx_cache:
        return _otx_cache[ip]
    async with httpx.AsyncClient() as client:
        result = await _fetch_otx(client, ip)
    if result is None:
        result = {"pulse_count": 0, "reputation": 0, "pulses": [], "malware_families": []}
    _otx_cache[ip] = result
    return result
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/chenleiv/threatwatcher/backend && /Users/chenleiv/threatwatcher/backend/venv/bin/python -m pytest tests/ -v
```

Expected: All 10 tests PASS (7 existing + 3 new OTX tests)

- [ ] **Step 6: Add OTX_API_KEY to .env**

Append to `backend/.env`:
```
OTX_API_KEY=<your key from otx.alienvault.com>
```

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/tests/test_otx.py backend/.env
git commit -m "feat: OTX AlienVault endpoint GET /api/ip/{ip}/otx"
```

---

## Task 2: Frontend models + store method

**Files:**
- Modify: `frontend/src/app/shared/models/threat.models.ts`
- Modify: `frontend/src/app/core/services/threat-store.service.ts`

- [ ] **Step 1: Add OtxPulse and OtxData to threat.models.ts**

Append at the end of `frontend/src/app/shared/models/threat.models.ts`:

```typescript
export interface OtxPulse {
  name: string;
  tags: string[];
  author: string;
  created: string;
}

export interface OtxData {
  pulse_count: number;
  reputation: number;
  pulses: OtxPulse[];
  malware_families: string[];
}
```

- [ ] **Step 2: Add fetchOtxData to ThreatStoreService**

In `frontend/src/app/core/services/threat-store.service.ts`, after the existing `fetchIpGeo` method, add:

```typescript
fetchOtxData(ip: string) {
  return this.http.get<OtxData>(`/api/ip/${encodeURIComponent(ip)}/otx`);
}
```

Also add `OtxData` to the import from `threat.models.ts` at the top of the file.

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/chenleiv/threatwatcher/frontend && npx tsc --noEmit 2>&1
```

Expected: no output (no errors)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/shared/models/threat.models.ts frontend/src/app/core/services/threat-store.service.ts
git commit -m "feat: add OtxData model and fetchOtxData store method"
```

---

## Task 3: Drawer — OTX accordion

**Files:**
- Modify: `frontend/src/app/features/threats/threat-detail-drawer/threat-detail-drawer.component.ts`
- Modify: `frontend/src/app/features/threats/threat-detail-drawer/threat-detail-drawer.component.html`

- [ ] **Step 1: Add otxData signal and otxOpen to the component**

In `threat-detail-drawer.component.ts`, in the public signals section, add after `existingCaseId`:

```typescript
otxData = signal<OtxData | null>(null);
otxOpen = signal(false);
```

Add `OtxData` to the import from `threat.models.ts`.

- [ ] **Step 2: Reset otxData in the effect and fetch it**

In the existing `effect()` in the constructor, after `this.existingCaseId.set(null)`, add:

```typescript
this.otxData.set(null);
this.otxOpen.set(false);
```

After the existing `getIpCase` subscription block, add:

```typescript
// OTX threat intelligence
this.store.fetchOtxData(ip)
  .pipe(takeUntilDestroyed(this.destroyRef))
  .subscribe({ next: d => this.otxData.set(d), error: () => {} });
```

- [ ] **Step 3: Add OTX accordion to the template**

In `threat-detail-drawer.component.html`, after the ABUSEIPDB INTEL section (after the closing `}` of `@if (abuseConfidence !== undefined)`), add:

```html
@if (otxData() && otxData()!.pulse_count > 0) {
  <div class="section">
    <button class="section-toggle" (click)="otxOpen.update(v => !v)">
      <span class="section-title">THREAT INTEL (OTX)</span>
      <span class="toggle-chevron" [class.open]="otxOpen()">›</span>
    </button>
    @if (otxOpen()) {
      <div class="otx-summary">
        <div class="otx-header-row">
          <span class="otx-rep-badge"
            [class.rep-malicious]="otxData()!.reputation === 2"
            [class.rep-suspicious]="otxData()!.reputation === 1"
            [class.rep-clean]="otxData()!.reputation === 0">
            {{ otxData()!.reputation === 2 ? '🔴 Malicious' : otxData()!.reputation === 1 ? '🟡 Suspicious' : '🟢 Clean' }}
          </span>
          <span class="otx-count">{{ otxData()!.pulse_count }} pulses</span>
          <a class="otx-view-all" [routerLink]="['/threats/ip', ip()]">View all →</a>
        </div>
        @for (pulse of otxData()!.pulses.slice(0, 2); track pulse.name) {
          <div class="otx-pulse">
            <span class="otx-pulse-name">{{ pulse.name }}</span>
            <div class="otx-tags">
              @for (tag of pulse.tags.slice(0, 3); track tag) {
                <span class="otx-tag">#{{ tag }}</span>
              }
            </div>
          </div>
        }
        @if (otxData()!.pulse_count > 2) {
          <span class="otx-more">+ {{ otxData()!.pulse_count - 2 }} more pulses</span>
        }
      </div>
    }
  </div>
}
```

- [ ] **Step 4: Add RouterLink to drawer imports**

In `threat-detail-drawer.component.ts`, add `RouterLink` to the `imports` array:

```typescript
imports: [DatePipe, NgClass, RouterLink],
```

Also import `RouterLink` from `@angular/router`.

- [ ] **Step 5: Add OTX styles to drawer SCSS**

In `threat-detail-drawer.component.scss`, append:

```scss
.otx-summary { display: flex; flex-direction: column; gap: 8px; padding: 8px 0; }

.otx-header-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}

.otx-rep-badge {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
  &.rep-malicious { background: #ef444418; color: #ef4444; }
  &.rep-suspicious { background: #f59e0b18; color: #f59e0b; }
  &.rep-clean { background: #22c55e18; color: #22c55e; }
}

.otx-count { font-size: 11px; color: #6b7280; }

.otx-view-all {
  margin-left: auto; font-size: 11px; color: #3b82f6;
  text-decoration: none; cursor: pointer;
  &:hover { text-decoration: underline; }
}

.otx-pulse {
  background: #0d1117; border: 1px solid #1e2a3a; border-radius: 6px;
  padding: 8px 10px; display: flex; flex-direction: column; gap: 4px;
}

.otx-pulse-name { font-size: 12px; color: #e5e7eb; font-weight: 500; }

.otx-tags { display: flex; flex-wrap: wrap; gap: 4px; }

.otx-tag {
  font-size: 10px; color: #60a5fa; background: #1e3a5f22;
  padding: 1px 5px; border-radius: 3px;
}

.otx-more { font-size: 11px; color: #4b5563; padding: 2px 0; }
```

- [ ] **Step 6: TypeScript check**

```bash
cd /Users/chenleiv/threatwatcher/frontend && npx tsc --noEmit 2>&1
```

Expected: no output

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/features/threats/threat-detail-drawer/
git commit -m "feat: OTX accordion in threat detail drawer"
```

---

## Task 4: IpDetailComponent — full OTX page

**Files:**
- Create: `frontend/src/app/features/threats/ip-detail/ip-detail.component.ts`
- Create: `frontend/src/app/features/threats/ip-detail/ip-detail.component.html`
- Create: `frontend/src/app/features/threats/ip-detail/ip-detail.component.scss`
- Modify: `frontend/src/app/app.routes.ts`

- [ ] **Step 1: Create ip-detail.component.ts**

```typescript
import {
  Component,
  inject,
  signal,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { DatePipe, Location } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../../core/services/threat-store.service';
import { OtxData } from '../../../shared/models/threat.models';

@Component({
  selector: 'app-ip-detail',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './ip-detail.component.html',
  styleUrl: './ip-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IpDetailComponent {
  // ── public signals ────────────────────────────────────────────
  ip      = signal('');
  otxData = signal<OtxData | null>(null);
  loading = signal(true);

  // ── private injections ────────────────────────────────────────
  private readonly store      = inject(ThreatStoreService);
  private readonly route      = inject(ActivatedRoute);
  private readonly router     = inject(Router);
  private readonly location   = inject(Location);
  private readonly destroyRef = inject(DestroyRef);

  // ── constructor ───────────────────────────────────────────────
  constructor() {
    const ipParam = this.route.snapshot.paramMap.get('ip') ?? '';
    this.ip.set(ipParam);

    if (!ipParam) {
      this.router.navigate(['/threats']);
      return;
    }

    this.store.fetchOtxData(ipParam)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next:  d => { this.otxData.set(d); this.loading.set(false); },
        error: () => this.loading.set(false),
      });
  }

  // ── public methods ────────────────────────────────────────────
  back() { this.location.back(); }

  reputationLabel(rep: number): string {
    if (rep === 2) return '🔴 Malicious';
    if (rep === 1) return '🟡 Suspicious';
    return '🟢 Clean';
  }

  reputationClass(rep: number): string {
    if (rep === 2) return 'rep-malicious';
    if (rep === 1) return 'rep-suspicious';
    return 'rep-clean';
  }
}
```

- [ ] **Step 2: Create ip-detail.component.html**

```html
<div class="ip-detail-page">

  <div class="page-header">
    <button class="back-btn" (click)="back()">← Back</button>
    <div class="header-info">
      <span class="ip-address mono">{{ ip() }}</span>
      @if (otxData()) {
        <span class="rep-badge" [class]="reputationClass(otxData()!.reputation)">
          {{ reputationLabel(otxData()!.reputation) }}
        </span>
        <span class="pulse-count">{{ otxData()!.pulse_count }} pulses</span>
      }
    </div>
  </div>

  @if (loading()) {
    <div class="loading-state">Loading OTX threat intelligence…</div>
  }

  @if (!loading() && otxData()) {

    @if (otxData()!.pulse_count === 0) {
      <div class="empty-state">No OTX threat intelligence found for this IP.</div>
    } @else {

      <section class="card">
        <h2 class="section-title">PULSES ({{ otxData()!.pulse_count }})</h2>
        <div class="pulse-list">
          @for (pulse of otxData()!.pulses; track pulse.name) {
            <div class="pulse-item">
              <div class="pulse-top">
                <span class="pulse-name">{{ pulse.name }}</span>
                <span class="pulse-date">{{ pulse.created | date:'MMM d, y' }}</span>
              </div>
              <div class="pulse-meta">
                <span class="pulse-author">by {{ pulse.author }}</span>
                <div class="pulse-tags">
                  @for (tag of pulse.tags; track tag) {
                    <span class="tag">#{{ tag }}</span>
                  }
                </div>
              </div>
            </div>
          }
        </div>
      </section>

      @if (otxData()!.malware_families.length > 0) {
        <section class="card">
          <h2 class="section-title">MALWARE FAMILIES</h2>
          <div class="family-list">
            @for (family of otxData()!.malware_families; track family) {
              <span class="family-chip">{{ family }}</span>
            }
          </div>
        </section>
      }

    }
  }

</div>
```

- [ ] **Step 3: Create ip-detail.component.scss**

```scss
.ip-detail-page {
  padding: 24px 32px;
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.back-btn {
  background: none;
  border: 1px solid #1e2a3a;
  color: #9ca3af;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  &:hover { color: #e5e7eb; border-color: #3b82f6; }
}

.header-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

.ip-address { font-size: 20px; color: #e5e7eb; font-weight: 600; }

.rep-badge {
  font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 4px;
  &.rep-malicious { background: #ef444418; color: #ef4444; }
  &.rep-suspicious { background: #f59e0b18; color: #f59e0b; }
  &.rep-clean { background: #22c55e18; color: #22c55e; }
}

.pulse-count { font-size: 13px; color: #6b7280; }

.card {
  background: #0d1117;
  border: 1px solid #1e2a3a;
  border-radius: 10px;
  padding: 20px;
}

.section-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #4b5563;
  margin: 0 0 16px;
}

.pulse-list { display: flex; flex-direction: column; gap: 12px; }

.pulse-item {
  background: #080d14;
  border: 1px solid #1a2332;
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pulse-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.pulse-name { font-size: 13px; color: #e5e7eb; font-weight: 500; flex: 1; }
.pulse-date { font-size: 11px; color: #4b5563; white-space: nowrap; }

.pulse-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pulse-author { font-size: 11px; color: #6b7280; }

.pulse-tags { display: flex; flex-wrap: wrap; gap: 4px; }

.tag {
  font-size: 10px;
  color: #60a5fa;
  background: #1e3a5f22;
  padding: 2px 6px;
  border-radius: 3px;
}

.family-list { display: flex; flex-wrap: wrap; gap: 8px; }

.family-chip {
  background: #ef444418;
  color: #ef4444;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 12px;
  border-radius: 6px;
}

.loading-state, .empty-state {
  text-align: center;
  color: #4b5563;
  padding: 40px;
  font-size: 14px;
}

.mono { font-family: 'JetBrains Mono', monospace; }
```

- [ ] **Step 4: Add route to app.routes.ts**

In `frontend/src/app/app.routes.ts`, inside the `children` array after the `threats` route, add:

```typescript
{
  path: 'threats/ip/:ip',
  loadComponent: () =>
    import('./features/threats/ip-detail/ip-detail.component').then(m => m.IpDetailComponent),
},
```

- [ ] **Step 5: TypeScript check**

```bash
cd /Users/chenleiv/threatwatcher/frontend && npx tsc --noEmit 2>&1
```

Expected: no output

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/features/threats/ip-detail/ frontend/src/app/app.routes.ts
git commit -m "feat: IpDetailComponent full OTX page at /threats/ip/:ip"
```

---

## Task 5: Deploy + verify

- [ ] **Step 1: Add OTX_API_KEY to Render environment**

In Render Web Service → Environment, add:
```
OTX_API_KEY=<your key from otx.alienvault.com>
```

- [ ] **Step 2: Push**

```bash
git push origin master
```

- [ ] **Step 3: Verify in the app**

1. Click any IP in the Threats table → drawer opens
2. Scroll to "THREAT INTEL (OTX)" accordion — should show pulse count + 2 pulses
3. Click "View all →" → navigates to `/threats/ip/<ip>` page
4. Full pulse list + malware families visible
5. "← Back" returns to previous page

- [ ] **Step 4: Verify fallback (no key)**

Remove `OTX_API_KEY` from `.env` locally, restart backend — OTX accordion should not appear in drawer (pulse_count === 0).
