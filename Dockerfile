# syntax=docker/dockerfile:1
FROM mwader/static-ffmpeg:8.0.1@sha256:252705ff88532fa338e7065c21792756552f8fe7c212f84bc503d3c340689594 AS ffmpeg-static

# Assemble a tiny payload separately so the Python base is copied only once.
FROM scratch AS cli-files
COPY --chmod=644 pyproject.toml /app/pyproject.toml
COPY --chmod=755 foundry/ /app/foundry/
COPY --chmod=644 web/bridge.py /app/web/bridge.py
COPY --chmod=755 scripts/worker.sh /usr/local/bin/foundry-worker
COPY --chmod=755 scripts/foundry-entrypoint.py /usr/local/bin/foundry
COPY --chmod=644 scripts/seed-demo.py /app/scripts/seed-demo.py
COPY --chmod=644 scripts/container-start.py /opt/foundry-start.py

FROM python:3.11-slim-bookworm AS cli
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app FOUNDRY_ROOT=/data
WORKDIR /app
COPY --from=cli-files --chmod=755 / /
# Full CPU inference dependencies; model weights are never downloaded during build.
RUN --mount=type=secret,id=proxy_ca \
    --mount=type=bind,from=ffmpeg-static,source=/ffmpeg,target=/tmp/foundry-ffmpeg \
    --mount=type=bind,from=ffmpeg-static,source=/ffprobe,target=/tmp/foundry-ffprobe \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    apt-get update && apt-get install -y --no-install-recommends ca-certificates libgomp1 xz-utils && \
    install -m755 /tmp/foundry-ffmpeg /usr/local/bin/ffmpeg && install -m755 /tmp/foundry-ffprobe /usr/local/bin/ffprobe && \
    ffmpeg -version >/dev/null && ffprobe -version >/dev/null && \
    pip install --no-compile 'torch==2.9.1+cpu' --index-url https://download.pytorch.org/whl/cpu && \
    python -c "import tomllib,subprocess,sys;p=tomllib.load(open('pyproject.toml','rb'));subprocess.check_call([sys.executable,'-m','pip','install','--no-compile',*p['project']['dependencies'],*p['project']['optional-dependencies']['monitor']])" && \
    find /usr/local/lib/python3.11/site-packages -type d -name tests -prune -exec rm -rf '{}' + && \
    find /usr/local/lib/python3.11/site-packages -type d -name __pycache__ -prune -exec rm -rf '{}' + && \
    rm -rf /var/lib/apt/lists/* && \
    python -c "import numpy,torch,imagehash; from sentence_transformers import SentenceTransformer; from transformers import CLIPModel,CLIPProcessor" && \
    mkdir -p /usr/local/lib/python3.11/site-packages/foundry-bin && \
    mv /usr/local/bin/ffmpeg /usr/local/bin/ffprobe /usr/local/lib/python3.11/site-packages/foundry-bin/ && \
    XZ_OPT="-T2 -3" tar -C /usr/local/lib/python3.11/site-packages -cJf /opt/foundry-python.tar.xz . && \
    rm -rf /usr/local/lib/python3.11/site-packages/* && \
    groupadd --gid 10001 foundry && useradd --uid 10001 --gid foundry --create-home foundry && \
    mkdir -p /data && chown foundry:foundry /data
ENV HF_HOME=/data/models
USER foundry
ENTRYPOINT ["python", "/opt/foundry-start.py"]
CMD ["foundry", "--help"]

FROM cli AS worker-api
ARG APP_VERSION=0.1.0
ENV APP_VERSION=$APP_VERSION
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s CMD python -c "import os,urllib.request;r=urllib.request.Request('http://127.0.0.1:8000/health',headers={'Authorization':'Bearer '+os.environ.get('FOUNDRY_WORKER_API_KEY','')});urllib.request.urlopen(r,timeout=8)" || exit 1
CMD ["python", "-m", "foundry.worker", "--host", "0.0.0.0", "--port", "8000"]

FROM node:22-bookworm-slim AS deps
RUN --mount=type=secret,id=proxy_ca \
    --mount=type=bind,source=web/package.json,target=/app/web/package.json \
    --mount=type=bind,source=web/package-lock.json,target=/app/web/package-lock.json \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    cd /app/web && npm ci --cache /tmp/npm-cache && rm -rf /tmp/npm-cache

FROM node:22-bookworm-slim AS builder
ENV NEXT_TELEMETRY_DISABLED=1
ARG APP_VERSION=0.1.0
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ENV APP_VERSION=$APP_VERSION NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
RUN --mount=type=bind,source=web,target=/tmp/foundry-web \
    --mount=type=bind,from=deps,source=/app/web/node_modules,target=/app/web/node_modules \
    cp -R /tmp/foundry-web/. /app/web/ && cd /app/web && npm run build && \
    du -sh .next/standalone && \
    mkdir -p /runtime/usr/local/bin && mv .next/standalone /runtime/app && \
    mv .next/static /runtime/app/web/.next/static && cp bridge.py /runtime/app/web/bridge.py && \
    cp /usr/local/bin/node /runtime/usr/local/bin/node && rm -rf .next

FROM scratch AS web-assets
COPY --from=builder /runtime/ /

FROM cli AS web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0 \
    FOUNDRY_ROOT=/data FOUNDRY_REPO=/app FOUNDRY_PYTHON=/usr/local/bin/python
COPY --from=web-assets --chown=foundry:foundry / /
ARG APP_VERSION=0.1.0
ENV APP_VERSION=$APP_VERSION
USER foundry
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:3000/api/health',timeout=8)" || exit 1
ENTRYPOINT ["python", "/opt/foundry-start.py"]
CMD ["node", "web/server.js"]
