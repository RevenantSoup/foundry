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
incomplete reviews block packaging. QA samples the exact highest scoring target
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
same version; version changes do not overwrite earlier packages.

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
embedding backend after filtering. Keep reference files available until filtering.
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
cosine dedupe, quota transactions and CLI exit 2, trimmed video, normalized
embeddings, shortlist-only verification, resumability, QA boundaries, incomplete
reviews, manifest completeness, versioning, source isolation and all CLI helps.
