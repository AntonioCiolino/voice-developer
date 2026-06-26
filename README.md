# voice-developer

Speak a desire. The app rewrites itself.

```
Phone (voice → text)
     ↓
Controller (FastAPI) receives the prompt
     ↓
Claude API generates new App.jsx
     ↓
Vite HMR detects the file change
     ↓
Phone refreshes — new app is live
```

---

## Structure

```
voice-developer/
├── controller/          # FastAPI — receives prompts, calls Claude, writes App.jsx
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── generated-app/       # Vite + React — the app that gets rewritten live
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       └── App.jsx      # ← this file gets overwritten on each generation
├── worker/              # Background task runner — npm installs, git ops, etc.
│   └── worker.py
├── start.sh             # Starts everything (controller + vite dev server)
└── README.md
```

---

## Ports

| Service    | Port   | Purpose                        |
|------------|--------|--------------------------------|
| Controller | `8000` | Receives POST /generate        |
| Vite app   | `5173` | The live app (LAN accessible)  |

Both are bound to `0.0.0.0` — accessible from any device on your local network.

---

## Setup

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/voice-developer.git
cd voice-developer
```

### 2. Controller

```bash
cd controller
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

### 3. Generated App

```bash
cd generated-app
npm install
```

### 4. Start everything

```bash
chmod +x start.sh
./start.sh
```

This starts:
- FastAPI controller on `http://0.0.0.0:8000`
- Vite dev server on `http://0.0.0.0:5173`

---

## Usage

### Send a prompt from your phone (or anywhere)

```bash
curl -X POST http://YOUR_LOCAL_IP:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a red button that counts clicks"}'
```

Or use a voice-to-text app that POSTs to the same endpoint.

### Watch the app update live

Open `http://YOUR_LOCAL_IP:5173` on your phone. It auto-refreshes via Vite HMR.

---

## API

### `POST /generate`

Generate a new version of the app.

**Body:**
```json
{
  "prompt": "a dark mode toggle with a smooth animation",
  "history": []
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "App updated successfully"
}
```

### `GET /status`

Health check.

```json
{ "status": "running" }
```

### `GET /app`

Returns the current App.jsx source code.

---

## How it works

1. You speak into your phone. A voice-to-text app converts it to a string and POSTs it to the controller.
2. The controller sends the prompt to Claude with a system prompt that enforces clean, self-contained React.
3. Claude returns only the `App.jsx` source — no markdown, no explanation.
4. The controller writes the file directly to `generated-app/src/App.jsx`.
5. Vite's HMR (Hot Module Replacement) detects the change and pushes the update to your phone's browser instantly.

---

## Tips

- Your phone and Mac must be on the same Wi-Fi network.
- Find your local IP with `ipconfig getifaddr en0` (Mac).
- Use a shortcut app (iOS Shortcuts, Android Tasker) to trigger voice → POST automatically.
- The `history` field lets you pass prior prompts for iterative refinement.

---

## Requirements

- Python 3.10+
- Node.js 18+
- An Anthropic API key
