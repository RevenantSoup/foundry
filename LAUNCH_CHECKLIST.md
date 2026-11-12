# Foundry launch checklist

All checks are scoped to the evidence stated here. An unchecked item is work
remaining for the release owner, not an implied production guarantee.

## Pre-launch

- [x] Engineering: root pytest (original CLI plus later phases) and bridge tests pass on the final commit. 48 root tests and 8 bridge tests passed on the release source; GitHub CI repeats them on Python 3.11.
- [x] Engineering: npm ci, lint and production build pass; record browser/static bundle sizes. npm ci/lint/build passed locally; 24 static JS chunks total 1,283.8 KiB, one CSS file 72.9 KiB (all chunks, not initial payload).
- [x] Engineering: CLI and web multi-stage Docker builds pass with no keys baked in. Both passed locally, including the complete smoke script; build context excludes secrets/data.
- [x] Engineering: Compose starts both non-root services; shared /data persists SQLite and artifacts. Both services ran together and web was healthy. Worker seeded the shared DB; web served both demos. UID 10001, inference and FFmpeg verified. Cloud used the low-disk RAM override and --no-build after separate successful builds; CI tests default up --build.
- [x] Engineering: scripts/smoke-test.sh passes against the local full-stack run. Full script passed locally. HTTP checks used a consistent synthetic snapshot after the separately verified Compose run, allowing build checks within the 8 GB workspace.
- [ ] Release owner: GitHub Actions CI is green on the pushed commit; check the badge/run, not just YAML syntax.
- [ ] Operator: unique admin username/password/session secret configured; login/logout verified on public HTTPS.
- [ ] Operator: provider API keys configured and live quota/error behavior verified from the deployment host.
- [x] Engineering: auth does not protect public catalog/detail or replace v1 buyer-key checks. 8 browser tests passed, including login/logout, public catalog/detail, keyed buyer routes and the full wizard.
- [x] Engineering: duplicate asset-query parameters cannot bypass owner export authentication. Regression browser test verifies unauthenticated ambiguous image/manifest queries return 401.
- [x] Engineering: seeded demos are idempotent, synthetic-labeled, non-saleable and preserve 200-sample QA. Idempotency pytest passed; two labeled non-saleable fixtures each retain the required 200-sample QA.
- [ ] Release owner: demo/test data removed from the live CLIP root or unmistakably labeled.
- [ ] Release owner: attribution, licence obligations and exact manifest SHA-256 checked for every saleable launch dataset.
- [x] Engineering: checkout remains clearly marked PLACEHOLDER with 501 and no payment/card collection. Buyer API browser test verified the unchanged 501 contract.
- [x] Engineering: keyboard filters/login/tour, visible focus, image alt text, icon labels and semantic headings checked. Semantic controls and labels inspected; tour Escape/dismissal tested. Broader assistive-technology audit remains an operator task.
- [x] Engineering: dashboard, wizard, QA grid, catalog and detail checked at 390px; no document overflow. All five routes passed the 390px browser test; fixed a hidden mobile heading.
- [ ] Operator: NEXT_PUBLIC_SITE_URL set before build; canonical/OG/Twitter, robots and sitemap inspected with the real domain.
- [ ] Operator: logging retention configured; optional monitoring delivery tested if enabled.
- [ ] Operator: encrypted off-host SQLite/artifact backup and restore drill completed.
- [ ] Operator: concurrency/load/disk/model-cache capacity and TLS/reverse-proxy rate limits validated.

## Go live

- [ ] Operator: follow docs/DEPLOYMENT.md for the supported single-host Docker web + worker deployment.
- [ ] Future web owner: implement authenticated remote bridge/persistence before attempting full Vercel deployment.
- [ ] Future web owner: import Vercel project with web root and required build/server env only after that bridge is verified.
- [ ] Operator: deploy reviewed CLI-worker image and persistent volume; schedules use UTC and pause for real QA.
- [ ] Release owner: run smoke test against the actual production origin and inspect public health/version.
- [ ] Release owner: verify first keyed buyer list/detail/manifest request and revoked-key behavior.
- [ ] Release owner: confirm no secret, .env, generated database or buyer key is in the Git tree/image context.

## After launch

- [ ] Operator: monitor provider quota >=80%, 429s, retries, verifier errors and disk growth.
- [ ] Operator: inspect structured logs; rotate admin secrets/buyer keys if compromised.
- [ ] Release owner: confirm no placeholder checkout is mistaken for an actual purchase.
- [ ] Operator: verify scheduled batches and human QA approval before new exports appear.
- [ ] Operator: retain a known-good hardened image/data snapshot and exercise the rollback procedure.

## Local verification notes

- Production build with `NEXT_PUBLIC_SITE_URL=https://foundry-verification.invalid`
  embeds that reserved test origin in canonical/OG metadata. The actual launch
  domain and public HTTPS still need operator verification.
- YAML parsed locally and Compose configuration validates. Remote CI status must
  be checked after push.
- Additional malformed-Origin API regression passed; the full 8-test browser run
  and this extra request test cover 9 checks. CI reruns the complete suite.
