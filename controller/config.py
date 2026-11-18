import logging
import pathlib

from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).with_name(".env"))

REPO_ROOT = pathlib.Path(__file__).parent.parent
APP_ROOT = REPO_ROOT / "generated-app"
APP_SRC = APP_ROOT / "src"
# The blank app (tracked): setup.sh creates generated-app/ from it, New App resets src/ to it.
APP_TEMPLATE = REPO_ROOT / "app-template"
SAVED_APPS = REPO_ROOT / "saved-apps"
PLANS_DIR = REPO_ROOT / "plans"
logger = logging.getLogger("voice-developer")

DEFAULT_MAX_FILE_LINES = 150
