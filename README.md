# Foundry

Python 3.11+ CLI for a single image attribute query, six reference images,
licensed source discovery, a cheap-to-expensive cascade, manual QA, and
versioned image datasets. SQLite stores state; files live under data/raw/<id>.
No UI, authentication, training, TikTok, or Instagram integration.

## Install

System prerequisite: ffmpeg and ffprobe on PATH (needed for live video).
Run from this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
foundry --help
```

Dependencies include sentence-transformers, whose CLIP weights download on
first **live** filter. Offline commands never import it or download a model.
For a lightweight offline-only environment, install core dependencies explicitly:

```bash
pip install requests Pillow imagehash numpy ffmpeg-python click pytest
pip install -e . --no-deps
```

## Offline walkthrough

Provide exactly six readable image files in ./refs. You can create demonstration
references without downloading anything:

```bash
python - <<'PY'
from pathlib import Path
from PIL import Image
Path("refs").mkdir(exist_ok=True)
for i in range(6):
    Image.new("RGB", (128, 128), (i*40, 80, 120)).save(f"refs/{i}.png")
PY
foundry plan --prompt "people in safety glasses" --refs ./refs
```

The plan command prints a batch_id and creates one JSON file under data/plans.
Copy that ID into BATCH:

```bash
BATCH=<printed-batch-id>
foundry harvest --batch "$BATCH"
foundry filter --batch "$BATCH"
foundry qa --batch "$BATCH"
```

Default target is 200; harvest requests 400 records per source. Offline media
are deterministic synthetic patterns, clearly attributed as fixtures. They are
**not** retrieved photographs, actual matching scenes, or evidence of model quality.
Offline scores and verifier verdicts are deterministic fakes. Reference images
are validated but do not affect fake scores. CLIP uses them in live mode.

QA prints a contact-sheet path and writes 200 individual center crops, a labeled
10×20 PNG sheet, and verdicts.csv. Fill every verdict with accept or reject, leaving
IDs unchanged, then submit:

```bash
foundry qa --batch "$BATCH" --verdicts "data/qa/$BATCH/verdicts.csv"
foundry package --batch "$BATCH"
```

QA requires exactly 200 distinct accepted images. Below 0.90 precision it prints
every failing ID and exits 1; packaging also rechecks the review. Missing or
incomplete reviews block packaging. Reviews are bound to SHA-256 snapshots of the sampled image bytes. Changed or
missing reviewed files block packaging and require a new batch.
QA samples the exact highest scoring target
images eligible for the package; every sample must be reviewed.

For a completely automatic **synthetic pipeline demonstration only**:

```bash
foundry qa --batch "$BATCH" --stub-verdicts accept
foundry package --batch "$BATCH"
```

This option explicitly writes fake review verdicts, warns that they are synthetic,
and refuses live or mixed-source batches. It is not an assessment of precision.
Use --stub-verdicts reject to demonstrate the failure gate.

Each package lives at data/packages/<batch>-<content-version>/ and includes
manifest.csv, dataset.json, and images/<id>. The manifest has all specified Row
columns populated. For still images, frame_ts_ms is 0; unsampled QA verdicts are
not_sampled. Rows are deterministically split 90% train / 10% validation.
Provenance hashes bind image bytes to record metadata. Identical reruns reuse the
same version; earlier packages are never overwritten.

## Commands and configuration

Global --root defaults to data; put it **before** the command:

```bash
foundry --root ./another-dataset plan --prompt "people in safety glasses" --refs ./refs --target 300 --threshold 0.28
foundry --root ./another-dataset harvest --batch <id> --limit 600
foundry --root ./another-dataset filter --batch <id>
foundry --root ./another-dataset qa --batch <id>
foundry --root ./another-dataset package --batch <id>
```

- plan: writes search_terms, hashtags, negative_terms, checklist, threshold,
  absolute reference paths, target, mode, and batch_id. Planner is a stub even
  in live mode. Minimum target 200 supports the mandatory QA sample.
- harvest: searches both adapters, downloads/decodes images, computes pHash,
  validates licence/attribution and inserts global URL state. A failed source
  is reported while the other continues; both failed sources exit 1. Individual
  fetch failures and duplicate drops are logged in SQLite drops.
- filter: embeds every harvested image before retrieval, computes cosine scores,
  performs global cosine deduplication, selects at most 3×target above threshold,
  and calls the verifier only on that shortlist. Non-shortlisted rows receive
  explicit status strings. Embeddings are in embeddings.npy with the matching
  embeddings.ids.json index; SQLite retains vectors for interrupted-run recovery.
- qa: persists a deterministic 200-image sample and reads complete verdict CSVs.
- package: refuses missing rights or unapproved QA, then atomically writes a
  versioned package with manifest and copied image bytes.

Rerun commands with the same batch ID to resume. Seen URLs and pHashes are global
across batches. pHash Hamming distance <=10 or cosine >0.95 causes a duplicate drop.
Dropped URLs remain globally seen. A new plan intentionally creates a new batch;
to retry failed sources use the original batch. Do not change a batch's plan or
embedding backend after filtering. Backend/model identity is stored globally;
use a separate --root for synthetic and CLIP datasets. Legacy embeddings without
an identity are refused rather than compared in an unknown vector space.
Keep reference files available until filtering.
SQLite is the authoritative plan/state; plan JSON is the reviewable artifact.

## Live integrations

```bash
export YOUTUBE_API_KEY=...
export OPENAI_API_KEY=...
foundry plan --prompt "people in safety glasses" --refs ./refs --live
foundry harvest --batch <id> --video-dir ./licensed-videos
foundry filter --batch <id> --verifier openai
foundry qa --batch <id>
foundry qa --batch <id> --verdicts data/qa/<id>/verdicts.csv
foundry package --batch <id>
```

Openverse accepts only CC0 / CC-BY / CC-BY-SA; original author attribution is
required and the chosen licence string is preserved through export.
YouTube rows use exactly platform_public_as_is. This string records platform
provenance, and does not itself grant a reuse licence.

YouTube's Data API supplies metadata, not downloadable videos. Supply media
you are authorized to use as ./licensed-videos/<video-id>.mp4. Missing local
videos are skipped. ffmpeg selects scene changes >0.3, trims the first/last two
seconds, retains actual timestamps and caps extraction at 40 frames per video.
A source can legitimately yield too few images; QA then refuses until 200
accepted images are available. Use additional source material rather than
repeating samples.

Every live search.list page is charged 100 units before the request. UTC
per-source counters persist in SQLite. The YouTube daily budget is 10000 units;
exhaustion exits 2 immediately, including when another source succeeded.
Failed HTTP requests remain charged. Keep all consumers of the same API
project on this database for counters to represent the shared budget.

OpenAI verification uses a small vision model through the Verifier interface.
--verifier stub is available for explicit testing, and always returns accept.
Live CLIP/Openverse/YouTube/OpenAI calls require network access and are not part
of the offline test suite. Network timeouts are bounded; errors preserve DB
progress so the same batch can be retried.

## Development

```bash
pytest -q
python -m foundry.cli --help
```

Tests cover rights rejection, pHash re-encoding, cross-batch dedupe/drop logs,
cosine dedupe, quota transactions and CLI exit 2, trimmed scene extraction capped at 40 frames, normalized
embeddings, shortlist-only verification, resumability, QA boundaries, incomplete
reviews, manifest completeness, versioning, source isolation and all CLI helps.

## Frontend

Foundry also includes a local web workspace in **web/**, built with Next.js App
Router, TypeScript, Tailwind CSS, shadcn/ui (Base UI), Recharts, and Lucide.
The Python CLI and its existing commands remain unchanged.

### Install and run

Requires Node.js 20.9+ (Node 22 or 24 recommended), Python 3.11+, and the Python
dependencies installed above. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
cd web
npm install
npm run dev
```

