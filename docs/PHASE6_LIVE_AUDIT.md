# Phase 6 live audit and worker hosting feasibility

**Observed:** 2026-11-13 01:40–01:43 UTC (2026-11-12 17:40–17:43 PST).
**Target:** https://foundry-roan-nu.vercel.app . These results describe the deployed site, not the concurrently edited checkout. No deployment/version SHA was exposed or independently verified.

## Findings

1. **Live data functionality is blocked.** `/api/health` returns HTTP 503, `db:error`, `database_unavailable`. `/api/datasets` returns HTTP 400 `invalid_query` with `Python bridge unavailable: spawn python3 ENOENT`. The public catalog displays this internal implementation error and continues showing “Reading your workspace…” and skeleton cards. This is evidence that the deployed application is attempting its local Python bridge on Vercel; it is not evidence that a configured remote worker is reachable. Configure the supported authenticated remote worker before live end-to-end acceptance.
2. **Unknown dataset handling is obscured by the bridge failure.** `/datasets/phase6-unknown` renders a document with HTTP 200 and the same Python error; its dataset request returns 404. A genuine dataset-not-found state cannot be validated while the bridge is unavailable.
3. **Checkout is not verified live.** Public catalog copy says “checkout is not live.” Success/cancel pages render safe explanatory states, but there are no accessible live catalog results from which to start a purchase. No paid order, webhook, authorized download, real harvest, or QA run was exercised.

## Browser scope and evidence

Applied `build-web-apps:frontend-testing-debugging` and `cloud-environment:cloud-environment-runtime`. **Browser plugin not available**; used the repository's regular Playwright package with downloaded Chromium in `/tmp/phase6-browsers`. The first browser attempt failed on the environment's TLS inspection CA. The successful run trusted only the supplied proxy CA's exact SPKI hash through Chromium's certificate allowlist; HTTP probes retained inherited CA verification. No general `ignoreHTTPSErrors` or global certificate bypass was used.

Flow: anonymous entry → rendered login/public catalog → marketplace link, mobile navigation and filter submission → expected destination or explicit backend error. Tested Chromium at **1280×900, 768×900, 375×900**, fresh anonymous contexts. All 11 document routes below were checked at all three sizes (33 page navigations). Meaningful content and expected page titles rendered; no framework error overlay, page runtime exception, or horizontal document overflow was observed. This is a smoke audit, not a complete accessibility certification.

| Route | Observed result at all three widths |
| --- | --- |
| `/` | Redirects to `/login?next=%2F`; sign-in form renders. |
| `/login` | Public sign-in form; no console warnings/errors. No credentials submitted. |
| `/dashboard` | Redirects to `/login?next=%2Fdashboard`. |
| `/new` | Redirects to `/login?next=%2Fnew`; authenticated wizard inaccessible. |
| `/analytics` | Redirects to `/login?next=%2Fanalytics`; authenticated analytics inaccessible. |
| `/datasets` | Public shell/filter controls render; data fails as above. Console records HTTP 400 dataset and HTTP 503 health resource errors. |
| `/batches` | Redirects to `/login?next=%2Fbatches`. |
| `/datasets/phase6-unknown` | Public error document, HTTP 200; dataset request HTTP 404. |
| `/batches/phase6-unknown` | Redirects to `/login?next=%2Fbatches%2Fphase6-unknown`; missing-batch behavior behind login untested. |
| `/checkout/success` | “Check your test order”; explicitly states redirect is not payment proof; no download granted. No console errors. |
| `/checkout/cancel` | “Checkout cancelled”; explicitly says no download granted. No console errors. |

Interactions verified: “Browse the public marketplace” navigates `/login` → `/datasets` at every width. At 375 px, “Toggle navigation” opens the menu; Analytics navigates to the login redirect above. Entering `phase6 audit` and applying catalog filters updates URL to `/datasets?q=phase6+audit&sort=newest`; the backend error remains. Layout inspection: readable stacked controls and mobile header at 375 px; sidebar/two-column controls at 768 px; sidebar/wider filter grid at 1280 px. No clipping was observed in the inspected screenshots.

Raw evidence, screenshots and reproduction scripts are outside Git at `/tmp/phase6-live/`: `browser-results.json`, `http-results.json`, `interactions.json`, `navigation.json`, `audit.cjs`, `interactions.cjs`, `nav.cjs`. Representative screenshots: `1280-_datasets.png`, `768-_datasets.png`, `375-_login.png`, `375-menu.png`, `375-filter-error.png`. Temporary artifacts may expire with this environment.

## HTTP checks (anonymous GET)

| Endpoint | HTTP | Result |
| --- | --- | --- |
| `/api/v1` | 401 | `authentication_required`, dashboard sign-in message. This exact base path does not establish buyer API health. |
| `/api/v1/status` | 503 | `buyer_api_unavailable`; no buyer credentials supplied. |
| `/api/state` | 401 | `authentication_required`; admin state not disclosed. |
| `/api/auth/session` | 200 | `authenticated:false`. |
| `/api/health` | 503 | `db:error`, `database_unavailable`, version `0.1.0`. |
| `/api/datasets` | 400 | Missing Python executable exposed in `invalid_query` message. |
| `/robots.txt` | 200 | Allows catalog, excludes login/dashboard/new/batches/QA/analytics/API; points to correct-origin sitemap. |
| `/sitemap.xml` | 200 | Valid XML listing only the public `/datasets` URL; no dataset entries available. |

## Worker hosting: requirements and legitimate zero-cost paths

