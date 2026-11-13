# Phase 6 pipeline verification

The browser workflow in `web/e2e/workflow.spec.ts` drives the actual local application and Python CLI. It uses the supported offline synthetic source adapters. No source records, rights declarations, registry entries, or listing eligibility are changed to make the workflow appear saleable.

## What the workflow checks

1. Sign out, open the protected wizard, sign in through its real username/password form, and confirm the authenticated session.
2. Upload six references; generate a plan; run harvest and filter; generate the 200-image contact sheet.
3. Submit 179 accepts and 21 rejects. Assert persisted precision is 0.895, the QA flag remains false, and a separate package job fails specifically at the 90% QA gate.
4. Correct the 21 rejected verdicts; submit all 200 accepts; reload the page; verify persisted verdicts and the passed gate; package through the UI.
5. Read SQLite and the filesystem independently of the web bridge. Compare the persisted plan to its JSON file, check all six reference files and harvested raw files, verify 200 unique QA samples and their byte snapshots, and inspect the generated contact sheet and crops.
6. Verify all 200 manifest records against SQLite, compare raw image bytes to packaged bytes, recompute every image's provenance hash, check the manifest SHA-256 against `dataset.json` and the registry, and confirm the 180/20 train/validation split.
7. Download the actual manifest and ZIP. Confirm the synthetic package is labelled accordingly in the catalog and that a price-setting request is rejected with HTTP 400.

The run writes machine-readable IDs, paths, counts, hashes, job results, and sale-blocking reasons to the ignored `work/phase6-pipeline-evidence.json` file. It contains no credentials.

## Sale continuation boundary

The same offline dataset must stop before listing or checkout: the registry marks it synthetic and unsaleable. `Synthetic fixture; not for sale` is an expected guardrail, not a pipeline failure to bypass. Packages that include `platform_public_as_is` also require rights review because platform provenance does not grant resale rights.

The separate `web/e2e/payments.spec.ts` suite uses an explicitly test-only marketplace fixture with fabricated CC rights declarations. It exercises the checkout, signed webhook, order, and expiring download-grant implementation. That test does not establish real source licensing or prove that the offline pipeline dataset can be sold. A genuine same-dataset sale remains blocked until an independently rights-cleared, non-synthetic dataset exists.

## Execution evidence

The final local browser suite passed all **17 tests**. The earlier remote profile passed **7 tests** and retained separate pipeline evidence in `work/phase6-remote-pipeline-evidence.json`.

Artifact inspection completed at `2026-11-13T02:02:42.104Z` for batch `74291967c6f343cbb86f9459e93b06ee` and package `74291967c6f343cbb86f9459e93b06ee-4bab50ef0f5c19c4`.

| Evidence | Observed |
| --- | --- |
| Reference files | 6 readable PNGs, 6 distinct SHA-256 hashes |
| Harvested raw files / scored rows | 800 / 800 |
| Shortlisted and verified | 600, all accepted by the offline stub verifier; 200 not shortlisted |
| Embedding backend | `stub:sha256-rng:v1` |
| Batch embedding vectors | 800 |
| Global embedding matrix | `work/web-test-data/embeddings.npy`, shape 4800 × 512 |
| Embedding index | `work/web-test-data/embeddings.ids.json`; all 4800 IDs and vector bytes match SQLite |
| QA samples / byte snapshots | 200 / 200 |
| Rejected first review | 21 of 200; precision 0.895; package job exited 1 |
| Corrected persisted review | 200 accepts; QA passed after page reload |
| Packaged images / verified provenance hashes | 200 / 200 |
| Train / validation | 180 / 20 |
| Price-setting rejection | HTTP 400 for a valid $19.99 price |
| Sale continuation | **BLOCKED** |

The matrix is global across this test root, including earlier test batches; 800 of its vectors belong to this run. Scores and verifier accepts above are synthetic outputs and make no claim about live CLIP or visual quality.

Concrete artifacts:

- SQLite: `work/web-test-data/foundry.sqlite3`
- Plan: `work/web-test-data/plans/74291967c6f343cbb86f9459e93b06ee.json`
- QA images: `work/web-test-data/qa/74291967c6f343cbb86f9459e93b06ee/` (contact sheet plus 200 crops)
- Package: `work/web-test-data/packages/74291967c6f343cbb86f9459e93b06ee-4bab50ef0f5c19c4/` (manifest, dataset metadata, and 200 images)
- Manifest SHA-256: `d2501676e4d1a583896241e013488f3a002f331a25a4ae63e748bca5abd34bae`
- Full read-only inspection and job evidence: `work/phase6-pipeline-evidence.json`

The persisted registry reason is: `Synthetic fixture; not for sale; Platform provenance does not grant resale rights; rights review required`.

