from types import SimpleNamespace

from hominfer.web import server


def test_host_allowed_blocks_rebinding(monkeypatch):
    monkeypatch.setattr(server.socket, "gethostname", lambda: "Box")
    monkeypatch.setattr(server.config, "ALLOWED_HOSTS", {"llm.home"})
    for ok in ("192.168.1.5:8090", "127.0.0.1", "[::1]:8090", "localhost:8090", "box:8090", "box.local", "llm.home"):
        assert server.host_allowed(ok), ok
    for bad in ("evil.com:8090", "box.evil.com", "", None):
        assert not server.host_allowed(bad), bad


def request(raw):
    """Run one raw HTTP request through the real handler (no listening socket)."""
    import socket
    import threading
    app = SimpleNamespace(supervisor=SimpleNamespace(snapshot={"ready": False}),
                          registry=SimpleNamespace(reload_models=lambda: None))
    a, b = socket.socketpair()
    def serve():  # the server, not the handler, closes the connection
        server.make_handler(app)(b, ("127.0.0.1", 0), None)
        b.close()
    t = threading.Thread(target=serve)
    t.start()
    a.settimeout(5)
    a.sendall(raw.encode())
    out = b""
    while chunk := a.recv(65536):
        out += chunk
    t.join()
    return out.decode(errors="replace")


def test_foreign_host_refused_on_get_and_post():
    assert " 403 " in request("GET /api/status HTTP/1.0\r\nHost: evil.com:8090\r\n\r\n").split("\r\n")[0]
    post = "POST /api/reload HTTP/1.0\r\nHost: evil.com\r\nOrigin: http://evil.com\r\nContent-Length: 0\r\n\r\n"
    assert " 403 " in request(post).split("\r\n")[0]
    assert " 200 " in request("GET /api/status HTTP/1.0\r\nHost: 192.168.1.5:8090\r\n\r\n").split("\r\n")[0]


def test_unchanged_asset_answers_304():
    first = request("GET /js/main.js HTTP/1.0\r\nHost: localhost\r\n\r\n")
    etag = next(h.split(": ", 1)[1] for h in first.split("\r\n") if h.lower().startswith("etag:"))
    again = request(f"GET /js/main.js HTTP/1.0\r\nHost: localhost\r\nIf-None-Match: {etag}\r\n\r\n")
    assert " 304 " in again.split("\r\n")[0] and "no-cache" in again