Existing supported configuration is `docker-compose.worker.yml`: a `worker-api` Docker target and `cli-worker`, one shared persistent `foundry-data:/data` volume, loopback port 8000 behind an HTTPS reverse proxy, restart policy, and scheduled CLI polling. `docs/DEPLOYMENT.md` recommends **at least 4 GB RAM and 20 GB free disk**, with additional disk for model weights, datasets, packages and backups. CPU inference, FFmpeg, PyTorch, transformers and sentence-transformers are installed; long jobs and SQLite/files must live on the authoritative durable host. Web requests must reach an authenticated HTTPS worker; do not use Vercel's ephemeral filesystem as that host. Vercel requires its private worker URL/key plus dashboard credentials/session secret; payment/provider keys stay on the worker. The download-signing key must also be durable and private.

**Existing usable free worker: none verified.** Runtime status reports no configured secrets, runtime variables or outbound identities, and the repository contains Compose files but no provisioned Render/Fly/Railway/OCI deployment manifest or host. Runtime metadata does not reveal Vercel project settings. No accounts, settings, services or resources were created or changed.

| Option | Verified official terms, fetched during this audit | Fit / cost conclusion |
| --- | --- | --- |
| Existing owner-controlled Linux machine | No such machine or authorized ingress was supplied. | Potentially **$0 incremental hosting fee** only if suitable existing hardware, durable storage, power/network and publicly reachable HTTPS already exist. Electricity, connectivity, storage and backups are not proven free. Current session workspace is not a verified permanent host. |
| Render Free web service | Official [Deploy for Free](https://render.com/docs/free): 750 instance-hours/workspace/month; sleeps after 15 minutes idle; local SQLite/uploads lost on restart/redeploy/spin-down; Free services cannot attach persistent disks. Documentation also identifies free compute as 0.1 CPU/512 MB. | Free service exists, but **does not meet this application's durable SQLite/files or 4 GB starting RAM requirements**. Do not deploy the current worker there as production storage. No paid price inferred. |
| Oracle Cloud Always Free A1 | Official [Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm): first **1,500 OCPU-hours and 9,000 GB-hours/month**, described there as **2 OCPU/12 GB**, with **200 GB combined boot/block storage** in home region. Capacity may be unavailable; idle resources may be reclaimed. [Free Tier](https://www.oracle.com/cloud/free/) requires eligibility and card/identity verification. | A potential **$0 provider compute/storage path within those allowances**, subject to capacity, eligibility and resource limits. **Not deploy-ready**: A1 is ARM, while Dockerfile pins `torch==2.9.1+cpu` from the CPU wheel index; ARM wheel/base/FFmpeg build compatibility has not been tested. Requires an owner account and provisioning; neither authorized nor performed. AMD micro's 1 GB RAM is below the documented starting recommendation. Do not promise older 4 OCPU/24 GB allowances. |
| Vercel Hobby | Official [Hobby plan](https://vercel.com/docs/plans/hobby) states the plan is free with usage limits. Actual deployed account plan and permitted use were not inspected. | Describes web hosting only; it does not establish a free, persistent Docker worker or authorize this project's billing/use. No upgrade or billing action performed. |

### Paid owner option: expected baseline hosting cost

Verified **2026-11-13 01:45 UTC** from Akamai/Linode’s official unauthenticated [instance-type API](https://api.linode.com/v4/linode/types/g6-standard-2), documented by [Get a Linode type](https://techdocs.akamai.com/linode-api/reference/get-linode-type): `g6-standard-2` (“Linode 4GB”, standard shared CPU) lists **US$24/month** or **US$0.036/hour**, **4,096 MB RAM, 2 vCPUs, 81,920 MB included disk and 4,000 GB included transfer**. This is a plausible paid x86 Linux/Docker starting host, subject to confirming the selected region’s availability and the actual instance architecture before ordering. The response explicitly quotes regional exceptions: Jakarta **US$28.80/month**, São Paulo **US$33.60/month**. Saved response: `/tmp/phase6-live/linode-type.json`.

**Expected baseline: US$24/month for one continuously allocated worker instance in a base-price region**, using its included disk. This excludes additional block/object storage, backups, transfer overages, tax, domain registration, Vercel charges, provider API usage, payment processing, and operational labor; it is not an all-in project quote. The API separately lists optional base-region backups at US$5/month; backups are excluded from the US$24 estimate. No account/region capacity, checkout tax, workload benchmark or final invoice was inspected. Shared CPU and 4 GB RAM meet only the repository’s initial recommendation; dataset/model storage growth and concurrent inference can require a larger host. No instance was provisioned and no billing/settings action was taken.

The fastest supported path is an **already available x86-64 Docker host meeting the documented capacity**, with durable `/data`, HTTPS and independent worker/download secrets. If none exists, hosting is an explicit infrastructure dependency; the free options above do not establish a provisioned, production-ready host. Domain, backup, provider/API usage and payment-processing charges are outside the verified free compute/storage allowances; no invented monthly total is quoted.

## Limits and acceptance status

Anonymous access controls and responsive shells pass the observed smoke checks. **Live data and full product acceptance are blocked.** No production admin credential was supplied, so dashboard/new-dataset/batch/QA/analytics workflows remain inaccessible. No password guessing, account creation, authentication bypass, production writes, Stripe charge, webhook replay, setting changes, provisioning, commit or push was performed. Local automated tests elsewhere in Phase 6 cannot substitute for the missing live authenticated run.
