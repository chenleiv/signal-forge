# Rule Builder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a detection rule engine — analysts define conditions on threat events; matching rules auto-create incidents, block IPs, and log hits.

**Architecture:** Rules stored in backend `_rules: list[dict]`. Every WebSocket event passes through `_evaluate_rules()` before being forwarded. Frontend has a split-panel page (`/rules`) with a rules list on the left and a visual condition builder on the right that shows a live query preview.

**Tech Stack:** FastAPI (Python 3.9), Angular 19 standalone components, signals, OnPush CD, RxJS.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/main.py` | Modify | Add `_rules` store, 4 CRUD endpoints, `_evaluate_rules`, `_execute_actions` |
| `frontend/src/app/shared/models/threat.models.ts` | Modify | Add `RuleCondition`, `RuleAction`, `DetectionRule` interfaces |
| `frontend/src/app/core/services/threat-store.service.ts` | Modify | Add `getRules`, `createRule`, `updateRule`, `deleteRule` |
| `frontend/src/app/features/rules/rules.component.ts` | Create | Full rules page logic |
| `frontend/src/app/features/rules/rules.component.html` | Create | Split-panel UI |
| `frontend/src/app/features/rules/rules.component.scss` | Create | Styling |
| `frontend/src/app/app.routes.ts` | Modify | Add `/rules` lazy route |
| `frontend/src/app/layout/app-layout/app-layout.html` | Modify | Add nav item |

---

## Task 1 — Backend: Rules store + CRUD endpoints

**File:** `backend/main.py`

- [ ] **Step 1: Add `_rules` store** — after `_saved_hunts: list[dict] = []` (around line 833):

```python
_rules: list[dict] = []
```

- [ ] **Step 2: Add the 4 CRUD endpoints** — after the hunts endpoints, before `/health`:

```python
# ── REST: detection rules ─────────────────────────────────────

@app.get("/api/rules")
async def get_rules(_=Depends(verify_token)):
    return _rules


@app.post("/api/rules")
async def create_rule(body: dict, _=Depends(verify_token)):
    rule = {
        "id": str(uuid4())[:8],
        "name": body.get("name", "Unnamed Rule"),
        "enabled": body.get("enabled", True),
        "conditions": body.get("conditions", []),
        "logic": body.get("logic", "AND"),
        "actions": body.get("actions", ["alert"]),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "match_count": 0,
    }
    _rules.append(rule)
    return rule


@app.patch("/api/rules/{rule_id}")
async def update_rule(rule_id: str, body: dict, _=Depends(verify_token)):
    for rule in _rules:
        if rule["id"] == rule_id:
            for key in ["name", "enabled", "conditions", "logic", "actions"]:
                if key in body:
                    rule[key] = body[key]
            return rule
    raise HTTPException(status_code=404, detail="Rule not found")


@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str, _=Depends(verify_token)):
    global _rules
    _rules = [r for r in _rules if r["id"] != rule_id]
    return {"ok": True}
```

- [ ] **Step 3: Verify backend starts without errors**

```bash
cd backend && uvicorn main:app --reload
```
Expected: `Application startup complete.`

---

## Task 2 — Backend: Rule evaluation engine

**File:** `backend/main.py`

- [ ] **Step 1: Add helper functions** — before `_record_event`:

```python
def _eval_condition(cond: dict, event: dict) -> bool:
    field = cond.get("field", "")
    op    = cond.get("operator", "=")
    val   = cond.get("value", "")
    ev    = event.get(field)
    if ev is None:
        return False
    if op == ">":
        try:
            return float(ev) > float(val)
        except (ValueError, TypeError):
            return False
    if op == "<":
        try:
            return float(ev) < float(val)
        except (ValueError, TypeError):
            return False
    if op == "=":
        return str(ev).lower() == str(val).lower()
    if op == "contains":
        return str(val).lower() in str(ev).lower()
    return False


def _execute_actions(rule: dict, event: dict) -> None:
    if "incident" in rule["actions"]:
        _create_incident(event)
    if "block" in rule["actions"]:
        _blocked_ips.add(event["ip"])


