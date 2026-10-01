"""
tests/test_tmdb_key.py - La chiave TMDB predefinita: scelta, mascheratura e riservatezza.
Usa chiavi FINTE: nessuna chiave vera compare nei test.
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import requests  # noqa: E402

import embed_key  # noqa: E402
import media_operations as mo  # noqa: E402
import tmdb_client  # noqa: E402
import tmdb_key  # noqa: E402
from config import CONFIG  # noqa: E402

FAKE_DEFAULT = "d3f4u1tFAKEkey0123456789abcdef99"
FAKE_USER = "u5erFAKEkey9876543210fedcba000000"


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setitem(CONFIG, "api_key", "")
    monkeypatch.setattr(tmdb_key, "_cache", None)
    monkeypatch.setattr(tmdb_key, "_rd", None)


def _load_generated(path):
    spec = importlib.util.spec_from_file_location("generated_rd", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_embedded_file_does_not_contain_plain_key(tmp_path):
    out = tmp_path / "_runtime_data.py"
    assert embed_key.main([], out=out, env={"TMDB_API_KEY": FAKE_DEFAULT}) == 0
    text = out.read_text(encoding="utf-8")
    assert FAKE_DEFAULT not in text
    assert FAKE_DEFAULT[:10] not in text and FAKE_DEFAULT[-10:] not in text
    assert out.read_bytes().find(FAKE_DEFAULT.encode()) == -1


def test_embedded_key_roundtrip(tmp_path, monkeypatch):
    out = tmp_path / "_runtime_data.py"
    embed_key.main([], out=out, env={"TMDB_API_KEY": FAKE_DEFAULT})
    monkeypatch.setattr(tmdb_key, "_rd", _load_generated(out))
    assert tmdb_key.default_api_key() == FAKE_DEFAULT


def test_each_build_has_a_different_mask(tmp_path):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    embed_key.main([], out=a, env={"TMDB_API_KEY": FAKE_DEFAULT})
    embed_key.main([], out=b, env={"TMDB_API_KEY": FAKE_DEFAULT})
    assert a.read_text() != b.read_text()


def test_missing_key_is_ok_but_fails_when_required(tmp_path, capsys):
    out = tmp_path / "x.py"
    assert embed_key.main([], out=out, env={}) == 0 and not out.exists()
    assert embed_key.main(["--require"], out=out, env={}) == 1
    assert embed_key.main([], out=out, env={"TMDB_API_KEY": "corta"}) == 1
    printed = capsys.readouterr()
    assert "corta" not in printed.out


def test_user_key_wins_over_default(monkeypatch):
    monkeypatch.setattr(tmdb_key, "_cache", FAKE_DEFAULT)
    assert tmdb_key.effective_api_key() == FAKE_DEFAULT          # campo vuoto: predefinita
    CONFIG["api_key"] = FAKE_USER
    assert tmdb_key.effective_api_key() == FAKE_USER             # chiave personale: ha la precedenza
    assert tmdb_key.has_api_key()


def test_no_key_at_all(monkeypatch):
    assert tmdb_key.default_api_key() == "" and not tmdb_key.has_api_key()


def test_default_key_is_never_stored_in_config(monkeypatch):
    monkeypatch.setattr(tmdb_key, "_cache", FAKE_DEFAULT)
    tmdb_key.effective_api_key()
    assert FAKE_DEFAULT not in " ".join(str(v) for v in CONFIG.values())


def test_request_uses_effective_key(monkeypatch):
    monkeypatch.setattr(tmdb_key, "_cache", FAKE_DEFAULT)
    seen = {}

    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"ok": True}

    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=0: seen.update(params) or R())
    assert tmdb_client.tmdb("/movie/1") == {"ok": True}
    assert seen["api_key"] == FAKE_DEFAULT


def test_default_key_never_leaks_in_errors_or_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(tmdb_key, "_cache", FAKE_DEFAULT)

    def boom(url, params=None, timeout=0):
        raise requests.ConnectionError(f"HTTPSConnectionPool: url=/3/movie/1?api_key={FAKE_DEFAULT}&language=it")

    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(RuntimeError) as err:
        tmdb_client.tmdb("/movie/1")
    assert FAKE_DEFAULT not in str(err.value) and "***" in str(err.value)

    monkeypatch.setitem(CONFIG, "logs_dir", str(tmp_path))
    mo.log_event("ERROR", f"qualcosa con {FAKE_DEFAULT} dentro")
    mo.log_csv_row("movies", ["a", "b"], ["x", f"riga con {FAKE_DEFAULT}"])
    written = [f for f in tmp_path.rglob("*") if f.is_file()]
    assert len(written) == 2, "il test non ha scritto né il log né il CSV: sarebbe un test vuoto"
    for f in written:
        text = f.read_text(encoding="utf-8-sig")
        assert FAKE_DEFAULT not in text, f.name
        assert "***" in text, f.name


def test_redact_hides_both_keys(monkeypatch):
    monkeypatch.setattr(tmdb_key, "_cache", FAKE_DEFAULT)
    CONFIG["api_key"] = FAKE_USER
    out = mo.redact(f"a {FAKE_DEFAULT} b {FAKE_USER} c")
    assert FAKE_DEFAULT not in out and FAKE_USER not in out
