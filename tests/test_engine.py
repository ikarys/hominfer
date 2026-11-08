from pathlib import Path

import pytest

from hominfer.domain import engine as engine_rules
from hominfer.errors import LaunchError

from .conftest import make_engine

MODEL = {"engine": "test", "port": 9000, "file": "/models/org--repo/model.gguf"}


def build(e, params=None, *, need=2000, free=30000, model=MODEL):
    return engine_rules.build_command(e, "my_model", model, params or {}, vram_need=need, free_vram=free,
                                      models_dir="/models")


def test_placeholders_and_defaults():
    argv, env, need = build(make_engine())
    assert argv == ["/bin/serve", "-m", "/models/org--repo/model.gguf", "--port", "9000", "-c", "4096"]
    assert env == {} and need == 2000


def test_file_placeholders_home_and_extra_args():
    e = make_engine(command=["~/bin/serve", "{file_dir}", "{file_name}", "{model_id}", "{models_dir}"],
                    params={})
    argv, _, _ = build(e, model=MODEL | {"extra_args": ["--flag", "x=1"]})
    assert argv == [str(Path.home() / "bin/serve"), "/models/org--repo", "model.gguf", "my_model", "/models",
                    "--flag", "x=1"]


def test_empty_env_var_and_argument_are_dropped():
    e = make_engine(command=["/bin/serve", "{flag}"], env={"A": "{opt}", "B": "fixed"},
                    params={"opt": {"label": "o"}, "flag": {"label": "f"}})
    argv, env, _ = build(e)
    assert argv == ["/bin/serve"] and env == {"B": "fixed"}


def test_optional_group_needs_all_its_placeholders():
    e = make_engine(command=["/bin/serve", ["--spec", "{spec}", "--draft", "{draft}"]],
                    params={"spec": {"label": "s"}, "draft": {"label": "d", "default": "7"}})
    assert build(e)[0] == ["/bin/serve"]
    assert build(e, {"spec": "mtp"})[0] == ["/bin/serve", "--spec", "mtp", "--draft", "7"]


def test_param_map():
    e = make_engine(command=["/bin/serve", "{vision}"],
                    params={"vision": {"label": "v", "default": "on", "map": {"on": "--vision", "off": ""}}})
    assert build(e)[0] == ["/bin/serve", "--vision"]
    assert build(e, {"vision": "off"})[0] == ["/bin/serve"]


@pytest.mark.parametrize("device, free, expected_env, expected_need", [
    ("cpu", 30000, "cpu", 0),
    ("cuda", 0, "cuda", 2000),
    ("auto", 30000, "cuda", 2000),
    ("auto", 2500, "cpu", 0),  # 2000 needed + margin doesn't fit
])
def test_device_param(device, free, expected_env, expected_need):
    e = make_engine(command=["/bin/serve"], env={"DEVICE": "{device}"}, device_param="device",
                    params={"device": {"label": "d", "default": "cpu"}})
    _, env, need = build(e, {"device": device}, free=free)
    assert env["DEVICE"] == expected_env and need == expected_need


@pytest.mark.parametrize("change, message", [
    ({"command": []}, "command"),
    ({"health": "health"}, "HTTP path"),
    ({"procs": []}, "procs"),
    ({"command": ["/bin/serve", "{nope}"]}, "{nope}"),
    ({"device_param": "gpu"}, "device_param"),
    ({"restart": "yes"}, "restart"),
])
def test_validate_rejects(change, message):
    raw = {"label": "x", "command": ["/bin/serve"], "health": "/h", "endpoint": "/v1", "procs": ["serve"]} | change
    with pytest.raises(LaunchError, match=message.replace("{", r"\{").replace("}", r"\}")):
        engine_rules.validate("x", raw)


def test_normalize():
    e = engine_rules.normalize({"command": ["x"], "params": {"ctx": "Context"}, "repo": "~/src"})
    assert e["params"] == {"ctx": {"label": "Context"}}
    assert e["needs_file"] is False and e["repo"] == str(Path.home() / "src")


RAW = {"test": {"label": "T", "command": ["/bin/serve", "{ctx}", "{vision}"], "env": {"A": "b"}, "procs": ["serve"],
                "params": {"ctx": {"label": "Context"}, "name": "Name",
                           "vision": {"label": "V", "default": "on", "values": [["on", "On"], ["off", "Off"]]}}}}


def test_with_default_sets_and_keeps_the_rest():
    out = engine_rules.with_default(RAW, "test", "ctx", "8192")
    assert out["test"]["params"]["ctx"] == {"label": "Context", "default": "8192"}
    assert out["test"]["command"] == RAW["test"]["command"] and out["test"]["env"] == {"A": "b"}
    assert list(out["test"]["params"]) == ["ctx", "name", "vision"]
    assert "default" not in RAW["test"]["params"]["ctx"]  # input untouched
    assert engine_rules.with_default(RAW, "test", "name", "x")["test"]["params"]["name"] == {"label": "Name", "default": "x"}


def test_with_default_empty_removes():
    out = engine_rules.with_default(RAW, "test", "vision", "")
    assert out["test"]["params"]["vision"] == {"label": "V", "values": [["on", "On"], ["off", "Off"]]}


@pytest.mark.parametrize("eid,key,value", [
    ("nope", "ctx", "1"), ("test", "command", "1"), ("test", "ctx", "a\nb"), ("test", "ctx", "a\x00"),
    ("test", "ctx", "x" * 201), ("test", "ctx", 5), ("test", "vision", "maybe")])
def test_with_default_rejects(eid, key, value):
    with pytest.raises(LaunchError):
        engine_rules.with_default(RAW, eid, key, value)
