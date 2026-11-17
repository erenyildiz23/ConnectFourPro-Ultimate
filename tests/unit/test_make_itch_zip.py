"""scripts/make_itch_zip.py: itch.io zip'i (yerlesim, adres dogrulama, server-config.js)."""

import importlib.util
import json
import os
import re
import zipfile

import pytest

import config

_spec = importlib.util.spec_from_file_location(
    "make_itch_zip", os.path.join(config.PROJECT_ROOT, "scripts", "make_itch_zip.py"))
itch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(itch)

SERVER = "https://connect4.example.com"


def fake_build(root, fallback=True, template=True):
    """Sahte Unity WebGL build klasoru (varsayilan: Decompression Fallback acik)."""
    (root / "Build").mkdir(parents=True)
    script = '<script src="server-config.js"></script>' if template else ''
    (root / "index.html").write_text(f"<html>{script}<script src='Build/WebGL.loader.js'></script></html>",
                                     encoding="utf-8")
    (root / "server-config.js").write_text('window.CF4_SERVER_URL = "";\n', encoding="utf-8")
    (root / "socket.io.min.js").write_text("/* io */", encoding="utf-8")
    (root / "Build" / "WebGL.loader.js").write_text("// loader", encoding="utf-8")
    ext = ".unityweb" if fallback else ".gz"
    for name in ("WebGL.wasm", "WebGL.framework.js", "WebGL.data"):
        (root / "Build" / (name + ext)).write_bytes(b"\x1f\x8b data")
    (root / "TemplateData").mkdir()
    (root / "TemplateData" / "style.css").write_text("body{}", encoding="utf-8")
    return root


def baked_url(js):
    match = re.search(r'window\.CF4_SERVER_URL = (.*);', js)
    return json.loads(match.group(1))


class TestServerUrl:
    @pytest.mark.parametrize("url", [SERVER, "https://connect4.onrender.com", "https://host:8443",
                                     "https://192.0.2.10"])
    def test_valid(self, url):
        assert itch.validate_server_url(url) == url

    @pytest.mark.parametrize("url", [
        "", "   ", "connect4.example.com", "/api", "//connect4.example.com", "ftp://connect4.example.com",
        "https://connect4.example.com/",            # sonda /
        "https://connect4.example.com/play",        # yol
        "https://connect4.example.com?x=1", "https://connect4.example.com#a",
        "https://user:pw@connect4.example.com", "https://user@connect4.example.com",
        " https://connect4.example.com", "https://connect4.example.com\n",
        'https://a.example.com";alert(1);//', "https://host:99999", "https://", "HTTPS://connect4.example.com",
        "javascript:alert(1)",
    ])
    def test_invalid(self, url):
        with pytest.raises(itch.PackError):
            itch.validate_server_url(url)

    def test_http_needs_flag(self):
        with pytest.raises(itch.PackError, match="mixed content"):
            itch.validate_server_url("http://localhost:5000")
        assert itch.validate_server_url("http://localhost:5000", allow_http=True) == "http://localhost:5000"

    def test_config_js_is_safe_literal(self):
        assert baked_url(itch.server_config_js(SERVER)) == SERVER


class TestZip:
    def test_layout_and_config(self, tmp_path):
        build = fake_build(tmp_path / "WebGL")
        out = tmp_path / "out" / "itch.zip"
        names = itch.make_zip(str(build), SERVER, str(out))
        with zipfile.ZipFile(out) as zf:
            listed = zf.namelist()
            assert sorted(listed) == sorted(names)
            assert "index.html" in listed                       # zip kokunde
            assert "Build/WebGL.wasm.unityweb" in listed
            assert "TemplateData/style.css" in listed
            assert listed.count("server-config.js") == 1
            for name in listed:
                assert "\\" not in name and not name.startswith("/") and ".." not in name.split("/")
                assert not re.match(r"^[A-Za-z]:", name)
            assert baked_url(zf.read("server-config.js").decode()) == SERVER
            assert zf.read("socket.io.min.js") == b"/* io */"
        # kaynak build degismez
        assert (build / "server-config.js").read_text(encoding="utf-8") == 'window.CF4_SERVER_URL = "";\n'

    def test_missing_config_file_is_added(self, tmp_path):
        build = fake_build(tmp_path / "WebGL")
        (build / "server-config.js").unlink()
        out = tmp_path / "itch.zip"
        itch.make_zip(str(build), SERVER, str(out))
        with zipfile.ZipFile(out) as zf:
            assert baked_url(zf.read("server-config.js").decode()) == SERVER

    def test_gzip_build_without_fallback_is_refused(self, tmp_path):
        build = fake_build(tmp_path / "WebGL", fallback=False)
        with pytest.raises(itch.PackError, match="Decompression Fallback"):
            itch.make_zip(str(build), SERVER, str(tmp_path / "itch.zip"))
        assert not (tmp_path / "itch.zip").exists()
        itch.make_zip(str(build), SERVER, str(tmp_path / "itch.zip"), allow_precompressed=True)
        assert (tmp_path / "itch.zip").exists()

    def test_old_template_is_refused(self, tmp_path):
        build = fake_build(tmp_path / "WebGL", template=False)
        with pytest.raises(itch.PackError, match="server-config.js"):
            itch.make_zip(str(build), SERVER, str(tmp_path / "itch.zip"))

    def test_not_a_build(self, tmp_path):
        (tmp_path / "empty").mkdir()
        with pytest.raises(itch.PackError, match="index.html"):
            itch.make_zip(str(tmp_path / "empty"), SERVER, str(tmp_path / "itch.zip"))
        with pytest.raises(itch.PackError):
            itch.make_zip(str(tmp_path / "missing"), SERVER, str(tmp_path / "itch.zip"))

    def test_output_inside_build_is_refused(self, tmp_path):
        build = fake_build(tmp_path / "WebGL")
        with pytest.raises(itch.PackError, match="icinde"):
            itch.make_zip(str(build), SERVER, str(build / "itch.zip"))

    @pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink yok")
    def test_symlink_out_of_build_is_refused(self, tmp_path):
        build = fake_build(tmp_path / "WebGL")
        secret = tmp_path / "secret.txt"
        secret.write_text("gizli", encoding="utf-8")
        try:
            os.symlink(secret, build / "TemplateData" / "link.txt")
        except OSError:
            pytest.skip("symlink olusturulamadi")
        with pytest.raises(itch.PackError, match="sembolik"):
            itch.make_zip(str(build), SERVER, str(tmp_path / "itch.zip"))

    def test_invalid_url_writes_nothing(self, tmp_path):
        build = fake_build(tmp_path / "WebGL")
        with pytest.raises(itch.PackError):
            itch.make_zip(str(build), "https://connect4.example.com/", str(tmp_path / "itch.zip"))
        assert not (tmp_path / "itch.zip").exists()

    def test_file_count_limit(self, tmp_path, monkeypatch):
        build = fake_build(tmp_path / "WebGL")
        monkeypatch.setattr(itch, "MAX_FILES", 3)
        with pytest.raises(itch.PackError, match="dosya"):
            itch.make_zip(str(build), SERVER, str(tmp_path / "itch.zip"))

    def test_cli(self, tmp_path, capsys):
        build = fake_build(tmp_path / "WebGL")
        out = tmp_path / "itch.zip"
        assert itch.main([str(build), "--server", SERVER, "--out", str(out)]) == 0
        assert out.exists() and SERVER in capsys.readouterr().out
        assert itch.main([str(build), "--server", "http://x.example", "--out", str(out)]) == 2
        assert "HATA" in capsys.readouterr().err
