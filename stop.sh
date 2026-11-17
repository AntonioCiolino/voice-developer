#!/usr/bin/env bash

ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT/.voice-developer.pids"

if [ ! -f "$PID_FILE" ]; then
  echo "Voice Developer is not running (no PID file)."
  exit 0
fi

VITE_PID=""
API_PID=""
while IFS='=' read -r name pid; do
  case "$name" in
    VITE_PID) VITE_PID="$pid" ;;
    API_PID) API_PID="$pid" ;;
  esac
done < "$PID_FILE"

stop_pid() {
  label="$1"
  pid="$2"

  case "$pid" in
    ''|*[!0-9]*)
      echo "Skipping $label: invalid PID in $PID_FILE."
      return
      ;;
  esac

  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  case "$command_line" in
    *"$ROOT"*) ;;
    *)
      echo "Skipping $label: PID $pid is not a Voice Developer process."
      return
      ;;
  esac

  echo "Stopping $label (PID $pid)..."
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "$label stopped."
      return
    fi
    sleep 0.1
done

  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  case "$command_line" in
    *"$ROOT"*)
      echo "$label did not stop after 1 second; sending SIGKILL."
      kill -KILL "$pid" 2>/dev/null || true
      ;;
    *)
      echo "$label stopped."
      ;;
  esac
}

stop_pid "Vite preview" "$VITE_PID"
stop_pid "controller" "$API_PID"
rm -f "$PID_FILE"
