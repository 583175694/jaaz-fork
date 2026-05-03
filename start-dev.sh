#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=57988
FRONTEND_PORT=5174
PIDS=()

log() {
  printf '[start-dev] %s\n' "$*"
}

cleanup() {
  log 'stopping child processes...'
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "missing required command: $1"
    exit 1
  fi
}

kill_port_listener() {
  local port="$1"
  local pids

  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    log "stopping existing listeners on port $port"
    while IFS= read -r pid; do
      [ -n "$pid" ] || continue
      kill "$pid" >/dev/null 2>&1 || true
    done <<<"$pids"
    sleep 1
  fi
}

wait_for_http() {
  local url="$1"
  local name="$2"
  local retries="${3:-60}"
  local i
  local urls=("$url")

  if [ "$url" = "http://127.0.0.1:${FRONTEND_PORT}" ]; then
    urls=("http://127.0.0.1:${FRONTEND_PORT}" "http://localhost:${FRONTEND_PORT}" "http://[::1]:${FRONTEND_PORT}")
  fi

  for i in $(seq 1 "$retries"); do
    for candidate in "${urls[@]}"; do
      if curl -fsS "$candidate" >/dev/null 2>&1; then
        log "$name is ready: $candidate"
        return 0
      fi
    done
    sleep 1
  done

  log "$name failed to become ready: $url"
  exit 1
}

ensure_node_deps() {
  local dir="$1"
  local npm_args=("install")

  if [ "$dir" = "$ROOT_DIR/react" ]; then
    # This workspace still has a React 19 peer dependency conflict.
    npm_args=("install" "--force")
  fi

  if [ ! -d "$dir/node_modules" ]; then
    log "installing npm dependencies in $dir"
    (
      cd "$dir"
      npm "${npm_args[@]}"
    )
    return 0
  fi

  if ! (
    cd "$dir"
    npm ls --depth=0 >/dev/null 2>&1
  ); then
    log "repairing npm dependencies in $dir"
    (
      cd "$dir"
      npm "${npm_args[@]}"
    )
  fi
}

ensure_python_env() {
  if [ ! -d "$ROOT_DIR/.venv" ]; then
    log 'creating python virtual environment'
    python3 -m venv "$ROOT_DIR/.venv"
  fi

  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"

  if ! python -c 'import fastapi, uvicorn, socketio' >/dev/null 2>&1; then
    log 'installing python dependencies'
    pip install -r "$ROOT_DIR/server/requirements.txt"
  fi
}

start_backend() {
  kill_port_listener "$BACKEND_PORT"

  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/list_models" >/dev/null 2>&1; then
    log "backend already running on ${BACKEND_PORT}, reusing it"
    return 0
  fi

  log "starting backend on ${BACKEND_PORT}"
  (
    cd "$ROOT_DIR"
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.venv/bin/activate"
    python server/main.py --port "$BACKEND_PORT"
  ) &
  PIDS+=("$!")

  wait_for_http "http://127.0.0.1:${BACKEND_PORT}/api/list_models" 'backend'
}

start_frontend() {
  kill_port_listener "$FRONTEND_PORT"

  if curl -fsS "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null 2>&1; then
    log "frontend already running on ${FRONTEND_PORT}, reusing it"
    return 0
  fi

  log "starting frontend on ${FRONTEND_PORT}"
  (
    cd "$ROOT_DIR/react"
    npm run dev
  ) &
  PIDS+=("$!")

  wait_for_http "http://127.0.0.1:${FRONTEND_PORT}" 'frontend'
}

start_electron() {
  log 'starting electron'
  (
    cd "$ROOT_DIR"
    npm run dev:electron
  ) &
  PIDS+=("$!")
}

main() {
  cd "$ROOT_DIR"

  require_cmd npm
  require_cmd python3
  require_cmd curl

  ensure_node_deps "$ROOT_DIR"
  ensure_node_deps "$ROOT_DIR/react"
  ensure_python_env

  start_backend
  start_frontend
  start_electron

  log 'all services started'
  log 'press Ctrl+C to stop everything'

  wait
}

main "$@"
