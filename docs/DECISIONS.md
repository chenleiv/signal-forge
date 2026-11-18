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

## 2026-11-18 · Settings: the Alert Thresholds card is removed

**Decision.** The Alert Thresholds card (critical, high and medium minimum
scores) and the `criticalThreshold`, `highThreshold` and `mediumThreshold`
fields of `AppSettings` are removed. Old saved values are dropped on load
through `LEGACY_KEYS` in `settings.service.ts`.

**Reason.** Nothing read the values. Severity comes from the server with each
event, so the card saved numbers that changed nothing, and an analyst could
believe they had retuned severity when they had not.

**Alternatives rejected.** Wiring the thresholds into the client: severity
would then differ between the browser and the server, and between analysts.
Moving them to the server as a shared setting: a separate feature, not
recorded as needed.

---

## 2026-11-18 · Console toggle: chip-height look, 44px hit area on touch

**Decision.** At or below `$tablet` the topbar console toggle (`>_`) keeps
its 36x21 desktop look and gets its touch target from an invisible `::after`
(inset -12px -4px), a 44x45 hit area. It replaces `min-width` and
`min-height: 44px` on the button itself. Desktop is unchanged.
The heights are explicit: the button is `height: 21px` and the chip
`height: 19px` (both from `$topbar-control-height`, with `line-height: 1`
and no vertical padding), so they no longer follow the fonts installed. With
`line-height: normal`, Linux fonts made the chip 18px, a 3px gap that failed
CI.
See `app-layout.scss`; guarded by `e2e/responsive-tools.e2e.ts`.

**Reason.** The 44x44 button stood far taller than the LIVE FEED chip (19px)
and the clock (12px) on phones and tablets, so the row looked uneven. The
hit area stays inside the 46px topbar and ends 4px before the chip (8px gap
on phones, 16px on tablets), so a tap on the chip never hits the button.

**Alternatives rejected.**
- Shrinking the button with no hit area: below the 44px touch target used
  for every single button at or below `$tablet`.
- Padding 2px to match the chip's 19px exactly: changes desktop too; the 2px
  difference with centres aligned was accepted by the owner.
- Growing the chip and clock to 44px: changes their look for a button's sake.

## 2026-11-18 · Admin password reset hashes off the event loop

**Decision.** `update_user` (admin or manager resetting another user's
password) runs `hash_password` with `run_in_threadpool`, as
`change_own_password` already did. The await lets other requests run between
the router's permission check and the write, so after hashing `update_user`
answers 409 if the user was deleted or got another role meanwhile.

**Reason.** bcrypt at 12 rounds takes about 0.25 s; on the event loop it
paused every request and WebSocket stream during a reset. The 409 keeps the
permission check valid: a manager may reset only analysts, and a role change
during the hash must not let the reset through.

**Alternatives rejected.**
- Hashing in the router before the permission check: spends bcrypt time on
  requests that are then denied.
- No re-check after the await: a concurrent promotion or deletion would be
  ignored.

Tests: new `backend/tests/test_admin_reset_threadpool.py`: the hash runs in a
thread with no event loop, and a manager's reset of an analyst who is deleted
or promoted during the hash gets 409 with the password and session key
unchanged. Both fail against the previous `update_user`.

Files: `backend/user_admin.py` (`update_user`).

## 2026-11-18 · WebSocket stream ends when the session token expires

**Decision.** `/auth/ws-ticket` copies the session's `exp` into the ticket as
`sexp` (epoch seconds). The handshake (`_ws_ticket_claims`) rejects a ticket
whose `sexp` is missing, not a number (a bool counts as invalid) or already
past, with 4001. This check runs last, so every other rejection keeps its own
reason. In `threats_ws` the idle wait is `min(WS_RECHECK_SECONDS, seconds
until sexp)` and the stream closes with 4001 (`WS_SESSION_ENDED`) when the
session has expired or `session_claims_valid` fails. `/auth/ws-ticket` answers
401 for a session with no usable `exp` (`jwt.decode` checks `exp` only when
present), so it never issues a ticket the handshake would reject; the server
and the handshake share `store.usable_expiry`. The 60/minute limit on
`/auth/ws-ticket`, the ticket's own 5-minute `exp` and the first-message flow
are unchanged.

