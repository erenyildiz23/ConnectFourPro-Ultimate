""".github/workflows/arena-cheat-check.yml: ucuncu taraf kod sabitlenmis ve dogrulanmis mi?"""

import os
import re

import config

WORKFLOW = os.path.join(config.PROJECT_ROOT, ".github", "workflows", "arena-cheat-check.yml")
PONS_SHA = "d6ba50d8aaf2308c769d9bf2abd42d90f34baf41"
BOOK_SHA256 = "f346cd449626fb81da93be0958e017ee854e5f74d85b6d38062357f5403aec53"


def _text():
    with open(WORKFLOW, encoding="utf-8") as f:
        return f.read()


def test_pons_pinned_to_fixed_commit():
    text = _text()
    assert "ls-remote" not in text, "Pons HEAD her kosuda yeniden cozulmemeli"
    assert PONS_SHA in text
    # Onbellek anahtari sabit SHA'ya bagli
    assert re.search(r"key: c4solver-\$\{\{ env\.PONS_SHA \}\}", text)


def test_opening_book_checksum_verified():
    text = _text()
    assert BOOK_SHA256 in text
    assert "sha256sum -c" in text


def test_checkout_does_not_persist_credentials():
    text = _text()
    checkout = re.search(r"uses: actions/checkout@\S+\n((?:\s{8,}.*\n)+)", text)
    assert checkout, "actions/checkout adimi yok"
    assert "persist-credentials: false" in checkout.group(1)


def test_secret_only_at_step_level():
    text = _text()
    top = text.split("\njobs:", 1)[0]
    assert "secrets." not in top
    job_head = text.split("\njobs:", 1)[1].split("steps:", 1)[0]
    assert "secrets." not in job_head
