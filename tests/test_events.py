"""Event log: what changed between two snapshots, the ring buffer and its `since` logic, the supervisor / updates hooks."""
from types import SimpleNamespace

from hominfer.domain import events as ev
from hominfer.services.events import EventLog
from hominfer.services.updates import Updates
from hominfer.web import routes


def model(state="stopped", error=None, preempt=None):
    m = {"state": state, "error": error}
    if preempt is not None:
        m["metrics"] = [{"label": "x", "value": preempt, "unit": "count", "event": ev.PREEMPTIONS}]
    return m


def snap(models=None, used=1000, total=10000, win=None):
    gpu = {"used": used, "total": total} | ({"processes": [{"name": "w", "bytes": b} for b in win]} if win else {})
    return {"ready": True, "gpu": gpu, "models": models or {"a": model()}}


def keys(events):
    return [e["key"].removeprefix("ui.ev.") for e in events]


def run(old, new):
    return ev.diff(old, new, 100.0, {"a": "Alpha"})


def test_nothing_before_a_first_real_snapshot():
    assert run({"ready": False}, snap()) == [] and run(None, snap()) == []


def test_unchanged_state_gives_no_event():
    s = snap({"a": model("ready", preempt=3)}, used=9500, win=[20000 * 2**20])
    assert run(s, s) == []


def test_start_ready_stop():
    assert keys(run(snap(), snap({"a": model("starting")}))) == ["started"]
    assert keys(run(snap({"a": model("starting")}), snap({"a": model("ready")}))) == ["ready"]
    assert keys(run(snap({"a": model("ready")}), snap({"a": model("stopping")}))) == []
    assert keys(run(snap({"a": model("stopping")}), snap())) == ["stopped"]
    assert keys(run(snap(), snap({"a": model("ready")}))) == ["started", "ready"]  # found already serving


def test_event_shape():
    [e] = run(snap(), snap({"a": model("starting")}))
    assert e == {"t": 100.0, "level": "run", "key": "ui.ev.started", "args": {"name": "Alpha"}, "model": "a"}


def test_crash_is_an_alarm_once():
    [e] = run(snap({"a": model("ready")}), snap({"a": model("error", "died: 1")}))
    assert (e["key"], e["level"], e["args"]["detail"]) == ("ui.ev.crashed", "alarm", "died: 1")
    assert run(snap({"a": model("error", "x")}), snap({"a": model("error", "x")})) == []


def test_health_check_failing_on_a_ready_model():
    [e] = run(snap({"a": model("ready")}), snap({"a": model("starting")}))
    assert (e["key"], e["level"]) == ("ui.ev.health", "alarm")
    assert keys(run(snap({"a": model("starting")}), snap({"a": model("starting")}))) == []  # still loading: normal


def test_vram_crossing_90_percent_and_back():
    [up] = run(snap(used=8900), snap(used=9100))
    assert (up["key"], up["level"], up["args"]["pct"]) == ("ui.ev.vram_high", "warn", 91)
    assert keys(run(snap(used=9100), snap(used=9500))) == []
    assert keys(run(snap(used=9100), snap(used=8000))) == ["vram_ok"]


def test_windows_gpu_memory_over_the_card_and_back():
    over, under = [11000 * 2**20], [5000 * 2**20]
    assert keys(run(snap(win=under), snap(win=over))) == ["win_over"]
    assert keys(run(snap(win=over), snap(win=over))) == []
    assert keys(run(snap(win=over), snap(win=under))) == ["win_ok"]
    assert keys(run(snap(), snap())) == []


def test_preemption_counter_increase_only():
    [e] = run(snap({"a": model("ready", preempt=2)}), snap({"a": model("ready", preempt=5)}))
    assert (e["key"], e["level"], e["args"]["n"]) == ("ui.ev.preempt", "warn", 3)
    assert run(snap({"a": model("ready", preempt=5)}), snap({"a": model("ready", preempt=0)})) == []  # engine restarted
    assert run(snap({"a": model("ready")}), snap({"a": model("ready", preempt=4)})) == []  # first reading


def test_buffer_ids_since_and_limit():
    log = EventLog(maxlen=3)
    assert log.since(0) == {"events": [], "last": 0}
    for n in range(5):
        log.add("info", "started", "a", name=str(n))
    got = log.since(0)
    assert got["last"] == 5 and [e["id"] for e in got["events"]] == [3, 4, 5]  # oldest dropped, ids kept
    assert [e["id"] for e in log.since(4)["events"]] == [5]
    assert log.since(5) == {"events": [], "last": 5}
    assert got["events"][0]["key"] == "ui.ev.started" and got["events"][0]["args"] == {"name": "2"}


def test_route_parses_since():
    app = SimpleNamespace(events=EventLog())
    app.events.add("run", "ready", "a", name="A")
    assert routes._events(app, {"since": "0"})["last"] == 1
    assert routes._events(app, {"since": "1"})["events"] == []
    assert len(routes._events(app, {"since": "nope"})["events"]) == 1
    assert routes.match("GET", "/api/events")[0]


def test_update_check_pushes_an_event(monkeypatch):
    from hominfer.services import updates
    log = EventLog()
    u = Updates(SimpleNamespace(engines={"e": {"repo": "/r", "label": "Alpha"}}), None, log)
    monkeypatch.setattr(updates.git, "behind", lambda repo: {"branch": "main", "current": "x", "behind": ["c1", "c2"]})
    u.check("e")
    assert u.behind("e") == 2
    monkeypatch.setattr(updates.git, "behind", lambda repo: {"branch": "main", "current": "x", "behind": []})
    u.check("e")
    assert u.behind("e") == 0
    assert [(e["key"], e["level"]) for e in log.since(0)["events"]] == [
        ("ui.ev.update_behind", "warn"), ("ui.ev.update_current", "info")]
    assert log.since(0)["events"][0]["args"] == {"name": "Alpha", "n": 2, "branch": "main"}