The frontend did not change: on 4001 it requests one ticket, the expired
cookie gets 401, and it shows SIGNED OUT with no reconnect, as for any other
ended session.

**Reason.** An open stream outlived its 8-hour session: nothing in the
ticket told the stream when the session ended (the "Limits" of the
2026-11-14 entry).

**Alternatives rejected.**
- A new close code for expiry: the client already handles 4001 the right
  way; a new code needs client changes and a deploy where client and server
  ship together.
- The expiry check inside `store.session_claims_valid`: the HTTP path already
  gets it from `jwt.decode`, and session tokens have no `sexp`.
- Treating a ticket without `sexp` as never expiring: fail open.
- Capping the ticket's 5-minute `exp` at the session's `exp`: the handshake
  check already rejects such a ticket.

**Correction: deletion versus password reset.** A manual test (2026-11-14,
commit 83ac9f2, idle re-check then 10 s) saw a deleted user's stream close
after about 10 s and a password reset's almost at once. The cause was timing,
not the action: both rotate the user's session key in memory before the
response (`user_admin._apply`), and the stream only sees that the key no
longer matches, at its next check (before the next event, or at the idle
re-check). The stream is idle when there are no threat IPs, the usual local
setup with `DEMO_MODE=false` and no AbuseIPDB key or cache. Each action was
tried once, so one landed just before a 10 s tick and the other just after.
The 2026-11-14 entry describes this only as "an idle stream took about 10 s".
`test_admin_action_closes_an_idle_stream_within_one_recheck` measures
deletion, password reset and role change on an idle stream with a 0.3 s
re-check: 5 runs in a row, 15 of 15 passed, each case 0.31 s from open to
close (bound 1.0 s). Not explained: in a browser the deleted user's tab
polls `/api/stats` every 5 s, gets 401 and leaves for `/login`, which closes
the socket from the client, so a browser should have seen at most about 5 s.

Deploy: a ticket issued by the old server just before the deploy has no
`sexp`, so the new server rejects it once with 4001; the client requests a
fresh ticket (with `sexp`) and reconnects. Without a database, session keys
are new after a restart anyway, so old cookies get 401 and show signed out.

E2E rate limit counts after this change (uvicorn access log, one pass each,
every pass under 60 seconds): phone 36 `/auth/ws-ticket` and 34
`/api/stats` (43.5 s), desktop 26 and 23 (39.8 s), tablet 32 and 30
(41.9 s), no 429s. The new spec stubs both routes and adds none.

Tests: one existing helper changed test data only, approved by the owner:
`_ws_ticket` in `test_security.py` gains a `sexp` claim, so its control
ticket stays valid; no assertion changed. New:
`backend/tests/test_ws_session_expiry.py`,
`threats.service.expiry.spec.ts`, `e2e/ws-session-expiry.e2e.ts`.

Files: `backend/main.py` (`_ws_ticket_claims`, `_seconds_left`,
`threats_ws`), `backend/routers/auth.py` (`ws_ticket`), `backend/store.py`
(`usable_expiry`), `README.md`.

## 2026-11-17 · WebSocket ticket as the first message, not in the URL

**Decision.** The client opens `/ws/threats` with no query string and sends
the ticket from `/auth/ws-ticket` as the first message:
`{"type": "auth", "ticket": "<jwt>"}`. The server accepts the socket, waits
up to `WS_AUTH_TIMEOUT_SECONDS` (5 s) for that message, runs the same checks
as before (HS256 signature, expiry, `typ: "ws"`, `session_claims_valid`) and
answers `{"type": "ready"}`; events follow. A missing, malformed, binary,
oversized (over `WS_AUTH_MAX_CHARS`, 4096) or invalid ticket closes with 4001;
no first message in time closes with 4408 (`WS_AUTH_TIMEOUT`). A `?ticket=`
in the URL is ignored. Nothing in this path is logged. The frontend sets
"connected", resets the backoff and clears the one-check flag for 4001 on
`ready`, not on open. Unchanged: a 401/403 on the ticket request is signed
out with no retry; a 4001 triggers one ticket check, then signed out; every
other close code (4408 included) reconnects with the doubling backoff. The
per-IP limit on `/auth/ws-ticket` (60/minute) is unchanged.

