# voice-developer

Open Voice Developer on your phone, tap the microphone on your keyboard, and say what you want the app to do. For example, “Make a game where I guess whether Dwight or Jim said the quote.” Your phone’s built-in voice-to-text turns the command into text. Then tap **Plan** or **Generate** and watch the game update in the live preview. You can use the same workflow on any device that can reach your controller and supports dictation.

We used it to make funny trivia games, including **Dwight or Jim?** and a nature-and-science edition of **Two Truths and a Lie**. We’d play a round, dictate a change with the game still open, and try the next version as soon as the preview updated.

Voice Developer receives the text from your device’s dictation. It doesn’t call a paid transcription API. **Plan** and **Generate** still use your own model API keys to edit the app and may incur provider charges.

## Setup

### Prerequisites

You need Git, Bash, Python 3.10 or newer, Node.js with npm, and a model provider for the action you use. **Plan** uses OpenAI by default, or local Ollama when selected explicitly. **Generate** continues to use Anthropic for a direct edit:

- OpenAI mode requires `OPENAI_API_KEY` and uses `OPENAI_MODEL` for planning and the queued Aider edits.
- Ollama mode requires a running local Ollama server and the model named by `OLLAMA_MODEL`; it does not require OpenAI credentials.
- `ANTHROPIC_API_KEY` is used by **Generate** and is unchanged by the planner provider setting.

For Google sign-in, create a Google OAuth client of type **Web application**. The controller generates its callback from the URL used to open it, so every URL you use for sign-in must have an exact matching authorized redirect URI. Add the Google accounts allowed to use the app as test users when the consent screen is in testing mode.

From the repository root, run setup once:

```sh
./setup.sh
```

`setup.sh` creates `controller/venv`, installs `controller/requirements.txt`, runs `npm install` in `generated-app`, and copies `controller/.env.example` to `controller/.env` only when that file does not already exist. It does not make model API calls. Fill in `controller/.env` before starting the app. Keep that file private; it is ignored by Git.

Set these values in `controller/.env` for the default OpenAI planner and Google sign-in:

```dotenv
PLANNER_PROVIDER=openai
OPENAI_MODEL=gpt-5.4-mini
OPENAI_API_KEY=your-openai-key
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_API_BASE=http://127.0.0.1:11434
ANTHROPIC_API_KEY=your-anthropic-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
ALLOWED_EMAILS=you@example.com
SESSION_SECRET=generated-64-hex-character-value
```

To use only the local planner, change `PLANNER_PROVIDER` to `ollama`, keep `OLLAMA_MODEL` and `OLLAMA_API_BASE` set to the local server, and remove or leave unset `OPENAI_API_KEY` and `OPENAI_API_BASE`. Ollama mode does not fall back to OpenAI or another cloud provider if the local endpoint or model is unavailable. `qwen2.5:7b` must already be installed in Ollama. It needs no cloud credential, but its smaller size can make task decomposition and code edits less reliable than a larger hosted model, and local generation can be slower or limited by the Mac's available memory. The planner remains planning-only until the queued Aider worker applies its tasks, so use a planning prompt for a local smoke check.

`ALLOWED_EMAILS` is a comma-separated allowlist. The controller accepts only a verified Google email in that list. Generate `SESSION_SECRET` with:

```sh
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

The model keys are needed only for the corresponding action.

### Local Mac use

The default local startup binds both services to loopback:

```sh
./start.sh
```

Open the controller at [http://127.0.0.1:8040](http://127.0.0.1:8040). The controller embeds the Vite preview at [http://127.0.0.1:5773](http://127.0.0.1:5773). `start.sh` starts Vite and Uvicorn in the foreground and prints both URLs. Press **Ctrl+C** once to stop both processes, or run `./stop.sh` from another terminal in the repository. `stop.sh` reads the PID file created by `start.sh`, validates that each PID still belongs to this checkout, and does nothing if the app is not running. Start `./start.sh` again to restart the app. Restarting clears the in-memory job queue and status, but it does not remove `generated-app/` or saved snapshots.

The loopback OAuth callback is:

```text
http://127.0.0.1:8040/auth/callback
```

Register that exact URI in the Google OAuth client when you use the controller from the Mac itself. The controller requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ALLOWED_EMAILS`, and a 64-character hexadecimal `SESSION_SECRET`.

### Mac access from a phone on the same network

Local authentication remains loopback-only unless you explicitly opt in to LAN mode. The Mac's LAN address for this setup is `192.168.5.33`, and `r2m2.local` resolves to that address. With `VOICE_DEVELOPER_LOCAL_AUTH=1` already set in `controller/.env`, stop any existing instance and run:

```sh
VOICE_DEVELOPER_HOST=192.168.5.33 VOICE_DEVELOPER_LOCAL_AUTH_LAN=1 ./start.sh
```

