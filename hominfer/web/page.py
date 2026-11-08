"""The page, in the UI language: index.html + the chosen shell + the views and dialogs, {{t:key}} replaced by
the text (no flash of untranslated text), plus the settings and texts the page's JS needs."""
import html
import importlib.metadata
import json
import re
import subprocess
from functools import cache

from .. import config, i18n
from ..infra import web_assets
from ..services.settings import shell_names, theme_names

VIEWS = ("/", "/index.html", "/models", "/modeles", "/settings")  # /modeles: old address of /models
_TEXT = re.compile(r"\{\{t:([\w.]+)\}\}")
_BUILT_IN_THEMES = ("auto", "light", "dark")  # in tokens.css: no stylesheet of their own
_VIEW_FILES = ("home", "manage", "settings")


@cache
def _read(*parts):
    """A file of web_assets/, read once."""
    return config.WEB_DIR.joinpath(*parts).read_text()


def _css(url):
    return f'<link rel="stylesheet" href="{url}">'


def _git(args):
    try:
        proc = subprocess.run(("git", *args), cwd=config.PKG.parent, capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _version():
    try:
        return "v" + importlib.metadata.version("hominfer"), ""
    except importlib.metadata.PackageNotFoundError:
        return "", ""


def _build_info():
    if not (config.PKG.parent / ".git").exists():  # installed package: no checkout to describe
        return _version()
    count = _git(["rev-list", "--count", "HEAD"])
    short = _git(["rev-parse", "--short", "HEAD"])
    date = _git(["log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M"])
    dirty = _git(["status", "--porcelain"])
    if not count or not short or not date or dirty is None:
        return _version()
    if dirty:
        short += "-dirty"
    return f"build {count} · {short}", date


BUILD, BUILD_DATE = _build_info()


def render(settings):
    lang, theme = settings.values["lang"], settings.values["theme"]
    shell = settings.values["shell"]
    boot = {"lang": lang, "theme": theme, "shell": shell, "themes": theme_names(), "shells": shell_names(),
            "shell_js": web_assets.shell_script(shell),
            "models_dir": settings.values["models_dir"], "favorites": settings.values["favorites"],
            "langs": {code: texts.get("lang.name", code) for code, texts in i18n.LOCALES.items()},
            "strings": i18n.LOCALES[i18n.DEFAULT_LANG] | i18n.LOCALES.get(lang, {})}
    views = "".join(_read(*web_assets.view_parts(shell, v)) for v in _VIEW_FILES)
    page = (_read("index.html").replace("{{SHELL}}", _read("shells", shell, "shell.html"))
            .replace("{{VIEWS}}", views).replace("{{DIALOGS}}", _read("views", "dialogs.html")))
    page = _TEXT.sub(lambda m: html.escape(i18n.tr(m[1])), page)
    builtin = theme in _BUILT_IN_THEMES
    page = (page.replace("{{LANG}}", lang)
            .replace("{{THEME_ATTR}}", "" if theme == "auto" else f' data-theme="{theme}"')
            .replace("{{THEME_CSS}}", "" if builtin else _css(f"/css/themes/{theme}.css"))
            .replace("{{SHELL_CSS}}", _css(f"/shells/{shell}/shell.css"))
            .replace("{{BUILD}}", html.escape(BUILD)).replace("{{BUILD_DATE}}", html.escape(BUILD_DATE))
            .replace("{{BOOT}}", json.dumps(boot, ensure_ascii=False).replace("</", "<\\/")))
    return page.encode()
