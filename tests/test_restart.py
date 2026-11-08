from hominfer.domain import restart as r


def poll(w, alive=True, healthy=True, history=(), now=10_000):
    return r.verdict(w, alive=alive, healthy=healthy, history=list(history), now=now)


def test_loading_never_restarts():
    w = r.new_watch()
    assert [poll(w, healthy=False) for _ in range(5)] == [None] * 5
    assert poll(w, alive=False, healthy=False) is None


def test_ready_then_fails():
    w = r.new_watch()
    poll(w)
    assert poll(w, healthy=False) is None and poll(w, healthy=False) is None
    assert poll(w, healthy=False) == "restart"


def test_healthy_resets_fails():
    w = r.new_watch()
    poll(w)
    poll(w, healthy=False), poll(w, healthy=False)
    poll(w)
    assert poll(w, healthy=False) is None and w["fails"] == 1


def test_dead_after_ready():
    w = r.new_watch()
    poll(w)
    assert poll(w, alive=False, healthy=False) == "restart"


def test_give_up_and_reset():
    w = r.new_watch()
    poll(w)
    assert poll(w, alive=False, healthy=False, history=[9_000, 9_100, 9_200]) == "give_up"
    assert w == {"ready": False, "fails": 0}
    assert poll(w, alive=False, healthy=False) is None


def test_old_entries_ignored():
    w = r.new_watch()
    poll(w)
    assert poll(w, alive=False, healthy=False, history=[1, 2, 3]) == "restart"
