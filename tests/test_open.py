"""
tests/test_open.py - Apertura di cartelle e link con i programmi di sistema.

Un fallimento di xdg-open/QDesktopServices era silenzioso: il bottone "Apri cartella" o un
link non facevano nulla e non si capiva perché. Qui si verifica che (1) il programma esterno
parta con un ambiente pulito dai percorsi interni del pacchetto, (2) ogni bottone e ogni link
passi dallo stesso punto, (3) se l'apertura fallisce l'utente lo sappia.
"""
import os
import re
import stat
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qtpy.QtCore import QUrl  # noqa: E402
from qtpy.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QTextBrowser  # noqa: E402

import platform_utils as pu  # noqa: E402

linux_only = pytest.mark.skipif(not pu.IS_LINUX, reason="xdg-open esiste solo su Linux")


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def frozen_linux(monkeypatch):
    """Simula un pacchetto PyInstaller/AppImage su Linux."""
    monkeypatch.setattr(pu, "IS_LINUX", True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/_MEIabc123", raising=False)


# ------------------------------------------------------------------ ambiente pulito
def test_child_environment_restores_original_library_path(frozen_linux):
    env = pu.child_environment({"LD_LIBRARY_PATH": "/tmp/_MEIabc123", "LD_LIBRARY_PATH_ORIG": "/opt/real", "HOME": "/h"})
    assert env["LD_LIBRARY_PATH"] == "/opt/real"
    assert "LD_LIBRARY_PATH_ORIG" not in env and env["HOME"] == "/h"


def test_child_environment_drops_bundle_only_paths(frozen_linux):
    assert "LD_LIBRARY_PATH" not in pu.child_environment({"LD_LIBRARY_PATH": "/tmp/_MEIabc123"})
    assert pu.child_environment({"LD_LIBRARY_PATH": "/tmp/_MEIabc123:/opt/lib"})["LD_LIBRARY_PATH"] == "/opt/lib"


def test_child_environment_cleans_qt_variables(frozen_linux):
    env = pu.child_environment({
        "QT_PLUGIN_PATH": "/tmp/_MEIabc123/PyQt5/Qt5/plugins",
        "QML2_IMPORT_PATH": "/tmp/_MEIabc123/qml:/usr/lib/qt5/qml",
    })
    assert "QT_PLUGIN_PATH" not in env
    assert env["QML2_IMPORT_PATH"] == "/usr/lib/qt5/qml"


def test_child_environment_untouched_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    original = {"LD_LIBRARY_PATH": "/qualcosa", "QT_PLUGIN_PATH": "/altro"}
    assert pu.child_environment(original) == original


def test_cleaned_environ_is_temporary(frozen_linux, monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEIabc123")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/opt/real")
    with pu.cleaned_environ():
        assert os.environ["LD_LIBRARY_PATH"] == "/opt/real"
        assert "LD_LIBRARY_PATH_ORIG" not in os.environ
    assert os.environ["LD_LIBRARY_PATH"] == "/tmp/_MEIabc123"      # ripristinato
    assert os.environ["LD_LIBRARY_PATH_ORIG"] == "/opt/real"


# ------------------------------------------------------------------ programma esterno vero
def _fake_xdg_open(tmp_path, monkeypatch, exit_code=0, stderr=""):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "calls.log"
    script = bindir / "xdg-open"
    script.write_text(
        "#!/bin/sh\n"
        f'echo "ARGS=[$*] LD=[$LD_LIBRARY_PATH] QTP=[$QT_PLUGIN_PATH]" >> "{log}"\n'
        + (f'echo "{stderr}" >&2\n' if stderr else "")
        + f"exit {exit_code}\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(bindir))      # niente gio né altro: solo il finto xdg-open
    return log


@linux_only
def test_open_external_runs_xdg_open_with_clean_environment(tmp_path, monkeypatch, frozen_linux):
    log = _fake_xdg_open(tmp_path, monkeypatch)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEIabc123")
    monkeypatch.setenv("QT_PLUGIN_PATH", "/tmp/_MEIabc123/PyQt5/Qt5/plugins")
    ok, details = pu.open_external("/media/Nuovo/Telefilm/Doctor Who (2005)/Season 07")
    assert ok, details
    line = log.read_text()
    assert "ARGS=[/media/Nuovo/Telefilm/Doctor Who (2005)/Season 07]" in line
    assert "LD=[]" in line and "QTP=[]" in line, line       # i percorsi interni NON arrivano al figlio


@linux_only
def test_open_external_reports_why_it_failed(tmp_path, monkeypatch):
    _fake_xdg_open(tmp_path, monkeypatch, exit_code=3, stderr="nessun file manager predefinito")
    ok, details = pu.open_external("/tmp")
    assert ok is False
    assert "nessun file manager predefinito" in details


@linux_only
def test_open_external_without_any_opener(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))                  # cartella vuota
    ok, details = pu.open_external("/tmp")
    assert ok is False and "xdg-open" in details


# ------------------------------------------------------------------ interfaccia
def test_open_target_tells_the_user_when_it_fails(app, tmp_path, monkeypatch):
    import ui.widgets as w
    monkeypatch.setattr(w, "open_external", lambda t: (False, "boom"))
    monkeypatch.setattr(w.QDesktopServices, "openUrl", staticmethod(lambda url: False))
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda parent, title, text: shown.append(text)))
    assert w.open_target(tmp_path) is False
    assert len(shown) == 1 and "boom" in shown[0] and str(tmp_path) in shown[0]
    assert QApplication.clipboard().text() == str(tmp_path)       # copiato negli appunti


