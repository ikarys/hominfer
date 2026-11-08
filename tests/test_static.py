import pytest

from hominfer.web import static


def test_assets_with_their_type():
    assert static.find("/js/main.js")[1].startswith("text/javascript")
    assert static.find("/css/themes/cyber.css")[1].startswith("text/css")
    assert static.find("/shells/classic/shell.css")[1].startswith("text/css")


@pytest.mark.parametrize("path", ["/../engines.json", "/css/../../hominfer/config.py", "/nope.js", "/js",
                                  "/index.html", "/shells/classic/shell.html", "/views/home.html",
                                  "/shells/../../config.py", "/css/themes/../../../config.py"])
def test_nothing_outside_web_missing_or_not_an_asset(path):
    assert static.find(path) is None


def test_etag_changes_with_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(static.config, "WEB_DIR", tmp_path)
    f = tmp_path / "a.js"
    f.write_text("1")
    first = static.find("/a.js")[2]
    f.write_text("22")
    assert static.find("/a.js")[2] != first