def _evaluate_rules(event: dict) -> None:
    for rule in _rules:
        if not rule["enabled"]:
            continue
        results = [_eval_condition(c, event) for c in rule["conditions"]]
        if not results:
            continue
        matched = all(results) if rule["logic"] == "AND" else any(results)
        if matched:
            rule["match_count"] += 1
            _execute_actions(rule, event)
```

- [ ] **Step 2: Call `_evaluate_rules` inside `_record_event`** — add at the end of `_record_event`, after `ip_store[event["ip"]].append(event)`:

```python
    _evaluate_rules(event)
```

- [ ] **Step 3: Smoke-test** — with backend running, create a rule via curl:

```bash
curl -s -X POST http://localhost:8000/api/rules \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"analyst","password":"threatwatcher"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')" \
  -d '{"name":"Test","conditions":[{"field":"score","operator":">","value":"0"}],"logic":"AND","actions":["incident"]}' | python3 -m json.tool
```
Expected: JSON with `"id"`, `"name":"Test"`, `"match_count":0`

---

## Task 3 — Frontend: Models

**File:** `frontend/src/app/shared/models/threat.models.ts`

- [ ] **Step 1: Add rule interfaces** — at the end of the file:

```typescript
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

## Task 4 — Frontend: Service methods

**File:** `frontend/src/app/core/services/threat-store.service.ts`

- [ ] **Step 1: Add imports** — add `DetectionRule, RuleCondition, RuleAction` to the existing import from `threat.models`:

```typescript
import {
  // ... existing imports ...
  DetectionRule,
} from '../../shared/models/threat.models';
```

- [ ] **Step 2: Add 4 methods** — at the end of `ThreatStoreService` class, after `deleteHunt`:

```typescript
  getRules() {
    return this.http.get<DetectionRule[]>('/api/rules');
  }

  createRule(rule: Partial<DetectionRule>) {
    return this.http.post<DetectionRule>('/api/rules', rule);
  }

  updateRule(id: string, patch: Partial<DetectionRule>) {
    return this.http.patch<DetectionRule>(`/api/rules/${id}`, patch);
  }

  deleteRule(id: string) {
    return this.http.delete<{ ok: boolean }>(`/api/rules/${id}`);
  }
```

---

## Task 5 — Frontend: RulesComponent

**Files:** Create 3 files in `frontend/src/app/features/rules/`

- [ ] **Step 1: Create `rules.component.ts`**

