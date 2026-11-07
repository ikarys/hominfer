from types import SimpleNamespace

from hominfer.services.library import Library


def test_items_report_which_model_uses_what(tmp_path):
    (tmp_path / "qwen").mkdir()
    (tmp_path / "qwen" / "q4.gguf").write_bytes(b"x")
    (tmp_path / "qwen" / "q8.gguf").write_bytes(b"x")
    (tmp_path / "loose.gguf").write_bytes(b"x")
    registry = SimpleNamespace(
        models={"a": {"name": "A", "engine_id": "e", "config": {"file": str(tmp_path / "qwen" / "q4.gguf")}}},
        engines={"e": {}})
    lib = Library(lambda: tmp_path, registry, downloads=None)
    items = {it["path"]: it for it in lib.items()}
    assert items["qwen"]["used_by"] == ["A"]
    assert {f["name"]: f["used_by"] for f in items["qwen"]["files"]} == {"q4.gguf": ["A"], "q8.gguf": []}
    assert items["loose.gguf"]["used_by"] == []
