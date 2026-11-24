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

## 2026-11-24 · GitHub Actions pinned to commit SHAs, Dependabot version updates, Node 26

**Decision.**
- Every `uses:` in `.github/workflows/` names a full 40-character commit SHA
  with the exact tag in a trailing comment, for example
  `actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0`.
  Each SHA was resolved from the tag with the GitHub API
  (`git/matching-refs/tags`, all lightweight tags pointing at commits) and
  checked to be the same commit as the floating major tag (`v4`, `v5`) the
  workflow used before, so behaviour did not change: `checkout` v4.4.0,
  `setup-python` v5.6.0, `setup-node` v4.4.0. Newer majors are left to
  Dependabot. There is no CodeQL or other workflow.
- `.github/dependabot.yml`: weekly version updates, Monday 05:00 UTC (an hour
  before the weekly audit run), for `github-actions` at `/` (limit 5), `npm`
  at `/frontend` (limit 5) and `pip` at `/backend` (limit 3), each with a
  3-day `cooldown` (version updates only; security updates are not delayed).
  Dependabot updates the SHA and the tag comment together.
- Groups. A package goes into the first matching group, so specific groups
  come first:
  - npm `angular`: `@angular/*`, `@angular-eslint/*`, `angular-eslint`,
    `ngx-echarts`, `typescript`. The framework packages pin each other
    exactly; `@angular/build` and `@angular/cli` follow their own patch line
    (21.2.31, framework 21.2.26, see the 2026-11-23 entry); `angular-eslint`
    21.4.0 needs `@angular/cli` below 22; `@angular/build` needs `typescript`
    `>=5.9 <6.0`; `ngx-echarts` majors follow Angular majors. Majors of all
    of these are ignored: an Angular major needs `ng update` and its code
    migrations.
  - npm `lint`: `eslint`, `@eslint/*`, `typescript-eslint`,
    `@typescript-eslint/*` (`typescript-eslint` 8.74.0 needs eslint
    `^8.57 || ^9 || ^10` and typescript `<6.1`).
  - npm `npm-minor-patch`: everything else, minor and patch; majors alone.
  - pip `pytest`: `pytest`, `pytest-asyncio`.
  - pip `pip-minor-patch`: everything else, minor and patch, except
    `uvicorn` (the start command flags were measured against 0.54, so a bump
    needs a re-check) and `pip-tools` (it writes the locks), which always
    get their own pull request.
  - actions `actions`: minor and patch; majors alone.
  - `vitest` and `@vitest/*` must match, but only `vitest` is a direct
    dependency, so no group is needed.
- Node 26 in a root `.node-version`. CI reads it (`node-version-file`),
  replacing a hardcoded 22 in three jobs; the README says 26. Before, CI used
  22, the README said 20.19+, and `build.sh` and Render set nothing (no
  `.node-version`, `.nvmrc` or `engines`), so Render used its own default.
- `ci.yml` concurrency group `ci-<event name>-<ref>`, with
  `cancel-in-progress` only for `pull_request`. There was no group before.
  With the event name in the group, a scheduled or manual run never cancels
  or queues behind a pull request run.

**Reason.** A tag can be moved to other code by whoever controls the action's
repository; a commit SHA cannot. The comment keeps the version readable and
lets Dependabot propose the next one, so pinning does not freeze the actions.
Grouping stops Dependabot from opening a pull request for one package of a
set that must match, which fails `npm ci` with ERESOLVE (as happened by hand
on 2026-11-23).

Dependabot and the hashed pip-compile lock, checked in the dependabot-core
source (`python/lib/dependabot/python/file_updater/pip_compile_file_updater.rb`,
`shared_file_fetcher.rb`, `language_version_manager.rb`, `language.rb`,
`python/helpers/requirements.txt`) on 2026-11-24:
- It runs `pip-compile` with the options read from each lock:
  `--generate-hashes` when the file has `--hash=sha`, `--allow-unsafe`,
  `--strip-extras`, `--no-emit-index-url`, `--output-file`, and merges
  `.pip-tools.toml`. It passes `-P <package>==<version>`, so only that
  package moves. Hashes are regenerated, not dropped; the original header is
  kept.
- It compiles `requirements.in` before `requirements-dev.in` (ordered by the
  `-r` reference), so the dev lock is compiled against the new
  `requirements.txt` that its `-c requirements.txt` reads.
- It reads `.python-version` from `/backend` or, failing that, the repository
  root, and has 3.13.18 preinstalled.
- It runs its own pip-tools, 7.6.1, not the repo's 7.7.0. The 7.7.0 release
  notes list no change to the output format (bug fixes, Python 3.15, pip
  26.2.2 minimum).
- The `python-lock` job recompiles every lock with the repo's pip-tools and
  fails on any difference, and every install uses `--require-hashes`, so a
  wrong lock from Dependabot cannot merge.

**Alternatives rejected.**
- Pinning to tags only: a tag can be repointed.
- SHA without a comment: unreadable, and Dependabot cannot show the version.
- A scheduled workflow that runs `pip-compile --upgrade` and opens a pull
  request: needs a write-scoped token and loses Dependabot's release notes;
  not needed, since Dependabot handles the pip-compile lock.
- One group per ecosystem for everything: a single failing package would
  block every other update.
- Letting Dependabot propose Angular majors: it cannot run the `ng update`
  migrations.
- Node 24: Node 26 is the current LTS and inside Angular 21's engines
  (`^20.19 || ^22.12 || >=24`); lint, unit tests and the build passed on it.
