#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
CONTROLLER="$ROOT/controller"

if [ ! -f "$CONTROLLER/.env" ]; then
  cp "$CONTROLLER/.env.example" "$CONTROLLER/.env"
  echo "Created controller/.env. Fill in your credentials before starting."
fi

python3 -m venv "$CONTROLLER/venv"
"$CONTROLLER/venv/bin/python" -m pip install -r "$CONTROLLER/requirements.txt"
# Aider gets its own environment: its dependencies would otherwise replace the
# controller's pinned FastAPI/Pydantic/OpenAI versions.
python3 -m venv "$CONTROLLER/aider-venv"
"$CONTROLLER/aider-venv/bin/python" -m pip install "aider-chat==0.86.2"
npm install --prefix "$ROOT/generated-app"
echo "Setup complete. Run ./start.sh after configuring controller/.env."