Open **http://localhost:3000**. The server can also be reached on the development
environment's forwarded port. Phase 4 adds a single-admin login for owner workflows; the marketplace remains
public and checkout supports configured Stripe test mode. See Local admin setup below.

For a production build on the same machine with the Python environment available:

```bash
cd web
npm run build
npm start
```

If the workspace is empty, create a clearly labeled synthetic demonstration batch:

```bash
cd web
npm run seed
```

The seed command generates six references, then runs the real CLI's offline plan,
harvest, filter, QA and package commands. It explicitly uses synthetic QA verdicts;
its results are fixtures, not evidence of model performance or sellable datasets.
The seed is idempotent: repeated calls reuse the same two labeled datasets. Each
keeps the required 200-image QA sample; the production quality gate is unchanged.
Empty workspaces also render normally without seeding.

### Configuration

Copy **web/.env.example** to **web/.env.local** if you need overrides; restart the
dev server after changes. Never commit .env.local or API keys.

| Variable | Default / purpose |
| --- | --- |
| FOUNDRY_ROOT | Absolute dataset directory, default repository **data/**. A repository-root path is also accepted and resolves to its data/ subdirectory. |
| FOUNDRY_PYTHON | Absolute Python executable; defaults to repository **.venv/bin/python**, otherwise **python3** on PATH. This interpreter must have the CLI dependencies. |
| FOUNDRY_VIDEO_DIR | Optional absolute directory of authorized **<video-id>.mp4** files for live YouTube extraction. |
| YOUTUBE_API_KEY | Live YouTube Data API access only. |
| OPENAI_API_KEY | Live image verification only. |

Keys remain on the server. The New Dataset wizard defaults to offline synthetic
mode; explicitly enable **Use live sources and models** for real integrations.
Live filtering uses CLIP plus OpenAI verification. Keep offline and live batches
in separate FOUNDRY_ROOT directories because embedding spaces cannot be mixed.
The live adapters have the same source availability and licensing constraints
documented in the CLI section above.

### Pages

- **Overview /**: live batch/row totals, average recorded QA precision, yield
  funnel, recent batches, source and licence mix, YouTube daily quota, and the
  local embedding index size. Quotas use the CLI's UTC daily counters.
- **New dataset /new**: a five-step workflow. Upload exactly six reference images
  (up to 10 MB each), generate the persisted plan, run harvest and filter, review
  the 200 sampled images, then package and download. Job output and exit codes
  appear in the UI, including partial source failures and quota exhaustion.
  Use **Resume wizard** on a batch to continue after a reload.
- **Batches /batches** and **/batches/[id]**: searchable batches, persisted plan
  JSON, stage counts, drop reasons, and an explorer for harvested manifest rows.
  Search, source/licence/verdict filters, column sorting, and pagination are
  supported. Licence and attribution columns are pinned rather than hidden.
