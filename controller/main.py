import os
import pathlib
import re
from contextlib import asynccontextmanager

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

APP_JSX_PATH = pathlib.Path(__file__).parent.parent / "generated-app" / "src" / "App.jsx"

SYSTEM_PROMPT = """You are an expert React developer.

The user will describe a UI or app they want. You must respond with ONLY the complete source code for a React component named `App`.

Rules:
- Return ONLY valid JSX/JavaScript. No markdown, no code fences, no explanations.
- The component must be a default export: `export default function App() { ... }`
- Use only inline styles (style={{ }}) or plain CSS classes. Do NOT import any CSS files.
- Tailwind CSS is available via CDN — you MAY use Tailwind classes.
- Do NOT import any external libraries. React hooks are available (useState, useEffect, etc.).
- The component must be completely self-contained.
- Keep it clean and visually polished.
- Start your response directly with the import statements or the function declaration."""


class GenerateRequest(BaseModel):
    prompt: str
    history: list[dict] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    APP_JSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="voice-developer controller", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/status")
def status():
    return {"status": "running"}


@app.get("/app")
def get_app():
    if not APP_JSX_PATH.exists():
        raise HTTPException(status_code=404, detail="App.jsx not found")
    return {"source": APP_JSX_PATH.read_text()}


@app.post("/generate")
def generate(req: GenerateRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    messages = []
    for entry in req.history:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": req.prompt})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e}")

    raw = response.content[0].text.strip()

    # Strip markdown code fences if Claude includes them despite instructions
    code = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
    code = re.sub(r"\n?```$", "", code, flags=re.MULTILINE).strip()

    APP_JSX_PATH.write_text(code)

    return {"status": "ok", "message": "App updated successfully"}
