import json
from pathlib import Path

import pytest

from hominfer import config, i18n
from hominfer.errors import LaunchError
from hominfer.services.settings import DEFAULTS, Settings


@pytest.fixture
def path(tmp_path):
    return tmp_path / "settings.json"


def test_defaults_without_a_file(path):
    s = Settings(path)
    assert s.values == DEFAULTS | {"favorites": [], "port": None, "lan": None}
    assert s.models_dir() == Path(DEFAULTS["models_dir"]).expanduser()


def test_update_writes_the_file_and_the_language(path, tmp_path):
    s = Settings(path)
    s.update({"lang": "fr", "theme": "cyber", "models_dir": str(tmp_path / "models")})
    assert json.loads(path.read_text()) == s.values and i18n.lang() == "fr"
    assert s.models_dir().is_dir()  # created
    assert Settings(path).values == s.values  # read back


def test_models_dir_accepts_home_paths(path):
    s = Settings(path)
    s.update({"models_dir": "~/hominfer_models"})
    assert s.models_dir() == Path.home() / "hominfer_models"


@pytest.mark.parametrize("change, message", [
    ({"lang": "xx"}, "Unknown language"),
    ({"theme": "pink"}, "Unknown theme"),
    ({"shell": "pink"}, "Unknown layout"),
    ({"models_dir": "relative/models"}, "absolute path"),
    ({"models_dir": "  "}, "absolute path"),
    ({"favorites": "qwen"}, "list of model ids"),
    ({"favorites": ["../x"]}, "list of model ids"),
    ({"favorites": [1]}, "list of model ids"),
    ({"port": "80"}, "between 1024"),
    ({"port": "abc"}, "between 1024"),
    ({"port": "70000"}, "between 1024"),
    ({"lan": "yes"}, "true or false"),
])
def test_update_rejects(path, change, message):
    s = Settings(path)
    with pytest.raises(LaunchError, match=message):
        s.update(change)
    assert not path.exists()


def test_models_dir_cant_move_during_a_download(path, tmp_path):
    s = Settings(path, models_busy=lambda: True)
    with pytest.raises(LaunchError, match="download is running"):
        s.update({"models_dir": str(tmp_path / "elsewhere")})
    s.update({"theme": "neo"})  # other settings still change


def test_invalid_file_values_fall_back_to_defaults(path):
    path.write_text(json.dumps({"lang": "xx", "theme": "pink", "shell": "pink", "models_dir": "relative"}))
    assert Settings(path).values == DEFAULTS | {"favorites": [], "port": None, "lan": None}


def test_favorites_are_saved_without_duplicates(path):
    s = Settings(path)
    s.update({"favorites": ["qwen", "gemma", "qwen"]})
    assert Settings(path).values["favorites"] == ["qwen", "gemma"]
    path.write_text(json.dumps({"favorites": "bad"}))
    assert Settings(path).values["favorites"] == []


def test_listen_follows_settings_over_environment(path, monkeypatch):
    monkeypatch.setattr(config, "LISTEN_HOST", "10.0.0.5")
    monkeypatch.setattr(config, "LISTEN_PORT", 9999)
    s = Settings(path)
    assert s.listen() == ("10.0.0.5", 9999)
    s.update({"port": "9100", "lan": True})
    assert s.listen() == ("0.0.0.0", 9100)
    assert Settings(path).values["port"] == 9100
    assert Settings(path).values["lan"] is True
    s.update({"lan": False, "port": ""})
    assert s.listen() == ("127.0.0.1", 9999)


def test_started_keeps_the_address_of_this_run(path):
    s = Settings(path)
    before = s.started
    s.update({"port": "9200"})
    assert s.started == before
    assert s.listen()[1] == 9200
