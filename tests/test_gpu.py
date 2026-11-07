from hominfer.infra import gpu


def test_failing_nvidia_smi_is_not_rerun_on_every_poll(monkeypatch):
    calls = []

    def smi(*args):
        calls.append(args)
        raise FileNotFoundError("nvidia-smi")
    monkeypatch.setattr(gpu, "_smi", smi)
    monkeypatch.setattr(gpu, "_retry_at", 0.0)
    assert gpu.query() is None and gpu.query() is None
    assert len(calls) == 1
