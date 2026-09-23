# Stage 1: Build React frontend (static assets only — not in final Trivy scan)
FROM --platform=$BUILDPLATFORM node:24-trixie-slim@sha256:8ec5d7557396cfe32d21c3f9c13072355ceab22b584578ca4bb28af31120cffe AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY assets/icon /app/assets/icon
COPY frontend/ ./
RUN npm run build

# Stage 2: Python dependencies (Chainguard dev image — not in final runtime)
# Locked Python: 3.14.7-r0 (digest pinned 2026-08-11)
FROM cgr.dev/chainguard/python:latest-dev@sha256:0b39915a883dc2dbbe6c43be2ef82a37126409818cb66f5919e84cfa3e394ea5 AS python-builder
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
FROM cgr.dev/chainguard/python:latest-dev@sha256:0b39915a883dc2dbbe6c43be2ef82a37126409818cb66f5919e84cfa3e394ea5 AS runtime-assembler
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
# Locked Python: 3.14.7-r0 (digest pinned 2026-08-11)
FROM cgr.dev/chainguard/python:latest@sha256:46e5b974e33be50d512688480df92f0e258ea849a562d9e63b701f8b080ea660

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
