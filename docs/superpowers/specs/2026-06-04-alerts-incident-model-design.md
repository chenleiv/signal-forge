# SignalForge — Alerts & Incident Model Redesign
**Date:** 2026-06-04  
**Status:** Approved

---

## Problem

The current system has two noise problems:

1. **Incidents** — created automatically every ~60 seconds by `_behavioral_loop()` and on every rule match. The `deque(maxlen=50)` fills instantly with auto-generated records, making user-created cases invisible.
2. **Alerts** — currently mirrors the raw WebSocket event feed. Thousands of rows, no meaningful signal, indistinguishable from the Live SOC Stream on the dashboard.

In a real SOC, the pyramid is:

```
Raw Events   ████████████████████  thousands/day  (dashboard feed)
Alerts       ████████              tens/day        (anomalies worth reviewing)
Incidents    ██                   handful          (cases being actively worked)
```

---

## New Model

Three distinct layers with clear ownership:

| Layer | Source | Store | Lifetime |
|-------|--------|-------|---------|
| **Live SOC Stream** | WebSocket events | frontend signal (buffer) | session only |
| **Alerts** | Behavioral detection + Rule `alert` action | `alerts_store` deque(100) | server lifetime |
| **Incidents** | User action + Rule `incident` action | DB (PostgreSQL) or deque(50) | persistent |

---

## What Creates an Alert

- `_behavioral_loop()` — RepeatedIP (≥8 events in 10 min) → Alert
- `_behavioral_loop()` — Escalation (recent avg 20+ above overall avg) → Alert
- Rule Builder rule with `action = "alert"` fires → Alert

## What Creates an Incident

- User clicks **"Create Case"** from the IP detail drawer
- User clicks **"Create Case"** from within an Alert
- Rule Builder rule with `action = "incident"` fires → Incident

## What Stops

- `_behavioral_loop()` no longer calls `_create_incident()`
- `_execute_actions()` routes `action="alert"` to `_create_alert()` instead of `_create_incident()`
- The Alerts component no longer subscribes to the WebSocket feed

---

## Alert Data Model

```python
{
  "id": "ALT-0001",              # sequential counter, format ALT-NNNN
  "source": "behavioral",        # "behavioral" | "rule"
  "type": "RepeatedIP",          # "RepeatedIP" | "Escalation" | rule name string
  "severity": "high",            # critical | high | medium | low
  "ip": "1.2.3.4",              # source IP (may be null for rule alerts with no ip condition)
  "message": "IP fired 12 events in 10 min",
  "status": "new",               # new | acknowledged | dismissed
  "created_at": "<iso>",
  "acknowledged_at": null        # iso timestamp or null
}
```

TypeScript interface added to `threat.models.ts`:

```typescript
export type AlertStatus = 'new' | 'acknowledged' | 'dismissed';
export type AlertSource = 'behavioral' | 'rule';

export interface ThreatAlert {
  id: string;
  source: AlertSource;
  type: string;
  severity: ThreatLevel;
  ip: string | null;
  message: string;
  status: AlertStatus;
  created_at: string;
  acknowledged_at: string | null;
}
```

---

## Backend Changes (`main.py`)

### New Store

```python
alerts_store: deque = deque(maxlen=100)
_alert_counter: int = 0
```

### New Factory

```python
def _create_alert(source: str, type: str, severity: str, ip: str | None, message: str) -> dict:
    global _alert_counter
    _alert_counter += 1
    now = datetime.now(timezone.utc).isoformat()
    alert = {
        "id": f"ALT-{_alert_counter:04d}",
        "source": source,
        "type": type,
        "severity": severity,
        "ip": ip,
        "message": message,
        "status": "new",
        "created_at": now,
        "acknowledged_at": None,
    }
    alerts_store.appendleft(alert)
    return alert
```

### Modified: `_behavioral_loop()`

RepeatedIP and Escalation detections call `_create_alert()` instead of `_create_incident()`:

```python
# RepeatedIP
_create_alert(
    source="behavioral",
    type="RepeatedIP",
    severity="high",
    ip=ip,
    message=f"{ip} fired {len(recent)} events in 10 min (dominant: {dominant})",
)

# Escalation
_create_alert(
    source="behavioral",
    type="Escalation",
    severity="critical",
    ip=ip,
    message=f"{ip} score escalated: overall avg {int(overall_avg)} → recent avg {int(recent_avg)}",
)
```

### Modified: `_execute_actions()`

```python
def _execute_actions(rule: dict, event: dict) -> None:
    if "incident" in rule["actions"]:
        _create_incident(event)
    if "alert" in rule["actions"]:
        _create_alert(
            source="rule",
            type=rule["name"],
            severity=event.get("threat_level", "medium"),
            ip=event.get("ip"),
            message=f"Rule '{rule['name']}' matched on {event.get('ip', 'unknown')}",
        )
    if "block" in rule["actions"]:
        _blocked_ips.add(event["ip"])
```

