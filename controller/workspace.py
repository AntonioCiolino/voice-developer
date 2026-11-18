import os
import pathlib
import re
import subprocess

from controller import config


_BINARY_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2',
                '.ttf', '.eot', '.map', '.lock'}


_CONFIG_FILES = ("vite.config.js", "index.html", "package.json")
_CODE_EXTS = (".jsx", ".js", ".tsx", ".ts")
_IMPORT_RE = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['"]([^'"]+)['"]""")


def snapshot_scope_files() -> list[pathlib.Path]:
    """Every file a task could change, which the revert snapshot and the commit cover.

    All non-binary src/ files plus the top-level config files. This stays the same no
    matter which files a task hands the coder: the coder may touch or create other
    files under src/, and index.html/package.json/vite.config.js stay covered so a
    stray edit there is reverted too. New src/ files are handled by snapshot_task_scope.
    """
    files = [f for f in sorted(config.APP_SRC.rglob("*")) if f.is_file() and f.suffix not in _BINARY_EXTS]
    for extra in _CONFIG_FILES:
        p = config.APP_ROOT / extra
        if p.exists():
            files.append(p)
    return files


def _resolve_import(importer: pathlib.Path, spec: str) -> set[pathlib.Path]:
    """Candidate files a relative import specifier can point at (extension/index resolution)."""
    base = pathlib.Path(os.path.normpath(importer.parent / spec))
    candidates = {base}
    candidates.update(base.with_name(base.name + ext) for ext in _CODE_EXTS)
    candidates.update(base / ("index" + ext) for ext in _CODE_EXTS)
    return candidates


def importers_of(named: list[pathlib.Path]) -> list[pathlib.Path]:
    """src/ files that directly import one of the named files (one level, relative imports)."""
    targets = {pathlib.Path(os.path.normpath(p)) for p in named}
    found = []
    for f in sorted(config.APP_SRC.rglob("*")):
        if not f.is_file() or f.suffix not in _CODE_EXTS or f in named:
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for spec in _IMPORT_RE.findall(text):
            if spec.startswith(".") and _resolve_import(f, spec) & targets:
                found.append(f)
                break
    return found


def task_scope_files(task_files: list[str] | None = None) -> list[pathlib.Path]:
    """The files handed to the coder for one task.

    task_files are the paths the task names (planning.parse_task_files), relative to the
    app root. The coder gets those, including ones that do not exist yet (Aider creates
    them), plus the existing src/ files that directly import them, so wiring a new module
    into App.jsx works when the task names App.jsx and editing a module also shows its
    caller. Aider's repo map still outlines the rest. With no task_files (the task names
    no file) it falls back to the whole snapshot scope, which is the earlier behavior.
    """
    if not task_files:
        return snapshot_scope_files()
    named = [config.APP_ROOT / rel for rel in task_files]
    files = list(named)
    for f in importers_of([p for p in named if p.exists()]):
        if f not in files:
            files.append(f)
    return files


def imports_of(files: list[pathlib.Path]) -> list[pathlib.Path]:
    """Existing src/ files that the given files import directly (one level, relative imports)."""
    found = []
    for f in files:
        if not f.is_file() or f.suffix not in _CODE_EXTS:
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for spec in _IMPORT_RE.findall(text):
            if not spec.startswith("."):
                continue
            for candidate in sorted(_resolve_import(f, spec)):
                if candidate.is_file() and config.APP_SRC in candidate.parents and candidate not in found:
                    found.append(candidate)
                    break
    return found


# Read-only reference files per task: enough for a few small modules, small enough for a local model.
REFERENCE_MAX_FILES = 8
REFERENCE_MAX_BYTES = 24_000


def reference_files(editable: list[pathlib.Path], earlier_task_files: list[str]) -> list[pathlib.Path]:
    """Files the coder may read but not edit for one task, so it uses their real names and APIs.

    The files the editable ones import, then the files earlier tasks of the same plan named
    (newest task first). Without them a task that creates a new file sees none of the
    modules earlier tasks just wrote, and guesses their exports (e.g. expecting `hud` from
    a hook that returns `status`). Only existing src/ files, none of the editable ones, at
    most REFERENCE_MAX_FILES files and REFERENCE_MAX_BYTES bytes in total.
    """
    editable_set = {pathlib.Path(os.path.normpath(p)) for p in editable}
    candidates = imports_of(editable)
    for rel in reversed(earlier_task_files):
        candidates.append(config.APP_ROOT / rel)
    chosen, total = [], 0
    for f in candidates:
        f = pathlib.Path(os.path.normpath(f))
        if f in editable_set or f in chosen or not f.is_file() or config.APP_SRC not in f.parents:
            continue
        size = f.stat().st_size
        if size == 0 or total + size > REFERENCE_MAX_BYTES:
            continue
        chosen.append(f)
        total += size
        if len(chosen) >= REFERENCE_MAX_FILES:
            break
    return chosen


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(config.APP_ROOT), capture_output=True, text=True)


def snapshot_task_scope() -> dict:
    """Capture file contents and the app repo HEAD before a task runs."""
    head = None
    if (config.APP_ROOT / ".git").exists():
        result = git("rev-parse", "HEAD")
        if result.returncode == 0:
            head = result.stdout.strip() or None
    return {
        "files": {f.relative_to(config.APP_ROOT).as_posix(): f.read_bytes() for f in snapshot_scope_files()},
        "src_files": {f.relative_to(config.APP_ROOT).as_posix() for f in config.APP_SRC.rglob("*") if f.is_file()},
        "head": head,
    }


def revert_task(snapshot: dict) -> str:
    """Undo one task's changes: only snapshotted files and new src/ files, never the whole app."""
    notes = []
    old_head = snapshot.get("head")
    if old_head:
        current = git("rev-parse", "HEAD")
        new_head = current.stdout.strip() if current.returncode == 0 else ""
        if new_head and new_head != old_head and git("merge-base", "--is-ancestor", old_head, new_head).returncode == 0:
            if git("reset", "--mixed", old_head).returncode == 0:
                notes.append("moved the app repo HEAD back to the previous step")
    for f in list(config.APP_SRC.rglob("*")):
        if f.is_file() and f.relative_to(config.APP_ROOT).as_posix() not in snapshot["src_files"]:
            f.unlink()
            notes.append(f"removed new file {f.relative_to(config.APP_ROOT).as_posix()}")
    for rel, data in snapshot["files"].items():
        path = config.APP_ROOT / rel
        if not path.exists() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            notes.append(f"restored {rel}")
    return "; ".join(notes)


