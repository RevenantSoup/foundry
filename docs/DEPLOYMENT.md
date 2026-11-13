# Deployment and operations

## Supported arrangement today

Run the **web and CLI worker on one persistent Docker host**, sharing the named
foundry-data volume. Both containers run as UID/GID 10001. The file is
**/data/foundry.sqlite3**; FOUNDRY_ROOT is the existing data-directory setting.
There is no second DATABASE_PATH setting. Images, manifests, embeddings, uploaded
references, jobs and logs share that data directory.

The web image contains Python 3.11, CPU inference dependencies, ffmpeg, Node 22,
the existing CLI and Next.js standalone output. No models are downloaded at build
time. Both CLI and web images come from the root multi-stage Dockerfile:
**--target cli** and the default final **web** target.

This is a single-host, low-concurrency arrangement, not a high-availability claim.
Keep the database off NFS and do not run writers on separate hosts against copied
SQLite files. Internal job/schedule locks coordinate writers on the shared volume.

## Primary example: Ubuntu VPS with Docker Engine + Compose

1. Provision a maintained Ubuntu 24.04 LTS VPS. Install Docker Engine and its
   Compose plugin from Docker's official instructions. Start with at least 4 GB
   RAM and 20 GB free disk, then size CPU/RAM/disk using your own datasets and load
   tests. Model downloads and dataset bytes need additional persistent space.
2. Clone the repository and choose a reviewed commit. Keep the CLI and web on the
   same commit. Copy .env.example to an ignored .env and restrict permissions:

   ```bash
   cp .env.example .env
   chmod 600 .env
   openssl rand -hex 32
   ```

   Set FOUNDRY_ADMIN_USER, a unique FOUNDRY_ADMIN_PASSWORD (minimum 12 characters),
   and FOUNDRY_SESSION_SECRET (minimum 32 random characters). Placeholder values
   are rejected. Store provider secrets in your host secret manager or protected
   environment, not Git. Set NEXT_PUBLIC_SITE_URL to the public HTTPS origin.
3. Build and start:

   ```bash
   docker compose --env-file .env up --build -d
   docker compose ps
   docker compose logs -f web cli-worker
   docker compose run --rm cli-worker foundry --help
   ```

   Port 3000 serves the app. Put it behind an HTTPS reverse proxy with restricted
   direct host access and sanitized forwarding headers. Do not expose the Docker
   socket. Run only trusted owner workflows in this first single-admin release.
4. For an empty isolated demonstration volume, seed only synthetic fixtures:

   ```bash
   docker compose run --rm cli-worker python /app/scripts/seed-demo.py --root /data
   ```

   Seeding is idempotent. It creates two 200-image packages because the mandatory
   QA sample contains 200 distinct images. Fixtures stay labeled DEMO/synthetic
   and unavailable for sale. Never seed into a live CLIP embedding root.
5. Check http://localhost:3000/api/health and the marketplace, then sign in at
   /login. Public discovery and dataset detail do not need login. Owner dashboard,
   wizard, batches, QA, analytics, price edits and exports require it.
6. Configure references/video files inside the persistent volume using container
   paths. Add a schedule with the existing CLI:

   ```bash
   docker compose run --rm cli-worker foundry --root /data schedule add \
     --spec /data/specs/safety.json --interval daily --time 10:00
   docker compose run --rm cli-worker foundry --root /data schedule list
   ```

   cli-worker polls run-scheduled every 300 seconds. Set
   FOUNDRY_SCHEDULE_POLL_SECONDS to change this interval. Schedule times remain
   UTC and QA remains manual. Alternatively disable the loop and call from host
   cron:

   ```cron
   */5 * * * * cd /srv/foundry && docker compose --env-file .env run --rm cli-worker foundry --root /data run-scheduled >> /srv/foundry/scheduler.log 2>&1
   ```

   Use one orchestration method; locks make overlapping invocations skip rather
   than duplicate work.
7. Create buyer keys via the CLI. Only hashes are stored. Buyer API authentication
   is independent of the admin cookie:

   ```bash
   docker compose run --rm cli-worker foundry --root /data api-key create --name buyer-acme
   ```

