""".env yukleme ve kurulum yardimcisi testleri."""

import importlib.util
import os
from urllib.parse import unquote, urlsplit

import config

_spec = importlib.util.spec_from_file_location(
    "setup_env", os.path.join(config.PROJECT_ROOT, "scripts", "setup_env.py"))
setup_env = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup_env)


class TestEnvFile:
    def test_parse_handles_comments_quotes_and_blank_lines(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text('# yorum\n\nA=1\nB = "iki kelime"\nC=\'tek\'\nD=x=y\nbozuk satir\n', encoding="utf-8")
        assert config.parse_env_file(str(env)) == {"A": "1", "B": "iki kelime", "C": "tek", "D": "x=y"}

    def test_missing_file_is_empty(self, tmp_path):
        assert config.parse_env_file(str(tmp_path / "yok.env")) == {}

    def test_environment_variables_take_precedence(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("C4_TEST_ONLY_FILE=dosya\nC4_TEST_BOTH=dosya\n", encoding="utf-8")
        monkeypatch.delenv("C4_TEST_ONLY_FILE", raising=False)
        monkeypatch.setenv("C4_TEST_BOTH", "terminal")
        config.load_env_file(str(env))
        assert os.environ["C4_TEST_ONLY_FILE"] == "dosya"
        assert os.environ["C4_TEST_BOTH"] == "terminal"
        monkeypatch.delenv("C4_TEST_ONLY_FILE")


class TestSetupHelpers:
    def test_password_special_characters_are_url_encoded(self):
        url = setup_env.build_url("postgres", "p@ss:w/rd#1", "localhost", "5432", "connect4")
        parts = urlsplit(url)
        assert parts.hostname == "localhost" and parts.port == 5432 and parts.path == "/connect4"
        assert unquote(parts.password) == "p@ss:w/rd#1"

    def test_empty_password_is_omitted(self):
        assert setup_env.build_url("postgres", "", "db", "5432", "x") == "postgresql://postgres@db:5432/x"

    def test_with_database_replaces_only_the_name(self):
        url = "postgresql://u:p%40@h:5433/connect4?sslmode=require"
        assert setup_env.with_database(url, "connect4_test") == "postgresql://u:p%40@h:5433/connect4_test?sslmode=require"
