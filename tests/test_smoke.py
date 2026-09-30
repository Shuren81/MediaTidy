"""
tests/test_smoke.py - Test automatici eseguiti da GitHub Actions su Linux, Windows e macOS.

Nessuna chiamata di rete: le risposte di TMDB sono simulate. Le operazioni sui file
invece sono REALI, sul filesystem del sistema che esegue il test: su Windows (NTFS) e
macOS (APFS) il disco non distingue le maiuscole, quindi qui si verifica davvero la
gestione delle maiuscole che su Linux si può solo simulare.

Esecuzione locale:  QT_QPA_PLATFORM=offscreen python -m pytest -v tests
"""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qtpy.QtWidgets import QApplication  # noqa: E402

from config import CONFIG  # noqa: E402
import platform_utils as pu  # noqa: E402
import media_operations as mo  # noqa: E402
import core.movie_handler as mh  # noqa: E402
import core.series_handler as sh  # noqa: E402
import tmdb_client  # noqa: E402


class _NoSignal:
    def emit(self, *a, **k):
        pass


def _mute(worker):
    for name in ("all_done", "row_update", "progress", "status", "file_progress", "error"):
        setattr(worker, name, _NoSignal())
    return worker


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_tmdb(monkeypatch):
    movies = {
        "1": ("3 Men and a Little Lady", "1990", "US", "Emile Ardolino"),
        "2": ("Film Due", "2020", "IT", "Regista"),
    }

    def movie(mid, lang=None):
        title, year, country, director = movies[str(mid)]
        return {"id": mid, "original": title, "english_or_local": title, "year": year,
                "country": country, "director": director, "poster_path": None}

    monkeypatch.setattr(mh, "get_movie_details_by_id", movie)
    monkeypatch.setattr(sh, "get_tv_details_by_id", lambda tv_id, lang=None: {
        "id": tv_id, "original": "Lanterns", "english_or_local": "Lanterns",
        "year": "2026", "country": "US", "poster_path": None})
    monkeypatch.setattr(sh, "get_episode_title", lambda *a, **k: "Pilot")
    monkeypatch.setattr(tmdb_client, "get_season_details", lambda *a, **k: {})


def _movie_item(path, tmdb_id):
    return {"path": Path(path), "from_dir": False, "tmdb_id": tmdb_id, "folder": "", "newname": "",
            "status": "status_to_test", "status_detail": "", "poster_path": None,
            "custom_override": False, "force_overwrite": False, "lang": None}


# --------------------------------------------------------------------------- #
def test_main_window_starts(app):
    from ui.main_window import MainWindow
    w = MainWindow()
    assert "MediaTidy" in w.title_label.text()


def test_icon_is_found():
    assert pu.resource_path("MT_Icon.png").is_file()


def test_platform_rules():
    # Una lettera di unità di Windows non è mai una destinazione SSH.
    assert mo.is_remote(r"D:\Film") is False
    assert mo.is_remote("D:/Film") is False
    # Le destinazioni SSH esistono solo su Linux.
    assert mo.is_remote("pi@raspberry:/mnt/film") is pu.IS_LINUX
    assert pu.safe_component("nul.mkv") == "nul_.mkv"
    assert pu.safe_component("To Be Continued...") == "To Be Continued"


def test_movie_move_to_new_folder(tmp_path, fake_tmdb):
    src = tmp_path / "download"
    src.mkdir()
    f = src / "Film.Due.2020.1080p.mkv"
    f.write_bytes(b"VIDEO")
    dest = tmp_path / "Film"
    CONFIG["dest_movies"] = str(dest)

    it = _movie_item(f, "2")
    w = _mute(mh.MovieWorker(items=[it], rows=[0], mode="action", action="move", clean_parent=True))
    w._ask_non_empty_dir = lambda *a: "no"
    w._test(0, it)
    assert it["status"] == "status_ready"
    w._process(0, it)
    w._cleanup_source_dirs()

    moved = list(dest.rglob("*.mkv"))
    assert [p.name for p in moved] == ["Film Due (2020).mkv"]
    assert moved[0].read_bytes() == b"VIDEO"
    assert not src.exists()  # cartella di origine rimasta vuota: rimossa


def test_case_only_rename_in_library(tmp_path, fake_tmdb):
    """Libreria con maiuscole diverse da quelle calcolate: su Windows/macOS è lo stesso
    file per il sistema. Deve essere rinominato sul posto, senza perdere il file e
    senza chiedere di cancellare la cartella."""
    dest = tmp_path / "Film"
    old = dest / "3 Men and a Little Lady (1990) {tmdb-1} [US, Emile Ardolino]"
    old.mkdir(parents=True)
    f = old / "3 Men and a Little Lady (1990).avi"
    f.write_bytes(b"CONTENUTO")
    CONFIG["dest_movies"] = str(dest)

    it = _movie_item(f, "1")
    w = _mute(mh.MovieWorker(items=[it], rows=[0], mode="action", action="move", clean_parent=True))

    def no_prompt(*a):
        raise AssertionError("nessuna domanda di cancellazione attesa")
    w._ask_non_empty_dir = no_prompt
    w._ask_duplicate = no_prompt

    w._test(0, it)
    assert it["status"] == "status_ready_inplace_rename"
    w._process(0, it)
    w._cleanup_source_dirs()

    files = list(dest.rglob("*.avi"))
    assert len(files) == 1 and files[0].read_bytes() == b"CONTENUTO"
    assert [p.name for p in dest.iterdir()] == ["3 Men And A Little Lady (1990) {tmdb-1} [US, Emile Ardolino]"]
    assert files[0].name == "3 Men And A Little Lady (1990).avi"

    # Un nuovo Test sul file ora deve risultare già a posto.
    it2 = _movie_item(files[0], "1")
    mh.MovieWorker(items=[it2], rows=[], mode="test")._test(0, it2)
    assert it2["status"] == "status_ready_inplace"


def test_series_episode_with_year(tmp_path, fake_tmdb):
    src = tmp_path / "Lanterns.S01"
    src.mkdir()
    (src / "Lanterns.2026.S01E01.1080p.mkv").write_bytes(b"EP")
    dest = tmp_path / "Serie"
    CONFIG["dest_series"] = str(dest)
    CONFIG["series_year_in_filename"] = True
    try:
        items = sh.collect_items_for_path(str(src), set())
        assert len(items) == 1
        items[0]["tmdb_id"] = "7"
        w = _mute(sh.SeriesWorker(items=items, rows=[0], mode="action", action="move", clean_parent=True))
        w._ask_non_empty_dir = lambda *a: "no"
        w._test(0, items[0])
        w._process(0, items[0])
        out = list(dest.rglob("*.mkv"))
        assert [p.name for p in out] == ["Lanterns (2026) - S01E01 - Pilot.mkv"]
        assert out[0].parent.name == "Season 01"
    finally:
        CONFIG["series_year_in_filename"] = False