- **QA /batches/[id]/qa**: contact sheet plus all 200 crops, individual
  accept/reject controls, running precision and remaining reviews. Drafts persist
  in the current browser. **Submit 200 verdicts** writes a CSV and executes the
  real CLI quality gate. Below 90%, the job reports exit 1 and failing IDs;
  packaging remains blocked. Reviewed bytes are hash-bound by the CLI.
- **Dataset catalog /datasets**: packaged datasets with row counts, train/
  validation counts, full provenance hash, licences, all attribution records, and
  manifest/image ZIP downloads. Rights-cleared, non-synthetic Creative Commons
  packages support persisted draft USD prices. Synthetic packages and packages
  containing **platform_public_as_is** stay in a separate private archive with
  pricing disabled. That platform label is not permission to resell.
  CC-BY credit/change notices and CC-BY-SA ShareAlike requirements are visible.
  Prices are editable listing drafts. Rights-cleared packages appear in the public
  marketplace; configured checkout uses Stripe test mode only. Legal clearance is
  still the operator's responsibility.
- **Analytics /analytics**: yield and precision across batches, CLIP score
  distribution, source/licence mix, and quota usage over time. Synthetic batches
  are included and clearly identified elsewhere in the workspace.

### How the bridge works

Next.js Node-runtime routes under **web/app/api/** spawn **web/bridge.py** using
the configured Python interpreter. The bridge reads source rows through read-only SQLite connections, reads package
manifests and QA artifacts, and invokes
**python -m foundry.cli --root <FOUNDRY_ROOT>** for every pipeline mutation.
There is no parallel mock backend and no rewrite of the CLI.

- POST **/api/plan** validates multipart uploads and invokes **foundry plan**.
- POST **/api/batches/[id]/actions** accepts harvest, filter, qa, review, or
  package and starts a background worker. Review writes all 200 verdicts to CSV
  before invoking **foundry qa --verdicts**.
- GET **/api/jobs/[id]** returns durable status, output, and the actual exit code.
  Refreshing the page reconnects to the active job. A per-root file lock prevents
  simultaneous pipeline mutations; conflicts are explicit retryable failures.