- `cancel-in-progress` for every event: a push to master or the weekly audit
  could be cut off.

**Not verified.** That Render reads the root `.node-version` for this Python
service (check the build log after the deploy); that a real Dependabot pip
pull request passes `python-lock` byte for byte; that Dependabot's npm honours
`packageManager: npm@11.12.1` when it writes the lock; how a group update
behaves when one member has a peer conflict; the GitHub runner on Node 26
(checked locally on 26.0.0 only).

Tests: no test changed. `actionlint` clean on `ci.yml`. Backend: `ruff check
.` clean, 941 passed (`--ignore=tests/test_env_example.py`). Frontend on Node
26.0.0 with the existing `node_modules`: lint clean, 396 unit tests passed,
production build and `check-og-tags.mjs` OK. e2e not run.

Files: `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.node-version`,
`README.md`, `docs/DECISIONS.md`.

## 2026-11-23 · Frontend dependency updates, npm-audit in CI

**Decision.**
- Angular framework packages (`common`, `compiler`, `core`, `forms`,
  `platform-browser`, `router`, `compiler-cli`) 21.2.24 to 21.2.26, the
  newest 21.2.x. `@angular/build` and `@angular/cli` 21.2.24 to 21.2.31:
  Angular publishes the CLI and build tooling on their own patch line, and
  21.2.31 is the first that drops `piscina` 5.2.0 (critical
  GHSA-67c8-pqhq-4rmx, `@angular/build` up to 21.2.28).
- `dompurify` 3.4.16 to 3.5.0 with `npm update`, inside the range `jspdf`
  allows (`^3.3.1`). `jspdf` stays at 4.2.1, the newest 4.x.
- Dev tooling, patch and minor only: `@playwright/test` 1.65.1, `eslint`
  10.15.0, `prettier` 3.10.1, `vitest` 4.1.12, `typescript-eslint` 8.74.0
  (still an exact pin). `d3` and `tslib` are runtime packages with no
  advisory, so they are left for the Dependabot PR.
- The framework group has exact peer pins on each other, and npm refused to
  move it while the 21.2.24 tree was in the lock (ERESOLVE). It was removed
  and added back with `npm uninstall` and `npm install`, so npm wrote the
  lock; it was never edited by hand.
- `npm audit fix` (without `--force`), in its own commit, moved five
  transitive dev packages to patch releases in range, lockfile only:
  `fast-uri` 3.1.9, `glob` 13.0.7, `ip-address` 10.7.6, `undici` 6.29.1
  (under `node-gyp`) and `source-map-js` 1.2.4. Full audit 23 findings
  (21 moderate, 2 high) to 19 (all moderate).
- CI (`.github/workflows/ci.yml`), new `npm-audit` job on the same triggers
  as `pip-audit` (pull request, push to master, weekly Monday 06:00 UTC,
  manual dispatch). `npm audit --omit=dev --audit-level=high` fails the job;
  a full `npm audit` runs in a `continue-on-error` step (reported, never
  failing). npm audit exits non-zero on a registry error too, so the job
  fails closed; rerun it after an outage. Whether it is a required check is
  decided in GitHub, not here.
- Not affected, updated anyway:
  - `@angular/router` GHSA-62vg-58rm-qff7 and GHSA-57xq-rjx2-v5xh (high,
    fixed in 21.2.25): both are denial of service in server-side rendering.
    This app has no SSR: no `@angular/ssr`, no `@angular/platform-server`,
    no `provideServerRendering`; it is served as static files.
  - `dompurify` GHSA-c6gr-qvv4-5v3f, GHSA-cg2g-xh64-v4q7,
    GHSA-mrv2-3pqr-j5jr (low): `dompurify` is an optional dependency of
    `jspdf` and is reachable only through `jspdf`'s `html()`. The app's only
    `jspdf` use (`frontend/src/app/core/utils/export.utils.ts`) calls
    `text`, `rect`, `addPage` and `save`, never `html()`.
- Known report-only findings after the update and `npm audit fix` (19,
  all moderate, dev tooling only; `npm audit --omit=dev` reports 0):
  - `minimatch` GHSA-g3hv-75wg-m249 and `glob` GHSA-3g3m-2fjr-6pw4, through
    `pacote` 21.5.1, which `@angular/cli` 21.2.31 pins. The chain flagged
    with them: `@npmcli/package-json`, `@npmcli/run-script`, `pacote`,
    `cacache`, `make-fetch-happen`, `@sigstore/sign`, `sigstore`,
    `@sigstore/tuf`, `tuf-js`, `@tufjs/models`, `npm-registry-fetch`,
    `ignore-walk`, `npm-packlist`, `@angular/cli`, and `angular-eslint`
    21.4.0 with `@angular-eslint/builder` and `@angular-eslint/schematics`
    (they depend on `@angular/cli`). npm's only fix is `@angular/cli` 22, a
    major bump.
  These run only on a developer machine or in CI (CLI, build, lint, unit
  tests), never in the browser bundle.

**Reason.** Before the update `npm audit --omit=dev` reported the two
`@angular/router` advisories (high) and the three `dompurify` advisories
(low); the full audit reported 41 findings, two critical (`piscina`,
through `@angular/build`). Updating costs one patch bump per package, and
keeps a not-affected call from depending on the app never adding SSR or
`html()`. The audit job mirrors `pip-audit`: the runtime packages gate, the
rest is visible without blocking.