def test_open_target_success_is_silent(app, tmp_path, monkeypatch):
    import ui.widgets as w
    monkeypatch.setattr(w, "open_external", lambda t: (True, ""))
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda parent, title, text: shown.append(text)))
    assert w.open_target(tmp_path) is True and shown == []


def test_open_target_missing_folder(app, tmp_path, monkeypatch):
    import ui.widgets as w
    called = []
    monkeypatch.setattr(w, "open_external", lambda t: called.append(t) or (True, ""))
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda parent, title, text: shown.append(text)))
    assert w.open_target(tmp_path / "non_esiste") is False
    assert called == [] and len(shown) == 1


def test_open_folder_button_goes_through_open_target(app, tmp_path, monkeypatch):
    import ui.widgets as w
    from localization import tr
    seen = []
    monkeypatch.setattr(w, "open_target", lambda target, parent=None: seen.append(str(target)) or True)
    dlg = w.NonEmptyDirDialog(str(tmp_path), "1.0 GB")
    [b for b in dlg.findChildren(QPushButton) if b.text() == tr("btn_open_folder")][0].click()
    assert seen == [str(tmp_path)]


def test_options_link_is_a_single_clickable_link(app, monkeypatch):
    import ui.widgets as w
    from ui.settings_dialog import SettingsDialog
    seen = []
    monkeypatch.setattr(w, "open_target", lambda target, parent=None: seen.append(target) or True)
    dlg = SettingsDialog()
    label = [l for l in dlg.findChildren(QLabel) if "href" in l.text()][0]
    assert len(re.findall(r"<a ", label.text())) == 1, "collegamenti annidati: la scritta risulterebbe tutta blu e non apribile"
    assert label.openExternalLinks() is False        # il clic passa dal nostro punto, che segnala gli errori
    label.linkActivated.emit("https://developer.themoviedb.org/docs/getting-started")
    assert seen == ["https://developer.themoviedb.org/docs/getting-started"]


def test_credits_links_go_through_open_target(app, monkeypatch):
    import ui.widgets as w
    seen = []
    monkeypatch.setattr(w, "open_target", lambda target, parent=None: seen.append(target) or True)
    dlg = w.CreditsPrivacyDialog()
    browsers = dlg.findChildren(QTextBrowser)
    assert len(browsers) == 2
    for b in browsers:
        b.anchorClicked.emit(QUrl("https://www.themoviedb.org/"))
    assert seen == ["https://www.themoviedb.org/"] * 2