- GET **/api/state** and **/api/batches/[id]** read real dataset state. Browser
  polling supplies current counts without fabricated progress percentages.
- GET **/api/asset** streams validated contact sheets, crops, manifests and ZIPs.
  ZIPs contain the immutable package images, manifest, and dataset metadata.
- POST **/api/price** stores validated draft prices for eligible packages.

Bridge jobs, uploaded references, review CSVs, and download caches live under
**data/web/** and are ignored by Git. Phase 3 prices, usage, schedules and API-key
hashes live in SQLite. Uploaded files are named by index,
and batch/package identifiers are validated before filesystem access.
Cross-origin mutation requests are refused. Jobs run on the local server, so this
bridge requires a persistent Node/Python host; it is not a static export or a
serverless deployment.

### Frontend verification

```bash
# From repository root
pytest -q                         # original 25 CLI tests
pytest web/tests -q               # bridge unit tests
cd web
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The Playwright suite starts **npm run dev** on port 3100 with an isolated ignored
dataset root at **work/web-test-data**. It drives the full wizard, reviews every
sample through the UI, deliberately fails QA at 179/200, checks server-side
packaging refusal, corrects the verdicts, packages 200 rows, and verifies downloads,
manifest filtering, catalog, analytics, navigation and mobile overflow. API tests
also cover malformed uploads, path traversal, and cross-origin writes.

## Phase 3 — Live marketplace + buyer API

Phase 3 extends the existing CLI and web routes. It adds live-provider resilience,
a SQLite dataset registry with pricing and manifest fingerprints, combined
marketplace discovery, dataset detail pages, read-only buyer keys, and cron
schedules. It adds no payment processing, dashboard authentication, queue service,
new source, training, or deployment system.

### Live requests, metadata and usage

- Openverse uses its real paginated API and admits only CC0 / CC-BY / CC-BY-SA.
  Missing licence/creator results are rejected and logged in drops. Accepted
  rows additionally retain creator, title, original image URL, source-page URL
  and licence URL in **image_metadata**.
- YouTube uses the existing **quota** table, keyed by source and UTC day.
  Every search.list attempt, including each retry, is charged **100** before
  the request. The ceiling stays **10,000/day**. A local cap or provider
  403 quotaExceeded/dailyLimitExceeded raises exit **2**, showing local units
  used, remaining units, and the next UTC-midnight reset. Provider exhaustion is
  recorded in quota_blocks until that reset; it is not silently truncated.
- Openverse/YouTube/OpenAI retry HTTP 429, 5xx and transient network failures
  at most **three times after the initial request**, with 1/2/4-second exponential
  backoff and bounded request timeouts. Other HTTP errors fail immediately.
  Provider error messages omit request URLs/credentials. Exhausted live download
  or source-search failures preserve other saved rows, then fail the batch with
  exit 1 so the same batch ID can resume.
- The OpenAI verifier still sees only the top **3 × target** shortlist. HTTP and
  invalid-verdict failures never become accept. Request latency, errors/retries,
  and returned token counts are recorded. Billed USD cost is not returned by the
  API, so it remains unknown rather than being invented.
- **usage_log** records provider/day/batch events, status, retries, latency,
  optional tokens/cost, and buyer usage. It never stores API keys. **/api/usage**
  and the existing Overview/Analytics pages show daily totals and an explicit
  warning at **80% YouTube usage** or provider quota exhaustion.

Environment configuration remains in **web/.env.local** / process environment:

| Variable | Purpose |
| --- | --- |
| OPENVERSE_API_KEY | Optional Openverse OAuth bearer access token; public API access is attempted when unset. Never forwarded to third-party image hosts. |
| YOUTUBE_API_KEY | Live YouTube Data API key. |
| OPENAI_API_KEY | Live verifier API key. |
| FOUNDRY_ROOT | Web dataset directory (or repository root); use the matching CLI --root path. |
| FOUNDRY_PYTHON | Python interpreter with the installed CLI dependencies. |
| FOUNDRY_VIDEO_DIR | Authorized local YouTube video files for the web bridge. Scheduled specs can set video_dir. |

Never commit .env.local, secrets, API keys, or generated data. **web/.env.example**
contains names and comments only. ffmpeg trimming, the 40-frame cap, dedupe rules,
required rights, and the 0.90 QA gate remain unchanged.

### Recurring pipelines

