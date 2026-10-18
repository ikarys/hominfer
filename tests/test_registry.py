import json

from hominfer.services.registry import Registry

ENGINE = {"label": "Test engine", "kinds": ["llm"], "file_ext": [".gguf"],
          "command": ["/bin/serve", "-m", "{file}", "--port", "{port}"],
          "health": "/health", "endpoint": "/v1", "procs": ["serve"]}


def registry(tmp_path):
    return Registry(tmp_path / "engines.json", tmp_path / "models.json", listen_port=8090)


def test_first_run_without_config(tmp_path):
    r = registry(tmp_path)
    assert r.engines == {} and r.models == {}


def test_add_engine_creates_the_file(tmp_path):
    r = registry(tmp_path)
    assert r.add_engine("test", ENGINE) is True
    assert "test" in r.engines
    assert json.loads((tmp_path / "engines.json").read_text())["test"]["label"] == "Test engine"
    assert r.add_engine("test", ENGINE | {"label": "Other"}) is False  # an existing id is left untouched


def test_models_sharing_an_engine_need_match_file(tmp_path):
    import pytest
    from hominfer.errors import LaunchError
    for name in ("a.gguf", "b.gguf"):
        (tmp_path / name).write_text("x")
    models = {mid: {"kind": "llm", "name": mid, "engine": "test", "file": str(tmp_path / f"{mid}.gguf"), "port": 8000}
              for mid in ("a", "b")}
    (tmp_path / "models.json").write_text(json.dumps(models))
    (tmp_path / "engines.json").write_text(json.dumps({"test": ENGINE}))
    with pytest.raises(LaunchError, match="match_file"):
        registry(tmp_path)
    (tmp_path / "engines.json").write_text(json.dumps({"test": ENGINE | {"match_file": True}}))
    assert set(registry(tmp_path).models) == {"a", "b"}
