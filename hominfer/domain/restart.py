"""Auto-restart of a model whose engine dies after being ready (engines.json `restart`, default on).

Pure: the supervisor keeps the state and gives the time."""
FAIL_LIMIT = 3     # failed health checks in a row, one per poll
MAX_PER_HOUR = 3   # beyond, a crash that keeps coming back is left to a human


def new_watch():
    return {"ready": False, "fails": 0}


def verdict(watch, *, alive, healthy, history, now):
    """None, "restart" or "give_up" for one poll; `watch` is updated in place.

    history: epoch seconds of the recent automatic restarts of the model (the last hour)."""
    if alive and healthy:
        watch.update(ready=True, fails=0)
        return None
    if not watch["ready"]:
        return None
    if alive:
        watch["fails"] += 1
        if watch["fails"] < FAIL_LIMIT:
            return None
    watch.update(new_watch())
    return "restart" if len([t for t in history if now - t < 3600]) < MAX_PER_HOUR else "give_up"
