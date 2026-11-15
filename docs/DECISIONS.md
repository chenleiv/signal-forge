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
