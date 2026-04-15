#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.streamlit/adforge-app.pid"
LOG_FILE="$ROOT_DIR/.streamlit/adforge-app.log"
PORT="${PORT:-8501}"
APP_PATTERN="streamlit run src/app.py"

mkdir -p "$(dirname "$PID_FILE")"

pick_runner() {
  if [[ -x "$ROOT_DIR/.venv/bin/streamlit" ]]; then
    echo "$ROOT_DIR/.venv/bin/streamlit"
    return 0
  fi

  if command -v streamlit >/dev/null 2>&1; then
    echo "streamlit"
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    echo "uv run streamlit"
    return 0
  fi

  echo "No streamlit runner found. Install dependencies first." >&2
  exit 1
}

read_pid() {
  if [[ -f "$PID_FILE" ]]; then
    cat "$PID_FILE"
  fi
}

pid_is_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

find_port_pid() {
  lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

status() {
  local pid
  pid="$(read_pid)"

  if pid_is_running "$pid"; then
    echo "running pid=$pid port=$PORT log=$LOG_FILE"
    return 0
  fi

  pid="$(find_port_pid)"
  if [[ -n "$pid" ]]; then
    echo "running pid=$pid port=$PORT (pid file stale) log=$LOG_FILE"
    return 0
  fi

  echo "stopped"
}

start() {
  local existing_pid
  existing_pid="$(read_pid)"
  if pid_is_running "$existing_pid"; then
    echo "App already running: pid=$existing_pid port=$PORT"
    return 0
  fi

  existing_pid="$(find_port_pid)"
  if [[ -n "$existing_pid" ]]; then
    echo "Port $PORT already in use by pid=$existing_pid"
    return 1
  fi

  local runner
  runner="$(pick_runner)"

  (
    cd "$ROOT_DIR"
    nohup bash -lc "$runner run src/app.py --server.headless true --server.port $PORT" \
      >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  )

  sleep 2

  local pid
  pid="$(read_pid)"
  if pid_is_running "$pid"; then
    echo "Started app: pid=$pid port=$PORT"
    echo "Log: $LOG_FILE"
    return 0
  fi

  echo "App failed to start. Check log: $LOG_FILE" >&2
  return 1
}

stop() {
  local pid
  pid="$(read_pid)"

  if pid_is_running "$pid"; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if pid_is_running "$pid"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "Stopped app pid=$pid"
    return 0
  fi

  pid="$(find_port_pid)"
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "Stopped app pid=$pid"
    return 0
  fi

  rm -f "$PID_FILE"
  echo "App already stopped"
}

restart() {
  stop
  start
}

usage() {
  echo "Usage: $0 {start|stop|restart|status}"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  *)
    usage
    exit 1
    ;;
esac
