import pytest

from hominfer.domain.status import baseline_ok, model_state, model_vram, on_gpu_for


@pytest.mark.parametrize("kw, expected", [
    ({"stopping": True, "running": True, "healthy": True, "failed": False}, "stopping"),
    ({"stopping": False, "running": False, "healthy": False, "failed": True}, "error"),
    ({"stopping": False, "running": False, "healthy": False, "failed": False}, "stopped"),
    ({"stopping": False, "running": True, "healthy": False, "failed": False}, "starting"),
    ({"stopping": False, "running": True, "healthy": True, "failed": False}, "ready"),
])
def test_model_state(kw, expected):
    assert model_state(**kw) == expected


def test_vram_of_the_only_model_on_the_gpu():
    assert model_vram("a", {"a": True, "b": False}, 25000, 1500, True, None) == (23500, "live")
    assert model_vram("a", {"a": True}, 25000, 1500, False, None) == (23500, "estimate")


def test_vram_on_cpu():
    assert model_vram("b", {"a": True, "b": False}, 25000, 1500, True, None) == (0, "cpu")


def test_vram_shared_gpu_uses_the_load_measure():
    on_gpu = {"a": True, "b": True}
    assert model_vram("a", on_gpu, 25000, 1500, True, 20000) == (20000, "load")
    assert model_vram("a", on_gpu, 25000, 1500, True, None) == (None, "shared")


def test_vram_without_pid_reports_uses_the_load_measure():
    # WSL (driver 617.x): nvidia-smi reports no compute PIDs, so the live delta is worthless
    # and the model is attributed by inference; the measure taken at load is used instead.
    assert model_vram("a", {"a": True}, 25000, 1500, True, 20000, pids_known=False) == (20000, "load")
    assert model_vram("a", {"a": True}, 25000, 1500, True, 0, pids_known=False) == (0, "cpu")
    assert model_vram("a", {"a": True}, 25000, 1500, True, None, pids_known=False) == (23500, "live")
    assert model_vram("a", {"a": True}, 25000, 1500, False, None, pids_known=False) == (23500, "estimate")


class P:
    def __init__(self, pid):
        self.pid = pid


def test_on_gpu_from_the_compute_pids():
    assert on_gpu_for({"a": [P(1)], "b": []}, {1}, False) == {"a": True, "b": False}
    assert on_gpu_for({"a": [P(2)], "b": []}, {1}, False) == {"a": False, "b": False}


def test_on_gpu_inferred_when_the_pids_are_missing():
    # WSL: the PIDs are empty while a model uses the GPU -> attribute the GPU to the running models
    assert on_gpu_for({"a": [P(1)], "b": []}, set(), True) == {"a": True, "b": False}
    assert on_gpu_for({"a": [P(1)], "b": []}, set(), False) == {"a": False, "b": False}


@pytest.mark.parametrize("pids, running, util, ok", [
    (set(), False, 0, True),      # idle: measure
    ({9}, False, 0, False),       # a compute PID: not the idle baseline
    (set(), True, 0, False),      # a model runs: never re-measure while a model uses VRAM
    (set(), False, 8, False),     # the GPU is busy (a Windows app): not the idle baseline
    (set(), False, 2, True),      # display noise
])
def test_baseline_only_when_truly_idle(pids, running, util, ok):
    assert baseline_ok(pids, running, util) == ok
