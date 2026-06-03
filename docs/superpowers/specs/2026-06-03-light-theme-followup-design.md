# Light Theme — Follow-up Spec

**Date:** 2026-06-03
**Status:** Draft
**Depends on:** `2026-06-03-light-theme-design.md` (implemented)

## Context

The initial light theme implementation (ThemeService, CSS custom properties, Settings toggle) is complete and working. This spec covers four remaining gaps identified during the implementation review.

---

## Gap 1: FOUT — Flash of Unstyled Theme on Reload

### Problem

`ThemeService` is injected in `AppLayout`, which loads after Angular bootstraps and the router resolves the auth guard. If a user has saved `light` preference, there is a brief dark flash on every page reload before `AppLayout` mounts and calls `body.setAttribute('data-theme', 'light')`.

### Solution

Add an **inline script** in `frontend/src/index.html` that runs synchronously before Angular boots:

```html
<script>
  (function() {
    var t = localStorage.getItem('sf_theme');
    document.body.setAttribute('data-theme', t === 'light' ? 'light' : 'dark');
  })();
</script>
```

Place it as the last child of `<head>`, before any stylesheet links. This guarantees `data-theme` is set before the first CSS paint.

**No Angular changes needed** — ThemeService still manages subsequent toggles. The inline script is just a bootstrap accelerator.

**Acceptance criteria:**
- Reloading the page on light mode shows no dark flash
- Script is < 5 lines, no external dependencies

---

## Gap 2: Hover States Invisible in Light Mode

### Problem

Two files replaced dark hover backgrounds (`#1a2035`, `#181f2e`) with `rgba(255, 255, 255, 0.02)`. This is nearly invisible on both dark and light backgrounds.

**Affected:**
- `frontend/src/app/features/alerts/alerts.scss` — table row hover (line ~168)
- `frontend/src/app/features/threats/threat-table/threat-table.component.scss` — row hover (line ~169)

### Solution

Replace `rgba(255, 255, 255, 0.02)` with `var(--c-border)` in both files, consistent with all other hover states in the codebase.

Light mode `--c-border: #c7d0e8` gives a visible, subtle blue-gray hover. Dark mode `--c-border: #1e2535` matches the existing design.

**Acceptance criteria:**
- Table row hover is visually distinct from non-hovered rows in both themes
- No hardcoded rgba values for hover backgrounds

---

## Gap 3: ECharts Colors on Light Mode

### Problem

ECharts chart configurations in `dashboard.ts` and `charts-column.component.ts` use hardcoded dark colors for chart backgrounds, axes, grid lines, and labels. In light mode, charts appear as dark islands on a light background.

**Affected values (approximate):**
- Chart background: `#13171f` → should be `transparent` or match `--c-panel`
- Axis label color: `#9ca3af` → `--c-text-2`
- Grid line color: `#1e2535` → `--c-border`
- Tooltip background: `#1e2535` → `--c-panel`
- Tooltip text: `#e5e7eb` → `--c-text`

### Solution

ECharts does not read CSS variables directly. Two approaches:

**Option A (recommended): Dynamic config via ThemeService signal**

In `charts-column.component.ts`, inject `ThemeService` and use a `computed()` to produce theme-aware chart options:

```typescript
private theme = inject(ThemeService);

chartOptions = computed(() => ({
  backgroundColor: 'transparent',
  textStyle: { color: this.theme.theme() === 'light' ? '#475569' : '#9ca3af' },
  // ... other options
}));
```

**Option B: ECharts theme registration**

Register two named ECharts themes (`sf-dark`, `sf-light`) and switch via `ThemeService`. More work, but fully decoupled from component logic.

**Acceptance criteria:**
- Dashboard charts are legible in both dark and light mode
- No dark backgrounds visible against light panel in light mode

---

## Gap 4: DB Persistence of Theme Preference

### Problem

Theme preference is stored in `localStorage` under `sf_theme`, separate from `AppSettings`. This is inconsistent with the long-term goal of persisting all user settings to the database (noted in `2026-06-03-light-theme-design.md` Out of Scope section).

### Solution

When user settings DB persistence is implemented (see `2026-06-01-real-apis-and-database-design.md`), extend it to include `theme: 'dark' | 'light'`.

**Migration path:**
1. Add `theme` field to `UserSettings` DB model
2. On `ThemeService` init: read from API first, fall back to localStorage, fall back to `'dark'`
3. On toggle: write to API (fire-and-forget) + localStorage (immediate)

**Acceptance criteria:**
- Theme preference syncs across browsers/devices for the same user
- localStorage remains as a cache for instant load (no FOUT waiting for API)

---

## Out of Scope (not planned)

- **Topbar toggle** — decided against; Settings is the correct location for preferences
- **System theme detection** (`prefers-color-scheme`) — adds complexity, deferred indefinitely
- **Command console theming** — intentionally dark-always, no change needed