### New Endpoints

```
GET  /api/alerts
```
Returns all alerts where `status != "dismissed"`. Ordered newest-first.
Query param: `?include_dismissed=true` to include dismissed (future use).

```
PATCH /api/alerts/{alert_id}
Body: { "status": "acknowledged" | "dismissed" }
```
Updates the alert's `status` field. If acknowledging, sets `acknowledged_at` to now.

```
POST /api/alerts/{alert_id}/case
```
Finds the alert by id, creates an Incident from its IP (calls the same logic as `create_incident_from_ip`), returns the created incident. If alert has no IP, returns 400.

### Helper

```python
def _find_alert(alert_id: str) -> dict | None:
    return next((a for a in alerts_store if a["id"] == alert_id), None)
```

---

## Frontend Changes

### `ThreatStoreService` — new state + methods

```typescript
// new signal — single source of truth for all alerts
readonly alerts = signal<ThreatAlert[]>([]);

readonly newAlertCount = computed(
  () => this.alerts().filter(a => a.status === 'new').length
);

fetchAlerts() {
  return this.http.get<ThreatAlert[]>('/api/alerts');
}
acknowledgeAlert(id: string) {
  return this.http.patch<ThreatAlert>(`/api/alerts/${id}`, { status: 'acknowledged' });
}
dismissAlert(id: string) {
  return this.http.patch<ThreatAlert>(`/api/alerts/${id}`, { status: 'dismissed' });
}
createCaseFromAlert(id: string) {
  return this.http.post<Incident>(`/api/alerts/${id}/case`, {});
}
```

### `ThreatsService` — extend `connect()` polling

Alerts polling is added alongside the existing stats poll so the sidebar badge stays current on every page, not just when `AlertsComponent` is mounted:

```typescript
// inside connect(), next to the existing statsSub:
this.alertSub = timer(0, 15_000).pipe(
  switchMap(() => this.store.fetchAlerts().pipe(catchError(() => EMPTY))),
).subscribe(alerts => this.store.alerts.set(alerts));
```

`disconnect()` cancels `alertSub` alongside `statsSub`.

### `AlertsComponent` — redesign

**Data source:** reads `store.alerts` signal directly — no local polling, no WebSocket subscription. Polling happens in `ThreatsService`.

**Row layout per alert:**
- Severity color dot
- `source` chip — `BEHAVIORAL` (amber) / `RULE` (blue)
- `type` label (RepeatedIP / Escalation / rule name)
- `message` text
- Relative timestamp
- Three action buttons: **Acknowledge** · **Create Case** · **Dismiss**

**Visual states:**
- `new` — full opacity, bold left border in severity color
- `acknowledged` — 70% opacity, ✓ icon, buttons reduced to Dismiss only
- `dismissed` — not rendered

**Filters (left panel):**
- Status: All / New / Acknowledged
- Severity: All / Critical / High / Medium / Low
- Source: All / Behavioral / Rule

**Sidebar badge:** the existing unread-count badge on the Alerts nav item shows count of `status === 'new'` alerts. Polls via `ThreatStoreService` alongside the main alert list.

---

## What Is NOT Changed

- `_create_incident()` logic — untouched
- All `/api/incidents/*` endpoints — untouched
- DB schema — no new tables, no migrations
- `incidents_store` deque — untouched
- Rule Builder UI — `alert` action was already selectable; behavior now actually fires correctly
- `_BEHAVIORAL_COOLDOWN_MIN`, `_REPEATED_EVENT_THRESHOLD`, `_ESCALATION_SCORE_DELTA` constants — untouched

---

## File Impact Summary

| File | Change |
|------|--------|
| `backend/main.py` | Add `alerts_store`, `_alert_counter`, `_create_alert()`, `_find_alert()`, 3 new endpoints; modify `_behavioral_loop()` and `_execute_actions()` |
| `frontend/src/app/shared/models/threat.models.ts` | Add `ThreatAlert`, `AlertStatus`, `AlertSource` types |
| `frontend/src/app/core/services/threat-store.service.ts` | Add `alerts` signal, `newAlertCount` computed, 4 alert methods |
| `frontend/src/app/core/services/threats.service.ts` | Add alerts poll to `connect()` / `disconnect()` |
| `frontend/src/app/features/alerts/alerts.ts` | Full redesign — reads `store.alerts` signal, new row/filter UI |
| `frontend/src/app/layout/app-layout/app-layout.ts` | Wire sidebar badge to `store.newAlertCount` |
