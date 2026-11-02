# syntax=docker/dockerfile:1
#
# WildfireGuardian: two images from one file. Guide: docs/solve2027/REPRODUCE.md
#
#   target "api"      Route-Check API (api/): Python 3.12, GNU time + procps, ./integration[packets] + API dependencies,
#                     and the recorded routing inputs downloaded and SHA-256-verified while the image is built.
#   target "planner"  The planner's static production build (planner/), served by nginx, with the same-origin
#                     /api/v1/* calls proxied to the API exactly as `npm run dev` / `npm run preview` do.
#
#   docker compose up --build        planner http://127.0.0.1:8080 · API http://127.0.0.1:8765/v1 (Swagger UI /docs)
#
# Nothing here changes the frozen kit, its thresholds or the API's fixed 30 s request budget (api/config.py BUDGET_S).
# A container is not the evaluated host (native macOS, Apple M5 Pro): heavy missions can end unresolved/TIMEOUT. Every
# API result records its compute host in its provenance, and the planner shows that host next to each compute time.

ARG PYTHON_IMAGE=python:3.12.14-slim-bookworm
ARG NODE_IMAGE=node:22.23.4-bookworm-slim
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.30.6-alpine

# ===================================================================================== Route-Check API (target: api)
FROM ${PYTHON_IMAGE} AS api

# Commit recorded in API provenance (the image has no .git): docker compose build passes WFG_GIT_COMMIT.
ARG WFG_GIT_COMMIT=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WFG_API_HOST=0.0.0.0 \
    WFG_API_PORT=8765 \
    WFG_API_GIT_COMMIT=${WFG_GIT_COMMIT}

# GNU time (/usr/bin/time -v) and procps (/bin/ps): the frozen kit controller launches and measures every request
# with them. Debian security updates move these package versions, so they are not pinned.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends time procps \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pinned routing packages (numpy 1.26.4, pyproj 3.7.0) and API dependencies, installed as in api/README.md.
COPY constraints-routing.txt ./
COPY api/requirements.txt api/
COPY integration/ integration/
RUN python -m pip install -c constraints-routing.txt './integration[packets]' -r api/requirements.txt

# Recorded routing inputs (research release research-final-20261015): the fetch tool checks the archive SHA-256 and
# every file's SHA-256 and extracts nothing on a mismatch, which fails this build.
COPY tools/fetch_routing_inputs.py tools/
RUN python tools/fetch_routing_inputs.py

# The API reads the kit (integration/), contract, release identity and the ablation study files (research/routing/).
# tests/api, the smoke script and the Solve 2027 reproduction script are included so they can run in the container.
COPY api/ api/
COPY contracts/ contracts/
COPY docs/RELEASE_IDENTITY.json docs/
COPY research/routing/ research/routing/
COPY tests/__init__.py tests/
COPY tests/api/ tests/api/
COPY scripts/api_smoke.sh scripts/
COPY docs/solve2027/reproduce/ docs/solve2027/reproduce/

# Run as an unprivileged user; only the runtime folder (job records, per-request packets) is writable.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin wfg \
 && mkdir -p /app/artifacts/api_runtime \
 && chown -R wfg:wfg /app/artifacts
USER 10001:10001

EXPOSE 8765
# Healthy only when the recorded regions are loaded and GNU time + ps are present (/v1/health status "ok").
HEALTHCHECK --interval=15s --timeout=10s --start-period=60s --retries=5 \
  CMD ["python", "-c", "import json,sys,urllib.request as u; o=u.build_opener(u.ProxyHandler({})); h=json.load(o.open('http://127.0.0.1:8765/v1/health', timeout=8)); sys.exit(0 if h.get('status') == 'ok' else 1)"]
CMD ["python", "-m", "api"]

# ============================================================================== planner static build (internal stage)
FROM ${NODE_IMAGE} AS planner-build
# Node's heap is capped for the build (2048 MB by default); raise NODE_MAX_OLD_SPACE_MB if a build runs out of memory.
ARG NODE_MAX_OLD_SPACE_MB=2048
ENV NODE_OPTIONS=--max-old-space-size=${NODE_MAX_OLD_SPACE_MB} \
    VITE_WFG_API_MODE=real \
    npm_config_audit=false \
    npm_config_fund=false \
    npm_config_update_notifier=false
WORKDIR /src/planner
COPY planner/package.json planner/package-lock.json ./
RUN npm ci
COPY planner/ ./
# `npm run build` = `tsc -b` (app, config and ../tests/planner) + `vite build`, which also copies planner/cache into
# dist/cache (the recorded results computed on the evaluated host; never its .state working folder).
COPY tests/planner/ /src/tests/planner/
RUN npm run build

# ============================================================================== planner web server (target: planner)
FROM ${NGINX_IMAGE} AS planner
# Upstream for /api/v1/* (host:port). nginx resolves it at request time, so the static app keeps working while the
# API is starting or absent. NGINX_ENTRYPOINT_LOCAL_RESOLVERS makes the image's entrypoint export the container's
# nameservers from /etc/resolv.conf as NGINX_LOCAL_RESOLVERS (Docker's embedded DNS on compose networks).
ENV WFG_API_UPSTREAM=api:8765 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
COPY --from=planner-build /src/planner/dist/ /usr/share/nginx/html/
# The nginx image renders /etc/nginx/templates/*.template with envsubst at start-up. Only defined environment
# variables are replaced (${WFG_API_UPSTREAM}, ${NGINX_LOCAL_RESOLVERS}); nginx's own $variables are left untouched.
COPY <<"NGINX" /etc/nginx/templates/default.conf.template
# WildfireGuardian planner: static build + same-origin proxy of /api/v1/* to the Route-Check API (/v1/*).
server {
    listen 8080;
    server_name _;
    server_tokens off;
    absolute_redirect off;
    # One page (state lives in the query string and hash): missing files are plain 404s, never the app.
    root /usr/share/nginx/html;
    index index.html;
    # Dispatch plans and drawn spread zones are JSON request bodies.
    client_max_body_size 16m;

    # The app always calls /api/v1/*; planner/vite.config.ts maps it to <API>/v1/* the same way.
    location ^~ /api/v1/ {
        resolver ${NGINX_LOCAL_RESOLVERS} valid=10s ipv6=off;
        set $wfg_api_upstream ${WFG_API_UPSTREAM};
        rewrite ^/api(/v1/.*)$ $1 break;
        proxy_pass http://$wfg_api_upstream;
        proxy_http_version 1.1;
        proxy_read_timeout 300s;
    }

    # Precomputed results copied into dist/cache by the build (served like planner/vite.config.ts does).
    location /cache/ {
        add_header Cache-Control "no-cache" always;
    }

    # Never serve hidden files or folders.
    location ~ /\. {
        return 404;
    }
}
NGINX

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD ["/bin/sh", "-c", "wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1"]