```typescript
import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  DestroyRef,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ThreatStoreService } from '../../core/services/threat-store.service';
import { DetectionRule, RuleCondition, RuleAction } from '../../shared/models/threat.models';

const OPERATORS: Record<string, string[]> = {
  score:       ['>', '<', '='],
  attack_type: ['='],
  region:      ['='],
  ip:          ['=', 'contains'],
};

const ATTACK_TYPES = ['SQLi', 'DDoS', 'BruteForce', 'PortScan', 'Malware'];
const REGIONS      = ['US', 'EU', 'RU', 'CN', 'IL', 'BR'];

@Component({
  selector: 'app-rules',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './rules.component.html',
  styleUrl: './rules.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RulesComponent {
  private store      = inject(ThreatStoreService);
  private destroyRef = inject(DestroyRef);

  rules    = signal<DetectionRule[]>([]);
  selected = signal<DetectionRule | null>(null);
  isNew    = signal(false);

  // Editor state
  editName       = signal('');
  editLogic      = signal<'AND' | 'OR'>('AND');
  editConditions = signal<RuleCondition[]>([{ field: 'score', operator: '>', value: 75 }]);
  editActions    = signal<Set<RuleAction>>(new Set<RuleAction>(['alert']));

  readonly operatorsFor = (field: string) => OPERATORS[field] ?? ['='];
  readonly attackTypes  = ATTACK_TYPES;
  readonly regions      = REGIONS;

  readonly queryPreview = computed(() => {
    const parts = this.editConditions().map(c => `${c.field}${c.operator}${c.value}`);
    return parts.length ? parts.join(` ${this.editLogic()} `) : '—';
  });

  constructor() {
    this.store.getRules()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(r => this.rules.set(r));
  }

  newRule() {
    this.selected.set(null);
    this.isNew.set(true);
    this.editName.set('');
    this.editLogic.set('AND');
    this.editConditions.set([{ field: 'score', operator: '>', value: 75 }]);
    this.editActions.set(new Set<RuleAction>(['alert']));
  }

  selectRule(rule: DetectionRule) {
    this.selected.set(rule);
    this.isNew.set(false);
    this.editName.set(rule.name);
    this.editLogic.set(rule.logic);
    this.editConditions.set(rule.conditions.map(c => ({ ...c })));
    this.editActions.set(new Set<RuleAction>(rule.actions));
  }

  addCondition() {
    this.editConditions.update(cs => [...cs, { field: 'score', operator: '>', value: 0 }]);
  }

  removeCondition(i: number) {
    this.editConditions.update(cs => cs.filter((_, idx) => idx !== i));
  }

  updateConditionField(i: number, field: string) {
    const ops = OPERATORS[field] ?? ['='];
    this.editConditions.update(cs =>
      cs.map((c, idx) => idx === i ? { ...c, field: field as RuleCondition['field'], operator: ops[0] as RuleCondition['operator'], value: '' } : c)
    );
  }

  updateConditionOp(i: number, operator: string) {
    this.editConditions.update(cs =>
      cs.map((c, idx) => idx === i ? { ...c, operator: operator as RuleCondition['operator'] } : c)
    );
  }

  updateConditionValue(i: number, value: string) {
    this.editConditions.update(cs =>
      cs.map((c, idx) => idx === i ? { ...c, value } : c)
    );
  }

  toggleAction(action: RuleAction) {
    this.editActions.update(set => {
      const next = new Set(set);
      next.has(action) ? next.delete(action) : next.add(action);
      return next;
    });
  }

  save() {
    const payload = {
      name:       this.editName().trim() || 'Unnamed Rule',
      logic:      this.editLogic(),
      conditions: this.editConditions(),
      actions:    [...this.editActions()] as RuleAction[],
      enabled:    true,
    };
    const rule = this.selected();
    if (rule) {
      this.store.updateRule(rule.id, payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(updated => {
          this.rules.update(list => list.map(r => r.id === updated.id ? updated : r));
          this.selected.set(updated);
        });
    } else {
      this.store.createRule(payload)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(created => {
          this.rules.update(list => [...list, created]);
          this.selected.set(created);
          this.isNew.set(false);
        });
    }
  }

  toggleEnabled(rule: DetectionRule, e: Event) {
    e.stopPropagation();
    this.store.updateRule(rule.id, { enabled: !rule.enabled })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(updated => {
        this.rules.update(list => list.map(r => r.id === updated.id ? updated : r));
        if (this.selected()?.id === updated.id) this.selected.set(updated);
      });
  }

  deleteRule(rule: DetectionRule, e: Event) {
    e.stopPropagation();
    this.store.deleteRule(rule.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        this.rules.update(list => list.filter(r => r.id !== rule.id));
        if (this.selected()?.id === rule.id) {
          this.selected.set(null);
          this.isNew.set(false);
        }
      });
  }

  cancel() {
    const rule = this.selected();
    if (rule) this.selectRule(rule);
    else { this.selected.set(null); this.isNew.set(false); }
  }

  valueOptions(field: string): string[] {
    if (field === 'attack_type') return ATTACK_TYPES;
    if (field === 'region')      return REGIONS;
    return [];
  }
}
```

- [ ] **Step 2: Create `rules.component.html`**

