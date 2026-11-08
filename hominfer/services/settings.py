"""User settings (settings.json, local), for every browser: UI language, theme, shell, models folder,
listen address, favourite models (listed first, shown by default on the dashboard)."""
import json
import re
from pathlib import Path

from .. import config, i18n
from ..errors import LaunchError
from ..i18n import tr
from ..infra import web_assets
from ..infra.files import read_json, write_atomic

DEFAULTS = {"lang": i18n.DEFAULT_LANG, "theme": "auto", "shell": "classic", "models_dir": config.DEFAULT_MODELS_DIR}
MAX_FAVORITES = 200


def theme_names():
    """Every theme the page offers: the built-in ones, then the files of css/themes/."""
    return ["auto", "light", "dark"] + web_assets.themes()


def shell_names():
    """Every shell the page offers: the folders of shells/."""
    return web_assets.shells()



def _favorites(value):
    """List of model ids, or None when it isn't one (ids as in models.json: word characters)."""
    if not isinstance(value, list) or len(value) > MAX_FAVORITES:
        return None
    if not all(isinstance(v, str) and re.fullmatch(r"\w{1,64}", v) for v in value):
        return None
    return list(dict.fromkeys(value))


def _folder(text):
    """'~/hominfer_models' -> Path, or None when it isn't an absolute path."""
    p = Path(str(text).strip()).expanduser()
    return p if str(text).strip() and p.is_absolute() else None


def _port(value):
    """Listen port, or None when it isn't an int (not a bool) in 1024..65535."""
    if isinstance(value, int) and not isinstance(value, bool) and 1024 <= value <= 65535:
        return value
    return None


def _lan(value):
    """LAN choice, or None when it isn't a bool."""
    return value if isinstance(value, bool) else None


class Settings:
    def __init__(self, path, *, models_busy=lambda: False):
        """models_busy: () -> True while something writes into the models folder (downloads)."""
        self.path, self.models_busy = path, models_busy
        s = DEFAULTS | read_json(path, {})
        self.values = {"lang": s["lang"] if s["lang"] in i18n.LOCALES else DEFAULTS["lang"],
                       "theme": s["theme"] if s["theme"] in theme_names() else DEFAULTS["theme"],
                       "shell": s["shell"] if s["shell"] in shell_names() else DEFAULTS["shell"],
                       "models_dir": s["models_dir"] if _folder(s["models_dir"]) else DEFAULTS["models_dir"],
                       "favorites": _favorites(s.get("favorites")) or [],
                       "port": _port(s.get("port")),
                       "lan": _lan(s.get("lan"))}
        i18n.set_lang(self.values["lang"])
        self.started = self.listen()  # address this run listens on; __main__ serves on it

    def models_dir(self):
        """The models folder (created if missing)."""
        p = _folder(self.values["models_dir"])
        p.mkdir(parents=True, exist_ok=True)
        return p

    def listen(self):
        """The address to listen on: the LAN choice and port from settings, else the environment."""
        lan = self.values["lan"]
        host = "0.0.0.0" if lan is True else "127.0.0.1" if lan is False else config.LISTEN_HOST
        return host, self.values["port"] or config.LISTEN_PORT

    def update(self, body):
        new = self.values | {k: str(body[k]).strip() for k in DEFAULTS if k in body}
        if "favorites" in body:
            new["favorites"] = _favorites(body["favorites"])
            if new["favorites"] is None:
                raise LaunchError(tr("settings.bad_favorites"))
        if "port" in body:
            raw = body["port"]
            if raw is None or str(raw).strip() == "":
                new["port"] = None
            else:
                try:
                    port = int(str(raw).strip())
                except ValueError:
                    raise LaunchError(tr("settings.bad_port"))
                if not 1024 <= port <= 65535:
                    raise LaunchError(tr("settings.bad_port"))
                new["port"] = port
        if "lan" in body:
            lan = body["lan"]
            if lan is not None and not isinstance(lan, bool):
                raise LaunchError(tr("settings.bad_lan"))
            new["lan"] = lan
        if new["lang"] not in i18n.LOCALES:
            raise LaunchError(tr("settings.bad_lang"))
        if new["theme"] not in theme_names():
            raise LaunchError(tr("settings.bad_theme"))
        if new["shell"] not in shell_names():
            raise LaunchError(tr("settings.bad_shell"))
        if new["models_dir"] != self.values["models_dir"]:
            self._check_models_dir(new["models_dir"])
        write_atomic(self.path, json.dumps(new, indent=2) + "\n")
        self.values = new
        i18n.set_lang(new["lang"])

    def _check_models_dir(self, text):
        folder = _folder(text)
        if not folder:
            raise LaunchError(tr("settings.bad_models_dir"))
        if self.models_busy():
            raise LaunchError(tr("settings.models_busy"))
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise LaunchError(tr("settings.models_dir_error", err=e.strerror or e))