Create a JSON specification, for example **specs/safety.json**:

```json
{
  "prompt": "people in safety glasses",
  "refs": "../refs",
  "target": 200,
  "threshold": 0.28,
  "offline": false,
  "video_dir": "../licensed-videos",
  "verdicts": "../reviews/{batch_id}.csv"
}
```

Exactly six reference images are required. Relative paths resolve from the spec
file's directory. offline defaults to false for schedules; use true only for
explicit synthetic workflow demonstrations. verdicts/video_dir are optional.
The verdict path can contain {batch_id}; it must contain all 200 reviewed IDs,
with accept/reject values, before QA can pass.

```bash
foundry --root ./data schedule add --spec ./specs/safety.json --interval daily --time 10:00
foundry --root ./data schedule list
foundry --root ./data run-scheduled
foundry --root ./data schedule remove <schedule-id>
```

Times are **UTC**. Weekly schedules recur seven days from the first selected UTC
occurrence. **schedules** stores ID, spec path, interval, next/last timestamps,
batch ID, enabled flag, time and status/error; schedule_log records stage output
and lock skips. Disabling preserves history.

run-scheduled reuses the real plan → harvest → filter → qa → package commands.
The batch ID is saved immediately after planning. Failed/quota-limited runs retry
that same batch on the next invocation. A schedule pauses at **awaiting_qa** until
the existing dashboard/CLI records a complete passing review or the configured
verdict CSV is available. It never generates automatic accept verdicts. Repeated
cron calls while waiting for QA do not re-harvest or spend quota. Packaging then
advances next_run_at; the next occurrence creates a new batch. A per-schedule lock
prevents duplicate occurrences, due state is rechecked under that lock, and the
shared web/pipeline.lock prevents simultaneous scheduled/web embedding mutations.

Example crontab (adjust absolute paths and environment):

```cron
*/5 * * * * cd /srv/foundry && /srv/foundry/.venv/bin/foundry --root /srv/foundry/data run-scheduled >> /srv/foundry/data/schedules.log 2>&1
```

Cron must receive the provider secrets through its environment or a protected
launcher. Next.js .env.local is loaded by Next.js, not automatically by cron.
Exit 2 indicates YouTube quota exhaustion; failed schedules otherwise yield exit 1.
An awaiting_qa or skipped schedule is not falsely reported as packaged.

### Discovery, dataset detail and pricing

The existing **/datasets** catalog now submits combined filters to SQLite through
**GET /api/datasets** and retains filters in the URL. Keyword, licence, source,
single attribute/label, inclusive image-count and USD price ranges, free-only,
newest/largest/price sorting, and pagination are supported. Empty states explain
that unsupported rights cannot become listings.

**/datasets/[id]** adds the description/attribute, size/date/count/split, explicit
USD price, licence links and obligations, full creator/source attribution, manifest
SHA-256, and at most 12 explicitly QA-accepted previews. Owner price edits are
stored in SQLite. An unavailable package has a clear reason; it cannot be priced
or returned by the buyer API.

**datasets** stores **price_cents INTEGER NOT NULL DEFAULT 0** and
**currency TEXT NOT NULL DEFAULT 'USD'**. No price is inferred from existing data.
Legacy Phase 2 JSON draft prices are superseded by the SQLite price field;
re-enter an explicit price if needed.

```bash
foundry --root ./data price <dataset-id> --price-cents 4999
foundry --root ./data price <dataset-id> --price-cents 0
```

Zero is displayed as **Free**; 4999 is **$49.99**. Packaging computes and stores
SHA-256 of the exact **manifest.csv** in dataset.json and the SQLite registry,
separately from per-image hashes. Verify it with **sha256sum manifest.csv**.
Existing valid packages are registered on discovery without overwriting their
files. Missing rights, unsupported sources, missing provenance, changed hashes,
synthetic fixtures or inadequate QA make a record unavailable.

As in Phase 2, platform_public_as_is is retained unchanged but is not a resale
licence. YouTube/platform packages and synthetic fixtures remain in the existing
private archive with pricing disabled, rather than becoming sale listings.

### Buyer API and Stripe test checkout

```bash
foundry --root ./data api-key create --name "buyer-acme"
foundry --root ./data api-key list
foundry --root ./data api-key revoke <key-id>
```

