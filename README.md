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
environment's forwarded port. No authentication or payment collection is included;
run it in your trusted local environment.

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
Each invocation creates a unique fixture specification so global deduplication
does not empty subsequent demonstrations. Empty workspaces also render normally
without seeding.

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
  Prices are editable listing drafts; no checkout, public listing, or automatic
  legal clearance service is implemented.
- **Analytics /analytics**: yield and precision across batches, CLIP score
  distribution, source/licence mix, and quota usage over time. Synthetic batches
  are included and clearly identified elsewhere in the workspace.

### How the bridge works

Next.js Node-runtime routes under **web/app/api/** spawn **web/bridge.py** using
the configured Python interpreter. The bridge reads SQLite through a read-only
connection, reads package manifests and QA artifacts, and invokes
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

Bridge jobs, uploaded references, review CSVs, download caches, and prices live
under **data/web/** and are ignored by Git. Uploaded files are named by index,
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
