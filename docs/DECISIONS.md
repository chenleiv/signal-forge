# Decisions

Why SignalForge is built the way it is: the choices that are not obvious from
the code, and what was considered instead. Read this before proposing a change
to anything listed here.

## How to add an entry

- Newest first. One entry per decision.
- Date: the date of the commit that made the change, not the date you write
  the entry.
- Each entry has three parts: **Decision**, **Reason**, **Alternatives
  rejected**.
- If a part is not known, write "Not recorded" rather than guess.
- Cite the commit or file the decision lives in, so it can be checked.

---

## 2026-11-15 · Settings cards are collapsible; the password form starts closed

**Decision.** Every Settings card (User Profile, Change Password, Appearance,
Connection, Alert Thresholds) sits in a native `<details>` element with shared
`.card-summary`, `.card-chevron` and `.card-body` styles. Only the password
card starts closed; the others start open so everyday settings are not hidden
behind a click. Closing a settings card keeps unsaved edits (Save and Reset sit
below all cards and act on them); only the password card clears on close, and
only it moves focus into a field on open. The other cards have no component
state: the browser owns their open state.

The change-password form is closed by default. The `<summary>` is the control,
so Enter, Space and the expanded state come from the browser. The element owns
the open state: the `pwOpen` signal only mirrors its `toggle` event, and code
changes it through `setPwOpen()`, never through an `[open]` binding. Opening
focuses the current-password field (not in demo mode, where it is disabled).
Closing clears the fields and the error. A successful change closes the form
and returns focus to the summary; the success message and the demo note sit
outside the details element so they stay visible. A server error keeps it open.
The form stays in the DOM while closed. Files: `settings.html`, `settings.ts`,
`settings.scss`, `settings.spec.ts`. The password API and validation are
unchanged.

**Reason.** The form is rarely used and took a full card. A native control
gives keyboard and screen reader behaviour without custom key handling. An
`[open]` binding only writes when its own last value changes, so after a
native toggle it can be stale and a programmatic close may not reach the
element; one owner (the element) avoids that.

**Alternatives rejected.**
- A `<button aria-expanded aria-controls>` with a hidden panel: more code for
  the same behaviour.
- Removing the form from the DOM with `@if` while closed: breaks existing tests
  that query the fields and messages.
- Binding `[open]` to the signal: the two can disagree (see Reason).
- All cards closed by default: the page would open as a list of headers and
  Save/Reset would act on values the user cannot see.
- Clearing every card on close: would silently drop unsaved settings edits.

## 2026-11-15 · Alerts, threats, map, console and TypeScript colors use theme tokens

**Decision.** The last hard-coded colors (alerts page, alert and threat
drawers, threat map, command console, dashboard charts) follow the token
mapping below (PR 3a). Choices specific to these areas:
- `SEVERITY_COLORS` in `threat.models.ts` holds `var(--c-sev-*-fill)` for
  dots, stripes and strokes; a new `SEVERITY_TEXT_COLORS` holds
  `var(--c-sev-*)` for labels. `scoreToColor` returns the fill tier and the
  new `scoreToTextColor` the text tier. Template bindings that appended a hex
  alpha (`+ '22'`, `'18'`, `'40'`) use the `tint()` helper, which returns
  `color-mix(in srgb, <color> N%, transparent)` with the same alpha (13%, 9%,
  25%).
- The threat map canvas and the command console are always dark. A
  `.theme-dark` class in `styles.scss` shares the dark token block, so those
  subtrees get the dark tokens in both themes without a copy of the values.
  The console uses `--c-accent` for the title, prompt and typed commands
  (was cyan `#00d4ff`), `--c-success` for output, `--c-muted` for the hint and
  placeholder (were `#2a4a6a` and `#1a3a5a`, about 2:1), `--c-text` for input.
