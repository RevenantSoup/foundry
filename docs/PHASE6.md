# Phase 6 stabilization report

## Scope and status

Starting checkout: clean `main`, `45f7bea743b4a7cf863843bf7968b9e38d6404b4`;
`git fetch origin main` confirmed the same remote head. No CLI algorithms, QA rules,
licences, pricing model, persistence architecture or payment authorization rules
were changed. No production writes, accounts, credentials, provider settings or
manual deployment were used.

The three reported code defects are repaired. Overall product acceptance remains
**PARTIAL**: there is no deployed worker; hosted authenticated workflows could not
be tested without an authorized session; and the supported synthetic offline
pipeline is deliberately not eligible for sale. Separate payment fixtures prove
payment processing, not resale rights or a sale of the offline dataset.

## Fixes and root causes

| Issue | Root cause / change | Evidence |
| --- | --- | --- |
| Sequential references disappear | `addFiles` replaced state. It now appends in order, validates image MIME/10 MB, deduplicates name/size/type/lastModified, caps six without removing valid selections, supports drop/remove/replace, resets inputs, revokes removed URLs and explains exactly-six gating. | `uploader.spec.ts`: actual browser controls, payload bytes/names, URL lifecycle and 375/768/1280 widths. |
| Login stays “Signing in…” | Cookie-setting fetch was followed by competing soft navigation/refresh while root client auth state could remain anonymous; no bounded request/finally cleanup. A fresh document navigation carries the cookie and discards stale anonymous state; safe same-origin return paths default to dashboard. Authenticated login visits redirect server-side. | `stability.spec.ts` plus actual login in the real CLI workflow: invalid credentials, network failure/retry, destination, refresh/session and logout/protection. |
| Workspace spinner never ends | No fetch timeout, overlapping interval polling, and pages rendered Loading whenever data was absent even when an error existed. Reads now have a 10-second client/8-second workspace backend deadline, serial polling after success, terminal error/Retry, abort cleanup and retained data on refresh failure. Long jobs retain separate budgets. | Failure/timeout/malformed/empty/background tests; `unavailable.spec.ts` uses a genuinely missing Python executable. |
| Catalog archive falsely appears empty | Admin archive ignored its state-fetch error and treated absent data as an empty package list. It now distinguishes loading, unavailable+Retry and a genuinely empty archive. | Actual missing-runtime browser assertion failed before the fix and passed after it. |
| Missing bridge misclassified as user error | Spawn failures were generic errors: catalog400/filter error, detail404 and executable errors leaked. Typed sanitized infrastructure errors now yield503 while true missing resources/invalid queries keep their statuses. | Actual missing-interpreter API/browser profile; live before/after audit. |
| Malformed download should not require worker | Reject syntactically invalid/oversized tokens with403 before contacting the backend; actual HMAC/paid-order/expiry checks remain on the worker. | Missing-interpreter profile plus local/remote paid and expired-download tests. |
| Anonymous buyer API returns503 | SQLite bridge started before checking absence of a key. Missing/oversized keys now return the existing401 contract before backend access; valid-key hashing/revocation/rate limiting stays in SQLite. | Missing-interpreter profile, existing401/403/429 marketplace/payment tests. |
| Logout/checkout can remain pending | Raw unbounded requests and unhandled logout failure. Reused bounded JSON helper; logout errors remain visible and don't claim success; checkout retains Stripe-host-only redirect validation and idempotency key. | Auth/payment regressions; source review. |
| Duplicate `next` can crash login | Next represents repeated query keys as arrays. `safeReturn` now accepts unknown input and validates the type before path checks. | Auth unsafe/duplicate-return browser regression. |
| Repeated payment fixtures sometimes fail before tests | Random synthetic pHashes could collide with prior test rows. The test-only generator now selects hashes separated by >10 before passing them through unchanged `Database.insert`; production dedupe is untouched. | Repeated actual fixture/payment setup against the existing test root. |
| Occupied reference controls cramped on mobile | Six columns left too little room for remove/replace. Mobile uses three columns; modified controls have visible focus. | Uploader viewport assertions and local mobile suite. |
| Catalog says checkout is unavailable | Phase3-era wording remained after test Checkout was implemented. Copy now explicitly says Stripe test mode / no real money. | Local catalog/payment tests; deployed catalog check when available. |

## Pages and flow coverage

