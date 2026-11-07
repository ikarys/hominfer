from hominfer.web import server


def test_host_allowed_blocks_rebinding(monkeypatch):
    monkeypatch.setattr(server.socket, "gethostname", lambda: "Box")
    monkeypatch.setattr(server.config, "ALLOWED_HOSTS", {"llm.home"})
    for ok in ("192.168.1.5:8090", "127.0.0.1", "[::1]:8090", "localhost:8090", "box:8090", "box.local", "llm.home"):
        assert server.host_allowed(ok), ok
    for bad in ("evil.com:8090", "box.evil.com", "", None):
        assert not server.host_allowed(bad), bad
