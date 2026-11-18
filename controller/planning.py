import re

from controller import config


_HEADING_RE = re.compile(r"^\s*#{1,6}\s")
_TASKS_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(\d+[.)]\s*)?tasks?\s*:?\s*$", re.IGNORECASE)
_TASK_LINE_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$")


def parse_tasks(plan_text: str) -> list[str]:
    """Extract the clean task list: only the Tasks section, outside code fences, deduplicated."""
    lines = (plan_text or "").splitlines()

    def numbered(section: list[str]) -> list[str]:
        found, in_fence = [], False
        for line in section:
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = _TASK_LINE_RE.match(line)
            if match:
                text = match.group(1).strip()
                if text and text not in found:
                    found.append(text)
        return found

    def until_heading(section: list[str]) -> list[str]:
        out, in_fence = [], False
        for line in section:
            if line.strip().startswith("```"):
                in_fence = not in_fence
            elif not in_fence and _HEADING_RE.match(line):
                break
            out.append(line)
        return out

    for idx, line in enumerate(lines):
        if _TASKS_HEADING_RE.match(line):
            return numbered(until_heading(lines[idx + 1:]))
    return numbered(until_heading(lines))


def planner_user_msg(prompt: str) -> str:
    """Build the planner user message including current app code for context."""
    msg = prompt
    # Attach current src files so planner knows what already exists
    src_snippets = []
    binary_exts = {'.png','.jpg','.jpeg','.gif','.ico','.svg','.woff','.woff2','.ttf','.eot','.map','.lock'}
    for f in sorted(config.APP_SRC.rglob("*")):
        if f.is_file() and f.suffix not in binary_exts:
            try:
                content = f.read_text(errors='ignore')
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                # App-relative (src/...), matching the [files: ...] paths the planner must write.
                src_snippets.append(f"### {f.relative_to(config.APP_ROOT).as_posix()}\n```\n{content}\n```")
            except Exception:
                pass
    if src_snippets:
        msg += "\n\n---\nCurrent app code for context:\n\n" + "\n\n".join(src_snippets)
    return msg


_TASK_FILES_RE = re.compile(r"[\[(]\s*files?\s*:\s*([^\])]*)[\])]", re.IGNORECASE)
_CONFIG_FILES = ("index.html", "package.json", "vite.config.js")
_BINARY_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2',
                '.ttf', '.eot', '.map', '.lock'}


def parse_task_files(task: str) -> list[str]:
    """File paths a task names, relative to the app root (generated-app/).

    The planner writes them at the end of the task as `[files: src/A.jsx, src/App.jsx]`
    (`(files: ...)` is accepted too). Only paths under src/ and the app's index.html,
    package.json and vite.config.js are kept; absolute paths, `..`, binary assets and
    anything else are dropped. Paths need not exist yet: a new file the task creates is
    named the same way. Order is kept, duplicates removed. An empty list means the task
    names no usable file, and the caller falls back to the whole src/ tree.
    """
    found: list[str] = []
    for match in _TASK_FILES_RE.finditer(task or ""):
        for raw in re.split(r"[,\s]+", match.group(1)):
            path = raw.strip("`'\"")
            if path.startswith("generated-app/"):
                path = path[len("generated-app/"):]
            if path.startswith("./"):
                path = path[2:]
            parts = path.split("/")
            if not path or path.startswith("/") or ".." in parts or "" in parts or "\\" in path:
                continue
            if not (path.startswith("src/") or path in _CONFIG_FILES):
                continue
            if "." in parts[-1] and "." + parts[-1].rsplit(".", 1)[1].lower() in _BINARY_EXTS:
                continue
            if path not in found:
                found.append(path)
    return found


def planner_system_prompt(max_lines: int = config.DEFAULT_MAX_FILE_LINES) -> str:
    return PLANNER_SYSTEM_PROMPT.replace("{MAX_LINES}", str(max_lines))


PLANNER_SYSTEM_PROMPT = """You are a software architect planning tasks for a pure React + Vite SPA.

ARCHITECTURE CONSTRAINTS (never violate these):
- Pure React frontend only. No backend server (no express, fastapi, next.js, etc.)
- All code lives in src/ as JSX/JS files
- SMALL FILES: one component or module per file, each file under {MAX_LINES} lines. The coder is a small model that cannot reliably edit large files.
- New features go in NEW files (e.g. src/components/Timer.jsx, src/hooks/useTimer.js) that are then wired into src/App.jsx with an import and a few lines. Do not add feature code to src/App.jsx or to any file that is already near {MAX_LINES} lines.
- No public/ folder, no JSON config files, no static assets unless creating them in src/
- Tailwind CSS via CDN in index.html — use className with Tailwind classes
- All data must be hardcoded in JS/JSX or fetched from external public APIs
- Tasks are executed by aider which reads the provided src/ files — keep tasks self-contained

OUTPUT FORMAT (use only these sections, never repeat the plan or add other sections, no code):

FOR SIMPLE REQUESTS (rename, small fix, minor change), output only:
## Tasks
1) Task name [files: src/...]
2) Task name [files: src/...]

FOR COMPLEX REQUESTS (new feature, refactor, system redesign), output only:
## 1) Requirements
...
## 2) Architecture
...
## 3) Tasks
1) Task name [files: src/...]
2) Task name [files: src/...]
## 4) Acceptance Criteria
...

List each task exactly once, in the Tasks section, as "1) Task name [files: src/path/File.jsx, src/App.jsx]".
Every task ends with a [files: ...] list of the src/ files it creates or edits, comma separated, paths relative to the app root, normally one to three files. Name a file that does not exist yet if the task creates it. A task that wires a new module into the app names src/App.jsx as well. Each task touches only the files it lists.
Do not include code snippets or a second copy of the task list. Keep tasks concrete and self-contained. Never plan tasks that require files outside src/."""