- D3 sets map colors with `.style('fill' | 'stroke', 'var(--token)')`: SVG
  presentation attributes cannot resolve `var()`. Land is
  `color-mix(--c-accent 12%, --c-panel)` and borders 25%, which keeps the old
  navy look (`#1c293e` and `#23385b` against `#1a2540` and `#2a3a60`). The
  map hint is `--c-muted` (was white 40%, about 3.3:1). The alert drawer risk
  gauge stroke moved from an SVG attribute to CSS for the same reason.
- ECharts draws on a canvas and cannot read CSS variables, so
  `chart-palette.ts` keeps a copy of the tokens per theme, keyed by variable
  name. Chart roles: axis and legend text `--c-muted` (dark was `#6b7280`,
  about 3.6:1), titles `--c-text-2`, the donut total `--c-text`, grid lines
  `--c-border`, severity and attack type slices the severity fills plus
  `--c-purple-fill`, regions US low, EU `--c-success`, RU critical, CN high,
  IL purple, BR medium, other `--c-muted`, top IP bars `--c-accent`.
  `styles.contrast.spec.ts` fails if any value differs from `styles.scss`,
  and checks text entries for 4.5:1 and marks for 3:1.
- Filled badges (alerts unread count, AbuseIPDB score) use `$sev-*` with
  `$on-sev`; in the dark theme their text is now dark instead of white
  (white on the old blue and orange was 2.2 to 3.8:1).
- Tints that pushed text below 4.5:1: accent text on a 15% accent tint
  measured 4.37:1 (dark, on `--c-panel`), so the "Correlation" source chip
  (alert list and drawer) and the detection timeline icon use
  `$accent-hover` (5.56:1 dark, 6.14:1 light). No tint had to be lowered;
  every other severity, purple and white tint measured 4.53:1 or more on
  `--c-panel` (lowest: `$sev-high` on a 15% tint, light).

**Reason.** Same as the entries below: the fixed values were tuned for the
dark theme and failed in the light theme, and several dark values were
already below 4.5:1.

**Alternatives rejected.**
- Copying the dark values into a separate block for the map and console:
  two sets of values to keep in step; the shared selector has none.
- Reading the CSS variables at runtime with `getComputedStyle` for ECharts:
  depends on render timing after a theme switch and cannot be checked by a
  unit test; the mirror plus the spec can.
- Keeping the console's cyan as a literal exception: the owner chose full
  tokens.

Limits: the 15% severity tints are measured on `--c-panel` and `--c-input`,
where the chips sit; on `--c-bg` the light `$sev-high` chip would be 4.14:1.
The logo gradient in `app.html` is brand artwork and keeps its literal colors.
Black shadows and the mobile backdrop stay literal, as in PR 3a.

Files: `threat.models.ts`, `alerts.scss`, `alerts.html`, `alerts.ts`,
`alert-detail-drawer.component.{scss,html,ts}`,
`threat-detail-drawer.component.{scss,html,ts}`,
`incidents.ts`, `incident-detail.component.{html,ts}`, `threat-map.ts`,
`threat-map.html`, `threat-map.scss`, `command-console.scss`,
`command-console.html`, `dashboard.ts`, `chart-palette.ts`,
`styles.scss`, `styles.contrast.spec.ts`.

## 2026-11-15 · Page colors map to theme tokens; `$green` removed

**Decision.** The dashboard, rules, incidents (list and detail), settings and
threat hunting pages follow the token mapping of the entry below (PR 3a).
The `$green` token (actually `rgba(255, 255, 255, 0.65)`) is removed from
`_tokens.scss`; its five uses map to `$secondary`. Choices specific to these
pages:
- Rules toggle "on" track: `color-mix(--c-text 51%)`. 51% is the lowest
  alpha that reaches 3:1 against `--c-panel` and `--c-bg` in both themes
  (light: 3.09:1 on the panel, 3.00:1 on the background; dark: 4.7 to
  4.8:1). The old 35% measured 2.05:1 in light and 2.90:1 in dark.
- Settings "saved" button: `$secondary` background with `$on-accent` text
  (7.56:1 light, 8.41:1 dark); its hover is `$success` (7.13:1 and 10.86:1),
  replacing the fixed `#15803d`.
