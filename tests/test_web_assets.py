"""Themes and shells: discovery, settings validation, and the contract every shell must keep (docs/theming.md)."""
import re

import pytest

from hominfer import config, i18n
from hominfer.infra import web_assets
from hominfer.services.settings import Settings, theme_names
from hominfer.web import page
from tests.test_page import FakeSettings

# what the scripts look up in the page, whatever the shell
REQUIRED = ["{{VIEWS}}", 'id="conn"', *(f'data-view="{v}"' for v in ("home", "manage", "settings", "stats"))]


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WEB_DIR", tmp_path)
    return tmp_path


def test_discovery_keeps_valid_names_only(web):
    (web / "css/themes").mkdir(parents=True)
    for name in ("zed.css", "alpha.css", "Bad.css", "x y.css", "a" * 33 + ".css", "notes.txt"):
        (web / "css/themes" / name).write_text("")
    for name in ("one", "Two", "t.w"):
        (web / "shells" / name).mkdir(parents=True)
        (web / "shells" / name / "shell.html").write_text("")
    (web / "shells/empty").mkdir()
    assert web_assets.themes() == ["alpha", "zed"]
    assert web_assets.shells() == ["one"]
    assert theme_names() == ["auto", "light", "dark", "alpha", "zed"]


def test_unknown_theme_or_shell_falls_back_when_a_file_is_removed(web, tmp_path):
    (web / "css/themes").mkdir(parents=True)
    (web / "css/themes/gone.css").write_text("")
    (web / "shells/mine").mkdir(parents=True)
    (web / "shells/mine/shell.html").write_text("")
    path = tmp_path / "settings.json"
    s = Settings(path)
    s.update({"theme": "gone", "shell": "mine"})
    assert Settings(path).values["theme"] == "gone" and Settings(path).values["shell"] == "mine"
    (web / "css/themes/gone.css").unlink()
    (web / "shells/mine/shell.html").unlink()
    assert Settings(path).values["theme"] == "auto" and Settings(path).values["shell"] == "classic"


def test_there_is_at_least_the_classic_shell_and_the_known_themes():
    assert "classic" in web_assets.shells()
    assert {"cyber", "pixel", "neo"} <= set(web_assets.themes())


@pytest.mark.parametrize("lang", list(i18n.LOCALES))
def test_every_theme_and_shell_has_its_label(lang):
    keys = [f"ui.theme.{n}" for n in theme_names()] + [f"ui.shell.{n}" for n in web_assets.shells()]
    assert [k for k in keys if k not in i18n.LOCALES[lang]] == []


@pytest.mark.parametrize("theme", web_assets.themes())
def test_themes_scope_every_rule_under_their_name(theme):
    css = (config.WEB_DIR / "css/themes" / f"{theme}.css").read_text()
    css = re.sub(r"/\*.*?\*/|@import[^;]*;", "", css, flags=re.S)
    for selectors in re.findall(r"(?:^|\})\s*([^{}@]+)\{", css):
        for sel in selectors.split(","):
            assert f'[data-theme="{theme}"]' in sel, sel.strip()


@pytest.mark.parametrize("shell", web_assets.shells())
def test_shell_keeps_the_contract(shell):
    html = (config.WEB_DIR / "shells" / shell / "shell.html").read_text()
    assert (config.WEB_DIR / "shells" / shell / "shell.css").is_file()
    assert [r for r in REQUIRED if r not in html] == []
    assert "style=" not in html


@pytest.mark.parametrize("theme", ["auto", "light", "dark", *web_assets.themes()])
@pytest.mark.parametrize("shell", web_assets.shells())
def test_page_renders_with_each_theme_and_shell(shell, theme):
    out = page.render(FakeSettings("en", theme, shell)).decode()
    assert "{{" not in out and "style=" not in out
    assert f'href="/shells/{shell}/shell.css"' in out
    assert ("data-theme" in re.search(r"<html[^>]*>", out)[0]) == (theme != "auto")
    assert (f"/css/themes/{theme}.css" in out) == (theme in web_assets.themes())
    for ident in ("cards", "cfgTable", "setTheme", "setShell", "modelDlg", "folderDlg"):
        assert f'id="{ident}"' in out


def test_view_override_falls_back_to_the_shared_view(web):
    (web / "shells/mine/views").mkdir(parents=True)
    (web / "shells/mine/views/home.html").write_text("")
    assert web_assets.view_parts("mine", "home") == ("shells", "mine", "views", "home.html")
    assert web_assets.view_parts("mine", "manage") == ("views", "manage.html")


def test_shell_script_only_when_present(web):
    (web / "shells/mine").mkdir(parents=True)
    assert web_assets.shell_script("mine") == ""
    (web / "shells/mine/shell.js").write_text("")
    assert web_assets.shell_script("mine") == "/shells/mine/shell.js"
