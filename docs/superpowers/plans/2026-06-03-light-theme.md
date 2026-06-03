# Light Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Cool Blue-Gray light theme to the entire app, switchable via a pill toggle in the Settings Appearance section, persisted in localStorage.

**Architecture:** A standalone `ThemeService` sets `data-theme` on `<body>` and persists preference to `localStorage('sf_theme')`. All component SCSS files replace hardcoded color hex values with CSS custom properties defined in two `body[data-theme]` blocks in `styles.scss`. The Settings page gains an Appearance section with a Dark/Light pill toggle that calls `ThemeService.toggle()`.

**Tech Stack:** Angular 17+ signals + `effect()`, SCSS CSS custom properties, Angular `DOCUMENT` token.

---

### Task 1: Define CSS Custom Properties in styles.scss

**Files:**
- Modify: `frontend/src/styles.scss`

- [ ] **Step 1: Replace styles.scss with themed version**

```scss
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body {
  height: 100%;
  margin: 0;
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}

body {
  background: var(--c-bg);
}

body[data-theme="dark"] {
  --c-bg:     #0f1117;
  --c-panel:  #13171f;
  --c-border: #1e2535;
  --c-text:   #e5e7eb;
  --c-text-2: #9ca3af;
  --c-muted:  #4b5563;
  --c-accent: #3b82f6;
  --c-input:  #0d1220;
}

body[data-theme="light"] {
  --c-bg:     #eef2ff;
  --c-panel:  #f5f7ff;
  --c-border: #c7d0e8;
  --c-text:   #1e293b;
  --c-text-2: #475569;
  --c-muted:  #64748b;
  --c-accent: #4f72de;
  --c-input:  #ffffff;
}

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1e2535; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2d3748; }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/styles.scss
git commit -m "feat: add CSS custom properties for dark/light themes"
```

---

### Task 2: Create ThemeService

**Files:**
- Create: `frontend/src/app/core/services/theme.ts`
- Create: `frontend/src/app/core/services/theme.spec.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/core/services/theme.spec.ts`:

```typescript
import { TestBed, fakeAsync, flushMicrotasks } from '@angular/core/testing';
import { DOCUMENT } from '@angular/common';
import { ThemeService } from './theme';

describe('ThemeService', () => {
  let service: ThemeService;
  let doc: Document;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    service = TestBed.inject(ThemeService);
    doc = TestBed.inject(DOCUMENT);
  });

  afterEach(() => localStorage.clear());

  it('defaults to dark', () => {
    expect(service.theme()).toBe('dark');
  });

  it('reads saved light theme from localStorage', () => {
    localStorage.setItem('sf_theme', 'light');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({});
    const fresh = TestBed.inject(ThemeService);
    expect(fresh.theme()).toBe('light');
  });

  it('toggle switches dark → light', () => {
    service.toggle();
    expect(service.theme()).toBe('light');
  });

  it('toggle switches light → dark', () => {
    service.toggle();
    service.toggle();
    expect(service.theme()).toBe('dark');
  });

  it('persists theme to localStorage on toggle', fakeAsync(() => {
    service.toggle();
    flushMicrotasks();
    expect(localStorage.getItem('sf_theme')).toBe('light');
  }));
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx ng test --include="**/theme.spec.ts" --watch=false
```

Expected: FAIL — "ThemeService not found" or similar.

- [ ] **Step 3: Create the service**

Create `frontend/src/app/core/services/theme.ts`:

```typescript
import { Injectable, inject, signal, effect } from '@angular/core';
import { DOCUMENT } from '@angular/common';

const THEME_KEY = 'sf_theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private doc = inject(DOCUMENT);

  readonly theme = signal<'dark' | 'light'>(
    (localStorage.getItem(THEME_KEY) as 'dark' | 'light') ?? 'dark'
  );

  constructor() {
    effect(() => {
      this.doc.body.setAttribute('data-theme', this.theme());
      localStorage.setItem(THEME_KEY, this.theme());
    });
  }

  toggle() {
    this.theme.update(t => (t === 'dark' ? 'light' : 'dark'));
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx ng test --include="**/theme.spec.ts" --watch=false
```

