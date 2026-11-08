import os
import time
from types import SimpleNamespace

import psutil

from hominfer.services import supervisor as sup


def make(monkeypatch, tmp_path, probe, gpu=None, gpu_mem=None):
    models = {f"m{i}": {"port": 9000 + i, "health": "/health", "name": f"m{i}", "engine_id": "e"} for i in range(3)}
    registry = SimpleNamespace(models=models, process_patterns=lambda: {})
    me = psutil.Process(os.getpid())
    monkeypatch.setattr(sup.processes, "find", lambda patterns: {mid: [me] for mid in models})
    monkeypatch.setattr(sup.net, "http_ok", probe)
    monkeypatch.setattr(sup.net, "lan_ip", lambda: None)
    return sup.Supervisor(registry, SimpleNamespace(behind=lambda eid: 0), gpu=lambda: gpu,
                          keep_awake=SimpleNamespace(set=lambda on: None), log_dir=tmp_path,
                          models_dir=lambda: tmp_path, default_baseline_mib=0, gpu_mem=gpu_mem)


def test_health_probes_run_in_parallel_outside_the_lock(monkeypatch, tmp_path):
    lock_free = []

    def probe(port, path):
        lock_free.append(s.lock.acquire(blocking=False) and (s.lock.release() or True))
        time.sleep(0.3)
        return port != 9001

    s = make(monkeypatch, tmp_path, probe)
    t = time.monotonic()
    s.poll()
    assert time.monotonic() - t < 0.6  # 3 probes x 0.3 s, not serialized
    assert lock_free == [True] * 3
    assert {mid: v["state"] for mid, v in s.snapshot["models"].items()} == \
        {"m0": "ready", "m1": "starting", "m2": "ready"}


def test_back_to_back_polls_measure_cpu_once(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(psutil.Process, "cpu_percent", lambda self, interval: calls.append("p") or 50.0)
    monkeypatch.setattr(sup.psutil, "cpu_percent", lambda interval: calls.append("m") or 20.0)
    s = make(monkeypatch, tmp_path, lambda port, path: True)
    s.registry.models = {"m0": s.registry.models["m0"]}
    s.poll()
    s.poll()  # e.g. the loop then a start/stop: the 2nd must not reset the window
    assert calls == ["p", "m"]
    assert s.snapshot["models"]["m0"]["cpu_pct"] == 50.0 and s.snapshot["cpu"]["pct"] == 20.0


def test_amd_per_process_memory_gives_exact_vram_and_baseline(monkeypatch, tmp_path):
    amd = {"vendor": "amd", "unified": True, "pdev": "0000:c4:00.0", "used": 5000, "total": 20000,
           "util": 30, "pids": set(), "cc": None}
    me = os.getpid()
    s = make(monkeypatch, tmp_path, lambda port, path: True, gpu=amd, gpu_mem=lambda pids, pdev, unified: {me: 3000})
    for mid in ("m1", "m2"):  # in place: the fake process finder reads the same dict
        s.registry.models.pop(mid)
    s.poll()
    m = s.snapshot["models"]["m0"]
    assert (m["on_gpu"], m["vram_mib"], m["vram_how"]) == (True, 3000, "live")
    assert s.snapshot["gpu"]["baseline"] == 2000 and "pdev" not in s.snapshot["gpu"]


def watched(monkeypatch, tmp_path, engine=None, stopping=False):
    s = make(monkeypatch, tmp_path, lambda port, path: False)
    s.registry.engines = {"e": engine or {}}
    s.runs["m0"] = {"popen": SimpleNamespace(poll=lambda: None, returncode=None), "opts": {"ctx": "1"}, "env": {},
                    "vram_before": None, "vram_load": None, "watch": {"ready": True, "fails": 2}}
    if stopping:
        s.stopping.add("m0")
    calls = []
    monkeypatch.setattr(s, "_restart", lambda *a: calls.append(a))
    monkeypatch.setattr(s, "_probe", lambda procs: {})  # no thread pool: Thread is faked below
    monkeypatch.setattr(sup.threading, "Thread", lambda target, args, daemon: SimpleNamespace(start=lambda: target(*args)))
    return s, calls


def test_unhealthy_ready_model_is_restarted(monkeypatch, tmp_path):
    s, calls = watched(monkeypatch, tmp_path)
    s.poll()
    assert [(c[0], c[2]) for c in calls] == [("m0", {"ctx": "1"})]


def test_restart_can_be_disabled(monkeypatch, tmp_path):
    s, calls = watched(monkeypatch, tmp_path, engine={"restart": False})
    s.poll()
    assert calls == []


def test_user_stop_is_not_restarted(monkeypatch, tmp_path):
    s, calls = watched(monkeypatch, tmp_path, stopping=True)
    s.poll()
    assert calls == []
