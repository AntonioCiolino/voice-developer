#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
CONTROLLER="$ROOT/controller"
APP="$ROOT/generated-app"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RESET='\033[0m'

echo -e "${CYAN}voice-developer${RESET}"
echo "---"

# --- Local IP ---
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
echo -e "Local IP: ${GREEN}$LOCAL_IP${RESET}"
echo -e "Controller:  ${GREEN}http://$LOCAL_IP:8040${RESET}"
echo -e "App (phone): ${GREEN}http://$LOCAL_IP:5773${RESET}"
echo "---"

# --- Controller deps check ---
if [ ! -d "$CONTROLLER/venv" ]; then
  echo "Setting up Python venv..."
  python3 -m venv "$CONTROLLER/venv"
fi
source "$CONTROLLER/venv/bin/activate"

echo "Installing controller dependencies..."
pip install -q -r "$CONTROLLER/requirements.txt"

if [ ! -f "$CONTROLLER/.env" ]; then
  echo "❌ ERROR: $CONTROLLER/.env not found"
  echo "Create it with your ANTHROPIC_API_KEY:"
  echo "  echo 'ANTHROPIC_API_KEY=sk-ant-...' > controller/.env"
  exit 1
fi

# Check aider is available
if ! command -v aider &> /dev/null; then
  echo "❌ ERROR: aider not found"
  echo "Install it with: pip install aider-chat"
  exit 1
fi

# --- App deps check ---
if [ ! -d "$APP/node_modules" ]; then
  echo "Installing npm dependencies..."
  npm install --prefix "$APP"
fi

# --- Start services ---
echo ""
echo "Starting services..."

# Vite in background
npm run dev --prefix "$APP" &
VITE_PID=$!

# FastAPI in foreground
uvicorn main:app --host 0.0.0.0 --port 8040 --reload --app-dir "$CONTROLLER" &
API_PID=$!

# Trap Ctrl+C to kill both
trap "kill $VITE_PID $API_PID 2>/dev/null; exit 0" INT TERM

echo "Controller PID: $API_PID  |  Vite PID: $VITE_PID"
echo "Press Ctrl+C to stop."
wait
