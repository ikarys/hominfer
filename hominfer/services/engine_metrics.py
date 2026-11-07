"""Engine metrics of the running models (engines.json `metrics`): fetched from the engine's
Prometheus endpoint, evaluated, cached a few seconds so the page's polling doesn't hammer the engine."""
import time
from concurrent.futures import ThreadPoolExecutor

from ..domain import metrics
from ..i18n import loc
from ..infra import net

TTL_S = 5


class EngineMetrics:
    def __init__(self, registry, fetch=net.http_text):
        """fetch: (port, path) -> text or None."""
        self.registry, self.fetch = registry, fetch
        self.cache = {}  # model id -> (time, items)

    def collect(self, mids):
        """{model id: items} for those of `mids` whose engine has metrics and answers. Never raises;
        a failing endpoint costs one timeout per TTL, not per poll."""
        models, engines = self.registry.models, self.registry.engines
        todo = {mid: (models[mid]["port"], engines[models[mid]["engine_id"]]["metrics"]) for mid in mids
                if mid in models and "metrics" in engines.get(models[mid]["engine_id"], {})}
        now = time.monotonic()
        stale = [mid for mid in todo if mid not in self.cache or now - self.cache[mid][0] >= TTL_S]
        if stale:
            with ThreadPoolExecutor(len(stale)) as ex:
                for mid, items in zip(stale, ex.map(lambda mid: self._read(*todo[mid]), stale)):
                    self.cache[mid] = (now, items)
        self.cache = {mid: v for mid, v in self.cache.items() if mid in todo}
        return {mid: self.cache[mid][1] for mid in todo if self.cache[mid][1]}

    def _read(self, port, spec):
        try:
            text = self.fetch(port, spec["path"])
            return metrics.evaluate(spec["show"], metrics.parse(text), loc=loc) if text else []
        except Exception:
            return []