Keys are shown once; api_keys stores only SHA-256 hashes and lifecycle timestamps.
Buyer dataset, checkout and order routes require Authorization: Bearer or X-API-Key. Missing/invalid
keys return 401, revoked/inactive keys 403, and over 60 authenticated requests in
a fixed UTC minute returns 429 + Retry-After. Usage is persisted by key ID.

- GET **/api/v1/datasets**: paginated saleable discovery with the same UI filters.
- GET **/api/v1/datasets/[id]**: full legal metadata, price and reviewed previews.
- GET **/api/v1/datasets/[id]/manifest**: JSON legal record including full
  attribution, licence list, manifest SHA-256, image/source/licence records and QA.
- POST **/api/v1/checkout**: authenticated Stripe test Checkout. Accepts dataset_id
  and email; returns session_id, url, order_id. Use Idempotency-Key for retries.
  Missing/invalid test configuration retains 501 checkout_not_implemented.
- GET **/api/v1/orders/[id]**: owner-key-only status and signed 24-hour paid download.
- POST **/api/v1/webhooks/stripe**: raw-body Stripe signature authentication.
- GET **/api/v1/downloads?token=...**: paid signed grant for images + manifest ZIP;
  kind=manifest returns CSV. Unknown/unpaid/tampered/expired links are denied.

The Buy dataset form collects only buyer email and an existing buyer API key,
then redirects to Stripe-hosted **test** Checkout. Card details never pass through
Foundry. Buyer keys remain separate from dashboard sessions. Existing free legal
manifests and owner exports remain available; buyer manifest JSON remains a legal
record, not an entitlement to paid images. Live Stripe keys are rejected.

With FOUNDRY_WORKER_URL set, all operations/files use an authenticated HTTPS worker
(FOUNDRY_WORKER_API_KEY, server-only). Without it the local subprocess bridge is
retained. Worker owns Stripe credentials, SQLite, jobs and files; Vercel needs its
worker URL/key and dashboard variables. See **docs/DEPLOYMENT.md** for the exact
variable table, worker Compose setup, Stripe webhook/test-card flow, signed links
and hosted upload/streaming limits. No production deployment is performed here.

See **docs/BUYER_API.md** for curl examples, schema, filters, hashing and statuses.

### Migrations and verification

Database initialization applies additive, idempotent migrations in foundry/db.py,
ending at PRAGMA user_version=5. Original rows/seen_urls/quota and their invariants
are retained. New tables are image_metadata, usage_log, quota_blocks, datasets,
schedules, schedule_log, api_keys and api_rate_limits. No existing dataset receives
an invented price or a synthetic legal approval.

```bash
pytest -q
pytest web/tests -q
cd web
npm run lint
npm run build
npm run test:e2e
```

New tests cover HTTP retry/backoff and sanitized failures, per-attempt quota/provider
exhaustion, metadata rejection, verifier tokens/fail-closed verdicts, manifest
fingerprints, combined search, pricing, hashed/revoked/rate-limited keys, schedules,
locks, and real scheduled pause/resume at QA. Browser tests extend the prior wizard
checks with real Next.js buyer routes, legal manifests, combined URL filters,
price edits, reviewed previews and unconfigured-checkout 501 behavior.

Live validation requires usable provider access. In the Phase 3 Cloud verification
environment, Openverse returned a 403 HTML “Just a moment” access challenge, and
YouTube/OpenAI credentials were not configured. No challenge bypass or replacement
source was added. Provider behavior is exercised by deterministic HTTP unit tests;
the application continues to use the real endpoints in live mode.

## Phase 4 — Production hardening and launch readiness