| Surface | Local verification | Live verification |
| --- | --- | --- |
| Login, logout, session, protected navigation | Actual browser auth, invalid/network retries, refresh, redirects, unsafe return paths | Anonymous login/redirects only; no authorized production session supplied |
| Dashboard, analytics, batches | Real SQLite data; mocked empty/background failure; actual absent-runtime failure and Retry | Protected: redirects to login |
| New Dataset / five stages | Real CLI plan, harvest, filter, QA and package; six unique reference byte streams | Protected; no safe authorized production planning possible |
| Batch detail / QA | Manifest filtering, rights always visible, 200 per-image controls, fail/recover gate and reload persistence | Protected; no accessible real batch |
| Catalog / detail / pricing | Real test registry discovery, filters, sorting, attribution, price save, missing-runtime states | Public filter/navigation/error behavior; no accessible dataset or price/listing action |
| Checkout / webhook / order / downloads | Mock only at Stripe SDK transport; actual signed webhook, SQLite pending→paid, duplicate single grant and byte-verified artifact; denied/expired cases | Safe success/cancel shells; no real purchase or webhook delivered by Stripe |
| Health / SEO / missing routes | Existing HTTP/browser coverage plus genuine runtime-unavailable503 | Health503 truthfully reports db:error; robots/sitemap200; public unknown dataset obscured by missing backend |
| Responsive layout / console | Existing mobile flow plus uploader375/768/1280; runtime page-error collection | 33 page checks at375/768/1280, navigation/filter interactions, console/network checks |

Full per-page observations, screenshots, exact hosting sources/cost assumptions and
owner steps are in [PHASE6_LIVE_AUDIT.md](PHASE6_LIVE_AUDIT.md). Actual batch IDs,
commands, artifact paths/hashes and persisted-stage evidence are in
[PHASE6_PIPELINE.md](PHASE6_PIPELINE.md).

## Infrastructure and incomplete acceptance

No existing persistent free worker was verified. Vercel/GitHub alone do not provide
the current always-available Docker/SQLite/files worker. No temporary serverless
SQLite, Actions artifact-as-database or session-workspace hosting shortcut was
implemented. Render Free lacks durable storage and sufficient starting RAM; OCI
A1 free allowances require an owner account/capacity and unverified ARM image
compatibility. These are researched possibilities, not deployed solutions.

The supported future owner setup is one persistent Docker host (Python3.11,
FFmpeg, CPU inference, detached long jobs, writable SQLite and dataset files,
outbound network, durable backups and inbound HTTPS), initially >=4 GB RAM and
>=20 GB free disk plus dataset/model capacity. A verified Linode4GB base quote is
US$24/month, excluding extras and regional differences; see the sourced audit.
An existing suitable owner machine could avoid an incremental host fee, but none
was supplied or verified.

Owner actions later: make the host available, deploy
`docker-compose.worker.yml`, persist `/data`, configure HTTPS and independent
worker/download secrets, then set the web project's `FOUNDRY_WORKER_URL` and
`FOUNDRY_WORKER_API_KEY`. Existing dashboard credentials/session secret are still
required. Live harvesting needs its existing provider keys/model files. Test
Checkout needs the existing Stripe test keys, webhook secret and return URLs on
the worker, plus the public webhook forwarding path. This phase requested none of
those credentials and changed no settings. Follow [DEPLOYMENT.md](DEPLOYMENT.md).

After worker setup the hosted dashboard, CLI jobs, QA, registry, files, buyer API,
schedules and configured test payments can use the same tested bridge. A genuinely
rights-cleared non-synthetic dataset is additionally needed for same-dataset sales
acceptance. Offline fixture success is not live harvesting/model-quality evidence.
No real hosted4242 purchase, live external harvest or full authenticated hosted
pipeline is claimed. No paid service or account was created.

## Verification and publication

Exact final commands/results, publication SHA and deployment observations are
recorded in the delivery response and CI run. Local logs and credential-free
artifact evidence are retained under ignored `work/phase6-*`; generated data,
private environment files, dependencies, screenshots and signed tokens are not
committed. The existing 200-review/0.90 gate, dedupe, quota exit2, hashed buyer keys,
webhook verification, token expiry and synthetic resale prohibition remain intact.


### Executed commands (before commit)

