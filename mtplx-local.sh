#!/usr/bin/env bash
# Run MTPLX on this Mac from the command line, with the same kind of settings as the Mac mini
# but sized for 16 GB. Listens on 127.0.0.1:8000 only (no API key needed on loopback), which is
# the "mtplx" model server in controller/.env. Stop the MTPLX app's own server first: both use port 8000.
#
#   ./mtplx-local.sh            start in this terminal (Ctrl-C stops it)
#   MTPLX_CONTEXT=32768 ./mtplx-local.sh   override any setting below the same way
set -euo pipefail

MTPLX="${MTPLX_BIN:-$HOME/Library/Application Support/MTPLX/runtime-venv/bin/mtplx}"
MODEL="${MTPLX_MODEL:-$HOME/.mtplx/models/Youssofal--Qwen3.5-4B-MTPLX-Optimized-Speed}"
PORT="${MTPLX_PORT:-8000}"
CONTEXT="${MTPLX_CONTEXT:-16384}"        # mini: 12288. Room for whole-file App.jsx edits.
PREFILL_CHUNK="${MTPLX_PREFILL_CHUNK:-512}" # mini: 64. Bigger chunks read prompts faster.
KV_QUANT="${MTPLX_KV_QUANT:-q8}"         # mini: q4. q8 is closer to full quality.

if [[ ! -x "$MTPLX" ]]; then
  echo "MTPLX command not found at: $MTPLX (is the MTPLX app installed?)" >&2
  exit 1
fi
if [[ ! -d "$MODEL" ]]; then
  echo "Model folder not found: $MODEL" >&2
  exit 1
fi
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Something is already listening on port $PORT (probably the MTPLX app's server). Stop it first." >&2
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >&2 || true
  exit 1
fi

# No --memory-limit max: this Mac runs a desktop and Kiro, so MTPLX keeps its default 75% cap.
exec "$MTPLX" serve \
  --model "$MODEL" \
  --host 127.0.0.1 --port "$PORT" \
  --reasoning off \
  --prefill-chunk-tokens "$PREFILL_CHUNK" \
  --paged-kv-quantization "$KV_QUANT" \
  --context-window "$CONTEXT" \
  --allow-swap
