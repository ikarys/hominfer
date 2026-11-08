"""Paths and environment settings (read once at startup)."""
import os
import shutil
from pathlib import Path

PKG = Path(__file__).resolve().parent  # bundled assets: page, locales, catalog
HOME = Path.home()

# localhost only by default; set HOMINFER_HOST=0.0.0.0 to reach the page from the LAN
LISTEN_HOST = os.environ.get("HOMINFER_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("HOMINFER_PORT", "8090"))
# extra host names the page may be reached by (comma-separated); IPs, localhost and this machine's name always pass
ALLOWED_HOSTS = {h.strip().lower() for h in os.environ.get("HOMINFER_ALLOWED_HOSTS", "").split(",") if h.strip()}

DEFAULT_MODELS_DIR = os.environ.get("HOMINFER_MODELS_DIR", "~/hominfer_models")  # changed in Settings

_XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
_XDG_STATE = Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local" / "state")

# engines.json, models.json, settings.json: local, never versioned
CONFIG_DIR = Path(os.environ.get("HOMINFER_CONFIG_DIR") or _XDG_CONFIG / "hominfer").expanduser()
STATS_FILE = Path(os.environ.get("HOMINFER_STATS_FILE") or _XDG_STATE / "hominfer" / "stats.json").expanduser()
LOG_DIR = Path(os.environ.get("HOMINFER_LOG_DIR") or _XDG_STATE / "hominfer" / "logs").expanduser()
ENGINES_FILE = CONFIG_DIR / "engines.json"
MODELS_FILE = CONFIG_DIR / "models.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
LOCALES_DIR = PKG / "locales"
CATALOG_DIR = PKG / "catalog"
WEB_DIR = PKG / "web_assets"  # the page: index.html, css/, js/

POLL_S = 2.0
# VRAM used by the display (Windows) and WSL with no model loaded; replaced by the real value
# as soon as the GPU is seen with no compute process
DEFAULT_BASELINE_MIB = 1500


def migrate_legacy_config() -> None:
    """Copy the JSON files a git checkout kept next to the code into CONFIG_DIR (once)."""
    legacy = PKG.parent
    if "HOMINFER_CONFIG_DIR" in os.environ or legacy == CONFIG_DIR:
        return
    for name in (ENGINES_FILE.name, MODELS_FILE.name, SETTINGS_FILE.name):
        src, dst = legacy / name, CONFIG_DIR / name
        if src.is_file() and not dst.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