**Alternatives rejected.**
- One 21.2.x version for every `@angular/*` package: the framework stops at
  21.2.26 and the CLI and build packages at 21.2.31; at 21.2.26 the build
  package would keep the critical `piscina` advisory.
- `npm install --force` or `--legacy-peer-deps` to get past ERESOLVE: they
  can write a lock with broken peers.
- Deleting the lock and regenerating it: it would also move `d3`, `tslib`
  and every other package to the newest version in range.
- `npm audit fix --force`: installs `@angular/cli` 22, a major bump.
- Failing CI on the full audit: the remaining findings are in dev tooling
  and have no fix inside Angular 21.

**Not verified.** That GitHub's runner reports the same audit results (the
advisory database changes over time); that the weekly scheduled run of
`npm-audit` starts as expected.

Tests: no test changed. After each commit, from a clean `npm ci`: lint
clean, unit tests 396 passed, production build and `check-og-tags.mjs` OK,
`npm run e2e` phone 43, desktop 32, tablet 37 passed, none failed.

Files: `frontend/package.json`, `frontend/package-lock.json`,
`.github/workflows/ci.yml`, `docs/DECISIONS.md`.

## 2026-11-23 · Hashed Python lock, Python 3.13 guard, pip-audit in CI

**Decision.**
- `backend/requirements.in` and `backend/requirements-dev.in` are the
  sources. `requirements.txt` and `requirements-dev.txt` are generated by
  pip-tools 7.7.0 (`pip-compile`) with every transitive package pinned and
  hashed; options in `backend/.pip-tools.toml` (`generate-hashes`,
  `allow-unsafe`, `strip-extras`, no index URL). The dev source has
  `-c requirements.txt`, so runtime packages have the same version in both
  locks. pip-tools itself is locked in `requirements-tools.txt`.