Expected: 5 tests passing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/services/theme.ts frontend/src/app/core/services/theme.spec.ts
git commit -m "feat: add ThemeService with localStorage persistence"
```

---

### Task 3: Wire ThemeService into AppLayout

**Files:**
- Modify: `frontend/src/app/layout/app-layout/app-layout.ts`

This ensures the `effect()` in ThemeService runs on first render, setting `data-theme` before any component paints.

- [ ] **Step 1: Add ThemeService injection to AppLayout**

In `frontend/src/app/layout/app-layout/app-layout.ts`, add the import and injection:

```typescript
import { Component, signal, inject, computed, ChangeDetectionStrategy, DestroyRef } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter, map } from 'rxjs/operators';
import { toSignal } from '@angular/core/rxjs-interop';
import { ThreatsService } from '../../core/services/threats.service';
import { SettingsService } from '../../core/services/settings.service';
import { ThemeService } from '../../core/services/theme';
import { CommandConsole } from '../../features/command-console/command-console';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Live Operations',
  '/threats':   'Threat Intelligence',
  '/alerts':    'Alerts',
  '/incidents': 'Incidents',
  '/map':       'Threat Map',
  '/network':   'Network Graph',
  '/hunting':   'Threat Hunting',
  '/rules':     'Detection Rules',
  '/settings':  'Settings',
};

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet, CommandConsole],
  templateUrl: './app-layout.html',
  styleUrl: './app-layout.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppLayout {
  readonly ws              = inject(ThreatsService);
  readonly settingsService = inject(SettingsService);
  readonly themeService    = inject(ThemeService);
  private router           = inject(Router);
  private destroyRef       = inject(DestroyRef);

  private navTitle = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map(e => PAGE_TITLES[e.urlAfterRedirects] ?? 'SignalForge'),
    ),
  );

  readonly pageTitle = computed(() => this.navTitle() ?? PAGE_TITLES[this.router.url] ?? 'SignalForge');

  time = signal('');

  constructor() {
    this.tick();
    const timer = setInterval(() => this.tick(), 1000);
    this.destroyRef.onDestroy(() => {
      clearInterval(timer);
      this.ws.disconnect();
    });
    this.ws.connect();
  }

  private tick() {
    this.time.set(new Date().toLocaleTimeString('he-IL', { hour12: false }));
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/layout/app-layout/app-layout.ts
git commit -m "feat: initialize ThemeService in AppLayout"
```

---

### Task 4: Appearance Section in Settings

**Files:**
- Modify: `frontend/src/app/features/settings/settings.ts`
- Modify: `frontend/src/app/features/settings/settings.html`
- Modify: `frontend/src/app/features/settings/settings.scss`

- [ ] **Step 1: Inject ThemeService in Settings component**

Replace `frontend/src/app/features/settings/settings.ts`:

```typescript
import { Component, inject, signal, ChangeDetectionStrategy } from '@angular/core';
import { SettingsService, AppSettings } from '../../core/services/settings.service';
import { AuthService } from '../../core/services/auth';
import { ThemeService } from '../../core/services/theme';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Settings {
  private svc = inject(SettingsService);
  private auth = inject(AuthService);
  readonly themeService = inject(ThemeService);

  form = signal<AppSettings>({ ...this.svc.settings() });

  saved = signal(false);

  save() {
    this.svc.save(this.form());
    this.saved.set(true);
    setTimeout(() => this.saved.set(false), 2000);
  }

  reset() {
    this.svc.reset();
    this.form.set({ ...this.svc.settings() });
  }

  logout() {
    this.auth.logout();
  }
}
```

- [ ] **Step 2: Add Appearance section to settings.html**

Add the Appearance section BEFORE the Connection section (after the User Profile closing `</section>` tag):

```html
        <!-- Appearance -->
        <section class="card">
            <div class="card-header">
                <svg class="card-icon" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.2"/>
                    <path d="M8 2.5v1M8 12.5v1M2.5 8h1M12.5 8h1M4.4 4.4l.7.7M10.9 10.9l.7.7M4.4 11.6l.7-.7M10.9 5.1l.7-.7"
                        stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                </svg>
                <h2 class="card-title">Appearance</h2>
            </div>
            <div class="field-grid">
                <div class="field full">
                    <label>Theme</label>
                    <div class="theme-toggle">
                        <button class="theme-btn"
                            [class.active]="themeService.theme() === 'dark'"
                            (click)="themeService.theme() !== 'dark' && themeService.toggle()">
                            🌙 Dark
                        </button>
                        <button class="theme-btn"
                            [class.active]="themeService.theme() === 'light'"
                            (click)="themeService.theme() !== 'light' && themeService.toggle()">
                            ☀️ Light
                        </button>
                    </div>
                </div>
            </div>
        </section>
```

The full `settings.html` sections order should be: User Profile → Appearance → Connection → Alert Thresholds.

- [ ] **Step 3: Add toggle styles to settings.scss**

Append to the end of `frontend/src/app/features/settings/settings.scss`:

```scss
// ── Theme Toggle ──────────────────────────────────────────────
.theme-toggle {
  display: flex;
  background: var(--c-input);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  overflow: hidden;
  width: fit-content;
}

.theme-btn {
  padding: 7px 20px;
  font-size: 12px;
  font-weight: 500;
  color: var(--c-text-2);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;

  &.active {
    background: var(--c-accent);
    color: #fff;
  }

  &:not(.active):hover {
    background: var(--c-border);
    color: var(--c-text);
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/features/settings/settings.ts \
        frontend/src/app/features/settings/settings.html \
        frontend/src/app/features/settings/settings.scss
git commit -m "feat: add Appearance section with theme toggle to Settings"
```

---

### Task 5: Update app-layout.scss

**Files:**
- Modify: `frontend/src/app/layout/app-layout/app-layout.scss`

- [ ] **Step 1: Replace the color variable declarations at the top**

Replace lines 1–11 of `frontend/src/app/layout/app-layout/app-layout.scss`:

```scss
// ── Palo Alto / XSIAM Palette ────────────────────────────────
$bg:       var(--c-bg);
$sb-bg:    var(--c-panel);
$panel-bg: var(--c-panel);
$border:   var(--c-border);

$accent:    var(--c-accent);
$text:      var(--c-text);
$secondary: var(--c-text-2);
$muted:     var(--c-muted);
$green:     #16a34a;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/layout/app-layout/app-layout.scss
git commit -m "feat: apply CSS variables to app-layout styles"
```

---

### Task 6: Update settings.scss variables and inline input colors

**Files:**
- Modify: `frontend/src/app/features/settings/settings.scss`

- [ ] **Step 1: Replace the variable declarations (lines 1–6)**

```scss
$bg:     var(--c-bg);
$panel:  var(--c-panel);
$border: var(--c-border);
$text:   var(--c-text);
$muted:  var(--c-text-2);
$accent: var(--c-accent);
```

- [ ] **Step 2: Replace inline input background colors**

In `frontend/src/app/features/settings/settings.scss`, replace both occurrences of `background: #0d1220` (in the `.field input` and `.threshold-field input[type="number"]` blocks) with:

```scss
background: var(--c-input);
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/features/settings/settings.scss
git commit -m "feat: apply CSS variables to settings styles"
```

---

### Task 7: Update alerts.scss

**Files:**
- Modify: `frontend/src/app/features/alerts/alerts.scss`

- [ ] **Step 1: Replace variable declarations (lines 1–6)**

```scss
$bg:     var(--c-bg);
$panel:  var(--c-panel);
$border: var(--c-border);
$text:   var(--c-text);
$muted:  var(--c-text-2);
$accent: var(--c-accent);
```

- [ ] **Step 2: Replace inline hardcoded colors throughout the file**

Use find-and-replace for each of the following (these are inline usages outside the variable block):

| Find | Replace |
|------|---------|
| `color: #9ca3af` | `color: var(--c-text-2)` |
| `border-color: #9ca3af` | `border-color: var(--c-text-2)` |
| `color: #e5e7eb` | `color: var(--c-text)` |
| `background: #1e2535` | `background: var(--c-border)` |
| `border-color: #4b5563` | `border-color: var(--c-muted)` |
| `border: 1px solid #1e2535` | `border: 1px solid var(--c-border)` |
| `border-bottom: 1px solid #1e2535` | `border-bottom: 1px solid var(--c-border)` |
| `scrollbar-color: #1e2535 transparent` | `scrollbar-color: var(--c-border) transparent` |
| `color: #9ca3af !important` | `color: var(--c-text-2) !important` |

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/features/alerts/alerts.scss
git commit -m "feat: apply CSS variables to alerts styles"
```

---

### Task 8: Update dashboard.scss and charts-column.scss

**Files:**
- Modify: `frontend/src/app/features/dashboard/dashboard.scss`
- Modify: `frontend/src/app/features/dashboard/charts-column/charts-column.component.scss`

- [ ] **Step 1: Replace dashboard.scss variable declarations (lines 1–14)**

```scss
// ── Palette ──────────────────────────────────────────────────
$panel-bg:  var(--c-panel);
$border:    var(--c-border);

$red:    #ef4444;
$orange: #f97316;
$yellow: #f59e0b;
$blue:   #60a5fa;
$green:  #22c55e;
$purple: #a855f7;
$accent:    var(--c-accent);
$text:      var(--c-text);
$muted:     var(--c-muted);
$secondary: var(--c-text-2);
```

- [ ] **Step 2: Replace inline colors in charts-column.component.scss**

In `frontend/src/app/features/dashboard/charts-column/charts-column.component.scss`, replace:
- `background: #13171f` → `background: var(--c-panel)`
- `border: 1px solid #1e2535` → `border: 1px solid var(--c-border)`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/features/dashboard/dashboard.scss \
        frontend/src/app/features/dashboard/charts-column/charts-column.component.scss
git commit -m "feat: apply CSS variables to dashboard styles"
```

---

### Task 9: Update threats-related SCSS files

**Files:**
- Modify: `frontend/src/app/features/threats/threats.scss`
- Modify: `frontend/src/app/features/threats/threat-table/threat-table.component.scss`
- Modify: `frontend/src/app/features/threats/threat-detail-drawer/threat-detail-drawer.component.scss`

- [ ] **Step 1: Replace inline colors in threats.scss**

threats.scss has no variable block — replace inline usages:
- Line 30: `background: #3b82f6` → `background: var(--c-accent)`
- Line 67: `border-left: 1px solid #1e2535` → `border-left: 1px solid var(--c-border)`

- [ ] **Step 2: Replace variable declarations in threat-table.component.scss (lines 2–8)**

```scss
// ── Palette ──────────────────────────────────────────────────
$bg:        var(--c-bg);
$panel:     var(--c-panel);
$border:    var(--c-border);
$text:      var(--c-text);
$muted:     var(--c-muted);
$secondary: var(--c-text-2);
$accent:    var(--c-accent);
```

- [ ] **Step 3: Replace variable declarations in threat-detail-drawer.component.scss (lines 1–7)**

```scss
$bg:        var(--c-bg);
$panel:     var(--c-panel);
$border:    var(--c-border);
$text:      var(--c-text);
$secondary: var(--c-text-2);
$muted:     var(--c-muted);
$accent:    var(--c-accent);
```

Then replace the inline color on line 394:
- `color: #3b82f6;` → `color: var(--c-accent);`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/features/threats/threats.scss \
        frontend/src/app/features/threats/threat-table/threat-table.component.scss \
        frontend/src/app/features/threats/threat-detail-drawer/threat-detail-drawer.component.scss
git commit -m "feat: apply CSS variables to threat styles"
```

---

### Task 10: Update incidents-related SCSS files

**Files:**
- Modify: `frontend/src/app/features/incidents/incidents.scss`
- Modify: `frontend/src/app/features/incidents/incident-detail/incident-detail.component.scss`

- [ ] **Step 1: Replace variable declarations in incidents.scss (lines 1–5)**

```scss
$border:    var(--c-border);
$text:      var(--c-text);
$secondary: var(--c-text-2);
$muted:     var(--c-muted);
$accent:    var(--c-accent);
```

- [ ] **Step 2: Replace inline colors in incidents.scss**

- Line 85: `background: #13171f` → `background: var(--c-panel)`
- Line 132 (inside `.pill-closed`): `color: #9ca3af` → `color: var(--c-text-2)`
- Line 251: `color: #4b5563` → `color: var(--c-muted)`
- Line 261: `background: #1e2535` → `background: var(--c-border)`

- [ ] **Step 3: Replace variable declarations in incident-detail.component.scss (lines 1–7)**

```scss
$panel:     var(--c-panel);
$border:    var(--c-border);
$text:      var(--c-text);
$secondary: var(--c-text-2);
$muted:     var(--c-muted);
$accent:    var(--c-accent);
$green:     #22c55e;
```

- [ ] **Step 4: Replace lighten() call in incident-detail.component.scss**

Line 174 uses `lighten(#3b82f6, 15%)` which is a SCSS compile-time function incompatible with CSS vars. Replace:
```scss
&:hover { color: lighten(#3b82f6, 15%); }
```
with:
```scss
&:hover { color: #60a5fa; }
```
(`#60a5fa` is the pre-computed lightened value already used in dashboard.scss)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/features/incidents/incidents.scss \
        frontend/src/app/features/incidents/incident-detail/incident-detail.component.scss
git commit -m "feat: apply CSS variables to incidents styles"
```

---

### Task 11: Update rules, threat-hunting, network-graph SCSS

**Files:**
- Modify: `frontend/src/app/features/rules/rules.component.scss`
- Modify: `frontend/src/app/features/threat-hunting/threat-hunting.component.scss`
- Modify: `frontend/src/app/features/network-graph/network-graph.component.scss`

All three have clean variable-only declarations and no inline hardcoded colors.

- [ ] **Step 1: Replace variable declarations in rules.component.scss (lines 1–7)**

```scss
$panel:     var(--c-panel);
$border:    var(--c-border);
$text:      var(--c-text);
$secondary: var(--c-text-2);
$muted:     var(--c-muted);
$accent:    var(--c-accent);
$green:     #22c55e;
```

- [ ] **Step 2: Replace variable declarations in threat-hunting.component.scss (lines 1–6)**

```scss
$panel:     var(--c-panel);
$border:    var(--c-border);
$text:      var(--c-text);
$secondary: var(--c-text-2);
$muted:     var(--c-muted);
$accent:    var(--c-accent);
```

- [ ] **Step 3: Replace variable declarations in network-graph.component.scss (lines 1–5)**

```scss
$border:    var(--c-border);
$text:      var(--c-text);
$secondary: var(--c-text-2);
$muted:     var(--c-muted);
$accent:    var(--c-accent);
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/features/rules/rules.component.scss \
        frontend/src/app/features/threat-hunting/threat-hunting.component.scss \
        frontend/src/app/features/network-graph/network-graph.component.scss
git commit -m "feat: apply CSS variables to rules, hunting, network-graph styles"
```

---

### Task 12: Update command-console.scss and threat-map.scss

**Files:**
- Modify: `frontend/src/app/features/command-console/command-console.scss`
- Modify: `frontend/src/app/features/threat-map/threat-map.scss`

Both files have no SCSS variable declarations — only inline hardcoded colors.

- [ ] **Step 1: Replace inline colors in command-console.scss**

Three occurrences of `#1e2535` (lines 24, 36, 92) — all `border...solid #1e2535`:
- Replace all: `1px solid #1e2535` → `1px solid var(--c-border)`

- [ ] **Step 2: Replace inline colors in threat-map.scss**

| Line | Find | Replace |
|------|------|---------|
| 10 | `background: #0a0f1a` | `background: var(--c-bg)` |
| 26 | `border-bottom: 1px solid #1e2535` | `border-bottom: 1px solid var(--c-border)` |
| 35 | `border: 1px solid #1e2535` | `border: 1px solid var(--c-border)` |
| 37 | `color: #9ca3af` | `color: var(--c-text-2)` |
| 43 | `border-color: #3b82f6` | `border-color: var(--c-accent)` |
| 44 | `color: #3b82f6` | `color: var(--c-accent)` |

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/features/command-console/command-console.scss \
        frontend/src/app/features/threat-map/threat-map.scss
git commit -m "feat: apply CSS variables to console and map styles"
```

---

### Task 13: Update login.scss

**Files:**
- Modify: `frontend/src/app/features/login/login/login.scss`

- [ ] **Step 1: Replace variable declarations (lines 1–7)**

```scss
$bg:        var(--c-bg);
$card:      var(--c-panel);
$border:    var(--c-border);
$text:      var(--c-text);
$muted:     var(--c-muted);
$secondary: var(--c-text-2);
$accent:    var(--c-accent);
```

Note: login.scss uses `$bg` with `background-image` radial gradients. Those gradients use hardcoded `rgba(59, 130, 246, 0.06)` etc. — these are decorative and acceptable to leave as-is since they reference specific aesthetic colors, not UI surface colors.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/features/login/login/login.scss
git commit -m "feat: apply CSS variables to login styles"
```

---

### Task 14: Smoke Test

- [ ] **Step 1: Build the app**

```bash
cd frontend && npx ng build --configuration development 2>&1 | tail -20
```

Expected: `✔ Building... [n]s` with no errors. Zero `ERROR` lines.

- [ ] **Step 2: Run the dev server and verify manually**

```bash
cd frontend && npx ng serve
```

1. Open http://localhost:4200 — app loads in dark mode
2. Navigate to Settings
3. Click ☀️ Light — entire app switches to Cool Blue-Gray light theme
4. Reload the page — light theme is preserved
5. Click 🌙 Dark — app returns to dark mode
6. Reload — dark mode is preserved

- [ ] **Step 3: Run all tests**

```bash
cd frontend && npx ng test --watch=false
```

Expected: all tests pass.

- [ ] **Step 4: Final commit if any fixups were needed**

```bash
git add -p && git commit -m "fix: theme smoke test fixups"
```