[![CI](https://github.com/RevenantSoup/foundry/actions/workflows/ci.yml/badge.svg)](https://github.com/RevenantSoup/foundry/actions/workflows/ci.yml)

Phase 4 hardens the existing app; it does not add sources, training or payments.
The CLI stays login-free. The public catalog/detail pages stay public. A single
admin login now protects owner workflows and internal APIs, while /api/v1/*
continues to use the existing hashed buyer API keys.

### Local admin setup

Copy web/.env.example to the ignored web/.env.local and set:

- FOUNDRY_ADMIN_USER
- FOUNDRY_ADMIN_PASSWORD: unique, at least 12 characters
- FOUNDRY_SESSION_SECRET: at least 32 random characters (e.g. openssl rand -hex 32)
- NEXT_PUBLIC_SITE_URL: local origin for development, final HTTPS origin before
  a production build

Placeholder credentials are rejected. Run npm install and npm run dev in web/,
then visit /login. The existing dashboard URL remains /; /dashboard is a protected
alias. /new, /batches (including QA), /qa, /analytics, owner asset exports, jobs,
state, usage and price mutations require an admin session. /datasets and
/datasets/[id] remain public; owner controls are hidden without a session.
?admin=1 explicitly requests the protected catalog/detail admin view.

Auth uses signed httpOnly, SameSite=Lax, eight-hour cookies, Secure in production.
Password/session-secret changes invalidate old cookies; recreate the web process
after editing environment values. Sign out clears the browser cookie. There are
no multi-user accounts, roles, resets or OAuth. CLI commands still need no login;
an admin cookie never substitutes for a buyer key.

### Docker / Compose quickstart

A single root multi-stage Dockerfile builds Python 3.11 + ffmpeg + CPU inference
dependencies and a Node 22 Next.js standalone web runner. Both final targets are
non-root; dependencies come from pyproject.toml and web/package-lock.json. Models
are not downloaded during image builds. Test/dev data, .env, .git, SQLite files,
node_modules and .next are excluded by .dockerignore. On first startup the
non-root entrypoint unpacks the trusted CPU SDK once into the shared data volume;
allow extra startup time and disk space. See the deployment guide for cache and
model-storage details.

```bash
docker build --target cli -t foundry-cli .
docker build --build-arg APP_VERSION="$(git rev-parse HEAD)" \
  --build-arg NEXT_PUBLIC_SITE_URL=https://your-real-domain.example \
  -t foundry-web .
docker run --rm foundry-cli --help
```

For local full-stack use, copy .env.example to ignored .env, set unique admin
credentials and the session secret, then:

```bash
docker compose --env-file .env up --build -d
docker compose ps
docker compose logs -f web cli-worker
docker compose run --rm cli-worker foundry --help
docker compose run --rm cli-worker python /app/scripts/seed-demo.py --root /data
# Open http://localhost:3000/datasets or /login
docker compose down
```

Both services mount **foundry-data:/data**. The database is
**/data/foundry.sqlite3**. FOUNDRY_ROOT remains the only data-path setting;
DATABASE_PATH is not a separate configuration. The cli-worker wrapper executes
explicit commands when supplied; otherwise it runs run-scheduled every 300
seconds (FOUNDRY_SCHEDULE_POLL_SECONDS). Schedules remain UTC and pause for real QA.

Compose passes NEXT_PUBLIC_SITE_URL to both build and runtime. Rebuild if the
canonical origin changes; changing a runtime public variable cannot rewrite
statically rendered HTML.

Managed HTTPS proxies can supply a trusted build CA without disabling TLS:

```bash
FOUNDRY_DOCKER_CA_FILE=/etc/ssl/certs/ca-certificates.crt \
  docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t foundry-web .
docker compose --env-file .env -f docker-compose.yml \
  -f docker-compose.build-ca.yml up --build -d
```

Normal hosts/CI use the ordinary commands without the optional CA override.
Do not use down -v on a real dataset volume without an intentional backup plan.

### Constrained-disk verification

Use the normal build/Compose commands above on a host with at least 20 GB free.
For small disks, the optional `docker-compose.low-disk.yml` keeps the reproducible
SDK cache in executable tmpfs (up to 2 GB RAM per service; use at least 8 GB RAM).
SQLite and dataset bytes still persist in the shared named volume. Build the
images first, then start with `--no-build` and the low-disk override.

The following staged cache commands were used for the managed vfs workspace.
Add the trusted `--secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt` flag
to builds when the managed proxy requires it. Pruning here removes disposable
build cache, not datasets or volumes.

```bash
docker build --build-arg BUILDKIT_INLINE_CACHE=1 --target cli -t foundry-cli .
docker build --build-arg BUILDKIT_INLINE_CACHE=1 --target web-assets -t foundry-assets .
docker builder prune -af
docker build --build-arg BUILDKIT_INLINE_CACHE=1 --cache-from foundry-cli \
  --cache-from foundry-assets -t foundry-web .
# Retain foundry-assets if running smoke-test.sh next: it reuses that optional cache.
# Otherwise release it and its disposable cache before starting the small-disk stack:
docker image rm foundry-assets
docker builder prune -af
docker compose --env-file .env -f docker-compose.yml \
  -f docker-compose.low-disk.yml up --no-build -d
```

CI verifies the default persistent-cache `docker compose up --build --wait`
arrangement and then runs the complete smoke script on a normal runner.

### Demo and guided tour

```bash
python scripts/seed-demo.py
# Optional isolated data directory:
python scripts/seed-demo.py --root ./data-demo
# web/npm run seed delegates to the same idempotent implementation.
```

Two DEMO · synthetic fixture packages are created through the real offline CLI,
using project-generated synthetic references/media and explicit fixture QA only.
They remain unavailable for sale and excluded from the buyer API. Existing licence,
attribution, dedupe and 200-sample / 0.90 rules are not relaxed: each demo contains
200 images, rather than pretending 20 images could satisfy the mandatory sample.
Rerunning reuses the same batches/packages. Do not seed into a live CLIP root.

Public visitors can inspect these labeled demo records; owner controls remain
protected. The first authenticated visit offers a non-blocking guided tour of
Overview → New Dataset → Batch → QA → Marketplace. It starts only when requested,
can be skipped/closed at every step, and remembers dismissal in localStorage.
The Tour button allows an explicit restart.

### Operational hooks, metadata and accessibility

- foundry --version and --help are supported. CLI errors/warnings emit timestamped,
  redacted JSON to stderr, optionally FOUNDRY_LOG_FILE. QA keeps exit 1 and YouTube
  quota keeps exit 2. Help/version preserve successful exits.
- GET /api/health returns status, db and version; DB failure is HTTP 503. Internal
  API errors consistently include error + message. Buyer error codes/contracts
  and unconfigured-checkout 501 behavior remain intact.
- Logging is centralized in foundry/logging.py and web/lib/logger.ts. Optional
  SENTRY_DSN activates server hooks; unset works without any monitoring vendor.
  Docker includes the Python optional SDK; source installs can use
  pip install -e '.[monitor]'. Request bodies, cookies and auth headers are not
  collected by the hook. No real monitoring delivery was assumed verified.
- Global error/not-found/loading boundaries and skeletons improve failure and
  loading states. CLI jobs remain background jobs with real status/counts.
- Existing public samples and private QA crops use next/image where practical.
  Private crop requests are unoptimized so browser session cookies reach the
  protected route; they are not sent through an unauthenticated image optimizer.
- Visible focus/skip navigation, field labels, keyboard-native filters/dialogs,
  semantic headings, alt text, icon labels, readable quiet text and 44px mobile
  controls are checked in the launch checklist.
- The title template is %s | Foundry. Public dataset metadata is derived from real
  dataset records, unavailable/demo records use noindex, and canonical/OG/Twitter,
  robots.txt, sitemap.xml and the app/social icons are supplied without fake claims.

### CI, smoke checks and release gates

.github/workflows/ci.yml runs Python 3.11 tests, bridge tests, Node 22 npm ci/lint/
build, browser regressions, and both Docker builds on main pushes and pull requests. Pip/npm caches are
enabled. Builds do not publish images or need provider/admin secrets.
Check the linked Actions run for the actual remote result; a valid YAML file alone
is not evidence of a green run.

```bash
pytest -q
pytest web/tests -q
cd web && npm run lint && npm run build && cd ..
# Requires a running local/production-like stack with a demo or licensed dataset:
bash scripts/smoke-test.sh
```

smoke-test.sh fails fast with named PASS/FAIL checks for pytest, Next build, both
Docker builds, health/DB, public catalog/detail and unauthenticated buyer API 401.
Set FOUNDRY_SMOKE_URL to another origin, SMOKE_PYTHON to a host interpreter, or
FOUNDRY_DOCKER_CA_FILE for a managed build proxy. It never starts payments.

See **docs/DEPLOYMENT.md** for the supported persistent-host arrangement, explicit
Vercel + authenticated worker setup, Stripe test mode, auth rotation, backups, rollback and monitoring.
See **LAUNCH_CHECKLIST.md** for honestly checked local evidence and outstanding
operator work. Real provider access, public TLS/domain, production load/restore
drills and a hosted Stripe test purchase require operator verification. No live payments are supported.