The phone can then open [http://r2m2.local:8040](http://r2m2.local:8040), and the preview is available at [http://r2m2.local:5773](http://r2m2.local:5773). The LAN opt-in is accepted only with `VOICE_DEVELOPER_HOST=192.168.5.33`; it does not allow `0.0.0.0` or another interface. Without `VOICE_DEVELOPER_LOCAL_AUTH_LAN=1`, local authentication still requires `127.0.0.1`.

This mode exposes the controller and unauthenticated preview to devices on the trusted local network. Anyone on that network may use the app, so do not use this mode on an untrusted network and do not expose either port to the public internet. The preview has no sign-in of its own. Google OAuth is supported by the controller, but no OAuth credentials are configured or remote access has been tested with OAuth. The current phone path uses this explicit LAN local-auth opt-in instead. This setup does not configure Google OAuth, TLS, macOS firewall rules, or router settings. The phone and Mac must be on the same network, and macOS may require an incoming-connection approval for the two ports.

`VOICE_DEVELOPER_HOST` is the exact environment variable used by `start.sh`, Uvicorn, and `generated-app/vite.config.js`. Set it in the shell command as shown; putting it only in `controller/.env` does not make `start.sh` use it for binding.

### Azure VM use

The repository documents an Azure VM setup, but it does not configure or deploy an Azure instance. It does not provision a VM, install packages on it, create a service, configure TLS, or manage secrets. Before using it, you need an existing Linux VM, SSH access, an Azure CLI installation with `az login`, and permission to modify the VM’s network security group. The VM also needs Git, Bash, Python 3.10 or newer, Node.js with npm, and the model credentials and Google authentication values described above.

Copy or clone the repository on the VM, run `./setup.sh`, and create `controller/.env` with the required model and authentication values. Use a strong `SESSION_SECRET`; do not put secrets in `azure-setup.sh`, the shell history, or the README.

#### Azure network setup

`azure-setup.sh` only asks Azure to allow TCP ports `8040` and `5773` on the existing VM. It does not install software, copy the project, configure `controller/.env`, start `start.sh`, discover the VM IP, or create a persistent service. It waits 10 seconds between the two `az vm open-port` calls. The default resource group and VM name are the values in the script. You can override them without editing the script:

```sh
AZURE_RESOURCE_GROUP=your-resource-group AZURE_VM_NAME=your-vm ./azure-setup.sh
```

You can also pass them as positional arguments:

```sh
./azure-setup.sh your-resource-group your-vm
```

Review the VM’s NSG rules after running the script. `az vm open-port` is a network-rule change and should not be treated as an application health check. Restrict the source address to your own IP or private network where possible. Opening both ports broadly makes the unauthenticated preview reachable and is unsafe for a public VM. The script does not configure an Azure firewall, subnet route, HTTPS listener, or reverse proxy.

The safer remote-development option is an SSH tunnel. Keep both services on the VM loopback and forward both ports to your Mac:

```sh
# On the VM
VOICE_DEVELOPER_HOST=127.0.0.1 ./start.sh

# On your Mac, in another terminal
ssh -N \
  -L 8040:127.0.0.1:8040 \
  -L 5773:127.0.0.1:5773 \
  user@your-vm-host
```

Open [http://127.0.0.1:8040](http://127.0.0.1:8040) on the Mac and register `http://127.0.0.1:8040/auth/callback` in Google OAuth. Stop the VM processes with **Ctrl+C** in the VM terminal. Stop the tunnel with **Ctrl+C** in the Mac terminal.

For direct access to an Azure VM, bind to the VM’s private address when possible:

```sh
VOICE_DEVELOPER_HOST=<vm-private-ip> ./start.sh
```

Using `0.0.0.0` binds all VM interfaces and should only be done when the NSG and host firewall restrict access to trusted source addresses:

```sh
VOICE_DEVELOPER_HOST=0.0.0.0 ./start.sh
```

Use `http://<vm-address>:8040` for the controller and port `5773` for the embedded preview. The application derives `/auth/callback` from the incoming request URL, so the exact external callback must be registered in Google OAuth. A direct public HTTP deployment is not a complete production setup because this repository has no TLS or reverse proxy. For public or phone access, put an HTTPS reverse proxy or other TLS-terminating service in front of the controller and register its exact HTTPS callback, then keep the preview port private if possible.

To stop and restart the foreground service, press **Ctrl+C** and rerun the same `VOICE_DEVELOPER_HOST=... ./start.sh` command. You can also run `./stop.sh` from another terminal in the repository. It stops only the validated PIDs recorded by `start.sh` and safely reports when no PID file exists. There is no systemd unit or other service manager in this repository. To check the listener without changing anything, run on the VM:

```sh
ss -ltn | grep -E ':(8040|5773)\b'
```

The authenticated `/status` endpoint is available at port `8040`, but the controller redirects unauthenticated requests to `/auth/login`. A simple listener check is therefore more useful before signing in. The VM must remain running for the foreground processes to remain available; use a service manager or terminal multiplexer only if you configure that separately.

## How it works

| Component | Role |
| --- | --- |
| FastAPI controller at the configured host, default `127.0.0.1:8040` | Serves the prompt UI, handles Google sign-in, manages the active workspace and saved apps, and reports job progress to the browser. |
| Plan → selected provider → Aider | The planner sends your prompt and app context to the provider selected by `PLANNER_PROVIDER`, turns the response into a task list, and queues it. In `openai` mode, both planning and the queued Aider worker use OpenAI. In `ollama` mode, both use the configured local Ollama-compatible endpoint and model, with cloud credentials removed from the Aider environment and no cloud fallback. The in-process worker runs Aider against the React source one task at a time. |
| Generate → Aider → Anthropic | Runs a direct edit without the planning queue. Aider receives your prompt and relevant JavaScript and JSX files. This path still uses `ANTHROPIC_API_KEY` and is unaffected by `PLANNER_PROVIDER`. |
| React and Vite at the configured host, default `127.0.0.1:5773` | Serves the current app in an iframe inside the controller. Vite watches the files and updates the preview when they change. |
| Local filesystem | The active app lives in `generated-app/`. Saved snapshots live in `saved-apps/`, which Git ignores because they belong to each local workspace. Copy that folder separately to back up or move your saved apps. The queue lives in controller memory, so restarting it clears job status. |

Each clone has one active workspace. Browser tabs connected to the same controller see the same app and job queue. The controller runs its own queue worker, so you can use the app without starting the separate CLI utilities in `worker/`.

## Model providers

`PLANNER_PROVIDER` explicitly selects the provider for **Plan**. It defaults to `openai`, preserving the existing behavior:

- `PLANNER_PROVIDER=openai` uses `OPENAI_MODEL` (default `gpt-5.4-mini`) for the planning request and the same OpenAI model for queued Aider edits. `OPENAI_API_KEY` is required.
- `PLANNER_PROVIDER=ollama` uses `OLLAMA_MODEL` and `OLLAMA_API_BASE` for both planning and queued Aider edits. The recommended local values are `qwen2.5:7b` and `http://127.0.0.1:11434`. Ollama mode is local-only: it requires the selected endpoint and model, never falls back to OpenAI or another cloud provider, and does not need `OPENAI_API_KEY` or `OPENAI_API_BASE`.

`Generate` remains the separate Anthropic direct-edit path and continues to use `ANTHROPIC_API_KEY`; changing `PLANNER_PROVIDER` does not change it. Keep all API keys, OAuth secrets, and session secrets in the ignored `controller/.env` file or another secret store. Do not commit credentials or put them in prompts, source files, or logs.

The local `qwen2.5:7b` model has no cloud credentials to configure, but a 7B model may produce less consistent plans or edits than a larger model. Its speed and context capacity also depend on local hardware and the model's Ollama installation. Pull and test the model before selecting it for regular edits.

To test only the local planning request without calling `/plan`, enqueueing a job, or editing `generated-app`, run this from the repository root. The command prints only a success message and deliberately unsets the OpenAI variables:

```sh
(
  cd controller
  env -u OPENAI_API_KEY -u OPENAI_API_BASE \
    PLANNER_PROVIDER=ollama \
    OLLAMA_MODEL=qwen2.5:7b \
    OLLAMA_API_BASE=http://127.0.0.1:11434 \
    ./venv/bin/python - <<'PY'
from main import create_planner_client, resolve_planner_provider

provider = resolve_planner_provider()
response = create_planner_client(provider).chat.completions.create(
    model=provider.model,
    messages=[
        {"role": "system", "content": "Return one numbered planning task."},
        {"role": "user", "content": "Plan a harmless color change in the React app."},
    ],
    max_completion_tokens=128,
)
assert response.choices and response.choices[0].message.content
print("Ollama planning-only smoke passed")
PY
)
```

Aider also supports Gemini, DeepSeek, and OpenRouter. Voice Developer currently exposes OpenAI and Anthropic in addition to the explicit Ollama planner path. [Aider provider documentation](https://aider.chat/docs/llms.html)

## Data and local execution

The selected model receives your prompt and relevant source code. How dictation audio is handled depends on your device and keyboard settings. Keep credentials and private data out of prompts and generated source.

Aider edits files under `generated-app/src/` and can create Git commits. **New App** and **Load App** replace the active source, so save changes you want to keep. Setup and some workspace actions run `npm install`, which can execute dependency scripts under your user account. Review generated changes and dependencies before reusing or distributing an app.

## License

[MIT](LICENSE)
