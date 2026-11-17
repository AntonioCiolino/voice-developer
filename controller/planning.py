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
                src_snippets.append(f"### {f.relative_to(config.REPO_ROOT)}\n```\n{content}\n```")
            except Exception:
                pass
    if src_snippets:
        msg += "\n\n---\nCurrent app code for context:\n\n" + "\n\n".join(src_snippets)
    return msg


PLANNER_SYSTEM_PROMPT = """You are a software architect planning tasks for a pure React + Vite SPA.

ARCHITECTURE CONSTRAINTS (never violate these):
- Pure React frontend only. No backend server (no express, fastapi, next.js, etc.)
- All code lives in src/ as JSX/JS files
- No public/ folder, no JSON config files, no static assets unless creating them in src/
- Tailwind CSS via CDN in index.html — use className with Tailwind classes
- All data must be hardcoded in JS/JSX or fetched from external public APIs
- Tasks are executed by aider which reads the provided src/ files — keep tasks self-contained

OUTPUT FORMAT (use only these sections, never repeat the plan or add other sections, no code):

FOR SIMPLE REQUESTS (rename, small fix, minor change), output only:
## Tasks
1) Task name
2) Task name

FOR COMPLEX REQUESTS (new feature, refactor, system redesign), output only:
## 1) Requirements
...
## 2) Architecture
...
## 3) Tasks
1) Task name
2) Task name
## 4) Acceptance Criteria
...

List each task exactly once, in the Tasks section, as "1) Task name", "2) Task name", etc.
Do not include code snippets or a second copy of the task list. Keep tasks concrete and self-contained. Never plan tasks that require files outside src/."""
