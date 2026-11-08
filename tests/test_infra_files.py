import json
import os

from hominfer.infra.files import cap_log, compact_json, prune, tail


def test_compact_json_round_trips_and_keeps_lines_short():
    data = {"engine": {"label": "x", "command": [f"--arg-{i}" for i in range(40)],
                       "params": {"ctx": {"label": "Context", "default": "0"}}}}
    text = compact_json(data)
    assert json.loads(text) == data
    assert max(len(line) for line in text.splitlines()) <= 110
    assert '"ctx": {"label": "Context", "default": "0"}' in text  # small objects stay on one line


def test_tail_strips_terminal_codes(tmp_path):
    log = tmp_path / "x.log"
    log.write_text("one\n\x1b[32mtwo\x1b[0m\r\nthree\n")
    assert tail(log, 2) == "two\nthree"
    assert tail(tmp_path / "missing.log") == ""


def test_cap_log_leaves_small_file_alone(tmp_path):
    log = tmp_path / "small.log"
    log.write_text("x" * 10)
    assert cap_log(log, 100) is False
    assert log.read_text() == "x" * 10


def test_cap_log_empties_big_file(tmp_path):
    log = tmp_path / "big.log"
    max_bytes = 1024
    log.write_text("x" * (max_bytes + 10))
    assert cap_log(log, max_bytes) is True
    text = log.read_text()
    assert "truncated" in text
    assert len(text.encode()) < max_bytes


def test_cap_log_missing_file(tmp_path):
    assert cap_log(tmp_path / "missing.log", 1024) is False


def test_prune_keeps_newest_and_ignores_other(tmp_path):
    files = []
    for i in range(4):
        p = tmp_path / f"download-{i}.log"
        p.write_text(str(i))
        files.append(p)
    other = tmp_path / "other.log"
    other.write_text("keep")
    for i, p in enumerate(files):
        os.utime(p, (100 + i, 100 + i))
    assert prune(tmp_path, "download-*.log", 2) == 2
    remaining = sorted(p.name for p in tmp_path.glob("download-*.log"))
    assert remaining == ["download-2.log", "download-3.log"]
    assert other.exists()