- Incidents toast: text is `$text` (8.15:1 light on its `--c-border`
  background); the blue identity is a 35% `$sev-low-fill` border plus a 3px
  `$sev-low-fill` left stripe.
- Accent text on accent tints (rules "New", logic toggle, action chips, save
  buttons, hunt "Run", note "Add") uses `$accent-hover`: with `$accent` the
  rest or hover state measured 3.73 to 4.49:1. The MITRE tag keeps `$accent`
  (4.98:1 light, 4.87:1 dark).
- Dashed "add condition" and "save hunt" buttons: text was the accent at 70%
  alpha (2.91:1 light, 3.47:1 dark); it is now plain `$accent` (5.03:1,
  5.91:1).
- Threat hunting "high" level badge: tint 7% instead of 12% (4.29:1 to
  4.57:1 in light), as for the "high" filter pill.
- Settings logout button: border `color-mix($sev-critical-fill 40%)` for the
  old dark red `#7f1d1d`; text `$sev-critical` at rest and on hover (the old
  lighter hover red `#fca5a5` has no token).
- Empty-state icons use `currentColor` with `$muted`; the task check mark uses
  `$success`.

**Reason.** Same as the entry below: the fixed values were tuned for the dark
theme and were invisible or below 4.5:1 in the light theme.

**Alternatives rejected.**
- A higher toggle alpha (55 to 65%): more contrast than the 3:1 the owner
  asked for, and the "on" dot (`$secondary`) blends further into the track.
- A lighter text color for the logout hover: no matching token, and new
  tokens are out of scope.

Limits: the "on" toggle dot measures 1.74:1 (dark) and 2.14:1 (light)
against its track; the state is shown by the track and the dot position.
The critical row flash on the dashboard peaks at an 18% red tint where
`$muted` text drops to 4.19:1 (light) and 4.43:1 (dark) for under 1.5 s.
Severity colors set from TypeScript (`dashboard.ts`, `incidents.ts`,
`incident-detail.component.ts`) are left for PR 3c, as are alerts, threats,
the threat map and the command console.

Files: `dashboard.scss`, `rules.component.scss`, `rules.component.html`,
`incidents.scss`, `incident-detail.component.scss`,
`incident-detail.component.html`, `settings.scss`,
`threat-hunting.component.scss`, `threat-hunting.component.html`,
`styles/_tokens.scss`.

## 2026-11-15 · Component colors map to theme tokens, no new tokens

**Decision.** Hard-coded colors in components are replaced with the existing
theme tokens; no token is added for them. A translucent tint is
`color-mix(in srgb, var(--c-<token>) N%, transparent)` with the alpha the old
`rgba()` had: blue `rgb(59,130,246)` maps to `--c-accent`, severity hues to the
`-fill` tier, white overlays (hovers, faint borders) to `--c-text`. Text uses
the text tier (`$sev-*`, `$accent`, `$secondary`), `#fff` on a filled button
uses `$on-sev` or `$on-accent`, and inline SVG icons use `currentColor` with a
token on the parent. Black shadows and the mobile navigation backdrop stay as
literal `rgba(0, 0, 0, x)`: a dark shadow or scrim reads correctly in both
themes and has no token. Where a tint pushed text below 4.5:1, the text color
or the tint was adjusted within the existing tokens:
- Accent text on accent tints that sit on `--c-bg` (filter pill "All", export
  button) uses `$accent-hover`: `$accent` measured 4.40:1 in the light theme.
- The user avatar and the "All" pill tint drops from 15% to 10%.
- The "high" filter pill tint drops from 12% to 7%: `$sev-high` on a 12% tint
  over the light `--c-bg` measured 4.29:1 (now 4.57:1).

**Reason.** The fixed values were tuned for the dark theme only. In the light
theme white overlays were invisible (about 1.0:1), and severity text on its
tint measured 1.7 to 3.0:1. `color-mix()` of a token keeps the same look in
dark and follows the light theme without new variables to keep in step.

