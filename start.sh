#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
CONTROLLER="$ROOT/controller"
APP="$ROOT/generated-app"
PID_FILE="$ROOT/.voice-developer.pids"
export VOICE_DEVELOPER_HOST="${VOICE_DEVELOPER_HOST:-127.0.0.1}"

if [ ! -f "$CONTROLLER/.env" ] || [ ! -x "$CONTROLLER/venv/bin/uvicorn" ] || [ ! -d "$APP/node_modules" ]; then
  echo "Run ./setup.sh and configure controller/.env first."
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
