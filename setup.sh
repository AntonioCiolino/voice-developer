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
# generated-app/ is the current app, with its own git repo, and is not part of this repo.
# A fresh clone starts it from app-template/ (the blank app New App also resets to).
if [ ! -d "$ROOT/generated-app" ]; then
  cp -R "$ROOT/app-template" "$ROOT/generated-app"
  git -C "$ROOT/generated-app" init -q
  git -C "$ROOT/generated-app" add -A
  git -C "$ROOT/generated-app" commit -q -m "New app" \
    || echo "Created generated-app/ but could not commit it (set git user.name and user.email)."
  echo "Created generated-app/ from app-template/."
fi
npm install --prefix "$ROOT/generated-app"
# ESLint for post-task validation lives here, not in the generated app.
npm install --prefix "$ROOT/controller/lint-tools"
echo "Setup complete. Run ./start.sh after configuring controller/.env."
