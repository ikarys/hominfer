from hominfer.domain import stats as st


def test_credit_creates_row_and_accumulates():
    rows = {}
    st.credit(rows, 1000, 10, "m", "e", {"running": 2.0, "waiting": 1.0, "limit": 5.0})
    st.credit(rows, 1000, 5, "m", "e", {"running": 3.0, "waiting": 2.0, "limit": 4.0})
    row = rows[st.key(0, "m")]
    assert row["up"] == 15
    assert row["busy"] == {"2": 10.0, "3": 5.0}
    assert row["peak"] == 3
    assert row["peak_waiting"] == 2
    assert row["limit"] == 4


def test_credit_level_zero_adds_up_but_no_busy():
    rows = {}
    st.credit(rows, 1000, 10, "m", "e", {"running": 0.0})
    row = rows[st.key(0, "m")]
    assert row["up"] == 10
    assert row["busy"] == {}


def test_credit_sample_none_adds_up_only():
    rows = {}
    st.credit(rows, 1000, 10, "m", "e", None)
    row = rows[st.key(0, "m")]
    assert row["up"] == 10
    assert row["busy"] == {}
    assert row["peak"] is None
    assert row["peak_waiting"] is None
    assert row["limit"] is None


def test_credit_two_polls_in_two_hours_give_two_rows():
    rows = {}
    st.credit(rows, 1000, 10, "m", "e", None)
    st.credit(rows, 4000, 10, "m", "e", None)
    assert len(rows) == 2
    assert st.key(0, "m") in rows
    assert st.key(3600, "m") in rows


def test_index_skips_bad_items_and_fills_defaults():
    items = [
        {"hour": 0, "model": "a", "engine": "e"},
        {"hour": "0", "model": "b", "engine": "e"},
        {"hour": True, "model": "c", "engine": "e"},
        {"model": "d", "engine": "e"},
        {"hour": 0, "engine": "e"},
        {"hour": 0, "model": "e"},
        "x",
        {
            "hour": 1,
            "model": "f",
            "engine": "e",
            "up": 7,
            "busy": {"1": 2.5, "x": 3, "2": "y", "3": True},
            "peak": 4,
            "peak_waiting": 1,
            "limit": 2,
        },
    ]
    rows = st.index(items)
    assert len(rows) == 2
    assert rows[st.key(0, "a")] == {
        "hour": 0,
        "model": "a",
        "engine": "e",
        "up": 0.0,
        "busy": {},
        "peak": None,
        "peak_waiting": None,
        "limit": None,
    }
    assert rows[st.key(1, "f")]["up"] == 7.0
    assert rows[st.key(1, "f")]["busy"] == {"1": 2.5}
    assert rows[st.key(1, "f")]["peak"] == 4
    assert rows[st.key(1, "f")]["peak_waiting"] == 1
    assert rows[st.key(1, "f")]["limit"] == 2


def test_prune_drops_old_rows_only():
    now = 1000000000
    old_hour = now - st.KEEP_S - 1000
    new_hour = now - 1000
    rows = {
        st.key(old_hour, "old"): {"hour": old_hour},
        st.key(new_hour, "new"): {"hour": new_hour},
    }
    st.prune(rows, now)
    assert st.key(old_hour, "old") not in rows
    assert st.key(new_hour, "new") in rows


def test_summary_shares_sum_per_level_across_rows():
    rows = [
        {"up": 0, "busy": {"1": 30}, "peak": None, "peak_waiting": None, "limit": None},
        {"up": 0, "busy": {"1": 10, "2": 40}, "peak": None, "peak_waiting": None, "limit": None},
    ]
    summary = st.summary(rows)
    assert summary["share"] == [[1, 0.5], [2, 0.5]]
    assert summary["busy"] == 80


def test_aggregate_per_engine_merges_two_models():
    rows = {}
    st.credit(rows, 1000, 10, "m1", "e", {"running": 1.0})
    st.credit(rows, 1000, 20, "m2", "e", {"running": 2.0})
    agg = st.aggregate(rows, 0, 3600)
    engine = agg["engines"]["e"]
    assert engine["up"] == 30
    assert engine["busy"] == 30
    assert agg["models"]["m1"]["engine"] == "e"
    assert agg["models"]["m2"]["engine"] == "e"


def test_aggregate_excludes_rows_outside_range():
    rows = {
        st.key(0, "m"): {
            "hour": 0,
            "model": "m",
            "engine": "e",
            "up": 10,
            "busy": {},
            "peak": None,
            "peak_waiting": None,
            "limit": None,
        },
        st.key(3600, "m"): {
            "hour": 3600,
            "model": "m",
            "engine": "e",
            "up": 20,
            "busy": {},
            "peak": None,
            "peak_waiting": None,
            "limit": None,
        },
        st.key(7200, "m"): {
            "hour": 7200,
            "model": "m",
            "engine": "e",
            "up": 30,
            "busy": {},
            "peak": None,
            "peak_waiting": None,
            "limit": None,
        },
    }
    agg = st.aggregate(rows, 3600, 7200)
    assert agg["total"]["up"] == 20
    assert agg["models"]["m"]["up"] == 20


def test_aggregate_hours_sums_and_takes_max_peak():
    rows = {}
    st.credit(rows, 1000, 10, "m1", "e", {"running": 1.0})
    st.credit(rows, 1000, 20, "m2", "e", {"running": 3.0})
    agg = st.aggregate(rows, 0, 3600)
    assert agg["hours"] == [[0, 3, 30, 30]]
