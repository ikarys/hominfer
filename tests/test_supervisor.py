import os
import time
from types import SimpleNamespace

import psutil

from hominfer.services import supervisor as sup


def make(monkeypatch, tmp_path, probe):
    models = {f"m{i}": {"port": 9000 + i, "health": "/health", "name": f"m{i}"} for i in range(3)}
    registry = SimpleNamespace(models=models, process_patterns=lambda: {})
    me = psutil.Process(os.getpid())
    monkeypatch.setattr(sup.processes, "find", lambda patterns: {mid: [me] for mid in models})
    monkeypatch.setattr(sup.net, "http_ok", probe)
    monkeypatch.setattr(sup.net, "lan_ip", lambda: None)
    return sup.Supervisor(registry, SimpleNamespace(status=lambda mid: None), gpu=lambda: None,
                          keep_awake=SimpleNamespace(set=lambda on: None), log_dir=tmp_path,
                          models_dir=lambda: tmp_path, default_baseline_mib=0)


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
