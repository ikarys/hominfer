from hominfer.services import stats as svc


def test_observe_twice_then_flush_reloads(tmp_path):
    path = tmp_path / "stats.json"
    hist = svc.StatsHistory(path)
    hist.observe(1000, {"m": ("e", {"running": 1.0})})
    hist.observe(1002, {"m": ("e", {"running": 1.0})})
    hist.flush(1002)
    assert path.exists()
    hist2 = svc.StatsHistory(path)
    agg = hist2.query(0, 3600)
    assert agg["total"]["up"] == 2
    assert agg["total"]["busy"] == 2
    assert agg["total"]["share"] == [[1, 1.0]]


def test_gap_above_max_gap_credits_zero(tmp_path):
    path = tmp_path / "stats.json"
    hist = svc.StatsHistory(path)
    first = 1000
    second = first + svc.MAX_GAP_S + 1
    hist.observe(first, {"m": ("e", {"running": 1.0})})
    hist.observe(second, {"m": ("e", {"running": 1.0})})
    hist.flush(second)
    agg = hist.query(0, second + 3600)
    assert agg["total"]["up"] == 0
    assert agg["total"]["busy"] == 0


def test_corrupt_file_loads_empty(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text("nope")
    hist = svc.StatsHistory(path)
    assert hist.rows == {}
    agg = hist.query(0, 3600)
    assert agg["total"]["up"] == 0


def test_query_returns_from_to_and_totals(tmp_path):
    path = tmp_path / "stats.json"
    hist = svc.StatsHistory(path)
    hist.observe(1000, {"m": ("e", {"running": 1.0})})
    hist.observe(1002, {"m": ("e", {"running": 1.0})})
    hist.flush(1002)
    agg = hist.query(0, 3600)
    assert agg["from"] == 0
    assert agg["to"] == 3600
    assert agg["total"]["up"] == 2
    assert agg["total"]["busy"] == 2
