from hominfer.domain import sessions as s

def test_empty_summary():
    assert s.summary(s.new_stats()) is None

def test_single_poll_summary_none():
    st = s.new_stats()
    s.record(st, {"running": 1}, 0.0)
    assert s.summary(st) is None

def test_basic_share_and_peak():
    st = s.new_stats()
    s.record(st, {"running": 1}, 0.0)
    s.record(st, {"running": 2}, 2.0)
    s.record(st, {"running": 2}, 4.0)
    s.record(st, {"running": 1}, 6.0)
    out = s.summary(st)
    assert out["peak"] == 2
    assert out["share"] == [[1, 0.333], [2, 0.667]]

def test_gap_longer_than_max_credits_nothing():
    st = s.new_stats()
    s.record(st, {"running": 1}, 0.0)
    s.record(st, {"running": 2}, 31.0)
    assert s.summary(st) is None

def test_running_none_breaks_chain():
    st = s.new_stats()
    s.record(st, {"running": 1}, 0.0)
    s.record(st, {"running": None}, 2.0)
    s.record(st, {"running": 3}, 4.0)
    s.record(st, {"running": 3}, 6.0)
    out = s.summary(st)
    assert out["peak"] == 3
    assert out["share"] == [[3, 1.0]]

def test_waiting_and_limit():
    st = s.new_stats()
    s.record(st, {"running": 1, "waiting": 2, "limit": 10}, 0.0)
    s.record(st, {"running": 1, "waiting": 5, "limit": 8}, 2.0)
    s.record(st, {"running": 1, "waiting": None, "limit": None}, 4.0)
    out = s.summary(st)
    assert out["peak_waiting"] == 5
    assert out["limit"] == 8
    assert out["share"] == [[1, 1.0]]

def test_waiting_and_limit_never_given():
    st = s.new_stats()
    s.record(st, {"running": 1}, 0.0)
    s.record(st, {"running": 1}, 2.0)
    out = s.summary(st)
    assert out["peak_waiting"] is None
    assert out["limit"] is None


def test_idle_only_gives_no_summary():
    st = s.new_stats()
    s.record(st, {"running": 0}, 0.0)
    s.record(st, {"running": 0}, 2.0)
    assert s.summary(st) is None

def test_negative_and_fractional_values():
    st = s.new_stats()
    s.record(st, {"running": -1}, 0.0)
    s.record(st, {"running": 1.6}, 2.0)
    s.record(st, {"running": 1.6}, 4.0)
    out = s.summary(st)
    assert out["peak"] == 2
    assert out["share"] == [[2, 1.0]]  # idle time (level 0) is left out

def test_valid_spec_ok():
    assert s.valid_spec({"running": "requests_total"})
    assert s.valid_spec({"running": "x{a=\"b\"}", "waiting": "y{c=\"d\"}", "limit": "z"})

def test_valid_spec_bad():
    assert not s.valid_spec("running")
    assert not s.valid_spec({"waiting": "x"})
    assert not s.valid_spec({"running": "x", "unknown": "y"})
    assert not s.valid_spec({"running": 1})
    assert not s.valid_spec({"running": "1bad"})
