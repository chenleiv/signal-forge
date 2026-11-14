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
