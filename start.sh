#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
CONTROLLER="$ROOT/controller"
APP="$ROOT/generated-app"
PID_FILE="$ROOT/.voice-developer.pids"

# A private IPv4 address (10.x, 172.16-31.x, 192.168.x): the only non-loopback host LAN mode accepts.
is_private_ipv4() {
  [[ "$1" =~ ^(10\.[0-9]+\.[0-9]+\.[0-9]+|192\.168\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+)$ ]]
}

# This Mac's current private LAN address, from the first network interface that has one.
# DHCP can change it, so it is read at every start instead of being written down.
detect_lan_host() {
  local iface addr
  for iface in en0 en1 en2 en3 en4 en5; do
    addr="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    if is_private_ipv4 "$addr"; then
      echo "$addr"
      return 0
    fi
  done
  return 1
}

if [ "${1:-}" = "--detect-host" ]; then
  detect_lan_host || { echo "No private LAN address found on en0-en5." >&2; exit 1; }
  exit 0
fi

# LAN mode with no host given (or "auto") listens on the detected LAN address.
if [ "${VOICE_DEVELOPER_LOCAL_AUTH_LAN:-}" = "1" ] && { [ -z "${VOICE_DEVELOPER_HOST:-}" ] || [ "$VOICE_DEVELOPER_HOST" = "auto" ]; }; then
  if ! VOICE_DEVELOPER_HOST="$(detect_lan_host)"; then
    echo "VOICE_DEVELOPER_LOCAL_AUTH_LAN=1 could not find this Mac's private LAN address on en0-en5 (is Wi-Fi connected?). Set VOICE_DEVELOPER_HOST yourself."
    exit 1
  fi
fi
export VOICE_DEVELOPER_HOST="${VOICE_DEVELOPER_HOST:-127.0.0.1}"

if [ "${VOICE_DEVELOPER_LOCAL_AUTH_LAN:-}" = "1" ] && ! is_private_ipv4 "$VOICE_DEVELOPER_HOST"; then
  echo "VOICE_DEVELOPER_LOCAL_AUTH_LAN=1 requires VOICE_DEVELOPER_HOST to be this Mac's private LAN address (10.x, 172.16-31.x or 192.168.x). Find it with: ipconfig getifaddr en0"
  exit 1
fi

if [ ! -f "$CONTROLLER/.env" ] || [ ! -x "$CONTROLLER/venv/bin/uvicorn" ] || [ ! -d "$APP/node_modules" ]; then
  echo "Run ./setup.sh and configure controller/.env first."
  exit 1
fi

if is_private_ipv4 "$VOICE_DEVELOPER_HOST" \
  && [ "${VOICE_DEVELOPER_LOCAL_AUTH_LAN:-}" != "1" ] \
  && grep -Eq '^[[:space:]]*VOICE_DEVELOPER_LOCAL_AUTH[[:space:]]*=[[:space:]]*1[[:space:]]*$' "$CONTROLLER/.env"; then
  echo "LAN local authentication requires VOICE_DEVELOPER_LOCAL_AUTH_LAN=1."
  exit 1
fi

source "$CONTROLLER/venv/bin/activate"

(cd "$APP" && exec node "$APP/node_modules/vite/bin/vite.js") &
VITE_PID=$!
cleanup() {
  kill "$VITE_PID" ${API_PID:+"$API_PID"} 2>/dev/null || true
  rm -f "$PID_FILE"
}
trap cleanup EXIT
trap 'exit 0' INT TERM

uvicorn main:app --host "$VOICE_DEVELOPER_HOST" --port 8040 --app-dir "$CONTROLLER" &
API_PID=$!
printf 'VITE_PID=%s\nAPI_PID=%s\n' "$VITE_PID" "$API_PID" > "$PID_FILE"

echo "Controller: http://$VOICE_DEVELOPER_HOST:8040"
echo "Preview:    http://$VOICE_DEVELOPER_HOST:5773"
echo "Press Ctrl+C to stop."
wait "$API_PID"