**Reason.** The ticket is a session credential for 5 minutes. In the query
string it was written to the uvicorn access log and to proxy logs (Render) on
every connect. In a message it never appears in a request line; the e2e
server log now shows `"WebSocket /ws/threats" [accepted]`.

Before this change the server closed a bad ticket before accepting the
socket, which a browser sees as 1006, so the 4001 path in the frontend only
ran for a stream that had been open. Now a rejected ticket reaches the
browser as 4001. Resetting the session check on open would then loop (open,
4001, check, open, 4001, ...) with no backoff, so it moved to `ready`. A new
e2e test (`e2e/ws-ticket.e2e.ts`) checks this in a real browser: an invalid
ticket gives exactly two ticket requests and two sockets, then SIGNED OUT.

4408 for the timeout, not 4001: a slow network must not sign the user out
after two slow opens; a plain reconnect with backoff is enough.

**Alternatives rejected.**
- The ticket in a `Sec-WebSocket-Protocol` header: browsers send it in the
  handshake, where proxies may log headers, and the server must echo a
  protocol back.
- The session cookie on the WebSocket handshake: `wsUrl` can point at
  another host (Settings), where the cookie is not sent, and the stream
  would depend on the cookie again instead of a short-lived ticket.
- No ready frame ("connected" on open): the client could not tell an
  accepted socket from one about to be closed, see the loop above.

**Known gap.** The server now accepts a socket before it is authenticated,
so an unauthenticated socket can stay open for up to 5 s
(`WS_AUTH_TIMEOUT_SECONDS`) each, and there is no per-IP limit on WebSocket
connections. Before, a bad ticket was refused at the handshake. Not
addressed here; a per-IP connection cap is the likely fix if it matters.

E2E rate limit counts after this change (uvicorn access log, one pass each,
every pass under 60 seconds): phone 36 `/auth/ws-ticket` and 34
`/api/stats`, desktop 26 and 24, tablet 32 and 30, no 429s. The new spec
stubs both routes and adds none.

Deploy: client and server must ship together. An old tab still sends the
ticket in the URL; the new server ignores it and closes with 4408, so the
tab keeps reconnecting with backoff until it is refreshed.

Tests: the existing WebSocket tests only changed how they connect (shared
helper `backend/tests/ws_client.py`; `FakeWebSocket.open()` in the two
`threats.service` specs now also delivers the ready frame); no assertion
changed. New: `backend/tests/test_ws_first_message.py`,
`threats.service.auth.spec.ts`, `e2e/ws-ticket.e2e.ts`.

Files: `backend/main.py` (`threats_ws`, `_ws_ticket_claims`),
`frontend/src/app/core/services/threats.service.ts`, `README.md`.

## 2026-11-17 · E2E: one pass per project for rate limit headroom

**Decision.** `npm run e2e` runs phone, desktop and tablet each in its own
Playwright pass (before: phone and desktop together, then tablet). Each pass
starts a fresh server, and the per-IP limits are in memory, so each pass
starts at zero. CI runs the same script (`ci.yml`, step renamed). The server
limits and the tests are unchanged.

Measured locally (uvicorn access log, every pass ran under 60 seconds, so
each total is the count for one limit window):

| Pass | `/auth/ws-ticket` (limit 60) | `/api/stats` (limit 50) | Time |
| --- | --- | --- | --- |
| Before: phone + desktop | 60 OK + 1 rejected (429) | 50 OK + 6 rejected (429) | 53.2s |
| Before: tablet | 32 | 31 | 30.2s |
| After: phone | 36 | 34 | 32.1s |
| After: desktop | 26 | 24 | 27.6s |
| After: tablet | 32 | 31 | 30.2s |

Total time: 83.4s before, 89.9s after (about +6.5s for one more build and
server start; the local Angular build was cached at about 3s, so CI may add
more). The phone pass, the largest, uses 60% of the ticket limit and 68% of
the stats limit.

**Reason.** The phone and desktop pass already got 429s on both routes
(see "E2E headroom" in the Settings entry below), so one more page load
could fail an unrelated test.