```html
<div class="rules-page">

  <!-- Left: rules list -->
  <div class="rules-sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">DETECTION RULES</span>
      <button class="btn-new" (click)="newRule()">+ New</button>
    </div>

    @if (rules().length === 0 && !isNew()) {
      <div class="sidebar-empty">
        <p>No rules yet</p>
      </div>
    }

    <div class="rules-list">
      @for (rule of rules(); track rule.id) {
        <div class="rule-item" [class.active]="selected()?.id === rule.id" (click)="selectRule(rule)">
          <button class="rule-toggle" [class.on]="rule.enabled" (click)="toggleEnabled(rule, $event)"
                  [title]="rule.enabled ? 'Disable' : 'Enable'">
            <span class="toggle-dot"></span>
          </button>
          <div class="rule-info">
            <span class="rule-name">{{ rule.name }}</span>
            <span class="rule-meta">{{ rule.match_count }} hits · {{ rule.actions.join(' + ') }}</span>
          </div>
          <button class="rule-del" (click)="deleteRule(rule, $event)">✕</button>
        </div>
      }
    </div>
  </div>

  <!-- Right: editor -->
  <div class="rules-editor">
    @if (!selected() && !isNew()) {
      <div class="editor-empty">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none">
          <path d="M12 4l8 4v8l-8 4-8-4V8l8-4z" stroke="#4b5563" stroke-width="1.2" stroke-linejoin="round"/>
          <path d="M12 12v4M12 8v.5" stroke="#4b5563" stroke-width="1.4" stroke-linecap="round"/>
        </svg>
        <p>Select a rule or create a new one</p>
      </div>
    } @else {
      <div class="editor-body">

        <!-- Name -->
        <div class="editor-section">
          <label class="field-label">RULE NAME</label>
          <input class="field-input" [value]="editName()"
                 (input)="editName.set($any($event.target).value)"
                 placeholder="e.g. High Score Russia" />
        </div>

        <!-- Conditions -->
        <div class="editor-section">
          <div class="conditions-header">
            <label class="field-label">CONDITIONS</label>
            <div class="logic-toggle">
              <button [class.active]="editLogic() === 'AND'" (click)="editLogic.set('AND')">AND</button>
              <button [class.active]="editLogic() === 'OR'"  (click)="editLogic.set('OR')">OR</button>
            </div>
          </div>

          <div class="conditions-list">
            @for (cond of editConditions(); track $index) {
              <div class="cond-row">
                <select class="cond-select" [value]="cond.field"
                        (change)="updateConditionField($index, $any($event.target).value)">
                  <option value="score">score</option>
                  <option value="attack_type">attack_type</option>
                  <option value="region">region</option>
                  <option value="ip">ip</option>
                </select>

                <select class="cond-select cond-op" [value]="cond.operator"
                        (change)="updateConditionOp($index, $any($event.target).value)">
                  @for (op of operatorsFor(cond.field); track op) {
                    <option [value]="op">{{ op }}</option>
                  }
                </select>

                @if (valueOptions(cond.field).length > 0) {
                  <select class="cond-select cond-val" [value]="cond.value"
                          (change)="updateConditionValue($index, $any($event.target).value)">
                    <option value="">— select —</option>
                    @for (v of valueOptions(cond.field); track v) {
                      <option [value]="v">{{ v }}</option>
                    }
                  </select>
                } @else {
                  <input class="cond-input" [value]="cond.value"
                         (input)="updateConditionValue($index, $any($event.target).value)"
                         [placeholder]="cond.field === 'score' ? '0–100' : 'value'" />
                }

                <button class="cond-del" (click)="removeCondition($index)"
                        [disabled]="editConditions().length === 1">✕</button>
              </div>
            }
          </div>

          <button class="btn-add-cond" (click)="addCondition()">+ Add Condition</button>
        </div>

        <!-- Actions -->
        <div class="editor-section">
          <label class="field-label">ACTIONS</label>
          <div class="actions-row">
            @for (action of (['alert', 'incident', 'block'] as const); track action) {
              <label class="action-chip" [class.checked]="editActions().has(action)">
                <input type="checkbox" [checked]="editActions().has(action)"
                       (change)="toggleAction(action)" />
                {{ action }}
              </label>
            }
          </div>
        </div>

        <!-- Query preview -->
        <div class="editor-section">
          <label class="field-label">QUERY PREVIEW</label>
          <div class="query-preview">{{ queryPreview() }}</div>
        </div>

        <!-- Buttons -->
        <div class="editor-footer">
          <button class="btn-cancel" (click)="cancel()">Cancel</button>
          <button class="btn-save" (click)="save()" [disabled]="!editName().trim()">
            {{ isNew() ? 'Create Rule' : 'Save Changes' }}
          </button>
        </div>

      </div>
    }
  </div>

</div>
```

