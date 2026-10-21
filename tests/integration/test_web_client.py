"""Unity WebGL istemcisinin /play rotasindan sunulmasi (gzip'li build dosyalari)."""

import gzip

import pytest


@pytest.fixture
def web_build(tmp_path, monkeypatch, server):
    """Sahte bir Unity WebGL build klasoru (Gzip sikistirma, Decompression Fallback kapali)."""
    build = tmp_path / "WebGL"
    (build / "Build").mkdir(parents=True)
    (build / "index.html").write_text("<html>Connect Four Pro</html>", encoding="utf-8")
    (build / "socket.io.min.js").write_text("/* io */", encoding="utf-8")
    (build / "Build" / "WebGL.loader.js").write_text("// loader", encoding="utf-8")
    for name, data in (("WebGL.wasm.gz", b"\0asm"), ("WebGL.framework.js.gz", b"var x;"), ("WebGL.data.gz", b"data")):
        (build / "Build" / name).write_bytes(gzip.compress(data))
    monkeypatch.setattr(server.config, "WEB_BUILD_DIR", str(build))
    return build


class TestWebClient:
    def test_root_and_play_redirect_to_game(self, http):
        assert http.get('/').headers['Location'].endswith('/play/')
        assert http.get('/play').headers['Location'].endswith('/play/')

    def test_index_is_served(self, http, web_build):
        r = http.get('/play/')
        assert r.status_code == 200 and b'Connect Four Pro' in r.data
        assert r.headers['Cache-Control'] == 'no-cache'

    @pytest.mark.parametrize("name, content_type", [
        ("WebGL.wasm.gz", "application/wasm"),
        ("WebGL.framework.js.gz", "application/javascript"),
        ("WebGL.data.gz", "application/octet-stream"),
    ])
    def test_gzip_files_have_encoding_and_real_type(self, http, web_build, name, content_type):
        r = http.get('/play/Build/' + name)
        assert r.status_code == 200
        assert r.headers['Content-Encoding'] == 'gzip'
        assert r.headers['Content-Type'] == content_type
        assert r.data == (web_build / "Build" / name).read_bytes()   # sunucu acmaz, tarayici acar

    def test_plain_javascript(self, http, web_build):
        r = http.get('/play/Build/WebGL.loader.js')
        assert r.status_code == 200 and r.headers['Content-Type'] == 'application/javascript'
        assert 'Content-Encoding' not in r.headers

    @pytest.mark.parametrize("path", ["../secret.txt", "Build/../../secret.txt", "missing.js"])
    def test_no_path_traversal_or_missing_files(self, http, web_build, path):
        (web_build.parent / "secret.txt").write_text("x")
        assert http.get('/play/' + path).status_code == 404

    def test_missing_build_explains_how_to_build(self, http, server, tmp_path, monkeypatch):
        monkeypatch.setattr(server.config, "WEB_BUILD_DIR", str(tmp_path / "none"))
        r = http.get('/play/')
        assert r.status_code == 404 and 'hint' in r.get_json()
