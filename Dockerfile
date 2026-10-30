# syntax=docker/dockerfile:1
# Daftar: one container – FastAPI serves the API, the landing site and the SPA (port 8080).
# Optional: trust an extra root CA during the build (TLS-inspecting proxy / antivirus):
#   docker build --secret id=extra_ca,src=ca.pem .   (docker-compose.override.yml does this locally)

# --- SvelteKit app ---
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca; fi; \
    npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- Python runtime ---
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANDING_DIR=/app/landing \
    WEB_DIR=/app/web \
    PORT=8080
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /tmp/ca.pem; export PIP_CERT=/tmp/ca.pem; \
    fi; \
    pip install -r requirements.txt && rm -f /tmp/ca.pem
RUN useradd --system --uid 10001 --home-dir /app --no-create-home daftar
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/daftar ./daftar
COPY landing/ /app/landing/
COPY --from=web /web/build/ /app/web/
USER daftar
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status == 200 else 1)"
# Migrations first (idempotent), then the server; exec so that signals reach Python.
CMD ["sh", "-c", "alembic upgrade head && exec python -m daftar"]