- [ ] **Step 3: Create `rules.component.scss`**

```scss
$bg: #0f1117;
$panel: #13171f;
$border: #1e2535;
$text: #e5e7eb;
$secondary: #9ca3af;
$muted: #4b5563;
$accent: #3b82f6;
$green: #22c55e;

:host {
  display: block;
  height: 100%;
  overflow: hidden;
}

.rules-page {
  height: 100%;
  display: flex;
  overflow: hidden;
}

// ── Sidebar ───────────────────────────────────────────────────
.rules-sidebar {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid $border;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: $border transparent;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 12px;
  border-bottom: 1px solid $border;
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: $text;
}

.btn-new {
  padding: 4px 10px;
  background: rgba(59,130,246,0.1);
  border: 1px solid rgba(59,130,246,0.35);
  color: $accent;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { background: rgba(59,130,246,0.2); }
}

.sidebar-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  p { font-size: 12px; color: $muted; }
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 10px;
}

.rule-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid $border;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { border-color: rgba(59,130,246,0.3); background: rgba(59,130,246,0.03); }
  &.active { border-color: rgba(59,130,246,0.5); background: rgba(59,130,246,0.06); }
}

.rule-toggle {
  width: 28px;
  height: 16px;
  border-radius: 8px;
  background: $border;
  border: none;
  cursor: pointer;
  position: relative;
  flex-shrink: 0;
  transition: background 0.2s;

  &.on { background: rgba(34,197,94,0.4); }

  .toggle-dot {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: $muted;
    transition: all 0.2s;
  }

  &.on .toggle-dot {
    left: 14px;
    background: $green;
  }
}

.rule-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rule-name {
  font-size: 11px;
  color: $text;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rule-meta {
  font-size: 9px;
  color: $muted;
  font-family: monospace;
}

.rule-del {
  background: none;
  border: none;
  color: $muted;
  font-size: 10px;
  cursor: pointer;
  padding: 2px 4px;
  flex-shrink: 0;
  transition: color 0.15s;

  &:hover { color: #ef4444; }
}

// ── Editor ────────────────────────────────────────────────────
.rules-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.editor-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;

  p { font-size: 12px; color: $muted; }
}

.editor-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  scrollbar-width: thin;
  scrollbar-color: $border transparent;
}

.editor-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: $muted;
  text-transform: uppercase;
}

.field-input {
  background: #0d1018;
  border: 1px solid $border;
  color: $text;
  border-radius: 3px;
  padding: 7px 10px;
  font-size: 12px;
  outline: none;
  max-width: 360px;

  &::placeholder { color: $muted; }
  &:focus { border-color: rgba(59,130,246,0.4); }
}

// ── Conditions ────────────────────────────────────────────────
.conditions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logic-toggle {
  display: flex;
  border: 1px solid $border;
  border-radius: 3px;
  overflow: hidden;

  button {
    padding: 3px 10px;
    background: transparent;
    border: none;
    color: $muted;
    font-size: 10px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s;

    &.active { background: rgba(59,130,246,0.15); color: $accent; }
    &:hover:not(.active) { color: $secondary; }
  }
}

.conditions-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cond-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cond-select {
  background: #0d1018;
  border: 1px solid $border;
  color: $text;
  border-radius: 3px;
  padding: 5px 8px;
  font-size: 11px;
  outline: none;
  cursor: pointer;

  &:focus { border-color: rgba(59,130,246,0.4); }
  option { background: #0d1018; }
}

.cond-op  { width: 80px; }
.cond-val { flex: 1; }

.cond-input {
  flex: 1;
  background: #0d1018;
  border: 1px solid $border;
  color: $text;
  border-radius: 3px;
  padding: 5px 8px;
  font-size: 11px;
  outline: none;

  &::placeholder { color: $muted; }
  &:focus { border-color: rgba(59,130,246,0.4); }
}

.cond-del {
  background: none;
  border: 1px solid $border;
  color: $muted;
  border-radius: 3px;
  width: 24px;
  height: 24px;
  font-size: 10px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;

  &:hover:not(:disabled) { border-color: #ef4444; color: #ef4444; }
  &:disabled { opacity: 0.3; cursor: default; }
}

.btn-add-cond {
  width: fit-content;
  padding: 4px 10px;
  background: transparent;
  border: 1px dashed rgba(59,130,246,0.3);
  color: rgba(59,130,246,0.7);
  border-radius: 3px;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { border-color: $accent; color: $accent; }
}

// ── Actions ───────────────────────────────────────────────────
.actions-row {
  display: flex;
  gap: 8px;
}

.action-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid $border;
  border-radius: 3px;
  font-size: 11px;
  color: $muted;
  cursor: pointer;
  transition: all 0.15s;

  input[type="checkbox"] { display: none; }

  &.checked {
    border-color: rgba(59,130,246,0.5);
    background: rgba(59,130,246,0.08);
    color: $accent;
  }

  &:hover:not(.checked) { border-color: rgba(59,130,246,0.25); color: $secondary; }
}

// ── Query preview ─────────────────────────────────────────────
.query-preview {
  background: #0d1018;
  border: 1px solid $border;
  border-radius: 3px;
  padding: 8px 12px;
  font-family: monospace;
  font-size: 12px;
  color: $accent;
  min-height: 36px;
  word-break: break-all;
}

// ── Footer ────────────────────────────────────────────────────
.editor-footer {
  display: flex;
  gap: 8px;
  padding-top: 4px;
}

.btn-cancel {
  padding: 7px 16px;
  background: transparent;
  border: 1px solid $border;
  color: $secondary;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { background: rgba(255,255,255,0.04); color: $text; }
}

.btn-save {
  padding: 7px 20px;
  background: rgba(59,130,246,0.12);
  border: 1px solid rgba(59,130,246,0.4);
  color: $accent;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;

  &:hover:not(:disabled) { background: rgba(59,130,246,0.22); }
  &:disabled { opacity: 0.4; cursor: default; }
}
```

