# Rule Builder — Design Spec
Date: 2026-05-31

## Overview

A detection rule engine that lets SOC analysts define conditions on incoming threat events. When a rule matches, the backend automatically executes actions (create alert, create incident, block IP). Rules are managed via a dedicated UI page and evaluated server-side on every WebSocket-generated event.

---

## Data Model

### Rule (backend + frontend)

```python
# backend
{
  "id": str,              # uuid4[:8]
  "name": str,
  "enabled": bool,
  "conditions": [
    {
      "field": "score" | "attack_type" | "region" | "ip",
      "operator": ">" | "<" | "=" | "contains",
      "value": str | int
    }
  ],
  "logic": "AND" | "OR",
  "actions": ["alert"] | ["alert", "incident"] | ["alert", "incident", "block"],
  "created_at": str,      # ISO
  "match_count": int
}
```

```typescript
// frontend — threat.models.ts additions
export interface RuleCondition {
  field: 'score' | 'attack_type' | 'region' | 'ip';
  operator: '>' | '<' | '=' | 'contains';
  value: string | number;
}

export type RuleAction = 'alert' | 'incident' | 'block';

export interface DetectionRule {
  id: string;
  name: string;
  enabled: boolean;
  conditions: RuleCondition[];
  logic: 'AND' | 'OR';
  actions: RuleAction[];
  created_at: string;
  match_count: number;
}
```

---

## Backend

### Storage
```python
_rules: list[dict] = []
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/rules` | List all rules |
| POST | `/api/rules` | Create a new rule |
| PATCH | `/api/rules/{id}` | Update rule (name, enabled, conditions, logic, actions) |
| DELETE | `/api/rules/{id}` | Delete rule |

All endpoints require `Depends(verify_token)`.

### Rule Evaluation Engine

Called inside `_record_event(event)` after the event is stored. Iterates all enabled rules:

```python
def _evaluate_rules(event: dict) -> None:
    for rule in _rules:
        if not rule["enabled"]:
            continue
        if _rule_matches(rule, event):
            rule["match_count"] += 1
            _execute_actions(rule, event)

def _rule_matches(rule: dict, event: dict) -> bool:
    results = [_eval_condition(c, event) for c in rule["conditions"]]
    return all(results) if rule["logic"] == "AND" else any(results)

def _eval_condition(cond: dict, event: dict) -> bool:
    field = cond["field"]
    op    = cond["operator"]
    val   = cond["value"]
    ev    = event.get(field)
    if op == ">":       return int(ev) > int(val)
    if op == "<":       return int(ev) < int(val)
    if op == "=":       return str(ev) == str(val)
    if op == "contains": return str(val).lower() in str(ev).lower()
    return False
```

### Actions

```python
def _execute_actions(rule: dict, event: dict) -> None:
    if "alert" in rule["actions"]:
        _alerts_store.appendleft({...})   # reuse existing alerts store
    if "incident" in rule["actions"]:
        _create_incident(event)
    if "block" in rule["actions"]:
        _blocked_ips.add(event["ip"])
```

---

## Frontend

### New Files
- `features/rules/rules.component.ts`
- `features/rules/rules.component.html`
- `features/rules/rules.component.scss`

### New Route
`/rules` → lazy-loaded `RulesComponent`

### New Nav Item
Sidebar under OPERATIONS, between Threat Hunting and Settings.

### New Service Methods (threat-store.service.ts)
```typescript
getRules()
createRule(rule: Partial<DetectionRule>)
updateRule(id: string, patch: Partial<DetectionRule>)
deleteRule(id: string)
```

### UI Layout

Two-panel layout (similar to Threat Hunting):

**Left panel — Rules list**
- Each row: toggle (enabled/disabled), rule name, match count, delete button
- Click row → load into editor on right
- "New Rule" button → blank editor

**Right panel — Rule editor**
- Name input
- Logic selector: AND / OR
- Conditions list (visual builder rows):
  - Each row: `[field ▼] [operator ▼] [value input] [× remove]`
  - `[+ Add Condition]` button
- Actions checkboxes: Alert / Incident / Block
- Query preview (read-only computed string):
  - `score>75 AND region=RU AND attack_type=BruteForce`
  - Generated from conditions array — no parsing needed, only serialization
- Save / Cancel buttons

### Query Preview Logic

The preview is **one-directional**: conditions array → string. No parsing in the other direction (keeping scope tight).

```typescript
readonly queryPreview = computed(() => {
  const parts = this.conditions().map(c => `${c.field}${c.operator}${c.value}`);
  return parts.join(` ${this.logic()} `);
});
```

This still demonstrates real-time derived state from structured data, which is the impressive part — the full bidirectional parser was descoped to keep implementation focused.

---

## Action Severity Defaults

Pre-selected actions by severity (UX hint, not enforced):
- score < 40 → Alert only
- score 40-79 → Alert + Incident
- score ≥ 80 → Alert + Incident + Block

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/main.py` | Add `_rules`, 4 endpoints, `_evaluate_rules`, `_execute_actions` |
| `shared/models/threat.models.ts` | Add `RuleCondition`, `RuleAction`, `DetectionRule` |
| `core/services/threat-store.service.ts` | Add 4 rule methods |
| `app.routes.ts` | Add `/rules` lazy route |
| `layout/app-layout/app-layout.html` | Add Rules nav item |
| `features/rules/` | New component (3 files) |
