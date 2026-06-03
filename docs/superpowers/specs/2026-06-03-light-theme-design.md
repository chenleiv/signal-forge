# Light Theme Design

**Date:** 2026-06-03
**Status:** Approved

## Summary

Add a light theme (Cool Blue-Gray palette) to SignalForge with a toggle in the Settings page. Theme preference persists in localStorage alongside existing app settings.

## Palette

### Dark (existing)
| Variable       | Value     |
|----------------|-----------|
| `--c-bg`       | `#0f1117` |
| `--c-panel`    | `#13171f` |
| `--c-border`   | `#1e2535` |
| `--c-text`     | `#e5e7eb` |
| `--c-text-2`   | `#9ca3af` |
| `--c-muted`    | `#4b5563` |
| `--c-accent`   | `#3b82f6` |
| `--c-input`    | `#0d1220` |

### Light (Cool Blue-Gray)
| Variable       | Value     |
|----------------|-----------|
| `--c-bg`       | `#eef2ff` |
| `--c-panel`    | `#f5f7ff` |
| `--c-border`   | `#c7d0e8` |
| `--c-text`     | `#1e293b` |
| `--c-text-2`   | `#475569` |
| `--c-muted`    | `#64748b` |
| `--c-accent`   | `#4f72de` |
| `--c-input`    | `#ffffff` |

`--c-green` (`#16a34a`) is identical in both themes.

## Architecture

### ThemeService (`frontend/src/app/core/services/theme.ts`)

- Signal `theme: Signal<'dark' | 'light'>`, initialized from `localStorage.getItem('sf_theme')`, defaults to `'dark'`
- An Angular `effect()` that:
  1. Sets `document.body.setAttribute('data-theme', theme())`
  2. Writes `localStorage.setItem('sf_theme', theme())`
- Public `toggle()` method: flips between `'dark'` and `'light'`
- Injected in `AppLayout` so the effect runs on first render, preventing a theme flash

### styles.scss

- Remove the hardcoded `background: #0f1117` from `html, body`
- Add `body[data-theme="dark"] { --c-bg: ...; ... }` block with all 8 variables
- Add `body[data-theme="light"] { --c-bg: ...; ... }` block with all 8 variables
- Keep scrollbar styles (they can stay dark in both themes or adapt — keep dark)

### SCSS Files to update (~15 files)

Replace every hardcoded color with the corresponding CSS custom property:

| Hardcoded color | Variable    |
|-----------------|-------------|
| `#0f1117`       | `var(--c-bg)` |
| `#13171f`       | `var(--c-panel)` |
| `#1e2535`       | `var(--c-border)` |
| `#e5e7eb`       | `var(--c-text)` |
| `#9ca3af`       | `var(--c-text-2)` |
| `#4b5563`       | `var(--c-muted)` |
| `#3b82f6`       | `var(--c-accent)` |
| `#0d1220`       | `var(--c-input)` |

Files affected:
- `app-layout/app-layout.scss`
- `settings/settings.scss`
- `dashboard/dashboard.scss`
- `dashboard/charts-column/charts-column.component.scss`
- `threats/threats.scss`
- `threats/threat-table/threat-table.component.scss`
- `threats/threat-detail-drawer/threat-detail-drawer.component.scss`
- `alerts/alerts.scss`
- `incidents/incidents.scss`
- `incidents/incident-detail/incident-detail.component.scss`
- `threat-map/threat-map.scss`
- `network-graph/network-graph.component.scss`
- `rules/rules.component.scss`
- `threat-hunting/threat-hunting.component.scss`
- `command-console/command-console.scss`
- `login/login/login.scss`

### Settings Page

- Add `theme: 'dark' | 'light'` field to `AppSettings` interface in `settings.service.ts`, default `'dark'`
- Add new **Appearance** section to `settings.html`, between User Profile and Connection
- Toggle UI: pill segmented control with two buttons — `🌙 Dark` and `☀️ Light`
  - Active button: filled blue background
  - Inactive button: transparent, muted text
  - Click calls `themeService.toggle()`
- `ThemeService` injected directly into the `Settings` component

### AppLayout

- Inject `ThemeService` (one line: `private theme = inject(ThemeService)`) so the effect initializes before any component renders

## Data Flow

1. App loads → `AppLayout` injects `ThemeService` → `effect()` reads localStorage, sets `data-theme` on `body`
2. User clicks Dark/Light in Settings → `ThemeService.toggle()` → signal updates → `effect()` fires → `data-theme` changes → CSS variables cascade to all components instantly
3. On next load → localStorage value is read, theme is restored

## Out of Scope

- DB persistence of theme preference (deferred — all settings currently use localStorage)
- Theme toggle in topbar
- System theme detection (`prefers-color-scheme`)