def changed_task_paths(snapshot: dict) -> list[str]:
    """Paths (relative to config.APP_ROOT) that a task changed, created, or deleted."""
    changed = []
    for rel, data in snapshot["files"].items():
        path = config.APP_ROOT / rel
        if not path.exists() or path.read_bytes() != data:
            changed.append(rel)
    for f in config.APP_SRC.rglob("*"):
        rel = f.relative_to(config.APP_ROOT).as_posix()
        if f.is_file() and rel not in snapshot["src_files"]:
            changed.append(rel)
    return changed


def over_limit_files(snapshot: dict, max_lines: int) -> list[tuple[str, int]]:
    """(path, line count) for text files this task changed or created that exceed max_lines.

    Only files the task touched are checked, so an old oversized file the task did not
    edit is not blamed on it. package.json and index.html are exempt (not code modules).
    """
    over = []
    for rel in changed_task_paths(snapshot):
        if not rel.startswith("src/"):
            continue
        path = config.APP_ROOT / rel
        if not path.is_file() or path.suffix in _BINARY_EXTS:
            continue
        lines = len(path.read_text(errors="ignore").splitlines())
        if lines > max_lines:
            over.append((rel, lines))
    return over


def commit_task(snapshot: dict, message: str) -> str:
    """Commit only the files this task changed, with a controller-written message."""
    if not (config.APP_ROOT / ".git").exists():
        return "no app repo, nothing committed"
    paths = changed_task_paths(snapshot)
    if not paths:
        return "no file changes to commit"
    added = git("add", "-A", "--", *paths)
    if added.returncode != 0:
        return f"commit skipped: git add failed: {added.stderr.strip()[-300:]}"
    committed = git("commit", "-q", "-m", message, "--", *paths)
    if committed.returncode != 0:
        return f"commit skipped: {(committed.stderr or committed.stdout).strip()[-300:]}"
    return f"committed {len(paths)} file(s)"


def commit_app_files(message: str) -> str:
    """Commit everything under src/ plus index.html and package.json (after New App or Load).

    Both replace the app's files wholesale. Without a commit, git still lists the old
    files, Aider's repo map warns about each one ("deleted from the file system but not
    from git?") and the next task's commit starts from the wrong base.
    """
    if not (config.APP_ROOT / ".git").exists():
        return "no app repo, nothing committed"
    paths = ["src"] + [p for p in ("index.html", "package.json") if (config.APP_ROOT / p).exists()]
    added = git("add", "-A", "--", *paths)
    if added.returncode != 0:
        return f"commit skipped: git add failed: {added.stderr.strip()[-300:]}"
    if not git("diff", "--cached", "--name-only", "--", *paths).stdout.strip():
        return "no file changes to commit"
    committed = git("commit", "-q", "-m", message, "--", *paths)
    if committed.returncode != 0:
        return f"commit skipped: {(committed.stderr or committed.stdout).strip()[-300:]}"
    return "committed"


_APP_IGNORES = ("node_modules/", "dist/", ".vite/", ".DS_Store")


def ensure_app_repo_hygiene() -> str:
    """Keep build artifacts out of the app repo so Aider does not scan thousands of files."""
    if not (config.APP_ROOT / ".git").exists():
        return ""
    gitignore = config.APP_ROOT / ".gitignore"
    existing = gitignore.read_text().splitlines() if gitignore.exists() else []
    missing = [p for p in _APP_IGNORES if p not in existing]
    if missing:
        text = "\n".join(existing + missing).strip("\n") + "\n"
        gitignore.write_text(text)
    tracked = [p.rstrip("/") for p in _APP_IGNORES if git("ls-files", "--", p.rstrip("/")).stdout.strip()]
    if tracked:
        git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *tracked)
    if not missing and not tracked:
        return ""
    git("add", "--", ".gitignore")
    # Commit the index without a pathspec: a pathspec commit would re-stage the
    # ignored files from the working tree and undo the `rm --cached`.
    result = git("commit", "-q", "-m", "chore: stop tracking build artifacts")
    return "untracked build artifacts" if result.returncode == 0 else ""
