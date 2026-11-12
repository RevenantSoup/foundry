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
Managed multi-host/serverless deployments need the bridge changes below.

## Vercel web: explicit limitation and preparation

The present **local subprocess + SQLite bridge cannot operate as the full app on
Vercel**: Vercel functions do not provide this Docker Python/ffmpeg environment,
persistent shared SQLite storage, or durable background CLI workers. Setting
FOUNDRY_ROOT on Vercel cannot mount the worker host's disk. A successful Next build
does not establish that backend functionality is deployed.

For a future Vercel frontend deployment:

1. Import RevenantSoup/foundry into Vercel and set Root Directory to **web/**.
2. Use Node 22, install command **npm ci**, build command **npm run build**.
3. Set NEXT_PUBLIC_SITE_URL to the final HTTPS origin **before building**, and set
   the three admin auth variables as server-only secrets. Add SENTRY_DSN only if
   using the optional hook. Never put admin/provider secrets in NEXT_PUBLIC vars.
4. Keep the CLI worker and database on the persistent host above.
5. **Before enabling traffic**, replace the subprocess transport in
   web/lib/server.ts with an authenticated internal HTTP job/read transport to
   that host. It must support durable job IDs/progress, references, QA, exports,
   prices, health and metadata. Use TLS, owner authorization, bounded uploads,
   and explicit request timeouts. Buyer v1 is read-only and is **not** a substitute
   for that internal mutation API. No remote-bridge env var is currently
   implemented; do not set an imaginary WORKER_API_URL and assume it works.
6. Alternatively migrate persistence/jobs to a production database/object store
   in a separately reviewed phase. Do not synchronize writable SQLite copies.
7. Run the complete smoke suite against that topology, verify auth/cookies,
   buyer-key handling, canonical URLs, logs and data integrity, then cut traffic.
   Until that adapter exists, use the supported single-host Docker arrangement.

No Vercel deployment was created in this phase. The launch checklist deliberately
leaves this future integration/deployment unchecked.

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
alongside it. The database contains buyer-key hashes and usage records: encrypt
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

- Vercel-to-worker transport/persistence is not implemented.
- SQLite is single-host; concurrency, scale and HA need deployment-specific tests.
- Checkout remains an explicit 501 placeholder. No payment is collected.
- Live Openverse access was blocked by a 403 challenge in the Cloud test
  environment; YouTube/OpenAI keys were unavailable. No bypass was added.
- Real provider credentials, public HTTPS/domain configuration, Sentry delivery,
  backup retention/restore and production load tests require operator validation.
