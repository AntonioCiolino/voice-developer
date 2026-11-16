# voice-developer

Open Voice Developer on your phone, tap the microphone on your keyboard, and say what you want the app to do. For example, “Make a game where I guess whether Dwight or Jim said the quote.” Your phone’s built-in voice-to-text turns the command into text. Then tap **Plan** or **Generate** and watch the game update in the live preview. You can use the same workflow on any device that can reach your controller and supports dictation.

We used it to make funny trivia games, including **Dwight or Jim?** and a nature-and-science edition of **Two Truths and a Lie**. We’d play a round, dictate a change with the game still open, and try the next version as soon as the preview updated.

Voice Developer receives the text from your device’s dictation. It doesn’t call a paid transcription API. **Plan** and **Generate** still use your own model API keys to edit the app and may incur provider charges.

## Quick start

You’ll need Git, Bash, Python 3.10 or newer, Node.js with npm, and Google OAuth credentials. Use your own OpenAI API key for **Plan** and an Anthropic API key if you want **Generate**.

```sh
git clone https://github.com/AntonioCiolino/voice-developer.git
cd voice-developer
./setup.sh
```

Setup creates a Python virtual environment, installs the controller and preview dependencies, and creates `controller/.env` from the example if it doesn’t already exist. It makes no model API calls.

1. Create a Google OAuth client of type **Web application**. Register `http://127.0.0.1:8040/auth/callback` as an authorized redirect URI. If your consent screen is in testing mode, add your account as a test user.
2. In `controller/.env`, enter your OAuth client ID and secret as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Set `ALLOWED_EMAILS` to a comma-separated list of the Google accounts you want to permit. The controller requires a verified Google email on that list.
3. Generate a session secret with the command below and paste its output into `SESSION_SECRET`. Keep the secret and the provider keys in your local `controller/.env`. Set `OPENAI_API_KEY` for **Plan** and `ANTHROPIC_API_KEY` for **Generate**.

```sh
python3 -c 'import secrets; print(secrets.token_hex(32))'
./start.sh
```

Open [the controller](http://127.0.0.1:8040) and sign in. The [Vite preview](http://127.0.0.1:5773) also opens on its own. Press Ctrl+C in the terminal to stop the services.

## How it works

| Component | Role |
| --- | --- |
| FastAPI controller at `127.0.0.1:8040` | Serves the prompt UI, handles Google sign-in, manages the active workspace and saved apps, and reports job progress to the browser. |
| Plan → OpenAI → Aider | The planner sends your prompt and app context to OpenAI, turns the response into a task list, and queues it. An in-process worker runs Aider against the React source one task at a time. The browser polls for task status, logs, and reported costs. |
| Generate → Aider → Anthropic | Runs a direct edit without the planning queue. Aider receives your prompt and relevant JavaScript and JSX files. |
| React and Vite at `127.0.0.1:5773` | Serves the current app in an iframe inside the controller. Vite watches the files and updates the preview when they change. |
| Local filesystem | The active app lives in `generated-app/`. Saved snapshots live in `saved-apps/`. The queue lives in controller memory, so restarting it clears job status. |

Each clone has one active workspace. Browser tabs connected to the same controller see the same app and job queue. The controller runs its own queue worker, so you can use the app without starting the separate CLI utilities in `worker/`.

## Model providers

**Plan** uses OpenAI for both planning and edits. **Generate** uses Anthropic for direct edits. You can use **Plan** with just an OpenAI key. The controller currently selects the models in code.

Aider also supports Gemini, DeepSeek, OpenRouter, and local models through Ollama. Exposing those options in Voice Developer would require changing the controller to accept a model and load that provider’s settings. [Aider provider documentation](https://aider.chat/docs/llms.html)

## Data and local execution

Your prompt and relevant source code go to the model provider used for the action. How dictation audio is handled depends on your device and keyboard settings. Keep credentials and private data out of prompts and generated source.

Aider edits files under `generated-app/src/` and can create Git commits. **New App** and **Load App** replace the active source, so save changes you want to keep. Setup and some workspace actions run `npm install`, which can execute dependency scripts under your user account. Review generated changes and dependencies before reusing or distributing an app.

## Optional network access

Both services bind to loopback by default. To opt into access from a trusted network, set `VOICE_DEVELOPER_HOST` to the machine’s LAN address when running `./start.sh`. To use a phone, the phone needs a controller address it can reach and a redirect URI that Google accepts for that address. The loopback callback above is for a browser on the same computer.

The preview has no sign-in of its own. Keep both ports off the public internet and restrict network access to people you trust.

## TODO

- [ ] Try local code generation with [Aider and Ollama](https://aider.chat/docs/llms/ollama.html). Add an optional Ollama model for **Generate**, then try the same trivia-game prompts with the local model and the current Anthropic model. Start from the same app snapshot for each run. Record whether the preview builds, whether the requested changes work, how long each edit takes, and how many follow-up prompts it needs. Record the local model tag and hardware so others can repeat the experiment.

## License

[MIT](LICENSE)