**Alternatives rejected.**
- New overlay or tint tokens (`--c-hover`, `--c-accent-tint`, ...): more
  variables to keep in sync for values `color-mix()` already gives.
- Themed shadow tokens: shadows are near-invisible on the light background
  either way, and nothing depends on them for contrast.

Limits: this entry covers the app shell, shared drawer and filter bar, filter
pills, export menu, login and admin users (PR 3a). Dashboard, rules,
incidents, settings and threat hunting (3b) and alerts, threats, threat map,
command console and the TypeScript colors (3c) follow. The `$green` token is
still used in 3b areas.

Files: `app-layout.scss`, `app-layout.html`, `styles/_drawer.scss`,
`styles/_filter-bar.scss`, `filter-pills.component.scss`,
`export-menu.component.scss`, `login.scss`, `login.html`,
`admin-users.component.scss`.

## 2026-11-14 · Themed palette with separate text and fill tiers

**Decision.** Both themes are defined only as CSS variables in
`frontend/src/styles.scss`. The severity colors (`--c-sev-critical`, `-high`,
`-medium`, `-low`) and `--c-purple` are themed. Each has two tiers: the plain
name is for text and must reach 4.5:1 on `--c-bg` and `--c-panel`. The
`-fill` name is for dots, bars and other non-text marks and must reach 3:1.
`--c-on-sev` is the text color on a severity background and must reach 4.5:1
on each one. Filled accent buttons use `--c-accent` with `--c-accent-hover`
on hover, and `--c-on-accent` as their text color, which must reach 4.5:1 on
both fills (dark theme: dark text on a lighter hover; light theme: white text
on a darker hover). In the dark theme the two tiers are the same color; in the light
theme only the text tier is darker, so dots stay bright. `_tokens.scss` exposes
them as `$sev-*`, `$sev-*-fill`, `$purple`, `$purple-fill`, `$on-sev`,
`$accent-hover` and `$on-accent`.
Because the tokens are CSS variables, transparency uses `color-mix()`, not
Sass `rgba()`. `src/styles.contrast.spec.ts` checks every ratio and fails if
any SCSS file applies a Sass color function (`rgba()`, `mix()`, `lighten()`
and similar) to a `var()`-based token.

**Reason.** The fixed severity hex values passed on the dark panel but failed
as text in the light theme (1.9 to 3.7:1), dark muted text was 2.4:1, purple
was 4.37:1 on the new dark panel, and white text on the severity badges was
2.2 to 3.8:1. White text on the filled accent buttons was 3.68:1 in the
dark theme and would have dropped to 3.20:1 with the lighter dark accent; its
hard-coded `#2563eb` hover could not serve both themes. One value per severity cannot be both a readable text color and
a bright dot in the light theme. Sass `rgba($accent, x)` compiled to
`rgba(var(--c-accent), x)`, which is invalid CSS, so those rules were silently
dropped.

**Alternatives rejected.**
- One darker value per severity for both text and dots: passes, but makes the
  light theme dots dull for no contrast gain.
- Keeping severity colors as fixed Sass hex values: cannot differ by theme.

Limits: hard-coded severity hex values in component SCSS and in
`threat.models.ts` / `dashboard.ts` do not use these tokens yet (follow-up
PR). Panel borders are decorative and stay below 3:1. The `rgba($green, x)`
uses (a literal white overlay, so valid CSS) are left for the follow-up PR,
as is the settings `.btn-save.saved` state (white overlay background, green
`#15803d` hover).

Files: `frontend/src/styles.scss`, `frontend/src/styles/_tokens.scss`,
`frontend/src/styles.contrast.spec.ts`; buttons in `login.scss`,
`settings.scss`, `admin-users.component.scss`,
`incident-detail.component.scss`.

## 2026-11-14 · Demo backfill at startup