**Alternatives rejected.**
- A shared fixture that stubs `/api/stats` and aborts `/auth/ws-ticket` in
  every spec: it changes every existing spec, and the tests that need the
  live stream (threats table, drawer, the stats 429 banner) would need
  opt-outs.
- An opt-in stub helper applied to existing specs: edits existing tests for
  less headroom than separate passes.
- Raising the server limits: they are a security control.

The rule for new specs stays: stub `GET /api/stats` and abort
`GET /auth/ws-ticket` unless the test needs the live stream.

Files: `frontend/package.json`, `frontend/playwright.config.ts` (comment),
`.github/workflows/ci.yml` (step name).

## 2026-11-17 · Settings: Save only with changes, every card starts closed

**Decision.**
- Save Settings is enabled only when the form differs from the stored
  settings: `dirty` in `settings.ts` compares each field of the form with
  `SettingsService.settings()`. Reverting the values disables it again.
  `save()` returns without storing when nothing changed (checked in the
  handler, not only on the button). After a save the button shows "✓ Saved"
  for 2 seconds and stays disabled until the next change.
- The password button keeps its own rule (`canSubmitPw`: enabled only when the
  form is valid; always disabled in the demo).
- A disabled `.btn-save` (both buttons) looks disabled: transparent
  background, a `$border` border and `$muted` text; the padding is 1px smaller
  so the border does not change the size. `$muted` is already guarded at
  4.5:1 on `$bg` and `$panel` in both themes (`styles.contrast.spec.ts`). The
  "✓ Saved" state keeps its own look while it shows. Before, the disabled
  password button looked the same as an enabled one.
- All five Settings cards start closed (before: only the password card, see
  "Settings cards are collapsible" below). Only the password card clears its
  fields on close.

**Reason.** An always-enabled Save gave no sign of unsaved changes and stored
the same values again; a disabled button that looks enabled reads as broken.
All cards closed: owner decision, reason not recorded.

**Alternatives rejected.**
- `opacity` for the disabled look: it lowers text contrast with no measured
  value.
- Comparing with `JSON.stringify`: depends on key order.

E2E headroom (not changed here): the phone and desktop pass sits at about 59
of the 60 `/auth/ws-ticket` requests per minute the server allows per IP (one
ticket per signed-in page load), and every signed-in page polls `/api/stats`
(50 per minute per IP). One extra page load made
`small-fixes.e2e.ts` "a 429 on /api/stats" fail: both ticket requests got
429, the socket never opened, so stats polling never started (seen in a
Playwright trace). New e2e specs must stub `GET /api/stats` and abort
`GET /auth/ws-ticket` with `page.route`, as `e2e/settings-save.e2e.ts` does.
The server limits stay as they are.

The existing test "each card is a details element ... every card starts
closed" in `settings.spec.ts` changed its title and expected open states,
approved by the owner; no other test changed.

Files: `settings.ts`, `settings.html`, `settings.scss`, `settings.spec.ts`
(one test), new specs `settings.save.spec.ts`, `e2e/settings-save.e2e.ts`.

## 2026-11-17 · Small fixes: stream reconnect, stats 429, toggle contrast, touch targets

**Decision.**
- Live stream (`threats.service.ts`): a failed `/auth/ws-ticket` request
  in `connect()` no longer stops the stream. 401 or 403 shows "signed out"
  with no retry; any other error (server down or starting) retries with a
  doubling delay from the reconnect setting (default 3s), capped at 30s and
  reset when a socket opens. Stats and alerts polling restart with each
  socket. A replaced socket can no longer schedule its own reconnect.
- `/api/stats` 429 (the open item in "Tablet breakpoint" below): the client
  pauses stats polling for one 60-second window, the server's fixed window
  (it sends no `Retry-After`), and sets `statsLimited` until the next
  successful poll. The server limit is unchanged. While it is set, the shell
  shows a "STATS" banner (`role="status"`, same style as the feed banner):
  live stats are paused, retrying in about a minute.
