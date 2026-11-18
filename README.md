# voice-developer

Open Voice Developer on your phone, tap the microphone on your keyboard, and say what you want the app to do. For example, “Make a game where I guess whether Dwight or Jim said the quote.” Your phone’s built-in voice-to-text turns the command into text. Then tap **Plan** and watch the game update in the live preview. You can use the same workflow on any device that can reach your controller and supports dictation.

We used it to make funny trivia games, including **Dwight or Jim?** and a nature-and-science edition of **Two Truths and a Lie**. We’d play a round, dictate a change with the game still open, and try the next version as soon as the preview updated.

Voice Developer receives the text from your device’s dictation. It doesn’t call a paid transcription API. **Plan** and **Continue plan** still use your own model API keys to edit the app and may incur provider charges.

## Setup

### Prerequisites

You need Git, Bash, Python 3.10 or newer, Node.js with npm, and a model provider for the action you use. **Plan** uses OpenAI by default, or local Ollama when selected explicitly. **Continue plan** runs whichever coder provider you configure; there is no separate cloud-only path:

- The planner and the coder (the queued Aider edits) are configured separately; see [Planner and coder models](#planner-and-coder-models). With no new settings, both use the provider selected by `PLANNER_PROVIDER`, as before.
- A role set to `openai` requires `OPENAI_API_KEY`. A role set to `ollama` requires a running local Ollama server and a model; it does not require OpenAI credentials.
- Where code runs (local or cloud, and which model) is decided by the ⚙ models panel when you have chosen there, otherwise by `PLANNER_*` and `CODER_*` in `controller/.env`, never by which button you press.

For Google sign-in, create a Google OAuth client of type **Web application**. The controller generates its callback from the URL used to open it, so every URL you use for sign-in must have an exact matching authorized redirect URI. Add the Google accounts allowed to use the app as test users when the consent screen is in testing mode.

From the repository root, run setup once:

```sh
./setup.sh
```

`setup.sh` creates `controller/venv`, installs `controller/requirements.txt`, runs `npm install` in `generated-app` and in `controller/lint-tools` (the ESLint used for task validation), and copies `controller/.env.example` to `controller/.env` only when that file does not already exist. It does not make model API calls. Fill in `controller/.env` before starting the app. Keep that file private; it is ignored by Git.

Set these values in `controller/.env` for the default OpenAI planner and Google sign-in:

```dotenv
PLANNER_PROVIDER=openai
OPENAI_MODEL=gpt-5.4-mini
OPENAI_API_KEY=your-openai-key
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_API_BASE=http://127.0.0.1:11434
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

Open the controller at [http://127.0.0.1:8040](http://127.0.0.1:8040). The controller embeds the Vite preview at [http://127.0.0.1:5773](http://127.0.0.1:5773). `start.sh` starts Vite and Uvicorn in the foreground and prints both URLs. Press **Ctrl+C** once to stop both processes, or run `./stop.sh` from another terminal in the repository. `stop.sh` reads the PID file created by `start.sh`, validates that each PID still belongs to this checkout, and does nothing if the app is not running. Start `./start.sh` again to restart the app. Plans are stored in `plans/` and survive a restart: a plan that was running becomes failed and can be resumed with **Continue plan**, and nothing runs automatically after a restart. Restarting does not remove `generated-app/` or saved snapshots.

The loopback OAuth callback is:

```text
http://127.0.0.1:8040/auth/callback
```

Register that exact URI in the Google OAuth client when you use the controller from the Mac itself. The controller requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ALLOWED_EMAILS`, and a 64-character hexadecimal `SESSION_SECRET`.

### Mac access from a phone on the same network

Local authentication remains loopback-only unless you explicitly opt in to LAN mode. `r2m2.local` always resolves to the Mac's current address, so the phone never needs an IP. In LAN mode `start.sh` finds the Mac's private LAN address itself on every start (the first of `en0`-`en5` that has one), because the router can hand out a new address. `./start.sh --detect-host` prints the address it would use. With `VOICE_DEVELOPER_LOCAL_AUTH=1` already set in `controller/.env`, stop any existing instance and run:

```sh
VOICE_DEVELOPER_LOCAL_AUTH_LAN=1 ./start.sh
```

The phone can then open [http://r2m2.local:8040](http://r2m2.local:8040), and the preview is available at [http://r2m2.local:5773](http://r2m2.local:5773). To pick the address yourself, set `VOICE_DEVELOPER_HOST`. The LAN opt-in is accepted only when the host is a private IPv4 address (10.x, 172.16-31.x or 192.168.x); it does not allow `0.0.0.0`, loopback or a public address. Phones must be in the same /22 network as the Mac (for `192.168.5.77`, that is `192.168.4.0/22`). Without `VOICE_DEVELOPER_LOCAL_AUTH_LAN=1`, local authentication still requires `127.0.0.1`.

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
| Plan → planner model → coder model (Aider) | The planner sends your prompt and app context to the provider selected by `PLANNER_PROVIDER` and `PLANNER_MODEL`, turns the response into a clean task list (only the `## Tasks` section, duplicates removed), and stores it as a plan. Nothing runs yet: the UI shows a 5 second countdown on the **Plan** button and then starts the plan. Click **Plan** or close the plan window during the countdown to cancel; the plan stays stored. The in-process worker runs Aider with the coder provider and model (`CODER_PROVIDER`, `CODER_MODEL`) against the React source one task at a time, with the edit format described under [Small files](#small-files), given only the files each task names, and each task prompt scoped to that one task. A failed task stops the run, earlier tasks stay done, and only the failed task's changes are reverted (never the whole app). The UI shows the timeout message or the Aider stderr/stdout tail. Each role set to `ollama` uses the loopback Ollama endpoint with no cloud credentials in its environment and never falls back to a cloud provider. The coder defaults to the planner's provider and model settings. |
| Continue plan | Resumes the most recent stored plan from its next pending or failed task, using the same coder settings as Plan. If no plan is stored it says so. |
| React and Vite at the configured host, default `127.0.0.1:5773` | Serves the current app in an iframe inside the controller. Vite watches the files and updates the preview when they change. |
| Local filesystem | The active app lives in `generated-app/`. Saved snapshots live in `saved-apps/`, which Git ignores because they belong to each local workspace. Copy that folder separately to back up or move your saved apps. Plans and their task status are saved as JSON in `plans/` (Git ignored) so they survive a controller restart. |

Each clone has one active workspace. Browser tabs connected to the same controller see the same app and job queue. The controller runs its own queue worker, so you can use the app without starting the separate CLI utilities in `worker/`.
### Code layout

`controller/main.py` is only the entry point (`uvicorn main:app --app-dir controller`). The code lives in the `controller` package:

- `app.py`: FastAPI app, startup, and router registration. `routes/` holds the endpoints (`ui`, `auth`, `system`, `apps`, `planner`, `jobs`).
- `auth.py`: Google sign-in session helpers, the local-auth and LAN checks, and startup auth validation.
- `providers.py`: planner and coder provider settings, loopback checks, and per-role subprocess environments.
- `coder/`: one module per coder engine (`aider.py`, `opencode.py`) with shared settings in `base.py`. A new engine is a new module here plus one name in `coder/base.py`, and one branch in `coder/__init__.py`.
- `escalation.py`: the coder ladder, escalation mode and plan cost cap settings.
- `planning.py`, `store.py`, `workspace.py`, `worker.py`: plan parsing and prompts, `plans/<id>.json` persistence, per-task snapshot/revert/commit, and the job worker.
- `config.py` (paths, `.env`), `state.py` (in-memory jobs and queue), `ui.py` with `templates/phone.html` (the phone page).

## Task validation

After each task that changed files, and before it is committed, the controller runs two checks on the generated app:

1. `vite build` with `--outDir` set to a temporary directory, so `generated-app/dist` and the app files are never touched. It runs for any change to a task-scope file, including `package.json`.
2. ESLint on the changed or created `src/` `.js`/`.jsx` files, with `no-undef`, `react/jsx-no-undef` and `react/jsx-uses-vars` only (no style rules). This catches a name used without an import and a JSX component that is not defined. ESLint is installed in `controller/lint-tools` and run with the app as its working directory, so the generated app gets no lint dependencies and no config file.

Both checks run even if the first fails. If either fails, the coder gets one retry on the current files with the error output in its prompt. If validation fails again, the task fails, its changes are reverted as for any failed task, the UI shows the build or lint output, and the run stops. The existing checks (exit code, `App.jsx`, partial apply, no-change) run first and fail the task immediately without a retry. The worst case for a task is two coder runs (each with its own `CODER_TIMEOUT_SECONDS`) plus two validations. The task log shows `Validating: build (vite)...`, `build passed`/`build FAILED`, and the same for lint. A task that changed nothing skips validation.

If node, `generated-app/node_modules` or `controller/lint-tools/node_modules` is missing, the affected check is skipped with a log line telling you to run `./setup.sh`; the task is not failed. Settings in `controller/.env`: `TASK_VALIDATION` (`build,lint` by default, a subset, or `off`) and `VALIDATION_TIMEOUT_SECONDS` (default `120`, applies to each check). The retry count is fixed at one.

Limit: these checks do not run the page. A runtime error such as reading a property of an undefined object still passes, and the page can still render blank.

## Small files

The local coder (a 7B model) edits small files reliably and large ones badly, so the app is kept as many small files.

- **Planner.** The planner prompt asks for one component or module per file, each under `MAX_FILE_LINES` lines (default 150), and for new features as new files wired into `src/App.jsx` instead of more code in `App.jsx`. Each task ends with the files it creates or edits: `1) Add a timer [files: src/components/Timer.jsx, src/App.jsx]`. Paths are relative to `generated-app/`, may name files that do not exist yet, and a task that wires a new module names `src/App.jsx` too. `(files: ...)` is accepted as well. Only paths under `src/` and `index.html`, `package.json` and `vite.config.js` are accepted; absolute paths, `..` and binary assets are ignored.
- **Files the coder gets.** Aider is given the files the task names, plus the existing `src/` files that directly import them (one level, relative imports, found by reading `import`/`require` lines), so a task editing a module also sees its caller. Aider's repo map outlines the rest. If a task names no usable file (older plans, or a planner that ignored the format), it falls back to the previous behavior: every non-binary `src/` file plus `vite.config.js`, `index.html` and `package.json`. `index.html`, `package.json` and `vite.config.js` are only handed to the coder when a task names them.
- **Revert and commit scope.** The per-task snapshot still covers every non-binary `src/` file and those three config files, whatever the coder was given, and new `src/` files are removed on revert. Revert and the controller's commit touch nothing outside that scope.
- **Line limit.** After a successful task the controller counts the lines of each `src/` file the task changed or created. A file over `MAX_FILE_LINES` is reported as a warning on that task (shown under the task in the UI and stored as `task_warnings` in the plan file). The task is not failed or reverted: reverting would make any task that touches an already oversized file, such as today's `App.jsx`, impossible, and would throw away a finished edit. Split the file in a later task or by hand.
- **Edit format.** With small files, local coders use Aider's `whole` format and cloud coders use `diff`. See `CODER_EDIT_FORMAT` below to override.

Splitting an existing app's `App.jsx` into modules is not done automatically.

## Planner and coder models
Plan uses two independently configured roles, set in `controller/.env` or chosen in the ⚙ models panel (see below):
| Variable | Meaning | Default when unset |
| --- | --- | --- |
| `PLANNER_PROVIDER` | `openai`, `ollama`, or `lmstudio` for the planner | `openai` |
| `PLANNER_MODEL` | Planner model | `OPENAI_MODEL` (default `gpt-5.4-mini`), `OLLAMA_MODEL`, or `LMSTUDIO_MODEL`, by planner provider |
| `CODER_PROVIDER` | `openai`, `ollama`, or `lmstudio` for the queued Aider edits | the planner provider |
| `CODER_MODEL` | Coder (Aider) model | `OPENAI_MODEL`, `OLLAMA_MODEL`, or `LMSTUDIO_MODEL`, by coder provider |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OLLAMA_MODEL`, `OLLAMA_API_BASE` | Existing settings; shared by both roles | unchanged |
| `LMSTUDIO_MODEL`, `LMSTUDIO_API_BASE` | LM Studio model identifier and local server URL; shared by both roles | no model; `http://127.0.0.1:1234` |
Existing `.env` files that set only `PLANNER_PROVIDER`, `OPENAI_MODEL`, and `OLLAMA_MODEL` behave exactly as before. An empty value counts as unset. Both roles share one `OLLAMA_API_BASE`, which must be loopback (`localhost`, `127.0.0.1`, or `::1`), and one `OPENAI_API_KEY`.

### Models panel (hot swap)

The ⚙ button next to ⓘ opens a panel with a provider and model dropdown for the planner and for the coder. Providers are LM Studio (local), Ollama (local) and OpenAI (cloud). Local models are listed live from the running servers; OpenAI models come from `OPENAI_MODELS` (comma list) plus `OPENAI_MODEL`, `PLANNER_MODEL` and `CODER_MODEL` in `.env`. Ollama models ending in `:cloud` or `-cloud` stay on the Ollama provider but are labeled cloud, and the "Local-only" badge turns off when a role uses one.

- Precedence per role: panel choice, then `.env`, then defaults. With nothing chosen, behavior is exactly the `.env` behavior.
- **Save** writes only `{provider, model}` per role to `controller/model-selection.json` (ignored by Git), so the choice survives a restart. **Use .env** deletes that file.
- The planner applies from the next **Plan**. The coder is resolved when a run starts: a running plan finishes on the coder it started with, and the new coder applies from the next run (Continue or a new plan).
- An unreachable server or a missing `OPENAI_API_KEY` is reported in the panel and the save is refused. Nothing falls back to another provider. API keys and server URLs are never shown or editable in the panel; they stay in `.env`.

Bad configuration fails with a clear message and never falls back from a local role to a cloud one: an invalid provider name, `openai` without `OPENAI_API_KEY`, `ollama` without a model, or a non-loopback `OLLAMA_API_BASE`. A bad coder setting also fails **Plan** up front, so you never get a plan that cannot run.

Example combinations:
- **All local.** Run `ollama pull qwen3:8b qwen2.5-coder:7b` yourself first.
  ```
  PLANNER_PROVIDER=ollama
  PLANNER_MODEL=qwen3:8b
  CODER_PROVIDER=ollama
  CODER_MODEL=qwen2.5-coder:7b
  OLLAMA_API_BASE=http://127.0.0.1:11434
  ```
  With models you already have, use `PLANNER_MODEL=qwen2.5:7b` and `CODER_MODEL=qwen2.5:7b`, or just the legacy `PLANNER_PROVIDER=ollama` and `OLLAMA_MODEL=qwen2.5:7b`.
- **Cloud planner, local coder.** Your prompt and app context go to OpenAI for planning. Aider edits stay local, and the Aider process does not receive `OPENAI_API_KEY`.
  ```
  PLANNER_PROVIDER=openai
  OPENAI_API_KEY=...
  PLANNER_MODEL=gpt-5.4-mini
  CODER_PROVIDER=ollama
  CODER_MODEL=qwen2.5-coder:7b
  OLLAMA_API_BASE=http://127.0.0.1:11434
  ```
- **All cloud.**
  ```
  PLANNER_PROVIDER=openai
  CODER_PROVIDER=openai
  PLANNER_MODEL=gpt-5.4-mini
  CODER_MODEL=<stronger model>
  OPENAI_API_KEY=...
  ```
- **Cloud planner, LM Studio coder.** In LM Studio, start the local server (Developer tab) and load the model. `LMSTUDIO_MODEL` / `CODER_MODEL` is the identifier LM Studio shows for it (also listed by `lms ls`). Aider reaches it as `lm_studio/<model>`.
  ```
  PLANNER_PROVIDER=openai
  OPENAI_API_KEY=...
  CODER_PROVIDER=lmstudio
  CODER_MODEL=qwen2.5-coder-7b-instruct
  LMSTUDIO_API_BASE=http://127.0.0.1:1234
  ```
  `lmstudio` follows the same rules as `ollama`: the server URL must be loopback, the Aider process gets the environment allowlist plus `LM_STUDIO_API_BASE` and a placeholder `LM_STUDIO_API_KEY` (LM Studio does not check it), and it never falls back to a cloud provider.
- **Legacy, unchanged.** Set only `PLANNER_PROVIDER`, `OPENAI_MODEL`, and `OLLAMA_MODEL`.

Credential isolation per role: an `ollama` Aider process gets a small allowlist of environment variables plus `OLLAMA_API_BASE`. An `openai` Aider process gets the same allowlist plus `OPENAI_API_KEY`, optional `OPENAI_API_BASE`/`OPENAI_BASE_URL`/`OPENAI_ORG_ID`, and proxy and certificate variables. It does not inherit unrelated secrets such as `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_SECRET`, or `SESSION_SECRET`. The controller badge shows planner and coder provider and model separately and shows `Local-only` only when both are local (`ollama` or `lmstudio`).

Local model caveats on an M2 Pro with 16 GB RAM:
- Models of about 7-8B fit. `qwen3:14b` is likely to swap.
- Ollama defaults to a small context window (often 2048-4096 tokens; check `ollama show <model>`). That truncates Aider's repo map and file contents. Raise it with `OLLAMA_CONTEXT_LENGTH` in the Ollama server environment or `num_ctx` in a Modelfile, which also raises RAM use.
- Two different local models loaded at once cost RAM for both. `OLLAMA_MAX_LOADED_MODELS=1` makes Ollama swap them, which is slower per task but safe.
- Aider has a 120 s timeout per task in `job_worker`, so slow local models may time out.

Restart the controller after editing `.env` (`./stop.sh`, then `./start.sh`).

## Coder escalation (model ladder)

The server, not the voice user, decides when a task needs a stronger coder. Set a ladder in `controller/.env` (weakest first, `provider:model`, comma separated; the split is on the first `:`, so `ollama:qwen2.5-coder:7b` works):

```
CODER_LADDER=lmstudio:mlx-community/qwen2.5-coder-7b-instruct,openai:gpt-6-luna,openai:gpt-6.1-terra,openai:gpt-6.2-sol,openai:gpt-6.2-astra
AUTO_ESCALATE=on          # on (default) | suggest | off
MAX_PLAN_COST=1.00        # dollars per plan, default 1.00
ESCALATE_LOCAL_ONLY=off   # on: local rungs only
```

- **Starting rung.** The coder from the ⚙ panel (else `.env`) is the starting rung. If it is in the ladder, only that rung and the ones above it are used. If it is not, it is added below the whole ladder. Every task starts on the starting rung again, not where the previous task ended.
- **One attempt per rung.** A rung attempt is the coder run plus the existing single build/lint retry with the error (that retry stays inside the rung). If the attempt fails, the task is reverted and the next rung runs it from the clean files, with the earlier failure text in its prompt.
- **What escalates.** Build or lint failure after the retry, coder timeout, "reflections allowed, stopping" (partial apply), no edit applied (model API error, SEARCH mismatch, edit-format error; this includes a local server that is down, logged as "the model server could not be reached"), and an `App.jsx` corruption. These do not escalate and fail the run as before: a non-zero Aider exit code, Aider missing, the opencode stub, a validator that could not run. When the last rung fails, the run fails with `Task N failed on all K rungs (...)`.
- **`AUTO_ESCALATE`.** `on` escalates automatically. `suggest` stops the run at the failed task (reverted) and names the next rung; press Continue to run that task on it. `off`, or no `CODER_LADDER`, is the single-coder behavior of before: no ladder state, no cost cap.
- **`MAX_PLAN_COST`.** The real cost Aider prints (`Cost: $X message`) is summed over every coder run of the plan. It is checked before each attempt on a cloud rung; when reached, the run stops and reports the spend and the task. Local attempts never count against it and are not blocked. A cloud attempt whose cost Aider did not print (timeout, crash) is estimated from the `Tokens: X sent, Y received` lines it printed, at the model's known price (a built-in table in `controller/escalation.py` for the GPT-6 models), or from a typical attempt of 8k in / 4k out when no counts were printed (about $0.003 on Luna, $0.03 on Terra, $0.18 on 6.2 Astra). A model with no known price is counted at a flat $0.10. The estimate is logged and the spend is shown with `~`. One attempt may overshoot the cap. The total is stored with the plan and survives Continue and a controller restart; to spend more, raise `MAX_PLAN_COST` in `.env` and restart the controller.
- **`ESCALATE_LOCAL_ONLY=on`.** Keeps only local rungs (`ollama`/`lmstudio`, not an Ollama `:cloud` model). If the starting coder runs in the cloud, the run fails with a clear message instead of switching.
- **Bad configuration fails clearly.** An unknown provider, a malformed or duplicate entry, a cloud rung without `OPENAI_API_KEY`, or a non-loopback local server fails the run (and the Continue request) naming the entry. No rung is skipped and nothing falls back to another provider. Each rung's Aider process gets only that rung's credentials. The edit format follows the rung (`whole` local, `diff` cloud) unless `CODER_EDIT_FORMAT` is set.
- **What you see.** Each task shows the rung that ran it in the task list (`↑` when it escalated), the task log lists lines like `gpt-6.1-terra, after qwen2.5-coder:7b failed lint: 'x' is not defined`, the running status shows spend against the cap, and the coder badge shows the model that actually ran last.

Not built: planner size tags that skip weak rungs, learning from history, a UI to edit the ladder.

## Model providers

`PLANNER_PROVIDER` explicitly selects the planner provider (and, unless `CODER_PROVIDER` is set, the coder provider). It defaults to `openai`, preserving the existing behavior:

- `PLANNER_PROVIDER=openai` uses `OPENAI_MODEL` (default `gpt-5.4-mini`) for the planning request and the same OpenAI model for queued Aider edits. `OPENAI_API_KEY` is required.
- `PLANNER_PROVIDER=ollama` uses `OLLAMA_MODEL` and `OLLAMA_API_BASE` for both planning and queued Aider edits. The recommended local values are `qwen2.5:7b` and `http://127.0.0.1:11434`. Ollama mode is local-only: it requires the selected endpoint and model, never falls back to OpenAI or another cloud provider, and does not need `OPENAI_API_KEY` or `OPENAI_API_BASE`.

Optional coder settings in `controller/.env` (see `controller/.env.example`):

- `CODER_TIMEOUT_SECONDS` is the per-task timeout, default `120`.
- `CODER_EDIT_FORMAT` is the Aider edit format: `diff`, `diff-fenced`, `udiff`, or `whole`. When unset, the default follows the coder in use: `whole` for a local coder (`ollama`, `lmstudio`) and `diff` for a cloud coder (`openai`, or an Ollama `:cloud`/`-cloud` model, which runs remotely). The default is resolved at the start of each run from the coder actually selected, so a coder hot-swapped in the models panel gets its own default. Setting `CODER_EDIT_FORMAT` overrides it for every coder.
- `TASK_VALIDATION` and `VALIDATION_TIMEOUT_SECONDS` control the post-task build and lint checks. See [Task validation](#task-validation).
- `MAX_FILE_LINES` is the line limit per generated source file (default `150`, `.env` only). See [Small files](#small-files).
- `AIDER_BIN` is the Aider executable. By default the controller uses `controller/aider-venv/bin/aider` (Aider 0.86.2, created by `./setup.sh`), falling back to `aider` on `PATH`. Aider lives in its own environment because its dependencies would otherwise replace the controller's pinned FastAPI, Pydantic and OpenAI versions. To create it by hand: `python3 -m venv controller/aider-venv && controller/aider-venv/bin/pip install aider-chat==0.86.2`.
- `CODER_ENGINE` is `aider` (default) or `opencode`. OpenCode is a stub that defines the command (`opencode run --model <provider/model> --format json`, Ollama through an OpenAI-compatible `/v1` endpoint with a 64k+ context). Selecting it fails with "not implemented yet"; it never falls back to Aider or a cloud provider.

Keep all API keys, OAuth secrets, and session secrets in the ignored `controller/.env` file or another secret store. Do not commit credentials or put them in prompts, source files, or logs.

The local `qwen2.5:7b` model has no cloud credentials to configure, but a 7B model may produce less consistent plans or edits than a larger model. Its speed and context capacity also depend on local hardware and the model's Ollama installation. Pull and test the model before selecting it for regular edits.

To test only the local planning request without calling `/plan`, enqueueing a job, or editing `generated-app`, run this from the repository root. The command disables `.env` loading for the smoke process, unsets the cloud-provider variables, and prints safe provider evidence without credentials:

```sh
(
  env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u OPENAI_API_BASE \
    -u AZURE_OPENAI_API_KEY -u AZURE_OPENAI_ENDPOINT -u AZURE_OPENAI_BASE_URL \
    -u ANTHROPIC_API_KEY -u ANTHROPIC_BASE_URL \
    -u GOOGLE_API_KEY -u GOOGLE_BASE_URL -u GOOGLE_API_BASE \
    -u GOOGLE_APPLICATION_CREDENTIALS -u GEMINI_API_KEY -u GEMINI_BASE_URL -u GEMINI_API_BASE \
    -u OPENROUTER_API_KEY -u OPENROUTER_API_BASE \
    -u DEEPSEEK_API_KEY -u DEEPSEEK_API_BASE \
    -u MISTRAL_API_KEY -u MISTRAL_API_BASE \
    -u COHERE_API_KEY -u COHERE_API_BASE \
    -u GROQ_API_KEY -u GROQ_API_BASE -u TOGETHER_API_KEY -u TOGETHER_API_BASE \
    -u XAI_API_KEY -u XAI_API_BASE \
    -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN \
    -u AWS_PROFILE -u AWS_REGION -u AWS_DEFAULT_REGION -u AWS_BEARER_TOKEN_BEDROCK \
    -u BEDROCK_API_KEY -u AIDER_API_KEY -u AIDER_API_BASE \
    PYTHON_DOTENV_DISABLED=1 \
    PLANNER_PROVIDER=ollama \
    OLLAMA_MODEL=qwen2.5:7b \
    OLLAMA_API_BASE=http://127.0.0.1:11434 \
    controller/venv/bin/python - <<'PY'
from controller.providers import create_planner_client, planner_provider_info, resolve_planner_provider

provider = resolve_planner_provider()
print("PROVIDER_EVIDENCE", planner_provider_info(provider))
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

Expected provider evidence includes `label: 'Ollama / local-only'` and `endpoint: 'http://127.0.0.1:11434/v1'`. This proves the application selected and used the validated loopback endpoint for this planner request. It does not prove that unrelated operating-system processes made no network connections, and it does not change or enforce firewall or router policy. To inspect the planner process during the request when practical, use `lsof -nP -a -p <planner-pid> -iTCP -sTCP:ESTABLISHED`.

Aider also supports Gemini, DeepSeek, and OpenRouter. Voice Developer currently exposes OpenAI and the explicit Ollama path. [Aider provider documentation](https://aider.chat/docs/llms.html)

## Data and local execution

The selected model receives your prompt and relevant source code. How dictation audio is handled depends on your device and keyboard settings. Keep credentials and private data out of prompts and generated source.

Aider edits files under `generated-app/src/` and can create Git commits. **New App** and **Load App** replace the active source, so save changes you want to keep. Setup and some workspace actions run `npm install`, which can execute dependency scripts under your user account. Review generated changes and dependencies before reusing or distributing an app.

## License

[MIT](LICENSE)
