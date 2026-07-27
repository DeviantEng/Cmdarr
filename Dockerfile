# Stage 1: Build React frontend (static assets only — not in final Trivy scan)
FROM --platform=$BUILDPLATFORM node:24-trixie-slim@sha256:4f2b45e32dc7d2caf66b6dbd59fac50e32f8077769efe0ef4d4c3f114672537d AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY assets/icon /app/assets/icon
COPY frontend/ ./
RUN npm run build

# Stage 2: Python dependencies (Chainguard dev image — not in final runtime)
# Locked Python: 3.14.6-r4 (digest pinned 2026-07-27; fixes CVE-2026-15308)
FROM cgr.dev/chainguard/python@sha256:7a568bcee42666f73f041645a41c913ce1d442f4c24cf6019bc543a90820e531 AS python-builder
USER root
WORKDIR /app
RUN apk add --no-cache gosu
COPY requirements.txt .
RUN python -m venv /app/venv \
    && /app/venv/bin/pip install --upgrade pip \
    && /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 3: Assemble runtime tree (dev image — shell/apk for mkdir/chown only)
FROM cgr.dev/chainguard/python@sha256:7a568bcee42666f73f041645a41c913ce1d442f4c24cf6019bc543a90820e531 AS runtime-assembler
USER root
WORKDIR /app

COPY --from=python-builder /app/venv /app/venv
COPY --from=python-builder /usr/bin/gosu /usr/bin/gosu
COPY requirements.txt .
COPY . .
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
COPY docker/entrypoint.py /app/docker/entrypoint.py

RUN mkdir -p /app/data/logs && chown -R 1000:1000 /app/data

# Stage 4: Distroless Wolfi runtime (COPY only — no RUN)
# Locked Python: 3.14.6-r4 (digest pinned 2026-07-27; fixes CVE-2026-15308)
FROM cgr.dev/chainguard/python@sha256:a0365f7b90bf7b78a5e35f2709efb7c9263acf9c7b1905e0ec4c3e943c88e64d

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