- Rule toggle on-dot: `--c-input` instead of `--c-text-2`. Measured against
  the on track (`--c-text` at 51%): dark 4.89:1 over the page, 5.23:1 over
  the panel; light 3.53:1 and 3.30:1. Before: 1.74/1.63 (dark), 2.14/2.29
  (light). Guarded by `e2e/small-fixes.e2e.ts` in both themes.
- Touch: at or below `$tablet` the rule toggle keeps its 28x16 look and gets
  a 44x44 hit area from an invisible `::after` (inset -14px -8px), which stays
  inside its row and clear of the rule name; the console input is 44px.
- Login demo hint (the demo username and password): on phones it wraps to a
  second line whole instead of losing the end of the password.
- Accessible names for icon-only buttons (Hunting, Rules, console), and
  `aria-pressed` on the rule toggle.

Measured only, no change: the Settings saved button with `--c-on-accent`
text is 8.41:1 on `--c-text-2` and 10.86:1 on the `--c-success` hover in dark,
7.56:1 and 7.13:1 in light.

**Reason.** After a backend restart the first reconnect usually reaches a
server that is still starting; the ticket error set "disconnected" and nothing
retried, while the chip read "RECONNECTING...". Without a database, session
keys are new after a restart, so the old cookie gets a 401: that is signed
out, not reconnecting.

**Alternatives rejected.**
- Raising or bypassing the `/api/stats` limit: it is a security control.
- Reworking the rule row for a larger toggle: the `::after` hit area is
  enough and keeps the look.
- Retrying alerts polling on 429: `GET /api/alerts` has no rate limit.

The banner needed one line of test data in the existing
`app-layout.spec.ts` stub (`statsLimited: signal(false)`), approved by the
owner; no assertion changed.

Files: `threats.service.ts`, `app-layout.html`, `app-layout.spec.ts` (stub
only), `threat-hunting.component.html`,
`rules.component.html`, `rules.component.scss`, `command-console.html`,
`command-console.scss`, `login.scss`, new specs
`threats.service.reconnect.spec.ts`, `rules.component.a11y.spec.ts`,
`threat-hunting.component.a11y.spec.ts`, `e2e/small-fixes.e2e.ts`.

## 2026-11-16 · Tool pages on tablets and phones

**Decision.** Threat Hunting, Detection Rules, Settings, Users, Login and the
console toggle adapt at `$tablet` (1024px) and `$narrow` (768px):
- Threat Hunting on phones: the query panel stacks above the results in the
  same DOM order, so the keyboard order is unchanged, and the page scrolls.
  The saved hunts list is capped at 30vh with its own scroll.
- Login on phones: the card is `min(360px, 100% - 32px)` wide, with 16px
  above and below and 24px/20px card padding.
- Users on phones: 12px page and 16px card padding; row actions, the role
  select, the form fields and Create are 44px.
- Single buttons are 44px at or below `$tablet`: Hunting Run, Clear, Save,
  saved hunt delete and investigate; Rules New, Add Condition, back, Cancel,
  Save, condition and rule delete; the console toggle. Chip groups (Rules
  AND/OR and actions) are 32px. Settings card headers (open/close) are 44px.
- The console toggle gets the accessible name "Toggle console" (it was
  ">_"); template only.

Every rule sits inside a `max-width` query, so 1025px and up is unchanged
(guarded by desktop tests at 1025px in `e2e/responsive-tools.e2e.ts`). The
Hunting tests stub only GET `/api/hunt` and GET `/api/hunts`.

**Reason.** Measured before the change at 390px: the 260px hunting panel
left 130px for the results; at 360px the login card touched both screen
edges, and at 320px the demo hint was clipped by 10px; users row actions were
26px; the console toggle was 36x21 at 390px and 820px. Rules and Settings did
not overflow at 390px or 820px, so only touch sizes changed.

**Alternatives rejected.**
- A 40vh cap on saved hunts: with 44px buttons, the results began at 854px
  on an 844px screen.
- One-pane hunting on phones, like Rules: hiding the query panel would hide
  the query that produced the results.
- Changing the Users form layout: its fields were already full width at
  390px (`auto-fit` gives one column).

Files: `threat-hunting.component.scss`, `login.scss`,
`admin-users.component.scss`, `rules.component.scss`, `settings.scss`,
`app-layout.scss`, `app-layout.html`, `e2e/responsive-tools.e2e.ts` (new).

