import json
import re
import shutil
import subprocess

from fastapi import APIRouter, HTTPException

from controller import config
from controller.schemas import LoadAppRequest, SaveRequest

router = APIRouter()

# The name of the app in generated-app/ (set by Save and Load, cleared by New App), so the
# phone can show it and Save can default to it. Git ignored; survives a restart.
CURRENT_APP_PATH = config.REPO_ROOT / "controller" / "current-app.json"
_APP_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")


def app_slug(name: str) -> str:
    """The folder name for a saved app: lowercase, spaces to '-', letters, digits, '-' and '_' only."""
    slug = re.sub(r"\s+", "-", (name or "").strip().lower())[:50]
    if not _APP_NAME_RE.match(slug):
        raise HTTPException(status_code=400, detail="App name: use letters, digits, spaces, '-' or '_'")
    return slug


def saved_app_path(name: str):
    """The saved app folder for an existing name, never outside saved-apps/."""
    path = (config.SAVED_APPS / name).resolve()
    if path.parent != config.SAVED_APPS.resolve() or not path.is_dir():
        raise HTTPException(status_code=404, detail=f"App '{name}' not found")
    return path


def current_app_name() -> str | None:
    try:
        name = json.loads(CURRENT_APP_PATH.read_text()).get("name")
    except (OSError, ValueError, AttributeError):
        return None
    return name if isinstance(name, str) and _APP_NAME_RE.match(name) else None


def set_current_app(name: str | None) -> None:
    if name is None:
        CURRENT_APP_PATH.unlink(missing_ok=True)
    else:
        CURRENT_APP_PATH.write_text(json.dumps({"name": name}) + "\n")


@router.get("/current-app")
def get_current_app():
    return {"name": current_app_name()}



@router.post("/save")
def save_app(req: SaveRequest):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="App name required")

    name = app_slug(req.name)
    save_path = config.SAVED_APPS / name

    if save_path.exists() and not req.overwrite:
        raise HTTPException(status_code=409, detail=f"App '{name}' already exists. Save with overwrite=true to replace it.")

    config.SAVED_APPS.mkdir(parents=True, exist_ok=True)

    try:
        app_root = config.APP_ROOT

        # Ensure git history exists before saving
        git_dir = app_root / ".git"
        if not git_dir.exists():
            subprocess.run(["git", "init"], cwd=str(app_root), capture_output=True)
            subprocess.run(["git", "add", "."], cwd=str(app_root), capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial commit"],
                cwd=str(app_root),
                capture_output=True,
            )

        if save_path.exists():
            shutil.rmtree(save_path)

        # Copy entire generated-app (includes .git for history)
        shutil.copytree(app_root, save_path)
        set_current_app(name)
        return {
            "status": "ok",
            "message": f"App saved as '{name}'",
            "name": name,
            "path": str(save_path),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")


@router.get("/list-apps")
def list_apps():
    try:
        if not config.SAVED_APPS.exists():
            return {"status": "ok", "apps": []}
        apps = []
        for app_dir in config.SAVED_APPS.iterdir():
            if app_dir.is_dir():
                git_dir = app_dir / ".git"
                apps.append({
                    "name": app_dir.name,
                    "has_history": git_dir.exists(),
                })
        return {"status": "ok", "apps": sorted(apps, key=lambda x: x["name"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list apps: {str(e)}")


@router.post("/load-app")
def load_app(req: LoadAppRequest):
    app_path = saved_app_path(req.name)
    try:
        gen_app_path = config.APP_ROOT

        # Replace src contents without deleting the dir — keeps Vite's watcher alive
        src_dest = gen_app_path / "src"
        src_dest.mkdir(parents=True, exist_ok=True)
        for item in src_dest.iterdir():
            item.unlink() if item.is_file() else shutil.rmtree(item)
        saved_src = app_path / "src"
        if saved_src.exists():
            for item in saved_src.iterdir():
                dest = src_dest / item.name
                shutil.copy2(item, dest) if item.is_file() else shutil.copytree(item, dest)

        # Update top-level config files (never overwrite vite.config.js — it has server settings)
        for config_file in ["package.json", "index.html"]:
            saved_file = app_path / config_file
            if saved_file.exists():
                shutil.copy2(saved_file, gen_app_path / config_file)

        # Ensure React import exists in JSX files
        for jsx_file in ["App.jsx", "main.jsx"]:
            jsx_path = src_dest / jsx_file
            if jsx_path.exists():
                content = jsx_path.read_text()
                if 'import React' not in content:
                    lines = content.split('\n')
                    lines.insert(0, 'import React from "react";')
                    jsx_path.write_text('\n'.join(lines))

        # Install deps in case package.json changed
        subprocess.run(
            ["npm", "install"],
            cwd=str(gen_app_path),
            capture_output=True,
            timeout=60,
        )

        # Saved folders made before names were validated may not be valid names; show none then.
        set_current_app(req.name if _APP_NAME_RE.match(req.name) else None)
        return {"status": "ok", "message": f"Loaded app '{req.name}'", "name": current_app_name()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Load failed: {str(e)}")


@router.post("/revert")
def revert(count: int = 1):
    """Revert to a previous commit in generated-app."""
    app_root = config.APP_ROOT
    try:
        # Get the commit hash to revert to
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{count + 1}"],
            cwd=str(app_root),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise HTTPException(status_code=400, detail="Not enough commits to revert")

        lines = result.stdout.strip().split("\n")
        if len(lines) < count + 1:
            raise HTTPException(status_code=400, detail=f"Only {len(lines) - 1} commits available")

        target_commit = lines[count].split()[0]

        # Reset to that commit
        result = subprocess.run(
            ["git", "reset", "--hard", target_commit],
            cwd=str(app_root),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise HTTPException(status_code=502, detail="Failed to revert")

        return {
            "status": "ok",
            "message": f"Reverted {count} version(s)",
            "commit": target_commit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revert failed: {str(e)}")


@router.post("/new")
def new_app():
    try:
        # Remove all src files
        for f in config.APP_SRC.iterdir():
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                shutil.rmtree(f)

        # Create fresh main.jsx
        main_jsx = config.APP_SRC / "main.jsx"
        main_jsx.write_text("""import React, { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
""")

        # Create blank App.jsx
        app_jsx = config.APP_SRC / "App.jsx"
        app_jsx.write_text("""import React from "react";

export default function App() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">New App</h1>
        <p className="text-gray-600">Ready to build...</p>
      </div>
    </div>
  );
}
""")

        # Ensure npm dependencies are installed
        subprocess.run(
            ["npm", "install"],
            cwd=str(config.APP_ROOT),
            capture_output=True,
        )

        set_current_app(None)
        return {
            "status": "ok",
            "message": "Fresh app created — ready to generate",
            "name": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"New app failed: {str(e)}")
