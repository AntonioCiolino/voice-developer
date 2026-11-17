import pathlib
import subprocess

from controller import config


_BINARY_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2',
                '.ttf', '.eot', '.map', '.lock'}


def task_scope_files() -> list[pathlib.Path]:
    """The exact files handed to the coder: non-binary src/ files plus top-level config files."""
    files = [f for f in sorted(config.APP_SRC.rglob("*")) if f.is_file() and f.suffix not in _BINARY_EXTS]
    for extra in ["vite.config.js", "index.html", "package.json"]:
        p = config.APP_ROOT / extra
        if p.exists():
            files.append(p)
    return files


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
        "files": {f.relative_to(config.APP_ROOT).as_posix(): f.read_bytes() for f in task_scope_files()},
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