## 2026-11-16 · Data pages on tablets and phones

**Decision.** Dashboard, Alerts, Incident detail and Threat Map adapt at
`$tablet` (1024px) and `$narrow` (768px):
- Alerts, at or below `$tablet`: the detail drawer opens over the list
  (capped at 90%) instead of beside it. On phones the five metrics form a
  2 to 3 column grid and the filters become one wrapping row per section
  above the list, with 32px chips and an 8px gap.
- Single buttons are 44px touch targets at or below `$tablet`: the Alerts and
  Incident drawer close buttons and the Threat Map filter buttons. Chip groups
  (Alerts filters, Incident status buttons on phones) are 32px, above the
  24px WCAG AA minimum.
- Incident detail on phones: status buttons wrap two per line with the arrows
  hidden; the meta grid is one column.
- Dashboard at or below `$tablet`: charts in a 2x2 grid; the page scrolls and
  the stream row keeps at least 300px.
- Threat table: no change; it already fits at 390px and 820px. A test guards it.

Every rule sits inside a `max-width` query, so 1025px and up is unchanged
(guarded by desktop tests at 1025px). The new tests in
`e2e/responsive-data.e2e.ts` stub only the GET alerts list, alerts summary
and incidents list with `page.route`, because the test server has no alerts
or incidents for the first 30 seconds or more.

**Reason.** Measured before the change: at 390px the Alerts metrics were
27px wider than the screen and the 160px filter column left 230px for the
list; at 820px the 420px drawer beside the list would leave it about 240px.
The Threat Map filters did not overflow at 390px (the last button ended at
309px) but were 22px tall. A 2x2 chart grid without scrolling would shrink
the stream panel to about 130px on a 1024x768 screen.

**Alternatives rejected.**
- 44px Alerts filter chips: 14 chips would wrap to about five rows and push
  the list down.
- Wrapping the Threat Map filters for overflow: there was none; only the
  touch size changed.
- Waiting for real alerts and incidents in e2e: too slow and not
  deterministic.

Files: `alerts.scss`, `alert-detail-drawer.component.scss`,
`incident-detail.component.scss`, `dashboard.scss`, `threat-map.scss`,
`e2e/responsive-data.e2e.ts` (new).

## 2026-11-16 · Tablet breakpoint: the slide-in menu up to 1024px

**Decision.** A second breakpoint, `$tablet: 1024px`, joins `$narrow: 768px`
in `_tokens.scss`. At or below `$tablet`:
- The sidebar is the same slide-in menu as on phones (menu button, backdrop,
  Escape closes it), with 44px menu and logout buttons. The breadcrumb, clock
  and short demo text still change only at `$narrow`.
- Overlay drawers (Threats, Incidents) are capped at 90% width so the page
  stays visible; the resize handle is hidden. Phones keep full width.
- Settings shows one column of cards; each card keeps two field columns.
- On phones the console is at most 40% of the screen height and hides its
  keyboard hint.

Every new rule sits inside a `max-width` query, so desktop above 1024px is
unchanged. E2E gains a `tablet` project (820x1180, touch) that skips the
phone-only one-pane rules test (`grepInvert`), plus new tests in
`e2e/responsive.e2e.ts`. `npm run e2e` runs the tablet project in a second
pass with its own server.

**Reason.** Between 769 and 1024px the fixed 220px sidebar left about 580px
for the page. In one pass, the extra tablet page loads exceed the 50/minute
per-IP limit on `/api/stats`, and the threats table stays empty.

**Alternatives rejected.**
- An icon rail sidebar on tablets: the owner chose the same slide-in menu.
- Raising or bypassing the `/api/stats` rate limit for tests: it is a
  security control.
- One-pane rules on tablets: two panes fit at 820px.

**Open item for PR 7.** `/api/stats` 429s are dropped silently
(`threats.service.ts`, `catchError(() => EMPTY)`): several users behind one
shared IP, each polling every 5 seconds, can exhaust 50 requests per minute
and the live table stays empty with no message.

