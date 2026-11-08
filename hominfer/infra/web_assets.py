"""Themes and shells the page can use, discovered from web_assets/ (see docs/theming.md)."""
import re

from .. import config

NAME = re.compile(r"[a-z0-9_-]{1,32}")


def themes():
    """Names of the extra themes: css/themes/<name>.css (auto, light and dark are built into tokens.css)."""
    found = (p.stem for p in (config.WEB_DIR / "css" / "themes").glob("*.css"))
    return sorted(n for n in found if NAME.fullmatch(n))


def shells():
    """Names of the shells: shells/<name>/shell.html."""
    found = (p.parent.name for p in (config.WEB_DIR / "shells").glob("*/shell.html"))
    return sorted(n for n in found if NAME.fullmatch(n))


def view_parts(shell, view):
    """Path parts (under web_assets/) of a view: the shell's own shells/<shell>/views/<view>.html, else the shared one."""
    own = ("shells", shell, "views", f"{view}.html")
    return own if config.WEB_DIR.joinpath(*own).is_file() else ("views", f"{view}.html")


def shell_script(shell):
    """URL of the shell's optional ES module (shells/<shell>/shell.js), or "" when it has none."""
    return f"/shells/{shell}/shell.js" if (config.WEB_DIR / "shells" / shell / "shell.js").is_file() else ""