All final outcomes below have **0 failures and exit code0**. Browser transport is
regular Playwright/Chromium; Browser plugin was unavailable. Local Python is
3.12.14; the existing CI explicitly repeats tests on Python3.11.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | 82 passed |
| `.venv/bin/python -m pytest web/tests -q` | 8 passed; root collection covers only `tests/` |
| `npm --prefix web run lint` | Passed; no rule suppressed |
| `npm --prefix web run build` | Production compilation, TypeScript and static generation passed |
| `PLAYWRIGHT_BROWSERS_PATH=/tmp/phase6-browsers npm --prefix web run test:e2e` | 17 passed, including actual CLI workflow |
| `PLAYWRIGHT_BROWSERS_PATH=/tmp/phase6-browsers npm --prefix web run test:e2e -- stability.spec.ts uploader.spec.ts` | 8 passed |
| `PLAYWRIGHT_BROWSERS_PATH=/tmp/phase6-browsers npm --prefix web run test:e2e -- stability.spec.ts -g 'authenticated login visits'` | 1 passed, including repeated query parameters |
| `PLAYWRIGHT_BROWSERS_PATH=/tmp/phase6-browsers npm --prefix web run test:e2e -- --config playwright.unavailable.config.ts` | 1 passed, actual missing runtime and malformed-link403 |
| `PLAYWRIGHT_BROWSERS_PATH=/tmp/phase6-browsers npm --prefix web run test:e2e -- --config playwright.payments.config.ts` | 4 passed; 1 remote-only case intentionally skipped |
| `PLAYWRIGHT_BROWSERS_PATH=/tmp/phase6-browsers FOUNDRY_TEST_REMOTE=1 npm --prefix web run test:e2e -- --config playwright.payments.config.ts` | 7 passed, full remote CLI and payment/fault profiles |
| `PLAYWRIGHT_BROWSERS_PATH=/tmp/phase6-browsers FOUNDRY_TEST_REMOTE=1 npm --prefix web run test:e2e -- --config playwright.payments.config.ts payments.spec.ts` | 5 passed, repeated after ZIP-byte and token checks |
| `PLAYWRIGHT_BROWSERS_PATH=/tmp/phase6-browsers npm --prefix web run test:e2e -- marketplace.spec.ts` | 2 passed after the archive error/empty fix |
| `git diff --check` | Passed |

Earlier test-harness failures were corrected rather than hidden: ambiguous Next
route-announcer alert selectors, a redirect-navigation test race, incorrect
lowercase expectation for stored USD currency, and random test pHash collision.
No failing test was excluded. Existing browser tests remain in the base profile;
the unavailable profile is separately selected because it deliberately runs with
no interpreter. CI invokes it explicitly.

Standalone local Docker build and `scripts/smoke-test.sh`: **NOT RUN in Phase6**;
no container definition changed. The existing CI still executes its container
builds and complete smoke test after the push; its actual outcome is reported
separately. Real Stripe-hosted4242 purchase: **NOT RUN**, no test-account
credentials supplied. Production authenticated/data workflow: **BLOCKED** as
listed above. No manual Vercel deployment was run.

### Changed files

```text
.github/workflows/ci.yml
docs/DEPLOYMENT.md
docs/PHASE6.md
docs/PHASE6_LIVE_AUDIT.md
docs/PHASE6_PIPELINE.md
web/app/api/[...path]/route.ts
web/app/api/datasets/[id]/route.ts
web/app/api/datasets/route.ts
web/app/api/v1/[...path]/route.ts
web/app/api/v1/downloads/route.ts
web/app/globals.css
web/app/login/page.tsx
web/components/batches.tsx
web/components/catalog.tsx
web/components/checkout.tsx
web/components/common.tsx
web/components/dataset-detail.tsx
web/components/login.tsx
web/components/overview.tsx
web/components/qa-review.tsx
web/components/shell.tsx
web/components/usage.tsx
web/components/wizard.tsx
web/e2e/payments.spec.ts
web/e2e/setup-marketplace.py
web/e2e/stability.spec.ts
web/e2e/unavailable.spec.ts
web/e2e/uploader.spec.ts
web/e2e/workflow.spec.ts
web/lib/auth.ts
web/lib/client.ts
web/lib/payments.ts
web/lib/return-path.ts
web/lib/server.ts
web/lib/worker.ts
web/playwright.config.ts
web/playwright.unavailable.config.ts
```