Files: `_tokens.scss`, `_drawer.scss`, `app-layout.scss`,
`command-console.scss`, `settings.scss`, `playwright.config.ts`,
`package.json`, `e2e/responsive.e2e.ts` (new).

## 2026-11-16 · Users page: load states, keyboard focus and themed row styles

**Decision.** The admin users page keeps its table (one row per user) and
gains:
- A loading state (three skeleton lines in a `role="status"`,
  `aria-busy="true"` region with hidden "Loading users" text), an empty state
  ("No users yet" with a `currentColor` icon in `$muted`), and a load error
  inside the Accounts card with a Retry button. Retry calls the same
  `getUsers()` again; it moves focus to the Accounts heading on success and
  keeps it on Retry on failure. The load error no longer uses the page-level
  error message, which stays for action errors.
- A user count next to the Accounts heading, `scope="col"` headers and a
  hidden table caption.
- Focus handling: opening a reset focuses the password field; the field sits
  in a `<form>`, so Enter saves. A delete confirmation focuses Cancel, the
  safe choice. Escape closes either one and returns focus to the button that
  opened it; a successful reset also returns focus there. After a delete the
  row is gone, so focus moves to the Accounts heading (`tabindex="-1"`).
  Focus moves by element id in `afterNextRender`, after the new controls
  exist.
- Reset and Delete buttons carry an `aria-label` with the username
  ("Reset password for alice"); the visible text is unchanged.
- Cancelling a reset clears the typed password. Opening a reset closes an
  open delete confirmation and the other way round, so only one is open.
- Styles, all from existing tokens with no new tokens: row hover and
  focus-within `color-mix(--c-text 4%)`; read-only roles as a pill,
  `$secondary` on `color-mix(--c-text 6%)`; the "you" tag `$accent-hover` on
  `color-mix(--c-accent 10%)` with a 40% accent border; selects and inputs
  get a 2px `$accent` focus ring, as the buttons already had.

Measured contrast, dark / light (WCAG sRGB, tints composited over
`--c-panel`, and over the hovered row where they can sit on one):
- Row hover: `$text` 13.31 / 12.82, `$secondary` 6.99 / 6.60, Delete text
  `$sev-critical` 5.69 / 5.65.
- Role pill text: 6.63 / 6.36; on a hovered row 5.95 / 5.92.
- "you" tag text: 6.01 / 6.60; on a hovered row 5.44 / 6.16.
- Focus ring `$accent`: on the panel 5.40 / 5.55, on a hovered row
  4.91 / 5.16, on `--c-input` 6.00 / 5.91.
- Empty icon `$muted` 5.77 / 5.54; empty text and count `$secondary`
  7.68 / 7.10; load error border `$sev-critical-fill` 6.25 / 4.54.

Every value met its target (4.5:1 text, 3:1 rings, icons and borders) on the
first measurement, so no tint or color had to change.

**Reason.** The page had no loading, empty or error state beyond plain text,
its inline reset and delete controls left keyboard focus behind, and its
row actions had the same name on every row for screen readers.

**Alternatives rejected.**
- Cards instead of a table: the layout per screen size belongs to the
  responsive PR, and existing tests read table rows.
- A collapsible "New user" card like Settings: the owner chose to leave it
  as it is.
- Skeleton rows inside `<tbody>`: they would count as user rows.

Limits: the API, permission checks and password rules are unchanged. Phone
layout is unchanged (the table still scrolls inside `.h-scroll`).

Files: `admin-users.component.html`, `admin-users.component.ts`,
`admin-users.component.scss`, `admin-users.component.spec.ts` (new tests
only).

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
(Note, 2026-11-18: `app.html` was the unused Angular starter template, never
rendered, and its gradient was the starter's Angular logo. It was deleted in
`Remove unused frontend code`.)
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
this decision (since 2026-11-18 it does, see "WebSocket stream ends when the
session token expires", which also corrects the 10 s manual test above).

Files: `backend/main.py` (`threats_ws`), `backend/store.py`
(`session_claims_valid`), `backend/routers/auth.py` (`ws_ticket`),
`frontend/src/app/core/services/threats.service.ts`. Commits: 83ac9f2 (backend),
d83dec1 (frontend).