**Decision.** In demo mode, when the threat feed falls back to the bundled
sample (`FEED_STATUS.state == "sample"`), startup records the last 15 minutes
of simulated events (40 per minute, at most `MAX_BACKFILL_EVENTS` = 600) into
the in-memory stores, so `/api/stats` and the charts built from it are
populated for the first visitor. The backfill never runs on live or cached
data, never outside demo mode, and never evaluates alert rules. The sample
keeps its public Censys scanner IPs.

**Reason.** A fresh demo process had no history: the stats charts started at
zero and filled over minutes. Generating the backfill at startup keeps the
timestamps relative to now, so it cannot go stale, and reuses the same event
generator as the live stream. Skipping rule evaluation keeps startup from
raising a burst of alerts.

**Alternatives rejected.**
- A committed JSON file of synthetic events: its timestamps go stale, it
  duplicates the generator's event shape, and it grows the repo.
- IPs from the documentation ranges (192.0.2.0/24, 198.51.100.0/24,
  203.0.113.0/24): `store.validate_ip` rejects them as non-public, so every
  IP action in the UI (lookup, block, case from IP) would fail with 422 for
  every demo event, and `_clean_ips` would drop them. Allowing them would
  loosen a security control.

Limits: the region chart, the summary cards and the map are built from the
WebSocket events in the browser, which the backfill does not replay; they
fill from the live sample stream within seconds. The behavioral loop treats
backfilled events like live ones, so it may raise RepeatedIP alerts about a
minute after startup, as the live stream would within ten minutes.

Files: `backend/simulation.py` (`backfill_demo_events`), `backend/store.py`
(`record_backfill`), `backend/main.py` (lifespan),
`backend/tests/test_demo_seed.py`.

---

## 2026-11-14 · WebSocket session revocation

**Decision.** A WebSocket stream ends when its session does. The ticket from
`/auth/ws-ticket` carries the session's role, session key (`sk`) and session id
(`sid`). `threats_ws` checks them at the handshake and again before every
message, and at least every `WS_RECHECK_SECONDS` (2 s) while the stream is
idle, using the same checks as HTTP requests (`store.session_claims_valid`).
When they fail the server closes the stream with code 4001. Logout, user
deletion, role change and password resets therefore end an open stream, and a
ticket issued before them cannot open a new one. The frontend treats 4001 as
"session ended": it requests one new ticket, reconnects if that succeeds (own
password change rotates the key but keeps this tab signed in) and otherwise
shows "signed out" without retrying.

**Reason.** Before this change the handshake checked only the ticket's
signature, expiry and type, and the stream never re-checked anything, so an
open connection kept receiving events after logout, deletion or a reset until
the client closed it. The checks are in-memory lookups, so running them per
message costs almost nothing: a busy stream (events every 0.5 to 1.5 s) closes
within about 1 s of a revocation, an idle one within about 2 s
(`WS_RECHECK_SECONDS`). The interval was first 10 s and was lowered to 2 s
after a manual test where an idle stream took about 10 s to close.

**Alternatives rejected.**
- A connection registry keyed by session or user, closed from logout and the
  user-admin paths: closes at once even when idle, but needs hooks in every
  place that revokes a session and couples those modules to the stream, for at
  most `WS_RECHECK_SECONDS` of gain. Not done yet; revisit if the stream ever
  goes quiet for long periods or the delay matters.
- Re-checking on a timer only: simpler loop, but up to a full interval of
  events after revocation while the stream is busy.

Limits: when no events flow (for example, the simulation is paused because
there is no AbuseIPDB key and no cache), revocation is caught only by the
idle re-check, so within `WS_RECHECK_SECONDS`. Revocations live in each
process's memory, so this holds for a single
uvicorn worker (the documented setup, `build.sh` and README). The stream does
not end when the 8-hour session token itself expires; that is not covered by
this decision.

Files: `backend/main.py` (`threats_ws`), `backend/store.py`
(`session_claims_valid`), `backend/routers/auth.py` (`ws_ticket`),
`frontend/src/app/core/services/threats.service.ts`. Commits: 83ac9f2 (backend),
d83dec1 (frontend).
