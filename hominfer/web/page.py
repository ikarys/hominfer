"""The HTML shell of every view, in the UI language: {{t:key}} replaced by the text (no flash of
untranslated text), plus the settings and texts the page's JS needs."""
import html
import importlib.metadata
import json
import re
import subprocess

from .. import config, i18n
from ..services.settings import THEMES

VIEWS = ("/", "/index.html", "/models", "/modeles", "/settings")  # /modeles: old address of /models
_TEXT = re.compile(r"\{\{t:([\w.]+)\}\}")


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
    boot = {"lang": lang, "theme": theme, "models_dir": settings.values["models_dir"], "favorites": settings.values["favorites"], "themes": THEMES,
            "langs": {code: texts.get("lang.name", code) for code, texts in i18n.LOCALES.items()},
            "strings": i18n.LOCALES[i18n.DEFAULT_LANG] | i18n.LOCALES.get(lang, {})}
    page = (config.WEB_DIR / "index.html").read_text()
    page = _TEXT.sub(lambda m: html.escape(i18n.tr(m[1])), page)
    page = (page.replace("{{LANG}}", lang).replace("{{THEME}}", theme)
            .replace("{{BUILD}}", html.escape(BUILD)).replace("{{BUILD_DATE}}", html.escape(BUILD_DATE))
            .replace("{{BOOT}}", json.dumps(boot, ensure_ascii=False).replace("</", "<\\/")))
    return page.encode()
