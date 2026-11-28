# Stage 1: Build React frontend (static assets only — not in final Trivy scan)
FROM --platform=$BUILDPLATFORM node:24-trixie-slim@sha256:4d00acb4bcc42c454c4eb801526f7ad7f772ea3bd4fd168c5cc2e384abcbb9d4 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY assets/icon /app/assets/icon
COPY frontend/ ./
RUN npm run build

# Stage 2: Python dependencies (Chainguard dev image — not in final runtime)
# Tag+digest required so Renovate can follow :latest-dev. Digest bump 2026-09-23
# (Python 3.14.7_git20260918-r0).
FROM cgr.dev/chainguard/python:latest-dev@sha256:a940d25c3807f523fc5b9bd6e9af0b95f04483d60c7434cd365cdb6fece39cd5 AS python-builder
USER root
WORKDIR /app
RUN apk add --no-cache gosu
COPY requirements.txt .
# Install app deps, then strip pip/setuptools/wheel so the runtime venv has no
# packaging toolchain (shrinks image + drops Trivy python-pkg findings from
# pip's vendored msgpack and ensurepip's setuptools).
RUN python -m venv /app/venv \
    && /app/venv/bin/pip install --upgrade pip \
    && /app/venv/bin/pip install --no-cache-dir -r requirements.txt \
    && /app/venv/bin/pip uninstall -y pip setuptools wheel \
    && find /app/venv -type d -name '__pycache__' -exec rm -rf {} + \
    && find /app/venv -type f -name '*.pyc' -delete \
    && rm -rf /root/.cache/pip

# Stage 3: Assemble runtime tree (dev image — shell/apk for mkdir/chown only)
FROM cgr.dev/chainguard/python:latest-dev@sha256:a940d25c3807f523fc5b9bd6e9af0b95f04483d60c7434cd365cdb6fece39cd5 AS runtime-assembler
USER root
WORKDIR /app

COPY --from=python-builder /app/venv /app/venv
COPY --from=python-builder /usr/bin/gosu /usr/bin/gosu
# Explicit app paths only — keep frontend source, icons, tooling out of runtime
COPY __version__.py run_fastapi.py cache_manager.py ./
COPY app/ ./app/
COPY clients/ ./clients/
COPY commands/ ./commands/
COPY database/ ./database/
COPY docker/ ./docker/
COPY services/ ./services/
COPY utils/ ./utils/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/data/logs && chown -R 1000:1000 /app/data

# Stage 4: Distroless Wolfi runtime (COPY only — no RUN)
# Tag+digest required so Renovate can follow :latest. Digest bump 2026-09-23
# (Python 3.14.7_git20260918-r0).
FROM cgr.dev/chainguard/python:latest@sha256:f166d50e3c50e03e7648641203735fabb68d9f762e6739a15d4e2bde4ae2f24f

ARG IMAGE_TAG=latest
ENV CMDARR_IMAGE_TAG=${IMAGE_TAG}

USER root
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/venv/bin:$PATH" \
    PUID=1000 \
    PGID=1000 \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8080 \
    LOG_LEVEL=INFO \
    LOG_RETENTION_DAYS=7

COPY --from=runtime-assembler /app /app
COPY --from=runtime-assembler /usr/bin/gosu /usr/bin/gosu

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["python", "/app/docker/healthcheck.py"]

ENTRYPOINT ["python", "/app/docker/entrypoint.py"]
CMD ["python", "run_fastapi.py"]