8. Verify from the repository on a host with Python dev dependencies and Node:

   ```bash
   FOUNDRY_SMOKE_URL=https://your-real-domain.example bash scripts/smoke-test.sh
   ```

   The script runs tests and local builds, then checks the supplied URL. It does
   not upload data or start real payments. It needs one existing licensed dataset
   or a labeled demo to test a detail page.
9. Stop without deleting data:

   ```bash
   docker compose down
   ```

   Do **not** add -v unless intentionally destroying the volume after a backup.

Other container hosts (Render persistent disks, Fly volumes, another VPS) can use
the same images, but preserve the single-host/shared-filesystem requirement.
Vercel uses the authenticated transport below; the database remains on one worker host.

## Vercel web + authenticated Docker worker

The remote bridge is implemented. Keep exactly one authoritative worker host for
SQLite and files; do not copy a writable database to Vercel or share it over NFS.
The original single-host arrangement above remains supported when
`FOUNDRY_WORKER_URL` is empty. A configured but failing worker never silently
falls back to a different local database.

Components and flow:

- **Vercel:** Next.js pages, dashboard sessions, public marketplace, `/api/v1`
  HTTP endpoints (including Checkout/webhook/order/download handling). Server-only
  transport forwards requests to the worker over HTTPS with a separate Bearer
  credential. No local Python, SQLite, uploads or dataset files are needed.
- **Worker host:** `python -m foundry.worker`, existing CLI, schedules, durable job
  records, SQLite `/data/foundry.sqlite3`, reference files and versioned packages.
  The shared Python payment service uses Stripe's official SDK here in remote
  mode, keeping payment validation identical to local subprocess mode. Stripe
  keys and the download-signing secret therefore live on this host, not Vercel.
- **Stripe test Checkout:** collects card details on Stripe's page. Foundry stores
  only order/payment identifiers, dataset/amount/currency, buyer email, status,
  technical idempotency/owner/hash fields, and expiring-grant metadata. It never
  stores raw webhook bodies or card fields.
- **Files:** worker validates access, then streams bytes through the Next.js
  response. Responses contain no worker address, filesystem path or worker key.
  ZIP downloads include the exact manifest, dataset metadata and that dataset's
  images. Attribution and provenance remain in the manifest and existing APIs.

### 1. Deploy the worker host

Use the Ubuntu/Docker prerequisites above (20 GB free disk minimum, then size for
model weights/data). Clone the reviewed commit and create an ignored `.env` with
mode 0600. Generate independent worker/download secrets with `openssl rand -hex
32`; do not reuse a buyer key, dashboard session secret or another service's key.

```bash
cp .env.example .env
chmod 600 .env
# Populate the server-only worker/payment/provider settings from the table below.
docker compose --env-file .env -f docker-compose.worker.yml config --quiet
docker compose --env-file .env -f docker-compose.worker.yml up --build -d
docker compose --env-file .env -f docker-compose.worker.yml logs -f worker-api cli-worker
```

This separate Compose file needs no dashboard/admin credentials. It binds the
worker API to **127.0.0.1:8000**. Put an HTTPS reverse proxy such as Caddy/Nginx in
front, preserve the Authorization header, restrict direct port access, add
request-rate/body limits, and omit query strings/Authorization from access logs.
Only publish the API through HTTPS; do not expose the Docker socket. The web
transport rejects HTTP except literal loopback addresses for local tests.

Every worker endpoint, including **GET /health**, requires
`Authorization: Bearer <worker credential>`. A missing/invalid key returns 401.
The Docker healthcheck reads the key from its environment without printing it.
The API is an allowlist, not a general command runner:

| Method / worker path | Input / result |
| --- | --- |
| GET /health | status, DB state, version; authenticated |
| POST /bridge | `{mode,payload}` for state/batch/refs_plan/plan/price/seo/health/demo/usage/discovery/dataset/buyer/payments; JSON result, private paths scrubbed |
| POST /jobs | `{batch,action,payload}`; durable queued job; actions harvest/filter/qa/review/package only |
| GET /jobs/{id} | status/log/exit code, private payload removed; jobs survive web restarts |
| POST /assets | validated asset selector; streamed contact/crop/sample/owner export |
| POST /paid-assets | signed token + kind; revalidated paid grant, streamed bytes only |

