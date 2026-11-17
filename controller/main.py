"""Entry point kept for `uvicorn main:app --app-dir controller` (see start.sh)."""
import pathlib
import sys

if not __package__:
    # Started as the top-level module `main`: make the `controller` package importable.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from controller.app import app  # noqa: E402,F401