- First lock = the set the backend suite already ran against locally
  (constrained to that venv's versions, then recompiled without the
  constraint): uvicorn 0.54.0, websockets 17.1, fastapi 0.141.1, starlette
  1.7.0 and the rest unchanged. One exception: pip-audit reported
  PYSEC-2026-4320 for certifi 2026.7.22 (compromised emSign intermediates; the
  backend's httpx calls to AbuseIPDB, ipinfo and Groq trust that bundle), so
  certifi is 2026.11.20 with a floor of 2026.10.19 in `requirements.in`.
- `build.sh` prints `python --version`, stops unless it is 3.13, and runs
  `python -m pip install --require-hashes --no-deps -r requirements.txt`.
  CI and the e2e venv install the same way.
- Render reads the repo's `.python-version`. Its build log says "Using Python
  version 3.13.18 via .python-version", and `PYTHON_VERSION` is not set in
  the Render environment. The lock's binary wheels are per minor version
  (cp313), so it holds for any 3.13.x.
- CI (`.github/workflows/ci.yml`), two new jobs that also run weekly (Monday
  06:00 UTC) and on manual dispatch; `backend`, `frontend` and `e2e` skip the
  scheduled run:
  - `python-lock`: installs `requirements-tools.txt` with hashes, recompiles
    the three locks on Linux and fails on any `git diff`.
  - `pip-audit`: `pip-audit --require-hashes --disable-pip` on
    `requirements.txt` fails the job on any advisory; the dev and pip-tools
    locks run in `continue-on-error` steps (reported, never failing).
    pip-audit exits 1 both on an advisory and on an error (network), so the
    job fails closed; rerun it after an outage.
  - Whether these jobs are required checks is decided in GitHub, not here.

**Reason.** `requirements.txt` had open ranges (`uvicorn[standard]` with no
version), so each Render build could install different versions from the ones
tested; the uvicorn flags in the start command were measured against 0.54
(entry below). Hashes also stop a changed or substituted file on the index.
The lock is generated on macOS and Render builds on Linux: the locks have no
environment markers, and pip-compile records the hashes of every published
file of each version, so one lock fits both; `python-lock` proves it on every
change. The version guard turns a Python change on Render into a clear build
failure instead of a missing-wheel or hash error.

pip-audit has no severity filter (most PyPI advisories carry no score), so
"fail only on high or critical" cannot be applied to Python. Any advisory in
the runtime lock fails; an accepted one would be skipped with
`--ignore-vuln ID` and recorded here.

**Alternatives rejected.**
- `uv pip compile --universal`: resolves for all platforms, but adds a tool,
  and Dependabot may not recognize its output as a pip-compile lock.
- Poetry, PDM, Pipenv: their locks need the tool on Render.
- `pip lock` (pylock.toml): experimental, and pip cannot install from it.
- `pip freeze` of the local venv as the lock: it held packages no requirement
  asks for (anthropic, cryptography, httpx2 and others) and no hashes.
- `--only-binary :all:` in `build.sh`: not checked that every package has a
  cp313 manylinux wheel.
- Running the audits only on a schedule: a new dependency with an advisory
  would merge unnoticed until the next run.

**Not verified.** That the Linux recompile in CI matches byte for byte (the
`python-lock` job is the check; verified only on macOS); the first Render
build with `--require-hashes`.

Tests: no test changed. Backend suite from a fresh venv installed from
`requirements-dev.txt` with `--require-hashes`, Python 3.13.15 on macOS: 941
passed (`--ignore=tests/test_env_example.py`), `ruff check .` clean,
`pip-audit` clean on all three locks. `npm run e2e` with `BACKEND_PYTHON`
pointing at that venv: phone 43, desktop 32, tablet 37 passed, none failed
(skips are the usual per-project ones).

Files: `backend/requirements.in`, `backend/requirements.txt`,
`backend/requirements-dev.in`, `backend/requirements-dev.txt`,
`backend/requirements-tools.in`, `backend/requirements-tools.txt`,
`backend/.pip-tools.toml`, `build.sh`, `.github/workflows/ci.yml`,
`README.md`.

## 2026-11-23 · Static link-preview tags (Open Graph, Twitter) in index.html

**Decision.**
- `frontend/src/index.html` carries static `description`, `og:*` and
  `twitter:*` meta tags. `og:url` is `https://signalforge-api-ah1q.onrender.com/`
  and `og:image` is the absolute URL of `/og-image.png` on the same host.
- The image lives in `frontend/public/og-image.png`, so Angular copies it to
  the build root and `build.sh` copies it to `backend/static/`. The source IP
  addresses in the screenshot are covered. `og:image:width` and
  `og:image:height` are the file's real size (2590x1442).
- `frontend/scripts/check-og-tags.mjs` fails when a tag is missing or empty,
  when the image URL is not the expected absolute https URL, or when the image
  is missing, not a PNG, over 5 MB or a different size from the tags. It runs
  after `ng build` in CI and in `build.sh`, so a deploy without the tags stops.
- The SPA catch-all in `backend/main.py` answers HEAD as well as GET, and is
  kept out of the OpenAPI schema (`include_in_schema=False`).
- `backend/tests/test_og_preview.py`: with a build in `backend/static`, `/`
  has the tags, `HEAD /` is 200, `/og-image.png` is `image/png` with the usual
  security headers, and 60 fetches of each from one address are not limited.
  It skips without a build, like the built-index checks.
- Copy says what the code does: all events are simulated and no real network
  is monitored; source IP addresses come from the AbuseIPDB blacklist when
  that feed is available (otherwise a cached list, or in demo mode the bundled
  Censys sample in `backend/threat_ips_sample.json`); public read-only demo
  accounts, no sign-up.

**Reason.** LinkedIn reported "We couldn't load a preview for this link".
Link-preview crawlers do not run JavaScript, and the built `index.html` had
only a title. Checked locally before the change: `GET /og-image.png` returned
the SPA HTML with status 200 (the catch-all serves `index.html` for any
missing file), and `HEAD /` returned 405 because the catch-all was GET only.
The security headers (CSP, nosniff, X-Frame-Options, COOP, HSTS) only govern
what a browser does with a page, so they do not stop a crawler reading the
HTML, and nosniff is satisfied once the image is served as `image/png`. The
per-IP rate limits apply only to decorated routes; the catch-all has none and
the limiter has no default limits. Adding HEAD to the catch-all gave a
duplicate OpenAPI operation id; the route is not an API route, so it is
hidden from the schema rather than renamed.

**Alternatives rejected.**
- Server-side rendering or prerendering: a larger change for a few static
  tags that are the same on every route.
- Setting the tags at runtime with Angular's `Meta` service: crawlers never
  see them.
- Tags in `redirect-site/index.html`: that site is being deleted, and the
  URL shared on LinkedIn is the API service.
- Serving the image from a separate host: it would need its own deploy and
  checks; the API service already serves static files.

**Known issue.** The live demo UI itself shows real third-party IP addresses
(from AbuseIPDB, or the Censys sample) next to randomly generated attacks,
scores and regions. No code change for now.

**Not verified.** Whether LinkedIn's crawler sends HEAD; that `DEMO_MODE` is
on in Render (the copy says "read-only"); how long LinkedIn keeps a cached
failed preview. The `/health` route still gives a duplicate operation id
warning in the tests; it predates this change and was left alone.

---

## 2026-11-23 · Fail closed on a short X-Forwarded-For chain; run uvicorn without proxy headers

**Decision.**
- `client_ip()` (`backend/rate_limit.py`): when `hops` is above 0 and
  `X-Forwarded-For` has fewer entries than `hops`, it returns the fixed key
  `xff-short-chain` instead of the socket address. Every such request shares
  one bucket. One warning per process names the variable and the two counts,
  never an address or a header value. With `hops` 0 the socket address is
  still used.
- The Render start command (API service), `build.sh` and
  `frontend/e2e/serve.mjs` pass `--no-proxy-headers`:
  `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --ws-max-size 8192 --no-proxy-headers`
- `FastAPI(..., redirect_slashes=False)` in `backend/main.py`.

**Reason.** Measured on Render: a request with a forged
`X-Forwarded-For: 203.0.113.9` showed `203.0.113.9:0` as the client in
uvicorn's access log. So Render's uvicorn trusts every peer
(`FORWARDED_ALLOW_IPS='*'`), uvicorn replaces `scope["client"]` with the
leftmost, client-chosen entry, and Render appends its own entries to a forged
header instead of replacing it. The socket address was therefore not a safe
fallback: on a short chain, a client chose its own key.

From the uvicorn 0.54 source (`middleware/proxy_headers.py`, `config.py`):
`--no-proxy-headers` only skips `ProxyHeadersMiddleware`, which changes
exactly `scope["client"]` (from `X-Forwarded-For`; with `*` the leftmost
entry, port 0 for a bare IP) and `scope["scheme"]` (from `X-Forwarded-Proto`).
Nothing else in the app depends on them: `is_https()` falls back to the last
`X-Forwarded-Proto` value, so HSTS stays; the cookie `Secure` flag comes from
`ENV`; CORS reads the `Origin` header; the WebSocket handler only uses
`client_ip()`.

The one exception was FastAPI's trailing-slash redirect. Checked locally
with a real uvicorn and an app routed like `main.py` without
`backend/static`: with the flag, `GET /api/stats/` redirected to
`http://signalforge-api-ah1q.onrender.com/api/stats`, without it to
`https://`. So slash redirects are switched off. The frontend never calls an
API path ending in a slash, and no e2e test, README example or script does.
With `backend/static` present the SPA catch-all answers such GET paths
anyway, so no redirect happens there. Verified on Render: the API service
has `backend/static` (`GET /login` on it returns the SPA HTML), and it
redirects HTTP to HTTPS (`http://signalforge-api-ah1q.onrender.com/health`
returns 301 to https). Slash redirects stay off so the app never builds an
`http://` URL itself.

Effect: the access log shows Render's proxy instead of a client address,
forged or real.

**Deploy order.**
1. Merge and deploy the code. Check: login works, the LIVE chip goes live,
   and the API service logs have no `xff-short-chain` warning (one would mean
   the hop values no longer match the chain). Forged addresses still appear
   in the access log until step 2.
2. Set the start command above on the API service and redeploy. Check:
   `curl -H "X-Forwarded-For: 203.0.113.9" https://signalforge-api-ah1q.onrender.com/health`,
   and the access log line no longer shows `203.0.113.9`;
   `curl -sI https://signalforge-api-ah1q.onrender.com/health` still has
   `Strict-Transport-Security`; login and the LIVE chip work. The static site
   (`signal-forge-tane`) never reaches uvicorn and cannot be used for this
   check.

Rollback: step 2, remove the flag from the start command and redeploy;
step 1, revert the merge or roll back the deploy on Render.

**Alternatives rejected.**
- Keep the socket fallback: client-chosen under `FORWARDED_ALLOW_IPS='*'`.
- Narrow `FORWARDED_ALLOW_IPS` to Render's proxy addresses: no stable
  published range is known (not verified).
- Refuse the request (429) on a short chain: locks everyone out if the
  chain changes; one shared bucket degrades instead.
- Keep slash redirects with the flag: they would point at `http://`.
- A startup warning when `hops` is 0 on a real host: the app cannot tell
  whether a proxy is in front; with the flag, 0 is coarse but not spoofable.

**Known gap (closed 2026-11-23).** `uvicorn` was not pinned
(`backend/requirements.txt`), so Render could run another version than the one
tested. Now pinned to 0.54.0 with hashes, the version measured here: see "Hashed
Python lock, Python 3.13 guard, pip-audit in CI" above.

Tests: new `backend/tests/test_client_ip_fail_closed.py` (fixed key on both
paths, peer ignored, hops 0 unchanged, one warning, no address in it), new
`backend/tests/test_proxy_headers_uvicorn.py` (real uvicorn with
`FORWARDED_ALLOW_IPS='*'`, with and without the flag: client, scheme, access
log, no slash redirect, where the default redirect would point; app in
`backend/tests/_scope_echo_app.py`), new `backend/tests/test_slash_redirects.py`
(real app). Changed with approval: two cases in `test_rate_limit.py` and three
rows in `test_proxy_hops.py` that expected the socket address on a short
chain.

Files: `backend/rate_limit.py`, `backend/main.py`, `build.sh`,
`frontend/e2e/serve.mjs`, `backend/.env.example` (comments), `README.md`,
tests above.

## 2026-11-22 · Separate proxy hop counts for HTTP and WebSocket

**Decision.** `TRUSTED_PROXY_HOPS` is replaced by `TRUSTED_PROXY_HOPS_HTTP`
and `TRUSTED_PROXY_HOPS_WS` (`backend/rate_limit.py`). `client_ip()` picks the
WebSocket value when `request.scope["type"] == "websocket"`, else the HTTP
value, and returns `entries[-hops]` or the socket address. Both default to 1.
The server refuses to start while the old `TRUSTED_PROXY_HOPS` is set to a
non-empty value; the message names the two new variables.

**Reason.** Measured on Render with the count diagnostic (entry below): HTTP
requests carry 2 `X-Forwarded-For` entries, WebSocket upgrades 1, and Render
had `TRUSTED_PROXY_HOPS=3`. Honest header `[C, P]` for HTTP, `[C]` for
WebSocket; a client that sends its own header adds X on the left:

| Request | Entries | Hops | Key | Client chooses it? |
|---|---|---|---|---|
| HTTP honest | 2 | 3 | socket peer, shared by all | no |
| HTTP honest | 2 | 2 | C | no |
| HTTP honest | 2 | 1 | P, shared by everyone behind it | no |
| WS honest | 1 | 3 or 2 | socket peer, shared by all | no |
| WS honest | 1 | 1 | C | no |
| HTTP forged | 3 | 3 | X | **yes** |
| HTTP forged | 3 | 2 | C | no |
| HTTP forged | 3 | 1 | P | no |
| WS forged | 2 | 2 | X | **yes** |
| WS forged | 2 | 1 | C | no |

So no single value fits both: 2 makes the WebSocket key spoofable and puts
every honest WebSocket user in one bucket; 1 is safe on both paths but keys
HTTP on P. With 3 (the value on Render), honest users of both kinds shared one
bucket and forged HTTP requests chose their own key.

The old name is refused rather than used as a fallback: Render held 3, which
a fallback would have silently applied to both paths.

**Deploy order.**
1. In Render, set `TRUSTED_PROXY_HOPS_HTTP=1` and `TRUSTED_PROXY_HOPS_WS=1`
   and delete `TRUSTED_PROXY_HOPS`, before merging (old code then also uses
   1, which is safe).
2. Merge and deploy.
3. Run the hash diagnostic (entry below, now removed). Only if the HTTP
   `entries[-2]` and the WebSocket `entries[-1]` of one browser match, raise
   `TRUSTED_PROXY_HOPS_HTTP` to 2. `TRUSTED_PROXY_HOPS_WS` stays 1.

**Alternatives rejected.**
- One value for both: wrong on one path whatever the value (table above).
- Keeping `TRUSTED_PROXY_HOPS` as a fallback: silently keeps an unsafe value.
- Ignoring the old name with a warning: safe, but leaves a variable that looks
  like it still does something.
- `uvicorn --forwarded-allow-ips='*'`: takes the leftmost, client-chosen entry.

**Result on Render** (measured with the hash diagnostic, which was then
removed):
- HTTP requests carry 2 `X-Forwarded-For` entries, WebSocket upgrades 1.
- In one process, the same browser gave the same hash for the HTTP
  `entries[-2]` and the WebSocket `entries[-1]`; the HTTP `entries[-1]` hash
  was different.
- From a phone on a cellular network the WebSocket hash changed, so the
  WebSocket entry is the client address, not a shared proxy hop.
- Render now has `TRUSTED_PROXY_HOPS_HTTP=2` and `TRUSTED_PROXY_HOPS_WS=1`.
- Functional check passed: after 6 failed logins from the phone on cellular,
  the phone was blocked, and a login from a desktop on Wi-Fi still worked, so
  the login rate limit is per client address.

**Observation (resolved 2026-11-23).** The peer address hash (`peer_hash`)
was equal to the `pick_hash` in every line. Explained by a later measurement:
Render's uvicorn trusts every peer and puts the leftmost entry into the
client address. For an honest `[C, P]` request that entry is C, the same
address as the pick. The pick from the header was correct, so the result
above stands; the socket fallback was not. Fixed in the entry above (fixed
key on a short chain, `--no-proxy-headers`).

**How to re-measure** (after a Render proxy change or a move to another
host):
1. On a temporary branch, restore the diagnostic from git history. It was last
   present in `eede244` (merge of PR #43):
   `backend/forwarded_diag.py`, `backend/tests/test_forwarded_diag.py` and the
   import and `app.add_middleware(ForwardedHashDiagnostic)` lines in
   `backend/main.py`.
2. Deploy it, set `DIAG_FORWARDED_COUNT=true` and restart.
3. Open the app in one browser and log in, then again from a second network
   (a phone on cellular). Read the `[diag] forwarded-hash` lines and compare
   hashes within one process only (the salt is random per process).
4. Set the hop values from the result, delete `DIAG_FORWARDED_COUNT`, record
   the result here and remove the diagnostic again.

Tests: new `backend/tests/test_proxy_hops.py` (every row above, split values,
each value isolated to its path, env parsing, defaults, the old name refused);
`test_rate_limit.py`, `test_ws_limits.py` and `test_env_example.py` moved to
the new names. `test_env_example.py` skips `TRUSTED_PROXY_HOPS` (named in
`LEGACY_VARS`): it is read only to refuse startup and is not in
`backend/.env.example`, since a copied example with a value would refuse to
start.

Files: `backend/rate_limit.py`, `backend/main.py`, `README.md`, tests above.

## 2026-11-22 · Temporary X-Forwarded-For hash diagnostic (removed)

**Removed** after the Render check: `backend/forwarded_diag.py`, its lines in
`backend/main.py`, `backend/tests/test_forwarded_diag.py` and the README
step are gone, and `DIAG_FORWARDED_COUNT` no longer does anything. The result
and the re-measure procedure are in the entry above. Kept as history.

**Decision.** Replaces the count diagnostic (entry below), same switch
(`DIAG_FORWARDED_COUNT=true`, exact value, any case, read once at startup),
same paths, at most 5 lines per kind and 10 per process. A line is logged
only for a new combination of values, so one page load does not use up the
cap:

```
[diag] forwarded-hash kind=http entries=2 pick=-2 pick_hash=3fa91c last_hash=a07e44 peer_hash=7d02be hops=1 line=1/10
[diag] forwarded-hash kind=ws entries=1 pick=-1 pick_hash=3fa91c peer_hash=7d02be hops=1 line=2/10
```

Each hash is the first 6 hex characters of HMAC-SHA256 with a random 16-byte
salt per process, never logged. HTTP lines hash `entries[-2]`,
`entries[-1]` and the TCP peer; WebSocket lines hash `entries[-1]` and the
peer. No address, header value, salt, cookie or ticket is logged.

**Reason.** The counts show how many entries each path has, not which one
is the client. Equal `pick_hash` values for HTTP and WebSocket in one browser
show that HTTP `entries[-2]` is the same address as WebSocket `entries[-1]`,
which `TRUSTED_PROXY_HOPS_HTTP=2` relies on. `last_hash` equal to the
WebSocket `pick_hash` would show that the WebSocket entry is a shared proxy
hop instead.

**Alternatives rejected.**
- Logging the addresses: personal data, and not needed for a comparison.
- An unsalted or fixed-salt hash: IPv4 is small enough to reverse by hashing
  every address.
- Longer hashes: 6 characters are enough to compare a handful of addresses.

Result on Render: recorded in the entry above.

Tests: `backend/tests/test_forwarded_diag.py` replaced (off unless "true",
exact line format, HTTP and WebSocket picks of one address match, no address,
peer, salt, cookie, ticket or bearer value in any record, repeated values
logged once, other paths ignored, 10-line cap shared across stacks).

Files: `backend/forwarded_diag.py`, `backend/main.py`, `README.md`.

## 2026-11-19 · Temporary X-Forwarded-For count diagnostic (superseded, removed)

**Removed**: replaced by the hash diagnostic (entry above), which was itself
removed after the Render check. Kept as history.

**Decision.** An ASGI middleware, outermost in `main.py`, off unless
`DIAG_FORWARDED_COUNT=true` (exact value, any case; read once at startup).
When on, it logs one line for each of the first 5 API requests (`/api/`,
`/auth/`) and the first 5 WebSocket upgrades to `/ws/threats`, at most 10
lines per process:

```
[diag] forwarded-count kind=ws xff=present entries=1 trusted_proxy_hops=1 line=6/10
```

Only the kind, whether `X-Forwarded-For` is present, the number of
non-empty comma-separated entries over all header lines (counted like
`rate_limit.client_ip`) and `TRUSTED_PROXY_HOPS`. The line is built from fixed
words and integers only: never an address, a header value, a ticket, a cookie
or any other header.

**Reason.** The WebSocket per-IP cap (entry below) is per user only if Render
adds `X-Forwarded-For` to WebSocket upgrade requests and `TRUSTED_PROXY_HOPS`
matches. The README step asked for a temporary count log, but no mechanism
existed, so checking meant a code change and a deploy each time.

**Alternatives rejected.**
- Counting `/health`: Render's health checker may call it without the proxy,
  so it could log "absent" while user traffic has the header.
- Logging the path or the remote address: not needed for the count, and an
  address is personal data.
- A permanent debug endpoint: anyone could call it; a log line on a flag is
  removed by deleting one variable.

Expected on Render with one proxy: `xff=present entries=1
trusted_proxy_hops=1` for both kinds. `entries` larger than
`trusted_proxy_hops` only when the client sent its own header. `xff=absent`
for `kind=ws` while `kind=http` is present: the per-IP WebSocket cap counts
all users as one client.

Result on Render: `kind=http entries=2`, `kind=ws entries=1`,
`trusted_proxy_hops=3`. Led to the split hop counts and was replaced by the
hash diagnostic (entries above, 2026-11-22).

Tests: new `backend/tests/test_forwarded_diag.py` (off by default and for any
value but "true", exact line content, no address, cookie, ticket or bearer
value in any record, other paths ignored, 10-line cap shared across stacks).

Files: `backend/forwarded_diag.py` (new), `backend/main.py`, `README.md`.

## 2026-11-19 · WebSocket connection caps, message size limit, one-way stream

**Decision.**
- `threats_ws` counts open sockets, unauthenticated and streaming alike,
  from before `accept()` until the handler returns: at most
  `WS_MAX_PER_IP` (20) per client IP and `WS_MAX_TOTAL` (500) in total. Over
  either cap the handshake is refused with HTTP 429 (`send_denial_response`),
  before the upgrade, so a refused socket holds nothing. The browser sees a
  failed connection (1006) and the frontend retries with its doubling backoff,
  which resets only on `ready`, so it never loops.
- The client IP is `rate_limit.client_ip`, the same as the HTTP limits:
  the rightmost `TRUSTED_PROXY_HOPS` entry of `X-Forwarded-For`. **The
  per-IP cap is only per user if Render adds `X-Forwarded-For` to WebSocket
  upgrade requests and `TRUSTED_PROXY_HOPS` is right.** Too high: a
  client-chosen entry becomes the key and the per-IP cap can be bypassed (the
  total cap still holds). Too low, or no header on the upgrade: every user
  shares the proxy's address, so the per-IP cap acts as a global cap of 20.
  Verify with the README Deployment checklist step (count the
  `X-Forwarded-For` entries, never the IPs, on one HTTP request and one
  WebSocket upgrade). Not yet verified on Render.
- Each incoming message is limited to 8 KiB by uvicorn:
  `--ws-max-size 8192` in the start command (Render setting, `build.sh`
  comment, `e2e/serve.mjs`). A larger one closes with 1009. The limit applies
  to the decompressed size, so permessage-deflate stays on. The app keeps its
  own 4096-character check on the ticket message (4001).
- After `ready` a reader task waits on `ws.receive()` beside the event queue:
  any text or binary frame closes the stream with 1008 (`WS_POLICY_VIOLATION`).
  The browser never sends one. Reading also stops uvicorn from pausing the
  socket, so keepalive pongs are seen.
- Unchanged: `WS_AUTH_TIMEOUT_SECONDS` stays 5 s, close codes 4001 and 4408,
  the 60/minute ticket limit, the frontend.

**Reason.** Measured locally (uvicorn 0.54.0, websockets 17.1, macOS, server
file limit set to 1024, RSS sampled every 50 ms, so peaks are lower bounds),
before the change:
- 1,100 unauthenticated sockets from one client: 1,012 accepted, the rest
  refused, `/health` failed while they were held, and recovered when they
  were closed with 4408 after 5 s. Repeatable every 5 s.
- First frame: a 15 MiB frame was buffered whole before the 4096-character
  check (RSS +31 MB, kept). 20 sockets × 15 MiB deflate-compressed frames,
  about 15 KiB each on the wire: peak +112 MB.
- After `ready`: uvicorn pauses reading after one message the app does not
  take, so a socket holds one message, and its keepalive then fails (1011,
  about 40 s). 5 sockets × 15 MiB compressed frames held +166 MB for 40 s.
- With `--ws-max-size 8192`: 1009 at once, peak +1 MB for the same floods.

**Alternatives rejected.**
- `--limit-concurrency`: counts WebSocket connections too, so a socket flood
  would turn every HTTP request into a 503.
- A shorter auth timeout: with the caps, one IP holds at most 20 slots however
  long each lasts; an attacker reconnects, while slow mobile networks would
  get 4408.
- Accepting and then closing with 1013 over a cap: costs an upgrade and a
  keepalive for a socket that is refused anyway.
- A separate cap for unauthenticated sockets: owner decision, not added.
- Turning off permessage-deflate: the size limit already bounds inflation, and
  compression saves bandwidth on the event stream.

Limits: counts are per process (single worker, as the rate limits). A flood
of raw TCP connections below the WebSocket layer is not stopped by the app.
Render's file limit and memory are not known.

Tests: new `backend/tests/test_ws_limits.py` (caps, spoofed
`X-Forwarded-For`, slot release on every exit path, 1008 for text and binary
frames; 6 tests fail against the previous `main.py`, checked with a stash),
`backend/tests/test_ws_max_size_uvicorn.py` (a real uvicorn with the flag:
1009 for large and compressed frames; it does not depend on `main.py`, and
its two limit tests fail when the flag is removed), and the frontend guard
`threats.service.close-codes.spec.ts` (1006, 1009 and 1008 back off without
signing out; the frontend did not change). No existing test changed.

Files: `backend/main.py` (`threats_ws`, `_serve_stream`),
`backend/rate_limit.py` (`client_ip` type hint), `frontend/e2e/serve.mjs`,
`build.sh` (comment), `README.md`.

## 2026-11-18 · Incidents toast is a polite live region

**Decision.** The incidents toast sits inside a `.toast-region` wrapper with
`role="status"`, `aria-live="polite"` and `aria-atomic="true"`. The wrapper is
always in the DOM; the `.toast` element is added inside it while a message
shows. This covers every toast on the page: failed status, assignee and task
updates, and "Case ... already exists — opened existing". The look is
unchanged: the wrapper has no styles and no position, so `.toast` keeps its
absolute position against the same ancestor.

**Reason.** The toast was a plain `div`, so screen readers did not announce
it. A live region added to the DOM together with its text is announced
unreliably; one that exists first and then changes is announced.

**Alternatives rejected.**
- `role="status"` on the `.toast` element itself: it is created with its text
  inside `@if`, the unreliable case above.
- `role="alert"` (assertive): it interrupts the user, and the "already exists"
  message is information, not an error. The failure messages are not urgent
  either: the value on screen is already back to the stored one.

Limits: the same message shown again while it is still on screen changes no
text, so it is not announced again.

Tests: new `incidents.toast-a11y.spec.ts`. Existing unit and e2e tests select
`.toast` by class and read its text, so they did not change.

Files: `incidents.html`.

## 2026-11-18 · Console: `clear` is not a server command

**Decision.** `POST /api/command` no longer accepts `clear`: it is removed from
`ALLOWED_COMMANDS` and its branch (which answered `__clear__`) is gone, so the
server answers it like any unknown command. The `help` text still lists
`clear`, because the console (`command-console.ts`) clears its own screen on
`clear` and never sends it. `ThreatStoreService.executeCommand` is unchanged:
it sends every other console command.

**Reason.** No client read `__clear__`, so the branch was dead code that
widened the command allowlist for nothing.

**Alternatives rejected.** Removing `clear` from the help text too: the
console still handles it, and users read the list from `help`.

Tests: new `backend/tests/test_console_commands.py`; its `clear` cases fail
against the previous `ip.py`.

Files: `backend/routers/ip.py`.

## 2026-11-18 · Incident detail: a failed task update rolls back that task only

**Decision.** `toggleTask` keeps its optimistic update. On a server error it
logs `[IncidentDetail] task update failed`, shows the same toast as a failed
status or assignee change (the server's `detail` when it is text, otherwise
"Please try again"), and puts back only the task that was toggled, on the
current set. The message is built by one helper, `failureMessage`, shared with
`patchAndEmit`.

**Reason.** The task PATCH had no error handler: on a 403 or 500 the checkbox
stayed in its new state with no message, so the analyst saw a task as done
that the server never stored.

**Alternatives rejected.**
- Restoring the whole set saved before the request: a second toggle made while
  the first request was in flight would be undone too.
- Waiting for the server before showing the change: slower for every click to
  handle a rare failure.

Tests: new `incidents.task-failure.spec.ts` (3 of its 4 tests fail with the
rollback removed, checked by hand) and `e2e/incident-task-failure.e2e.ts`.

Files: `incident-detail.component.ts`.

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
(Note, 2026-11-19: closed by "WebSocket connection caps, message size limit,
one-way stream" above. Correction to the security review that reopened this
gap: it assumed uvicorn buffers up to `ws_max_queue` (32) messages of 16 MiB
per socket. uvicorn 0.54 with `ws="auto"` uses its sans-I/O WebSocket
implementation, which never reads `ws_max_queue`: it pauses reading after
each message until the app takes it, so a socket held one message, and its
keepalive then closed it after about 40 s. The real costs were the 16 MiB
first frame read before the 4096-character check and the missing connection
cap.)

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
