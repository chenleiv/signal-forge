# SignalForge security report

**As of:** 2026-11-28, verified against commit `33127fc` on `master`
("Replace the Angular favicon with the SignalForge logo (#70)").

Each claim below was checked against the repository at that commit, its git
history, its tests and `docs/DECISIONS.md`, unless a different source (a
measurement on the hosting platform, a GitHub setting, an owner's account)
is named next to it.

---

## 1. Summary

SignalForge is a SOC-style dashboard demo (Angular 21, FastAPI, Python 3.13)
with simulated data. It is not a SIEM and monitors no real network. It is
deployed as one public demo on Render with public read-only demo accounts.

Security work was done in small pull requests. Each one names its finding,
adds tests that fail against the previous code, and records the decision,
the rejected alternatives and what was not verified in `docs/DECISIONS.md`.

The main results:

- The public demo shows only simulated IP addresses from the documentation
  ranges, and refuses lookups of any other address before an external
  service is called.
- The WebSocket stream no longer puts its credential in a URL, ends with the
  session, caps connections and message size, and refuses client messages.
- Rate-limit keys cannot be chosen by the client through `X-Forwarded-For`;
  a short chain fails closed.
- Python dependencies are hash-locked and audited, npm runtime packages are
  audited, GitHub Actions are pinned to commit SHAs, and Dependabot proposes
  updates after a cooldown.
- A set of smaller hardening items (CSP scope, CORS, bcrypt off the event
  loop, token placement, error output, quotas, ownership, CSV export).

There has been no external penetration test and no formal audit. The code
reviews were carried out by the owner with AI assistance (Claude Code), and
the owner reviewed, decided and approved every finding before any change was
merged. See [Limitations](#7-limitations).

---

## 2. Scope and threat model

**System.** One FastAPI process (single uvicorn worker) serving the API, a
WebSocket event stream and the built Angular SPA from the same origin, behind
Render's proxy. Optional PostgreSQL through `DATABASE_URL`; in-memory without
it. External services: AbuseIPDB, ipinfo, Groq (only when their keys are
set and demo mode allows them).

**Demo mode.** On unless `DEMO_MODE` is exactly `false` after trimming and
lower-casing (`backend/store.py`, "Fail closed"). In demo mode a middleware in
`backend/main.py` refuses every request other than `GET`, `HEAD` and
`OPTIONS` with `403 {"detail": "Read-only demo"}`, except `POST /auth/login`
and `POST /auth/logout`. "Read-only" in this report means exactly that: login
and logout are the only writes the demo accepts.

**Production state, checked 2026-11-28.**
- `GET https://signalforge-api-ah1q.onrender.com/api/config` (an
  unauthenticated, read-only request with `curl`) returned `200` with
  `{"demo_mode":true}`, plus the API security headers (`default-src 'none'`
  CSP, `no-store`, HSTS, `nosniff`, `X-Frame-Options: DENY`).
- Owner-reported: `DEMO_MODE` is not set in the Render environment, so the
  default (on) applies, and the live site shows the demo banner.

**Data.** In demo mode the stream, stats, alerts and listed incidents use a
built-in pool of 36 simulated addresses, 12 from each IPv4 documentation
range (RFC 5737: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), with ASNs
from the documentation range AS64496-64511 (RFC 5398) and the organisation
"Simulated network" (`backend/simulated_pool.py`). The IP lookup routes
accept only pool addresses (`store.validate_lookup_ip`); any other address
gets `404` before AbuseIPDB, ipinfo or Groq is called.

**Assets.**
- Session cookies and WebSocket tickets.
- The owner's paid or quota-limited API keys (Groq, ipinfo, AbuseIPDB).
- Availability of the single demo instance.
- Third parties: real hosts must not be shown as attack sources.

**Attackers considered.**
- An anonymous visitor on the internet.
- A signed-in visitor using the public demo accounts (their passwords are
  published, so this is effectively anyone).
- A signed-in user of a deployment with `DEMO_MODE=false` (for
  authorisation findings that do not apply to the public demo).

**Out of scope.** Render's and Cloudflare's own infrastructure, raw TCP
floods below the WebSocket layer, and the owner's developer machine.

---

## 3. Method

- Reviews of the code and of each diff, asking how an attacker could abuse
  each change and what stops them. The owner carried them out with AI
  assistance (Claude Code), and reviewed, decided and approved every finding
  before any change was merged. Earlier reviews numbered their findings L1 to
  L9; those IDs are kept below where they exist.
- Attack-style regression tests: `backend/tests/test_security.py` covers
  token confusion, JWT attacks (`alg: none`, forged signatures, tampered
  claims), a route-auth check that finds every route from the OpenAPI schema,
  SSRF and demo mode. RBAC cases live in `testing/permission-matrix.json` and
  run against both the real API and the frontend's mirror of the rules.
- Mutation checks: new security tests were run against the previous code
  and recorded as failing there (for example "30 of the 49 backend tests
  fail" for the simulated-IP change). The counts are in each DECISIONS entry.
- Measurements, both local (uvicorn, sockets, memory) and on Render. The
  Render measurements are the owner's notes in `docs/DECISIONS.md`; they were
  not re-run for this report.
- CI gates on every pull request: backend lint and tests, frontend lint, unit
  tests and build, end-to-end tests in three viewport projects, lock
  reproducibility, and dependency audits.

---

## 4. Findings

Severity is a judgment for this deployment (a public demo with simulated
data), with the reason in one sentence. "Fixed in" names the pull request or
commit. "Verified by" names tests at `33127fc`.

| ID | Area | Severity (reason) | What was wrong | Fix | Fixed in | Verified by |
|---|---|---|---|---|---|---|
| D1 | Demo data | **Medium.** Real third-party hosts were shown as the source of attacks they never made, and any visitor could spend the owner's API quotas on any address. | The demo streamed real addresses (the AbuseIPDB blacklist or a bundled Censys scanner sample) beside generated attacks, and accepted lookups of any public address. | Demo mode uses only the simulated pool; lookups outside it get `404` before any outbound call; stored incidents with other source IPs are hidden, not deleted. | #68 (`f5f41cb`) | `test_demo_simulated_ips.py` (startup with every outbound call recorded; 404 on 4 outside addresses on each of 6 lookup routes), `e2e/simulated-ips.e2e.ts` |
| W1 | WebSocket | **Low.** The ticket lives 5 minutes and the logs are readable only by the owner and the host, but it was a session credential written to logs. | The ticket was in the query string, so uvicorn and proxy access logs recorded it on every connect (CWE-598, the owner's classification). | The ticket is sent as the first message; a `?ticket=` in the URL is ignored; nothing in that path is logged. | #36 (`74dd49a`) | `test_ws_first_message.py`, `e2e/ws-ticket.e2e.ts` |
| W2 | WebSocket | **Low.** Only simulated read-only events leaked, and only to a holder of a once-valid session. | An open stream kept receiving events after logout, user deletion, role change or password reset. | Session checks at the handshake, before every message and every 2 s while idle; close code 4001. | `83ac9f2`, `d83dec1` | `test_ws_revocation.py` |
| W3 | WebSocket | **Low.** Same data as W2; it needed a session that had once been valid. | A stream outlived its 8-hour session. | The ticket carries the session expiry (`sexp`); the stream closes with 4001 when it passes; a ticket without a usable expiry is refused. | #37 (`b999697`) | `test_ws_session_expiry.py`, `e2e/ws-session-expiry.e2e.ts` |
| W4 | WebSocket | **Medium.** One client could make the single instance stop answering `/health` (measured locally), and the server buffered a 15 MiB frame before any check. | No connection cap, unauthenticated sockets held for up to 5 s each, uvicorn's default 16 MiB message size, and a stream that read nothing from the client. | At most 20 sockets per client IP and 500 in total (429 before the upgrade); `--ws-max-size 8192` (1009); the first message is capped at 4096 characters (4001), with a 5 s timeout (4408); any client frame after `ready` closes with 1008. | #41 (`a41082f`, `f3fc80f`) | `test_ws_limits.py`, `test_ws_max_size_uvicorn.py` (real uvicorn), `threats.service.close-codes.spec.ts` |
| P1 | Proxy chain, rate-limit keys | **Medium.** Per-IP limits, including the per-IP login limit, could be bypassed by forging `X-Forwarded-For`; the per-account login lockout still held. | One `TRUSTED_PROXY_HOPS=3` for both paths. Measured on Render (owner's notes): HTTP requests carry 2 `X-Forwarded-For` entries and WebSocket upgrades 1, so a forged entry became the key on HTTP, and honest users shared one bucket. | Separate `TRUSTED_PROXY_HOPS_HTTP` (Render: 2) and `TRUSTED_PROXY_HOPS_WS` (Render: 1); startup refuses the old variable. | #43 (`f402c79`) | `test_proxy_hops.py` (every row of the measured table) |
| P2 | Proxy chain, rate-limit keys | **Medium.** Same impact as P1, through the fallback path. | On a chain shorter than `hops` the key fell back to the socket address, but Render's uvicorn trusted every peer and replaced that address with the leftmost, client-chosen entry. Measured on Render (owner's notes): a forged entry appeared as the client in the access log. | A short chain returns the fixed key `xff-short-chain` (fails closed, one warning per process with counts only); uvicorn runs with `--no-proxy-headers`; `redirect_slashes=False`, so the app never builds an `http://` redirect. | #46 (`d93b490`) | `test_client_ip_fail_closed.py`, `test_proxy_headers_uvicorn.py` (real uvicorn with `FORWARDED_ALLOW_IPS='*'`), `test_slash_redirects.py` |
| S1 | Python supply chain | **Low.** It was hygiene, not an exploited issue, but each Render build could install untested versions. | Open version ranges (uvicorn unpinned) and no hashes. | pip-tools locks with every transitive package pinned and hashed; `--require-hashes` in CI, the e2e venv and `build.sh`; uvicorn 0.54.0, the version the proxy and message-size flags were measured against. The first `pip-audit` run found PYSEC-2026-4320 in certifi, so certifi was raised (floor `2026.10.19`). | #48 (`b489797`) | CI `python-lock` (recompile on Linux must match byte for byte), `pip-audit` |
| S2 | npm supply chain | **Low.** The critical and high advisories were in build tooling or in code paths the app does not use. | `npm audit --omit=dev` reported two `@angular/router` advisories (high) and three `dompurify` advisories (low); the full tree had two critical (`piscina` via `@angular/build`). | Updated in range (framework 21.2.26, CLI and build 21.2.31, `dompurify` 3.5.0), `npm audit fix` without `--force`, and a CI `npm-audit` job. | #49 (`6a5a796`) | CI `npm-audit` |
| S3 | CI supply chain | **Low.** Exploiting it needs control of an upstream action repository. | Actions referenced by movable tags. | Every `uses:` names a full commit SHA with the tag as a comment; Dependabot moves both. | #50 (`5c2a958`) | `.github/workflows/ci.yml` |
| L1 | Headers | **Low.** SPA pages under `/docs*` lost their CSP in production; no injection point was known. | Any path starting with `/docs` or `/redoc` skipped the CSP, even with the API docs off. | Only the exact paths `/docs`, `/docs/oauth2-redirect` and `/redoc` skip it, and only while `ENABLE_API_DOCS=true`. | #59 (`b355232`) | `test_docs_csp.py` |
| L2 | CORS | **Low.** Production is same-origin, but credentials were allowed for an origin whose site no longer existed. | Every method and header allowed; a hard-coded origin for a deleted static site. | Origins only from `CORS_ORIGINS` (exact origins; none when unset); a wildcard, path, trailing slash or uppercase stops startup; methods `GET`, `POST`, `PATCH`, `DELETE`; header `Content-Type` only. | #59 | `test_cors.py` |
| L4 | Availability | **Low.** It was triggered only by an admin or manager action, and paused the server for about 0.25 s each time. | bcrypt (12 rounds) ran on the event loop during user creation and admin password resets, pausing every request and stream. | `run_in_threadpool` for every hash and verify, with a re-check after the await (409 if the user changed meanwhile). | #59; `04d8237` (#37) | `test_create_user_threadpool.py`, `test_admin_reset_threadpool.py` |
| L6 | Secrets in transit | **Low.** The token reached only ipinfo's URL and local error messages. | The ipinfo token was a query parameter, so it could end up in request lines and httpx error text. | `Authorization: Bearer` header; a failed lookup logs the exception type and status only. | #59 | `test_ipinfo_token.py` |
| L9 | Error output | **Low.** It appeared only in startup logs, which only the owner can read. | A failed migration printed Alembic's full traceback, which can hold SQL and connection details. | One line: the last error line, URL credentials masked, at most 300 characters. Startup still stops. | #59 | `test_migration_output.py` |
| L7 | Rate limits | **Low.** Unlimited in-memory reads behind a login on a single instance. | Several GET routes had no limit. | `READ_LIMIT` 120/minute and `DB_READ_LIMIT` 60/minute per client IP and route; `/health` and the SPA stay unlimited for uptime checks and link crawlers. | #60 (`0a226c9`) | `test_read_limits.py` |
| L8 | Cost and quotas | **Medium.** The demo accounts are public, so anyone could spend the owner's Groq, ipinfo and AbuseIPDB quotas. | No per-user quotas on routes that call paid or quota-limited services; Groq client defaults (60 s timeout, 2 retries); no `Retry-After`. | Quotas keyed by a SHA-256 of user and client IP together (AI summary 5/minute and 50/day, plus a 500/day global cap; geolocation and AbuseIPDB 20/minute and 300/day), counted only when the service is really called; Groq `timeout=10.0, max_retries=0`; `Retry-After` on every rate-limit 429, which the frontend honours. | #60 | `test_external_quotas.py`, `test_groq_timeout.py`, `test_retry_after.py`, `threats.service.retry-after.spec.ts` |
| L3 | Authorisation | **Low.** It was not exploitable on the public demo, where hunt writes are refused; it mattered only with `DEMO_MODE=false`. | Any signed-in user could delete anyone's saved hunts, and one user could fill the global cap of 100. | `created_by` from the session; delete only by the creator or the admin (a hunt with no owner: admin only); 404 for unknown ids; caps of 20 per user and 100 in total; `READ_LIMIT` on the list. | #61 (`ec84e5a`) | `test_hunt_ownership.py`, `testing/permission-matrix.json` (9 delete-hunt rows), `threat-hunting.component.owner.spec.ts` |
| E1 | Export | **Low.** A formula needs a crafted incident title (from a rule name in a non-demo deployment), and the analyst has to open the CSV in a spreadsheet. | CSV cells were quoted but not neutralised, and spreadsheets run a quoted `=...` cell (CWE-1236). | A cell starting with `=`, `+`, `-`, `@`, tab or carriage return gets a leading apostrophe, then the usual quoting. JSON is built with `JSON.stringify` from typed items; Markdown escapes `\` first, then `|`, backtick, `[`, `]` and `<`, and turns line breaks into spaces. No defanging. | #64 (`5bbac39`) | `export.utils.spec.ts` (34), `export-menu.formats.spec.ts`, `threat-table.export.spec.ts`, `incidents.export.spec.ts` |
| O1 | Public assets | **Low.** It was a privacy issue for third parties in a marketing image, with no system impact. | The link-preview screenshot showed source IP addresses. | The address column is replaced with the text `x.x.x.x` before publishing (masking, not blur, so nothing can be recovered from it). | #47 (`16ab1e1`); retaken in #66 (`558e580`) | Visual check of `frontend/public/og-image.png`; `scripts/check-og-tags.mjs` checks the tags and the image size |

L5 (the session cookie's `Secure` flag) was reviewed and found correct, so
it has no entry: the cookie is `Secure` unless `ENV` is exactly
`development` (`backend/routers/auth.py`). The L5 ID and its result are
owner-reported; neither appears in `docs/DECISIONS.md` or the git history,
and no test asserts the flag.

Known limits of E1, pinned by unit tests so that changing them is a visible
decision: a leading space before a formula character (` =1+1`), and
full-width look-alikes (for example U+FF1D) are not prefixed. In Markdown,
`*` and `_` can still change emphasis but cannot form a link or HTML. How
Excel, LibreOffice and Google Sheets treat the apostrophe was not tested.

---

## 5. Supply chain and CI

**Python.**
- `backend/requirements.in`, `requirements-dev.in` and `requirements-tools.in`
  are compiled by pip-tools with `--generate-hashes`
  (`backend/.pip-tools.toml`).
- Every install uses `pip install --require-hashes --no-deps`.
- `python-lock` recompiles all three locks on Linux and fails on any
  difference from the committed files.
- `pip-audit` fails the job on any advisory in the runtime lock. The dev and
  tools locks are report-only. pip-audit has no severity filter, so any
  runtime advisory blocks.
- `build.sh` stops on any Python version other than 3.13.

**npm.**
- `npm audit --omit=dev --audit-level=high` fails the `npm-audit` job. The
  full tree is report-only.
- Documented "not affected" decisions (DECISIONS 2026-11-23), updated anyway:
  - `@angular/router` SSR denial of service: the app has no server-side
    rendering.
  - `dompurify`: reachable only through `jspdf`'s `html()`, which the app
    never calls.
- At that time the remaining full-tree findings were moderate and in dev
  tooling pinned by `@angular/cli` 21, which only a major upgrade would fix.

**GitHub Actions and Dependabot.**
- Every action is pinned to a 40-character commit SHA, and the workflow has
  `permissions: contents: read`.
- `.github/dependabot.yml` runs weekly for `github-actions`, `npm` and `pip`,
  each with `cooldown: default-days: 3` (version updates only; security
  updates are not delayed).
- Grouped updates:
  - `angular`, `lint`, `npm-minor-patch`, `pytest`, `pip-minor-patch`,
    `actions`.
  - uvicorn and pip-tools are excluded from the pip group, so each gets its
    own pull request: the start-command flags were measured against uvicorn
    0.54, and pip-tools writes the locks.
  - Angular majors are ignored because they need `ng update` migrations.
- No workflow in the repository merges automatically. Dependabot pull
  requests go through the same required checks as any other.

**Branch protection on `master`.** Read from the GitHub API on 2026-11-28
(`gh api repos/chenleiv/signal-forge/branches/master/protection`, a plain
GET):
- Required status checks: `backend`, `frontend`, `e2e`, `python-lock`, with
  `strict: true` (the branch must be up to date).
- A pull request is required, with 0 required approvals (one developer).
- Force pushes and deletion are disabled.
- `enforce_admins` is disabled, so the repository admin can bypass these
  rules.
- `pip-audit` and `npm-audit` are not required checks (owner's choice). A
  new advisory then shows as a red check without blocking unrelated merges;
  the audits still run on every pull request, on every push to `master` and
  weekly.

---

## 6. Decisions and accepted risks

- **8-hour sessions** for every account, the demo accounts included
  (`backend/routers/auth.py`). Mitigations: logout revokes the session on the
  server, and deleting a user, changing a role or resetting a password
  rotates the user's session key. Owner's rationale (stated 2026-11-28): the
  session length is not security-critical for a demo of simulated data with
  writes refused; it only needs to be long enough that a visitor is not
  logged out in the middle of exploring, and any value from about two hours
  up would serve the same purpose. The same 8 hours also applies with
  `DEMO_MODE=false`, which this rationale does not address.
- **The demo admin password is public** by design (shown on the login page).
  It works only in demo mode, where every write except login and logout is
  refused. The demo accounts are exempt from the per-account lockout, so
  nobody can lock visitors out.
- **FastAPI `max_body_size` and `form_limits` are not configured.**
  `BodySizeLimitMiddleware` already answers 413 over 64 KB for every request,
  chunked bodies included. The app has no form or file parameters and does
  not install `python-multipart`.
- **`constants.GEO_DATA` still lists 12 real addresses**, used only as a
  geolocation fallback outside demo mode. The demo never streams them, and
  lookups of them are refused in demo mode.
- **The Censys sample (`backend/threat_ips_sample.json`) is still in the
  repository** with real scanner addresses. It is no longer loaded at startup
  and cannot be reached in demo mode. Its removal is a recorded follow-up.
- **Free text in stored incidents** (titles, notes) is not scanned for
  addresses. In demo mode an incident is shown only when its source IP is a
  pool address.
- **The AI summary still calls Groq in demo mode** for pool addresses, with
  the quotas above (owner decision). Its context is the simulated events
  only.
- **Rate-limit and WebSocket counters are in memory, per process.** They are
  correct only with a single uvicorn worker (the documented setup) and reset
  on restart.
- **A short `X-Forwarded-For` chain shares one bucket.** This degrades
  instead of locking everyone out.
- **CI traces are public.** On an e2e failure the job uploads Playwright
  traces and screenshots (`retain-on-failure`, kept 7 days), which anyone
  signed in to GitHub can download.
  - The `e2e` job has no `env:` and no `secrets.*`.
  - `frontend/e2e/serve.mjs` uses an e2e-only `JWT_SECRET` and empty API
    keys.
  - `e2e/fixtures.ts` aborts every browser request to other hosts.
  - The rule that the job must stay free of real secrets is recorded in
    DECISIONS (2026-11-25).

---

## 7. Limitations

- No external penetration test, no formal audit, no bug bounty. The findings
  come from the owner's AI-assisted reviews (see [Method](#3-method)).
- No SAST or DAST tool runs in CI (no CodeQL or similar workflow).
- Render measurements (the `X-Forwarded-For` entry counts, the forged entry
  in the access log, the hop values, the per-client login check from two
  networks) are the owner's notes in `docs/DECISIONS.md` and were not re-run
  for this report.
- Not verified: Render's file and memory limits; how spreadsheets handle the
  CSV apostrophe; whether ipinfo accepts the Bearer header for this token on
  Render; whether the production database holds older incidents with real
  addresses (they are hidden either way).
- Raw TCP floods below the WebSocket layer are not handled by the app.
- The CI findings below are process observations, not vulnerabilities.

### CI and process observations

- **Export menu clipping (PR #64).** On a one-row desktop threat table, the
  table container (`overflow: hidden`) cut off the new JSON item and hid the
  Markdown item. Caught by CI; the uploaded trace and screenshot were used to
  diagnose it (owner-confirmed). Locally the live feed filled the table and
  hid the issue. Fixed with a `position: fixed` menu and guarded by
  `e2e/export-menu-clipping.e2e.ts`.
- **Flaky 44px touch-target test (PR #69).** CI measured the console input at
  43.99993896484375px. The input is exactly 44px; the test measured on the
  first frame of a `translateY` slide-up, where float math under a fractional
  transform is one float32 step off. The test now waits for the overlay's own
  animations to finish. The check stays `>= 44` with no tolerance, and no
  style changed (DECISIONS 2026-11-28; the failing frame on the CI runner
  itself was inferred from the same value reproduced locally).

---

## 8. How to verify

From the repository root, with the backend virtual environment active:

```bash
# Backend: lint and the full suite (test_env_example.py runs in CI)
cd backend
ruff check .
python -m pytest -q --ignore=tests/test_env_example.py

# The tests behind the findings above
python -m pytest -q \
  tests/test_demo_simulated_ips.py \
  tests/test_ws_first_message.py tests/test_ws_revocation.py \
  tests/test_ws_session_expiry.py tests/test_ws_limits.py \
  tests/test_ws_max_size_uvicorn.py \
  tests/test_proxy_hops.py tests/test_client_ip_fail_closed.py \
  tests/test_proxy_headers_uvicorn.py tests/test_slash_redirects.py \
  tests/test_docs_csp.py tests/test_cors.py \
  tests/test_create_user_threadpool.py tests/test_admin_reset_threadpool.py \
  tests/test_ipinfo_token.py tests/test_migration_output.py \
  tests/test_health_route.py tests/test_read_limits.py \
  tests/test_external_quotas.py tests/test_groq_timeout.py \
  tests/test_retry_after.py tests/test_hunt_ownership.py \
  tests/test_security.py tests/test_permission_matrix.py

# Dependencies
pip-audit --require-hashes --disable-pip -r requirements.txt

# Frontend: lint, unit tests (export escaping included), build, audit
cd ../frontend
npm run lint
npm test -- --watch=false
npx ng build && node scripts/check-og-tags.mjs && node scripts/check-icons.mjs
npm audit --omit=dev --audit-level=high

# End-to-end (starts its own backend; set BACKEND_PYTHON to the venv python)
npm run e2e
```

Quick checks without running anything:

```bash
# Demo mode fails closed
grep -n "DEMO_MODE =" backend/store.py
# Every action pinned to a commit SHA
grep -n "uses:" .github/workflows/ci.yml
# Cooldown and groups
grep -n "cooldown\|default-days\|exclude-patterns" .github/dependabot.yml
# The live demo reports demo mode (read-only GET)
curl -s https://signalforge-api-ah1q.onrender.com/api/config
```

Design reasons, rejected alternatives and per-change test results are in
[`docs/DECISIONS.md`](DECISIONS.md).
