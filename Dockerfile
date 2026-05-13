# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS frontend-builder

ARG NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
ENV npm_config_registry=${NPM_CONFIG_REGISTRY}

WORKDIR /app/react

COPY react/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --force

COPY react/ ./
ARG VITE_JAAZ_BASE_API_URL
ENV VITE_JAAZ_BASE_API_URL=${VITE_JAAZ_BASE_API_URL}
RUN npx vite build

FROM python:3.12-slim AS runtime

ARG DEBIAN_MIRROR=https://mirrors.aliyun.com/debian
ARG DEBIAN_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST} \
    HOST=0.0.0.0 \
    PORT=57988 \
    USER_DATA_DIR=/data \
    CONFIG_PATH=/data/config.toml \
    UI_DIST_DIR=/app/react/dist \
    DEFAULT_PORT=57988

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    set -eux; \
    printf 'deb %s trixie main\n' "$DEBIAN_MIRROR" > /etc/apt/sources.list; \
    printf 'deb %s trixie-updates main\n' "$DEBIAN_MIRROR" >> /etc/apt/sources.list; \
    printf 'deb %s trixie-security main\n' "$DEBIAN_SECURITY_MIRROR" >> /etc/apt/sources.list; \
    rm -f /etc/apt/sources.list.d/debian.sources; \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libmediainfo0v5

COPY server/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt

COPY server/ /app/server/
COPY --from=frontend-builder /app/react/dist/ /app/react/dist/

VOLUME ["/data"]
EXPOSE 57988

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/list_models" >/dev/null || exit 1

CMD ["sh", "-c", "python server/main.py --host \"$HOST\" --port \"$PORT\""]
