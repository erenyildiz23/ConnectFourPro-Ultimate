"""Sifreleme ve ELO hesabi (veritabani gerektirmez)."""

import hashlib

import pytest

import database as db


class TestPasswordHashing:
    def test_hash_is_salted_pbkdf2(self):
        h1, h2 = db.hash_password("secret"), db.hash_password("secret")
        assert h1.startswith("pbkdf2_sha256$") and h1 != h2   # farkli tuz
        assert "secret" not in h1

    def test_check_password(self):
        stored = db.hash_password("secret")
        assert db.check_password("secret", stored)
        assert not db.check_password("Secret", stored)
        assert not db.check_password("", stored)

    def test_legacy_sha256_hashes_still_verify(self):
        legacy = hashlib.sha256(b"old-pass").hexdigest()
        assert db.check_password("old-pass", legacy)
        assert not db.check_password("wrong", legacy)
        assert db._needs_rehash(legacy)

    def test_iteration_count_is_stored_and_used(self):
        stored = db.hash_password("pw", iterations=1234)
        assert stored.split("$")[1] == "1234"
        assert db.check_password("pw", stored)

    @pytest.mark.parametrize("stored", ["pbkdf2_sha256$bad", "pbkdf2_sha256$x$y$z", ""])
    def test_malformed_hashes_never_verify(self, stored):
        assert not db.check_password("pw", stored)


class TestElo:
    def test_equal_ratings_split_k_factor(self):
        assert db.elo_change(1200, 1200, k_factor=30) == 15

    def test_upset_win_gains_more(self):
        assert db.elo_change(1000, 1400, k_factor=30) > db.elo_change(1400, 1000, k_factor=30)

    def test_minimum_change(self):
        assert db.elo_change(2000, 1000, k_factor=30, minimum=10) == 10

    def test_never_exceeds_k_factor(self):
        assert db.elo_change(0, 3000, k_factor=30) <= 30
