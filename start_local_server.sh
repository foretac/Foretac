#!/usr/bin/env bash

set -euo pipefail

WEB_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${FORETAC_PYTHON:-python3}"
BIND_ADDR="${FORETAC_BIND:-0.0.0.0}"
PORT_NUMBER="${FORETAC_PORT:-8125}"
PID_FILE="${FORETAC_PID_FILE:-/tmp/foretac-web-${PORT_NUMBER}.pid}"
LOG_FILE="${FORETAC_LOG_FILE:-/tmp/foretac-web-${PORT_NUMBER}.log}"

server_cmd=(
  "$PYTHON_BIN"
  "$WEB_ROOT/tools/serve_range_http.py"
  --directory "$WEB_ROOT"
  --bind "$BIND_ADDR"
  --port "$PORT_NUMBER"
)

lan_address="$(hostname -I 2>/dev/null | awk '{print $1}')"
print_urls() {
  printf 'ForeTac local preview: http://127.0.0.1:%s/\n' "$PORT_NUMBER"
  if [[ -n "$lan_address" ]]; then
    printf 'ForeTac LAN preview:   http://%s:%s/\n' "$lan_address" "$PORT_NUMBER"
  fi
}

is_running() {
  [[ -s "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

case "${1:-}" in
  --status)
    if is_running; then
      printf 'ForeTac preview is running (PID %s).\n' "$(cat "$PID_FILE")"
      print_urls
    else
      printf 'ForeTac preview is not running on port %s.\n' "$PORT_NUMBER"
      exit 1
    fi
    ;;
  --stop)
    if is_running; then
      pid="$(cat "$PID_FILE")"
      kill "$pid"
      rm -f "$PID_FILE"
      printf 'Stopped ForeTac preview (PID %s).\n' "$pid"
    else
      rm -f "$PID_FILE"
      printf 'No managed ForeTac preview is running.\n'
    fi
    ;;
  --background)
    if is_running; then
      printf 'ForeTac preview is already running (PID %s).\n' "$(cat "$PID_FILE")"
      print_urls
      exit 0
    fi
    rm -f "$PID_FILE"
    nohup setsid "${server_cmd[@]}" >"$LOG_FILE" 2>&1 < /dev/null &
    server_pid=$!
    printf '%s\n' "$server_pid" >"$PID_FILE"
    sleep 0.2
    if ! kill -0 "$server_pid" 2>/dev/null; then
      printf 'Failed to start ForeTac preview. Log:\n' >&2
      cat "$LOG_FILE" >&2 || true
      rm -f "$PID_FILE"
      exit 1
    fi
    printf 'Started ForeTac preview in background (PID %s).\n' "$server_pid"
    printf 'Log: %s\n' "$LOG_FILE"
    print_urls
    ;;
  "")
    print_urls
    exec "${server_cmd[@]}"
    ;;
  *)
    printf 'Usage: %s [--background|--status|--stop]\n' "$0" >&2
    exit 2
    ;;
esac
