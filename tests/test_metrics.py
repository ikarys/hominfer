import pytest

from hominfer.domain import metrics
from hominfer.errors import LaunchError
from hominfer.services.engine_metrics import EngineMetrics

from .conftest import make_engine

TEXT = '''# HELP x_total things
# TYPE x_total counter
x_total 10
x_total_nan NaN
x_inf +Inf
pool{domain="device",kind="live"} 5 1700000000
pool{domain="device",kind="free"} 7
pool{domain="host",kind="live"} 100
weird{path="/a,b}{c",kind="live"} 3
bad line here
zero 0
'''


def samples():
    return metrics.parse(TEXT)


def test_parse_skips_comments_nan_inf_and_bad_lines():
    names = [n for n, _, _ in samples()]
    assert names == ["x_total", "pool", "pool", "pool", "weird", "zero"]


def test_parse_labels_with_quoted_commas_and_braces():
    s = dict((n, lab) for n, lab, _ in samples())
    assert s["weird"] == {"path": "/a,b}{c", "kind": "live"}
    assert metrics.select(samples(), 'weird{kind="live"}') == 3


def test_timestamp_ignored():
    assert metrics.select(samples(), 'pool{domain="device",kind="live"}') == 5


def test_selector_sums_matching_samples_and_none_when_missing():
    assert metrics.select(samples(), "pool") == 112
    assert metrics.select(samples(), 'pool{kind="live"}') == 105
    assert metrics.select(samples(), 'pool{kind="nope"}') is None
    assert metrics.select(samples(), "absent") is None


def test_evaluate_ratio_one_minus_and_division_by_zero():
    show = [{"label": "a", "value": "x_total"},
            {"label": "r", "ratio": ["pool{domain=\"host\"}", "x_total"], "unit": "x"},
            {"label": "m", "ratio": ["x_total", "pool"], "one_minus": True, "unit": "pct"},
            {"label": "z", "ratio": ["x_total", "zero"]},
            {"label": "gone", "value": "absent"}]
    out = metrics.evaluate(show, samples())
    assert out == [{"label": "a", "value": 10, "unit": "count"},
                   {"label": "r", "value": 10.0, "unit": "x"},
                   {"label": "m", "value": pytest.approx(1 - 10 / 112), "unit": "pct"}]


GOOD = {"path": "/metrics", "show": [{"label": "A", "value": 'pool{domain="host"}', "unit": "bytes"},
                                     {"label": {"en": "B"}, "ratio": ["a", "b"], "one_minus": True}]}


def test_engine_accepts_good_metrics():
    assert make_engine(metrics=GOOD)["metrics"] == GOOD


@pytest.mark.parametrize("bad", [
    {"show": GOOD["show"]},
    {"path": "metrics", "show": GOOD["show"]},
    {"path": "/m", "show": []},
    {"path": "/m", "show": "x"},
    {"path": "/m", "show": [{"label": "A", "value": "a"}] * 17},
    {"path": "/m", "show": [{"label": "A" * 61, "value": "a"}]},
    {"path": "/m", "show": [{"value": "a"}]},
    {"path": "/m", "show": [{"label": "A"}]},
    {"path": "/m", "show": [{"label": "A", "value": "a", "ratio": ["a", "b"]}]},
    {"path": "/m", "show": [{"label": "A", "ratio": ["a"]}]},
    {"path": "/m", "show": [{"label": "A", "value": "a b"}]},
    {"path": "/m", "show": [{"label": "A", "value": "a{k=v}"}]},
    {"path": "/m", "show": [{"label": "A", "value": "a", "unit": "kg"}]},
    GOOD | {"sessions": {"waiting": "w"}},
    "nope",
])
def test_engine_rejects_bad_metrics(bad):
    with pytest.raises(LaunchError):
        make_engine(metrics=bad)


def test_service_evaluates_caches_and_survives_failures():
    calls = []
    texts = {9000: "a 4\n", 9001: None}

    def fetch(port, path):
        calls.append((port, path))
        if port == 9002:
            raise OSError
        return texts[port]
    show = [{"label": {"en": "A", "fr": "Aa"}, "value": "a"}]
    eng = {"metrics": {"path": "/m", "show": show}}
    models = {f"m{i}": {"port": 9000 + i, "engine_id": "e"} for i in range(3)} | {"plain": {"port": 1, "engine_id": "p"}}
    reg = type("R", (), {"models": models, "engines": {"e": eng, "p": {}}})()
    svc = EngineMetrics(reg, fetch)
    ids = ["m0", "m1", "m2", "plain", "unknown"]
    assert svc.collect(ids) == {"m0": [{"label": "A", "value": 4, "unit": "count"}]}
    svc.collect(ids)
    assert len(calls) == 3  # cached, failures included



def test_engine_metrics_reads_sessions_gauges():
    eng = {"metrics": {"path": "/m", "show": [{"label": "A", "value": "a"}],
                       "sessions": {"running": "run", "limit": "lim"}}}
    reg = type("R", (), {"models": {"m": {"port": 1, "engine_id": "e"}}, "engines": {"e": eng}})()
    svc = EngineMetrics(reg, lambda port, path: "a 1\nrun 2\nlim 4\n")
    svc.collect(["m"])
    assert svc.samples() == {"m": {"running": 2, "limit": 4}}
