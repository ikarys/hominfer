"""The engine catalog shipped with the launcher: every entry is complete and its engine block is
valid and buildable."""
import json

import pytest

from hominfer import config
from hominfer.domain import engine as engine_rules

CATALOG = json.loads((config.CATALOG_DIR / "catalog.json").read_text())


@pytest.mark.parametrize("cid", list(CATALOG))
def test_catalog_entry(cid):
    c = CATALOG[cid]
    assert {"label", "desc", "url", "dir", "script", "disk_gb", "minutes", "engine"} <= set(c)
    assert (config.CATALOG_DIR / c["script"]).is_file()
    engine_rules.validate(cid, json.loads(json.dumps(c["engine"])))
    e = engine_rules.normalize(c["engine"])
    ext = (e["file_ext"] or [""])[0]
    model = {"engine": cid, "port": 9000, "file": f"/models/org--repo/model{ext}" if ext else None}
    argv, _, _ = engine_rules.build_command(e, "m", model, {}, vram_need=0, free_vram=0, models_dir="/models")
    assert argv and all(argv)


def test_recipes_follow_the_gpu_vendor(tmp_path):
    from types import SimpleNamespace

    from hominfer.services.catalog import Catalog
    registry = SimpleNamespace(engines={}, installed=lambda cid: False)
    cat = Catalog(config.CATALOG_DIR, registry, tmp_path, lambda: tmp_path)
    nvidia, amd = {"vendor": "nvidia", "cc": 8.6}, {"vendor": "amd", "cc": None}
    assert cat.compat("llama.cpp", nvidia)[0] and not cat.compat("llama.cpp", amd)[0]
    assert not cat.compat("llama.cpp", None)[0] and cat.compat("llama.cpp-vulkan", None)[0]
    assert not cat.compat("ninfer", nvidia)[0]  # min_cc 12.0
    assert cat.suggest("gguf", "llm", "org/repo", nvidia)["id"] == "llama.cpp"
    assert cat.suggest("gguf", "llm", "org/repo", amd)["id"] == "llama.cpp-vulkan"
