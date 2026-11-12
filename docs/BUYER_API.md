# Foundry buyer API v1

This read-only API exposes rights-cleared, QA-approved, non-synthetic datasets.
It does not process payments or grant rights beyond the declared source licences.
The dashboard remains the unauthenticated local owner interface. Buyer keys protect
**/api/v1/**; they are not dashboard authentication.

## Create and manage keys

Use the same data directory as the web app:

```bash
foundry --root /absolute/path/to/data api-key create --name "buyer-acme"
foundry --root /absolute/path/to/data api-key list
foundry --root /absolute/path/to/data api-key revoke <key-id>
```

Creation prints an ID and the plaintext key once. Save it securely. SQLite stores
only its SHA-256 hash; listing never returns the key or its hash. Revocation takes
effect on the next request. Do not commit keys or put them in query strings.

Set the printed key in your client environment, then send either header:

```bash
export FOUNDRY_BUYER_KEY='<key-printed-once>'
curl -H "Authorization: Bearer $FOUNDRY_BUYER_KEY" \
  http://localhost:3000/api/v1/datasets
# X-API-Key is also supported:
curl -H "X-API-Key: $FOUNDRY_BUYER_KEY" \
  http://localhost:3000/api/v1/datasets
```

Missing/unknown keys return **401**. Revoked/inactive keys return **403**. Each
active key gets **60 authenticated requests per fixed UTC minute**. Over the limit,
responses are **429**, with a positive integer **Retry-After** header in seconds.
Successful and rate-limited requests are recorded in usage_log using the key ID,
never the plaintext key. last_used_at tracks accepted authenticated requests.
All responses use Cache-Control: no-store.

## List and filter

```http
GET /api/v1/datasets
```

The same SQL filters power the UI and **GET /api/datasets**:

| Query | Meaning |
| --- | --- |
| q | Case-insensitive literal keyword in the dataset name/specification |
| licence | CC0, CC-BY, CC-BY-SA, or platform_public_as_is |
| source | openverse or youtube |
| attribute | Case-insensitive substring of the single dataset attribute/label |
| min_size / max_size | Inclusive image-count bounds, nonnegative integers |
| min_price / max_price | Inclusive USD bounds, up to two decimal places |
| free=true | Only price_cents = 0 |
| sort | newest (default), largest, price_low, price_high |
| page | 1-based page, default 1 |
| limit | Page size 1–100, default 12 |

Filters combine with AND. Unsupported filters/invalid numeric bounds return 400.
All datasets must have supported licences, attribution, image provenance, an
unchanged manifest fingerprint, and QA precision >=0.90 on 200 complete verdicts.
Synthetic fixtures never appear in buyer results. platform_public_as_is remains
recorded provenance, not resale clearance: such packages stay unavailable and a
YouTube/platform filter can legitimately return no saleable results.

```bash
curl -G -H "Authorization: Bearer $FOUNDRY_BUYER_KEY" \
  --data-urlencode 'q=safety' \
  --data-urlencode 'licence=CC-BY' \
  --data-urlencode 'source=openverse' \
  --data-urlencode 'attribute=glasses' \
  --data-urlencode 'min_size=200' \
  --data-urlencode 'max_size=2000' \
  --data-urlencode 'min_price=0' \
  --data-urlencode 'max_price=50.00' \
  --data-urlencode 'sort=price_low' \
  --data-urlencode 'page=1' --data-urlencode 'limit=12' \
  http://localhost:3000/api/v1/datasets
```

Response shape:

```json
{"items": [], "total": 0, "page": 1, "limit": 12}
```

Items include ID, name/description, attribute/labels, image and split counts,
size_bytes, created_at, batch_id, source/licence lists, full attribution records,
manifest_sha256, price_cents and currency. Existing packages default to 0 / USD;
the UI labels 0 as **Free**. No price is inferred from quality or image count.

## Dataset detail

```http
GET /api/v1/datasets/<dataset-id>
```

```bash
curl -H "Authorization: Bearer $FOUNDRY_BUYER_KEY" \
  http://localhost:3000/api/v1/datasets/<dataset-id>
```

Unavailable/unknown datasets return 404 to buyers. Detail includes full creator,
title, licence URL, source-page/source-URL attribution, QA precision, and at most
12 sample URLs. Every sample has an explicit QA accept verdict. Public preview
images are served separately from v1; they do not expose a bulk image-download
endpoint. Dataset pages at **/datasets/<dataset-id>** show the same legal record,
with an explicit unavailable reason for private/uncleared packages. Creator/source
records are visible on the page and the full attribution JSON is downloadable
from /api/datasets/<dataset-id>/attribution.

## Legal JSON manifest

```http
GET /api/v1/datasets/<dataset-id>/manifest
```

```bash
curl -H "Authorization: Bearer $FOUNDRY_BUYER_KEY" \
  http://localhost:3000/api/v1/datasets/<dataset-id>/manifest \
  -o buyer-manifest.json
```

The response includes:

- dataset metadata and the explicit USD price;
- licence list and **full attribution** records with creator and source URLs;
- provenance_hash, hash_algorithm = SHA-256, hashed_file = manifest.csv;
- the full image list with each source URL, licence and attribution;
- QA precision.

**The provenance hash fingerprints the exact CSV bytes, not the JSON serialization.**
Download the owner-export CSV in the local UI and run:

```bash
sha256sum manifest.csv
```

The digest must match manifest_sha256 / provenance_hash. Image-level provenance
hashes remain in CSV/JSON image records. If an indexed CSV changes, discovery and
buyer access fail closed. Legacy valid packages are registered by fingerprint
during migration/first discovery; packages with missing rights/provenance or
unapproved QA are unavailable. Registration never invents a price.

## PLACEHOLDER: Checkout

```http
POST /api/v1/checkout
```

A valid key is still required and rate limiting still applies. This route always
returns **501**:

```json
{
  "error": "checkout_not_implemented",
  "message": "Checkout is a placeholder in Phase 3. No payment is processed."
}
```

```bash
curl -X POST -H "Authorization: Bearer $FOUNDRY_BUYER_KEY" \
  http://localhost:3000/api/v1/checkout
```

The **Buy dataset** UI opens a panel saying: “Checkout is not live yet — this is
a placeholder. No payment will be taken.” No provider, redirect, card field, order,
or charge is implemented. Free saleable datasets also expose a legal-manifest
download from the detail page; paid datasets expose their legal record through
the read-only buyer API without pretending a purchase occurred.
