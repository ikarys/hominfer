import os
import shlex
from types import SimpleNamespace

import psutil

from hominfer.domain import engine as engine_rules
from hominfer.services import supervisor as sup


def make(monkeypatch, tmp_path, probe, gpu=None, gpu_mem=None, procs=None):
    procs = procs or ["python"]
    models = {
        f"m{i}": {
            "port": 9000 + i, "health": "/health", "name": f"m{i}", "engine_id": "e",
            "procs": procs, "config": {}, "fixed": {}, "vram_mib": 0,
        }
        for i in range(3)
    }
    registry = SimpleNamespace(models=models, engines={"e": {}}, process_patterns=lambda: {})
    me = psutil.Process(os.getpid())
    monkeypatch.setattr(sup.processes, "find", lambda patterns: {mid: [me] for mid in models})
    monkeypatch.setattr(sup.net, "http_ok", probe)
    monkeypatch.setattr(sup.net, "lan_ip", lambda: None)
    return sup.Supervisor(registry, SimpleNamespace(behind=lambda eid: 0), gpu=lambda: gpu,
                          keep_awake=SimpleNamespace(set=lambda on: None), log_dir=tmp_path,
                          models_dir=lambda: tmp_path, default_baseline_mib=0, gpu_mem=gpu_mem)


def test_redact_argv_separate_value():
    argv, env = engine_rules.redact(["srv", "--api-key", "abc", "--port", "1"])
    assert argv == ["srv", "--api-key", "***", "--port", "1"]
    assert env == {}


def test_redact_argv_equals_value():
    argv, _ = engine_rules.redact(["srv", "--api-key=abc"])
    assert argv == ["srv", "--api-key=***"]


def test_redact_env_and_non_secret_untouched():
    argv, env = engine_rules.redact(["srv", "--port", "1"], {"HF_TOKEN": "x", "PATH": "/bin"})
    assert argv == ["srv", "--port", "1"]
    assert env == {"HF_TOKEN": "***", "PATH": "/bin"}


def test_cmdlines_reports_engine_process(monkeypatch, tmp_path):
    me = psutil.Process(os.getpid())
    s = make(monkeypatch, tmp_path, lambda port, path: True, procs=[os.path.basename(me.cmdline()[0])])
    s.poll()
    expected = shlex.join(engine_rules.redact(me.cmdline())[0])
    assert s.snapshot["models"]["m0"]["cmdlines"] == [expected]


def test_cmdlines_empty_when_process_name_not_matched(monkeypatch, tmp_path):
    s = make(monkeypatch, tmp_path, lambda port, path: True, procs=["nothing"])
    s.poll()
    assert s.snapshot["models"]["m0"]["cmdlines"] == []


def test_preview_redacts_argv_and_env(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sup.engine_rules, "build_command",
        lambda *args, **kwargs: (["srv", "--api-key", "abc", "--port", "1"], {"HF_TOKEN": "x"}, 0))
    monkeypatch.setattr(sup, "clean_options", lambda m, opts: {})
    s = make(monkeypatch, tmp_path, lambda port, path: True)
    assert s.preview("m0", {}) == {"argv": "srv --api-key '***' --port 1", "env": {"HF_TOKEN": "***"}}


def test_redact_spares_flags_that_only_contain_a_secret_word():
    argv, env = engine_rules.redact(["srv", "--draft-tokens", "7", "--hf-token", "t"], {"MAX_TOKENS": "9", "OPENAI_API_KEY": "k"})
    assert argv == ["srv", "--draft-tokens", "7", "--hf-token", "***"]
    assert env == {"MAX_TOKENS": "9", "OPENAI_API_KEY": "***"}