The pipeline's actual job records include harvest, filter, contact-sheet QA, failed review, blocked package, corrected review, and successful package. Their logs and reconstructed command arguments are included in the evidence JSON. Arguments were reconstructed from `web/bridge.py`, persisted plan/review files, and job payloads; the runner does not retain an original argv trace. No command was rerun to manufacture this evidence.

Representative command forms from those artifacts:

```sh
/workspace/foundry-project/.venv/bin/python -u -m foundry.cli --root /workspace/foundry-project/work/web-test-data plan --prompt 'Browser fixture safety glasses 1794535218579' --refs /workspace/foundry-project/work/web-test-data/web/refs/c7a87bc5-63f2-40cd-bea2-26768f07fbd7 --target 200 --threshold 0.28
/workspace/foundry-project/.venv/bin/python -u -m foundry.cli --root /workspace/foundry-project/work/web-test-data harvest --batch 74291967c6f343cbb86f9459e93b06ee
/workspace/foundry-project/.venv/bin/python -u -m foundry.cli --root /workspace/foundry-project/work/web-test-data filter --batch 74291967c6f343cbb86f9459e93b06ee
/workspace/foundry-project/.venv/bin/python -u -m foundry.cli --root /workspace/foundry-project/work/web-test-data qa --batch 74291967c6f343cbb86f9459e93b06ee
/workspace/foundry-project/.venv/bin/python -u -m foundry.cli --root /workspace/foundry-project/work/web-test-data qa --batch 74291967c6f343cbb86f9459e93b06ee --verdicts /workspace/foundry-project/work/web-test-data/web/reviews/056789d53dce4cb281bcd5912bc6f811.csv
/workspace/foundry-project/.venv/bin/python -u -m foundry.cli --root /workspace/foundry-project/work/web-test-data package --batch 74291967c6f343cbb86f9459e93b06ee
```

The real browser workflow additionally downloads the manifest and ZIP, visits the batch, catalog, analytics, and overview pages, and checks desktop/mobile overflow and browser errors. Suite-level results are recorded in the overall Phase 6 verification report.


The payment regression also independently opens the authorized ZIP and compares
its manifest, metadata and every image byte to that test fixture's real package.
It reads the actual webhook-created paid order and single grant from SQLite;
`work/phase6-sales-evidence.json` records order/session IDs, amount/currency,
manifest hash and matched-image count, never a buyer key or signed download token.
The corresponding remote profile uses `work/phase6-remote-sales-evidence.json`.
These assertions must pass in the recorded payment rerun; they do not remove the
same-dataset sale boundary above.

Split representation follows the existing package contract: the CSV's `split`
column records train/validation membership. No standalone train/validation files
are emitted or claimed by this verification.

Remote pipeline artifact: batch `5e8b497d46cc4eb0b636e036aebe3647`, package `5e8b497d46cc4eb0b636e036aebe3647-109a85469a9b9f5f`, manifest SHA-256 `247a05380bc422cbcf6fe71161062c3967d0326f3b3d748d5cc095b5764db1d5`. Its separate evidence records 800 raw files, 200 QA snapshots, 200 packaged images and verified provenance hashes, and the 180/20 split; its synthetic sale continuation also remains blocked.

## Separate test-only sales evidence

The local payment rerun recorded paid order `0a98d6996a6d4d73baf47642963b941c` for fixture dataset `17e536f62e1643c7a6d72b162d7d7f68-00d0b4080f9e9984`, session `cs_test_7e001f9ba9d317422ca87629fca85eff`, amount **1999 USD cents**. Authorized download: **HTTP 200**, **200 byte-matched images / 202 ZIP entries**. Manifest SHA-256: `2ec99fd109145a478d109227ca38bca9cebeac34543bcfd1e342d82e2ed9e502`. Evidence: `work/phase6-sales-evidence.json`.

The remote payment rerun recorded paid order `2ae20ef2dc2041859b18aafc2cb9f81f` for fixture dataset `5c841b661f29415aa52ceb92e7fb37cb-a7e599dcb1fa21fd`, session `cs_test_42ad6e3ba3b21bdaae0596fed7414819`, amount **1999 USD cents**. Authorized download: **HTTP 200**, **200 byte-matched images / 202 ZIP entries**. Manifest SHA-256: `7f488dc958df4f6780702fb47723d60f6f4718ef4337d3dac94edc3a7e2a1f30`. Evidence: `work/phase6-remote-sales-evidence.json`.

These are explicitly test-only synthetic-rights fixtures, separate from the unsaleable pipeline batches. They prove payment/download implementation, not genuine resale clearance. The tests then deliberately expire their grants to assert HTTP410; paid order records persist.