`refs_plan` accepts exactly six `{data: base64}` references and prompt/target/
threshold/live settings. Names never select host paths. Worker requests are
bounded to 86 MiB with 125-second socket timeouts and at most 16 request threads.
Next's JSON RPC timeout is 120 seconds; file streaming timeout is 300 seconds.
Long harvest/filter/QA/package work starts detached jobs and is polled, rather
than occupying a Vercel invocation. Stripe Session creation has a 20-second
network timeout; retry with the same Idempotency-Key after an uncertain result.

### 2. Deploy the Vercel web project

1. Import `RevenantSoup/foundry`; select **web/** as Root Directory, Node **22**,
   install **npm ci**, build **npm run build**, and the normal Next.js framework.
2. Set the Vercel-side variables below in environment settings (Production and/or
   Preview as appropriate). Use an isolated worker/data volume for Preview.
   `FOUNDRY_WORKER_URL` must be the worker's HTTPS origin; do not prefix it with
   `NEXT_PUBLIC_`. Do not set a local Python or data path on Vercel.
3. Set `NEXT_PUBLIC_SITE_URL` to the actual web HTTPS origin before build. Set
   unique dashboard credentials/session secret. Configure the same worker key on
   both sides; it is unrelated to hashed buyer keys.
4. Deploy through Vercel's normal workflow. **This task does not deploy it.**
   Check public `GET /api/health` -> status=ok/db=ok/version, dashboard login,
   public catalog, a dataset detail, refs upload, each pipeline stage, QA and
   signed downloads. Verify requests continue working when no local Python path
   or writable local data directory exists.
5. On the worker, set success/cancel URLs to this web origin (table below), then
   configure the Stripe test webhook and run the test flow below before traffic.

Hosted reference previews are resized in the browser to at most 1024 pixels and
450 KiB each; six plus form fields fit below Vercel's request-body limit. The
server rejects remote reference bodies above 3 MiB. Local mode retains original
references. Actual harvested dataset bytes are never resized by this upload step.
Downloads use streaming responses, not a buffered JSON/base64 file. The download
routes allow 300 seconds; select a Vercel plan/function duration and worker/proxy
limits appropriate to package sizes. Very large exports require capacity testing;
this phase does not introduce object storage or multi-host SQLite.

### Environment variables by side

All credentials are server-only. `.env.example` files contain empty values or
placeholders; enter real **test** credentials through secret managers, never Git.

| Variable | Vercel / web in remote mode | Worker host / local subprocess web |
| --- | --- | --- |
| FOUNDRY_WORKER_URL | Required HTTPS origin; empty selects local mode | Not needed on worker |
| FOUNDRY_WORKER_API_KEY | Required independent 32+ character secret | Same value on worker API; not needed for local subprocess mode |
| FOUNDRY_ADMIN_USER | Required owner login username | Only local web; not worker |
| FOUNDRY_ADMIN_PASSWORD | Required owner password, 12+ characters | Only local web; not worker |
| FOUNDRY_SESSION_SECRET | Required separate 32+ character session secret | Only local web; not worker |
| NEXT_PUBLIC_SITE_URL | Actual public web origin, build + runtime | Local web origin; worker does not need it |
| APP_VERSION | Reviewed commit SHA/version | Same release version recommended |
| STRIPE_SECRET_KEY | Not needed remotely | Required for Checkout; must be a test secret (`sk_test_…`), never live |
| STRIPE_PUBLISHABLE_KEY | Not needed remotely; no Stripe.js/card form is used | Required test-mode configuration (`pk_test_…`); never live |
| STRIPE_WEBHOOK_SECRET | Not needed remotely | Required endpoint/Stripe-CLI signing secret (`whsec_…`) |
| FOUNDRY_DOWNLOAD_SECRET | Not needed remotely | Independent random 32+ character HMAC secret |
| STRIPE_SUCCESS_URL | Not needed remotely | e.g. `https://WEB-ORIGIN/checkout/success?order={ORDER_ID}&session_id={CHECKOUT_SESSION_ID}` |
| STRIPE_CANCEL_URL | Not needed remotely | e.g. `https://WEB-ORIGIN/checkout/cancel`; `{DATASET_ID}` also supported |
| FOUNDRY_ROOT | Do not set a local path | `/data`; DB and files persist in named volume |
| FOUNDRY_REPO / FOUNDRY_PYTHON | Not needed remotely | Local web source root/interpreter; Docker sets `/app` / `/usr/local/bin/python` |
| OPENVERSE_API_KEY | Not needed remotely | Optional bearer token for live Openverse |
| YOUTUBE_API_KEY / OPENAI_API_KEY | Not needed remotely | Only for live CLI providers/verifier |
| FOUNDRY_VIDEO_DIR | Not needed remotely | Authorized local videos; paths must exist inside worker container |
| FOUNDRY_SCHEDULE_POLL_SECONDS | Not needed | Scheduler loop interval, default 300; UTC schedules |
| FOUNDRY_LOG_FILE | Not needed | Optional redacted CLI JSON-lines log, e.g. `/data/logs/cli.jsonl` |
| SENTRY_DSN | Optional | Optional; unset disables monitoring vendor connection |
| FOUNDRY_DOCKER_CA_FILE | Not needed | Optional trusted build-CA bundle on managed proxy hosts |

Return URLs must use HTTPS except loopback development URLs. Test secret,
publishable key, webhook secret, signing secret and return URLs must all be valid
before checkout is enabled. Live keys are rejected. Rotating the download secret
invalidates existing links; it does not mint replacement grants.

### Stripe test webhook and purchase

**Exact public webhook: POST /api/v1/webhooks/stripe**. It is not protected by buyer
keys or the dashboard cookie; Stripe's raw-body signature is the authentication.
Next passes the untouched bytes to the official SDK verifier. Missing/invalid,
tampered, stale/future signatures or malformed event bodies return 400 and grant
nothing. Unconfigured payment services fail closed (501; missing signature can
be rejected with 400 first). The worker endpoint itself always requires its
separate internal Bearer key.

1. In Stripe Dashboard select **test mode**, copy test API keys into the trusted
   payment backend environment. Create a test webhook endpoint pointing to
   `https://WEB-ORIGIN/api/v1/webhooks/stripe`, subscribe to
   `checkout.session.completed`, `checkout.session.expired` and
   `checkout.session.async_payment_failed`, and configure its signing secret on
   that backend. Do not use live credentials or live endpoint events.
2. For local testing, authenticate the Stripe CLI to a test account and run:

   ```bash
   stripe listen --forward-to localhost:3000/api/v1/webhooks/stripe \
     --events checkout.session.completed,checkout.session.expired,checkout.session.async_payment_failed
   ```

   Use the temporary signing secret reported by this listener, then restart local
   web (or the remote test worker). Never commit it or paste it into project logs.
3. Prepare a real rights-cleared, QA-approved package and set its existing USD
   price using `foundry --root /data price DATASET_ID --price-cents 1999`. Synthetic demos and
   platform-only YouTube packages remain unavailable for sale. Create a buyer
   key with the existing CLI, and keep the plaintext key private.
4. Open the public dataset page, click Buy dataset, enter buyer email + buyer API
   key, then Continue to Stripe test checkout. Direct clients can POST JSON
   `{ "dataset_id": "DATASET_ID", "email": "buyer@example.test" }` to
   `/api/v1/checkout` with existing buyer Bearer auth and an `Idempotency-Key`.
   The response is `{session_id,url,order_id}`. An order is pending before
   redirect. Reusing an idempotency key binds the same dataset/email/price; a
   conflicting retry returns 409. Amount is the dataset's existing integer minor
   units and currency; no FX, tax or discount is introduced.
5. On **Stripe's hosted test page only**, use **4242 4242 4242 4242**, any future
   expiry and any test CVC. Foundry has no card inputs. Do not use a real card.
6. A success redirect alone grants nothing. Check the signed webhook returned
   200, then on `/checkout/success?order=ORDER_ID` enter the same buyer API key to
   query `GET /api/v1/orders/ORDER_ID`. Only that key's owner can read the receipt.
   Status becomes paid only for a verified completed Session with paid status,
   matching Session/order/dataset/amount/currency and unchanged licensed package.
   Mismatches go to review with no grant. Duplicate deliveries keep one order
   and one original grant; they never extend its expiry.
7. The paid receipt returns a **relative signed download_url**, valid for
   **24 hours from verified payment**, plus expires_at. It serves images +
   manifest ZIP; append `&kind=manifest` for CSV. Unknown, unpaid, tampered or
   mismatched links return 403; expired links return 410 (an altered grant can
   also return 403). Access is rechecked on every request. Do not log these URLs
   or query strings. Existing buyer manifest JSON remains a legal/provenance
   record, not an entitlement to the paid image files.
8. Verify duplicate webhook delivery, failure/expiry, wrong amount/currency and
   revoked buyer-key behavior on an isolated test volume. To exercise expiry
   without waiting a day, use the isolated automated tests; do not edit a live
   order's expiry or grant a new token manually.

Automated tests mock Stripe's SDK transport with realistic SDK resources and
verify real HMAC signatures, local and remote APIs, grants and files. They never
call Stripe. No Stripe credentials were available during implementation, so a
real hosted 4242 purchase/webhook delivery is **not claimed** and remains an
operator test. Stripe must stay in test mode; live commerce, tax/refunds and
production money are outside this phase.

### Troubleshooting and updates

- **501 checkout_not_implemented:** keys/secrets/return URLs are missing, invalid
  or live-mode. Set the entire test configuration on the worker in remote mode,
  or local web's process in local mode. Keep the existing buyer key header;
  missing/revoked/rate-limited buyer keys still return 401/403/429 first.
- **400 webhook:** verify the exact raw body, correct endpoint signing secret,
  Signature header and synchronized clocks (300-second tolerance). A Stripe CLI
  listener's secret differs from a Dashboard endpoint's secret. Do not bypass
  verification; there is no grant on error.
- **Worker unreachable/timeout:** web returns clear 503; durable jobs continue on
  the host. Check HTTPS certificate, reverse proxy, firewall and worker logs.
  A configured worker never falls back to an empty local database.
- **Worker 401:** internal key mismatch/missing/placeholder; web maps this to a
  configuration-error 503, while direct worker calls return 401. This is separate
  from buyer API 401. Never fix it by exposing the worker key in the browser.
- **Local fallback:** unset FOUNDRY_WORKER_URL and restart Next.js, install the
  updated Python dependencies (`pip install -e '.[test]'`), and use the existing
  FOUNDRY_ROOT/FOUNDRY_PYTHON settings. Local mode needs no worker credential.
- **Download denied:** verify paid status, same dataset/manifest, unchanged files,
  expiry and signing secret. Do not loosen licence or QA gates. Refund processing
  and dispute automation are not implemented; handle test cases manually.

Update by reviewing/pulling the release on the worker host and rerunning
`docker compose --env-file .env -f docker-compose.worker.yml up --build -d`, then
redeploy the matching web commit through Vercel. Back up database/packages first;
use the backup/rollback procedure below. No production deployment or live
credential rotation is performed by this task.

## Environment reference

| Setting | Scope |
| --- | --- |
| FOUNDRY_ROOT | Existing data directory. Compose fixes /data; DB is /data/foundry.sqlite3. |
| FOUNDRY_PYTHON | Web bridge interpreter. Container uses /usr/local/bin/python. |
| FOUNDRY_REPO | Container source root /app; normally inferred for local source runs. |
| FOUNDRY_ADMIN_USER | Single admin username; required for dashboard login. |
| FOUNDRY_ADMIN_PASSWORD | Unique password, minimum 12 characters; no committed defaults. |
| FOUNDRY_SESSION_SECRET | At least 32 random characters, server-only. |
| NEXT_PUBLIC_SITE_URL | Canonical HTTPS origin; passed at build **and** runtime in Compose. Rebuild if changed. |
| APP_VERSION | Git SHA or package version for health. Pass --build-arg APP_VERSION=$(git rev-parse HEAD). |
| OPENVERSE_API_KEY | Optional Openverse OAuth bearer token; never forwarded to image hosts. |
| YOUTUBE_API_KEY / OPENAI_API_KEY | Live providers only. |
| FOUNDRY_SCHEDULE_POLL_SECONDS | Worker polling interval, default 300. |
| FOUNDRY_LOG_FILE | Optional JSON-lines CLI log, Compose /data/logs/cli.jsonl. |
| SENTRY_DSN | Optional server monitoring; unset means no vendor connection. |
| FOUNDRY_DOCKER_CA_FILE | Optional **build-only** trusted CA bundle for a managed HTTPS proxy. |

Compose reads root .env; local Next dev reads web/.env.local. Neither is committed.
CLI commands remain usable without login. Do not export a container-only
FOUNDRY_PYTHON path into a host environment that uses a different interpreter.

### Admin session behavior and rotation

Sessions are signed, httpOnly, SameSite=Lax, eight-hour cookies. Secure is always
set in production; use HTTPS away from localhost. Password or session-secret
rotation invalidates all old cookies because the signature binds current
credentials. Edit secrets and recreate web:

```bash
docker compose up -d --force-recreate web
```

Sign-out deletes the current browser cookie. Stateless cookies cannot individually
revoke a stolen token; rotate credentials immediately if compromised. Login has a
bounded, credential-wide in-memory attempt budget; add trusted reverse-proxy rate
limits for Internet exposure/multiple replicas. No multi-user roles/reset/OAuth
were added. /api/v1/* continues to require buyer keys even for logged-in admins.

### Monitoring and logs

CLI failures/source warnings are JSON lines on stderr with timestamp, command,
batch ID and preserved exit code. The optional file uses the same redacted records.
Web logging lives in web/lib/logger.ts; health/internal server errors use it.
FOUNDRY_ADMIN_PASSWORD, FOUNDRY_SESSION_SECRET, provider keys, Bearer tokens and
buyer-key-shaped strings are redacted. Do not log request bodies or auth headers.

SENTRY_DSN activates optional server hooks only. Web @sentry/node has default
integrations and request/header/body collection disabled; explicit reports contain
sanitized errors. CLI images include sentry-sdk; source installs can use
pip install -e '.[monitor]'. No Sentry account or paid service is required.
Sentry delivery with a real DSN is not part of local verification.

GET /api/health is public and reports status, DB accessibility/integrity and
APP_VERSION (or 0.1.0). An unavailable DB returns HTTP 503 with db=error and a
consistent error/message. Supervise it externally and rotate log files on the
host; unbounded dataset growth/log retention is an operator responsibility.

For constrained disks with at least 8 GB RAM, see the README staged-cache build
commands and optional `docker-compose.low-disk.yml`. This uses executable RAM
mounts only for the trusted reproducible SDK (up to 2 GB per service); dataset
bytes and SQLite stay on disk. Each service unpacks its own RAM cache after a
restart. Default deployments share one persistent SDK cache instead.

## Container dependency cache

FFmpeg/ffprobe come from the digest-pinned `mwader/static-ffmpeg:8.0.1` build
stage ([upstream source/build recipe](https://github.com/wader/static-ffmpeg));
they retain the existing CLI scene-split/trim/frame-cap behavior.

The image packs its full CPU Python dependencies and static FFmpeg tools into a trusted xz archive to keep
image layers small. The non-root entrypoint expands it once into
`/data/.runtime/<archive-sha256>` under a shared file lock, then starts the CLI
or web process with that SDK on `PYTHONPATH` and its tools on `PATH`. Both
services share the same cache. Use the bootstrap entrypoint for one-off commands
(`docker compose run`), rather than bypassing it with `docker exec foundry`.
The container sets `HF_HOME=/data/models` so later live CLIP downloads survive
container recreation. Model weights are reproducible but need their own disk
budget. Allow roughly 2 GB for the unpacked runtime plus model weights and dataset data;
first startup takes longer. Do not override the entrypoint. This cache is
reproducible and can be excluded from backups. Remove old hash directories only
after stopping every container using that image version; retain the current
version. Logs, datasets and SQLite remain under the usual `/data` paths.

## Backups and rollback

Use sqlite3.Connection.backup for a consistent DB snapshot. Back up the package
directories/manifests/images, raw bytes, embeddings/index, plans and QA records
alongside it. The database contains buyer-key hashes, usage records, orders and buyer emails: encrypt
backups and restrict access. Back up secrets separately in a secret manager.

For a simple maintenance-window backup, stop web/worker writers, then run a
one-off CLI container against the same volume to create a DB backup and archive
/data to a protected off-host destination. Example DB snapshot:

```bash
docker compose stop web cli-worker
docker compose run --rm cli-worker python -c \
 'import sqlite3,pathlib; p=pathlib.Path("/data/backups"); p.mkdir(exist_ok=True); sqlite3.connect("/data/foundry.sqlite3").backup(sqlite3.connect(str(p/"foundry.sqlite3.backup")))'
# Copy/archive the volume to your encrypted backup destination, then restart:
docker compose start web cli-worker
```

Perform and document a restore drill before launch; local tests do not prove your
off-site restore process. Retain matching CSVs and dataset.json files so manifest
hashes remain verifiable.

Rollback by redeploying a previous **known-good hardened commit/image**, restoring
the matching DB/data snapshot if a migration needs it, and rerunning health/smoke.
There are no automatic down-migrations. Do not publicly roll back to the earlier
unauthenticated dashboard without adding an external access gate.

## Not production-ready or not verified

- Vercel-to-worker transport is implemented; deployment-specific TLS, capacity and hosted verification remain operator work.
- SQLite is single-host; concurrency, scale and HA need deployment-specific tests.
- Checkout is Stripe TEST mode only; unconfigured installations retain 501. No live money is supported.
- Live Openverse access was blocked by a 403 challenge in the Cloud test
  environment; YouTube/OpenAI keys were unavailable. No bypass was added.
- Real provider credentials, public HTTPS/domain configuration, Sentry delivery,
  backup retention/restore and production load tests require operator validation.

## Workspace failures and Phase 6 verification

Ordinary browser reads time out after 10 seconds. Workspace/health RPC reads have
an 8-second backend deadline; job creation/planning retain their 120-second
budget and file streaming retains 300 seconds. CLI jobs remain detached and are
polled rather than given the short read deadline. A terminal read failure stops
polling, replaces the initial spinner with an error and Retry, and preserves any
previously loaded data. Retry starts a fresh request; navigating away cancels the
browser request and timer. Authentication failures, invalid responses and network
errors remain distinguishable from `database_unavailable`.

On Vercel without `FOUNDRY_WORKER_URL`, a page shell or successful admin login is
not proof that the dataset backend works. Public dataset routes return sanitized
503 infrastructure errors when the Python bridge cannot start. Health remains
503 with `db:error`; missing buyer credentials return 401 without needing Python.
No persistent serverless SQLite workaround is provided.

See [Phase 6 pipeline evidence](PHASE6_PIPELINE.md) and the
[live audit / hosting assessment](PHASE6_LIVE_AUDIT.md). The offline fixture can
prove CLI persistence and packaging, but remains synthetic and unsaleable. It
must not be relabelled to make a purchase test pass.

Focused regressions use the existing Playwright setup:

```sh
cd web
npm run test:e2e -- stability.spec.ts uploader.spec.ts
npm run test:e2e -- --config playwright.unavailable.config.ts
```

The second profile deliberately uses a nonexistent Python interpreter, exercises
real routes rather than frontend mocks, and stores any test data under
`work/unavailable-test-data`. CI runs both profiles and the existing local/remote
payment tests. Installing Chromium uses the existing `npx playwright install chromium`.
