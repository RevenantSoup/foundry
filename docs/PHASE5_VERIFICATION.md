# Phase 5 verification

No production deployment, live Stripe credentials or real charge is part of this
verification. No account test credentials were provided: a real hosted 4242 test
purchase and Stripe-delivered webhook remain unverified. The documented manual
procedure in DEPLOYMENT.md is an operator step, not a claimed test result.

## Source tests (0 failures)

- `.venv/bin/pytest -q`: **82 passed**. Includes original CLI/quota/QA/legal tests,
  orders, real signature verification, duplicate/mismatched events, immutable TTL,
  unpaid/unknown/tampered/expired grants, image integrity, worker auth and jobs.
- `.venv/bin/pytest web/tests -q`: **8 passed**, existing local bridge contracts.
- `npm --prefix web run lint`: passed.
- `npm --prefix web run build`: passed, Next.js production compilation and types.
- `PLAYWRIGHT_BROWSERS_PATH=/workspace/foundry-project/work/browsers npm --prefix web run test:e2e`:
  **9 passed**, existing dashboard, buyer-key errors, QA refusal/recovery, wizard,
  manifests and mobile regressions.
- `PLAYWRIGHT_BROWSERS_PATH=/workspace/foundry-project/work/browsers npm --prefix web run test:e2e -- --config playwright.payments.config.ts`:
  **4 passed**, one remote-only case skipped. Actual local subprocess route,
  realistic mocked Stripe SDK resources, signed webhook, order and downloads.
- `PLAYWRIGHT_BROWSERS_PATH=/workspace/foundry-project/work/browsers FOUNDRY_TEST_REMOTE=1 npm --prefix web run test:e2e -- --config playwright.payments.config.ts`:
  **6 passed** before adding the separately run transport-fault case: authenticated
  worker, same payment API contracts and complete real CLI wizard. Web's Python
  executable and storage paths were deliberately unusable; no local fallback.
- `PLAYWRIGHT_BROWSERS_PATH=/workspace/foundry-project/work/browsers FOUNDRY_TEST_REMOTE=1 npm --prefix web run test:e2e -- --config playwright.payments.config.ts -g 'worker faults'`:
  **1 passed**, covering worker 401, dropped connection, invalid empty response
  and unexpected encoding; safe 503/502 errors and recovery without local writes.

The SDK fake is confined to web/e2e, excluded from Docker, and makes no Stripe
network calls. Signature verification uses the official SDK and real HMACs over
exact bytes. No production fake-Stripe flag exists.

## Docker (all exit 0)

The managed workspace has an 8 GB vfs filesystem. Trusted CA build secrets and
staged inline caches were used; TLS verification stays enabled.

```bash
docker build --build-arg BUILDKIT_INLINE_CACHE=1 --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt --target cli -t foundry-cli .
docker build --build-arg BUILDKIT_INLINE_CACHE=1 --cache-from foundry-cli --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt --target worker-api -t foundry-worker-api .
docker compose -f docker-compose.worker.yml config --quiet
docker compose -f docker-compose.worker.yml build --build-arg BUILDKIT_INLINE_CACHE=1 worker-api
docker builder prune -af
docker build --build-arg BUILDKIT_INLINE_CACHE=1 --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt --target web-assets -t foundry-assets .
docker builder prune -af
docker build --build-arg BUILDKIT_INLINE_CACHE=1 --cache-from foundry-cli --cache-from foundry-assets --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t foundry-web .
```

Worker API container startup/health was also tested on Python 3.11: no worker key
401, valid worker key 200/db=ok, buyer key rejected as worker key, missing Stripe
configuration 501 after buyer authentication, unknown download grant 403. The
constrained workspace used an executable RAM mount for the reproducible SDK cache
after its disk unpack hit ENOSPC; no dataset data was moved to RAM. Temporary test
volume was removed after verification. Normal persistent-cache Compose is tested
in CI on a runner with adequate storage.

CI repeats Python 3.11 tests, all browser profiles, lint/build, CLI/web/worker
Docker builds, worker Compose configuration, main + worker health and the complete
launch smoke script. Check the actual run for the pushed commit; local evidence
does not imply a hosted Vercel deployment or an actual Stripe test purchase.