---

## Task 6 — Frontend: Route + Nav item

**Files:** `app.routes.ts`, `app-layout.html`

- [ ] **Step 1: Add route to `app.routes.ts`** — after the `/hunting` route:

```typescript
{
  path: 'rules',
  loadComponent: () => import('./features/rules/rules.component').then((m) => m.RulesComponent),
},
```

- [ ] **Step 2: Add nav item to `app-layout.html`** — after the Threat Hunting `<a>` item:

```html
<a class="item" routerLink="/rules" routerLinkActive="active">
  <svg class="item-icon" viewBox="0 0 16 16" fill="none">
    <path d="M2 4h12M2 8h8M2 12h10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
    <circle cx="13" cy="8" r="2" stroke="currentColor" stroke-width="1.2"/>
  </svg>
  Detection Rules
</a>
```

- [ ] **Step 3: Also add `'network'` and `'rules'` and `'hunting'` to `PAGE_TITLES`** in `app-layout.ts`:

```typescript
const PAGE_TITLES: Record<string, string> = {
  '/dashboard':  'Live Operations',
  '/threats':    'Threat Intelligence',
  '/alerts':     'Alerts',
  '/incidents':  'Incidents',
  '/map':        'Threat Map',
  '/network':    'Network Graph',
  '/hunting':    'Threat Hunting',
  '/rules':      'Detection Rules',
  '/settings':   'Settings',
};
```

- [ ] **Step 4: Verify in browser**

Navigate to `/rules` → page loads with empty state.
Create a rule with `score > 0`, actions `incident`.
Wait a few seconds (WebSocket events fire every 0.5–1.5s).
Navigate to Incidents → new auto-created incidents should appear.
