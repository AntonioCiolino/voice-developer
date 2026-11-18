"""Post-task validation: production build and ESLint of the generated app.

Nothing here writes into the app: the build goes to a temporary output directory and
ESLint runs from controller/lint-tools with the app as its working directory.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
from typing import Callable

from controller import config
from controller.workspace import changed_task_paths

OUTPUT_TAIL_LIMIT = 3000
_LINT_SUFFIXES = (".js", ".jsx")


def lint_tools_dir() -> pathlib.Path:
    return config.REPO_ROOT / "controller" / "lint-tools"


def lint_targets(snapshot: dict) -> list[str]:
    """Changed or created src/ .js/.jsx files that still exist, relative to the app root."""
    return sorted(
        rel for rel in changed_task_paths(snapshot)
        if rel.startswith("src/") and rel.endswith(_LINT_SUFFIXES) and (config.APP_ROOT / rel).is_file()
    )


def _tail(text: str) -> str:
    return text.strip()[-OUTPUT_TAIL_LIMIT:]


def _run(command: list[str], timeout: int, label: str) -> tuple[bool, str]:
    env = {**os.environ, "PATH": str(pathlib.Path(command[0]).parent) + os.pathsep + os.environ.get("PATH", "")}
    try:
        result = subprocess.run(
            command, cwd=str(config.APP_ROOT), env=env, capture_output=True, text=True,
            timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"{label} timed out after {timeout} s (VALIDATION_TIMEOUT_SECONDS)"
    except OSError as exc:
        return False, f"{label} could not run: {exc}"
    output = _tail((result.stdout or "") + "\n" + (result.stderr or ""))
    return result.returncode == 0, output or f"{label} exited with code {result.returncode}"


def validate_app(snapshot: dict, checks: set[str], timeout: int, log: Callable[[str], None]) -> list[tuple[str, str]]:
    """Run the enabled checks; return (check, output) for each one that failed.

    Returns [] when everything passed or was skipped (no changed files, missing tools).
    Build and lint both run even if the first fails, so a retry sees both outputs.
    """
    if not checks:
        return []
    if not changed_task_paths(snapshot):
        log("Validation skipped: no files changed")
        return []
    node = shutil.which("node")
    failures: list[tuple[str, str]] = []
    if "build" in checks:
        vite = config.APP_ROOT / "node_modules" / ".bin" / "vite"
        if not node or not vite.exists():
            log("Validation skipped (build): node or node_modules missing, run ./setup.sh")
        else:
            log("Validating: build (vite)...")
            with tempfile.TemporaryDirectory(prefix="vd-build-") as out:
                ok, output = _run([str(vite), "build", "--outDir", out, "--emptyOutDir", "--logLevel", "warn"],
                                  timeout, "build")
            log("build passed" if ok else "build FAILED")
            if not ok:
                failures.append(("build", output))
    if "lint" in checks:
        targets = lint_targets(snapshot)
        tools = lint_tools_dir()
        eslint = tools / "node_modules" / ".bin" / "eslint"
        if not targets:
            log("Validation skipped (lint): no changed .js/.jsx files")
        elif not node or not eslint.exists():
            log("Validation skipped (lint): node or lint tools missing, run ./setup.sh")
        else:
            log(f"Validating: lint (eslint, {len(targets)} file(s))...")
            ok, output = _run([str(eslint), "-c", str(tools / "eslint.config.js"), "--no-warn-ignored", *targets],
                              timeout, "lint")
            log("lint passed" if ok else "lint FAILED")
            if not ok:
                failures.append(("lint", output))
    return failures
