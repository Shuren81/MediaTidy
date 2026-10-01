#!/usr/bin/env python3
"""
platform_utils.py - Differenze tra Linux, Windows e macOS, raccolte in un solo punto.

Regole decise per la 1.1:
- le destinazioni remote (SSH/rsync) e il montaggio/smontaggio automatico da
  /etc/fstab esistono SOLO su Linux;
- su Windows e macOS la destinazione è sempre un percorso locale (disco interno,
  esterno o di rete già montato dal sistema, es. "D:\\Film" o "/Volumes/NAS/Film").
"""
import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Windows: percorsi con lettera di unità ("C:\\...", "C:/...") o UNC ("\\\\server\\share").
_WINDOWS_ABS_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")

# Nomi di file/cartella riservati da Windows (anche con estensione: "CON.txt").
_WINDOWS_RESERVED = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)

# Windows (senza il supporto ai percorsi lunghi attivato) non gestisce percorsi
# completi più lunghi di 259 caratteri.
WINDOWS_MAX_PATH = 259


def supports_remote():
    """Destinazioni SSH (utente@host:/percorso): solo Linux."""
    return IS_LINUX


def supports_fstab_mount():
    """Montaggio/smontaggio automatico dei dischi da /etc/fstab: solo Linux."""
    return IS_LINUX


def looks_like_windows_path(path):
    return bool(_WINDOWS_ABS_RE.match(str(path)))


def default_log_dir():
    """Cartella standard per log e CSV su ciascun sistema.
    Linux: ~/.local/share/MediaTidy/logs (invariata rispetto alla 1.0)
    Windows: %LOCALAPPDATA%\\MediaTidy\\logs
    macOS: ~/Library/Application Support/MediaTidy/logs"""
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "MediaTidy" / "logs"
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / "MediaTidy" / "logs"
    return Path.home() / ".local" / "share" / "MediaTidy" / "logs"


def resource_path(name):
    """Percorso di un file distribuito col programma (es. l'icona), sia avviando da
    sorgente sia dall'eseguibile creato da PyInstaller (che estrae i dati in _MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / name
    return Path(__file__).resolve().parent / name


def safe_component(name):
    """Rende un singolo nome di file o cartella valido anche su Windows (e sui dischi
    NTFS/exFAT usati da Linux e macOS): toglie punti e spazi finali, che Windows
    elimina in silenzio, e aggiunge "_" ai nomi riservati (CON, NUL, COM1...).
    Applicato su tutti i sistemi, così la stessa libreria ha gli stessi nomi ovunque."""
    if not name:
        return name
    cleaned = name.rstrip(" .")
    if not cleaned:
        return "_"
    stem = cleaned.split(".", 1)[0]
    if stem.upper() in _WINDOWS_RESERVED:
        cleaned = f"{stem}_{cleaned[len(stem):]}"
    return cleaned


def safe_relative_path(rel):
    """Applica safe_component a ogni parte di un percorso relativo "a/b/c"."""
    parts = str(rel).replace("\\", "/").split("/")
    return "/".join(safe_component(p) for p in parts)


def path_too_long(full_path):
    """True se il percorso completo supera il limite di Windows (solo su Windows)."""
    return IS_WINDOWS and len(str(full_path)) > WINDOWS_MAX_PATH


def play_done_sound():
    """Suono di fine operazione. Ritorna True se è stato riprodotto."""
    try:
        if IS_WINDOWS:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            return True
        if IS_MACOS:
            sound = "/System/Library/Sounds/Glass.aiff"
            if os.path.exists(sound):
                subprocess.Popen(["afplay", sound], stderr=subprocess.DEVNULL)
                return True
    except Exception:
        pass
    return False


def notify(title, message):
    """Notifica di sistema per Windows/macOS. Ritorna True se inviata.
    Windows: nessuna notifica nativa senza dipendenze aggiuntive; il riepilogo di fine
    lavoro compare comunque a schermo."""
    if IS_MACOS:
        try:
            esc = lambda s: str(s).replace("\\", "\\\\").replace('"', '\\"')
            subprocess.Popen(
                ["osascript", "-e", f'display notification "{esc(message)}" with title "{esc(title)}"'],
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False
    return False


# --------------------------------------------------------------------------- #
#  Apertura di cartelle e link con i programmi di sistema
# --------------------------------------------------------------------------- #
# Variabili che un pacchetto PyInstaller/AppImage imposta verso le SUE librerie interne:
# se restano nell'ambiente, i programmi esterni lanciati da MediaTidy (xdg-open, il
# browser, il file manager) caricano librerie incompatibili e non partono.
_BUNDLE_PATH_VARS = ("QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH")


def _strip_bundle_paths(value, bundle_dir):
    """Toglie da una lista di percorsi (separati da ':') quelli dentro bundle_dir."""
    kept = [p for p in value.split(os.pathsep) if p and not (bundle_dir and p.startswith(bundle_dir))]
    return os.pathsep.join(kept)


def child_environment(environ=None):
    """Ambiente da dare ai programmi esterni: quello attuale, ripulito dai percorsi
    interni del pacchetto quando MediaTidy gira da AppImage/eseguibile PyInstaller su Linux."""
    env = dict(os.environ if environ is None else environ)
    if not (IS_LINUX and getattr(sys, "frozen", False)):
        return env
    bundle_dir = getattr(sys, "_MEIPASS", "") or ""
    orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig            # valore che c'era prima dell'avvio
    elif "LD_LIBRARY_PATH" in env:
        cleaned = _strip_bundle_paths(env["LD_LIBRARY_PATH"], bundle_dir)
        if cleaned:
            env["LD_LIBRARY_PATH"] = cleaned
        else:
            env.pop("LD_LIBRARY_PATH")
    for var in _BUNDLE_PATH_VARS:
        if var in env:
            cleaned = _strip_bundle_paths(env[var], bundle_dir)
            if cleaned:
                env[var] = cleaned
            else:
                env.pop(var)
    return env


@contextlib.contextmanager
def cleaned_environ():
    """Applica child_environment() a os.environ per la durata del blocco (serve quando a
    lanciare il programma esterno è Qt, che usa l'ambiente del processo)."""
    clean = child_environment()
    previous = {}
    for key in set(os.environ) | set(clean):
        if os.environ.get(key) != clean.get(key):
            previous[key] = os.environ.get(key)
            if clean.get(key) is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = clean[key]
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_opener(cmd, env, wait=0.8):
    """Lancia un programma di apertura staccato da MediaTidy. Ritorna (ok, dettagli).
    Se è ancora in esecuzione dopo qualche secondo (es. un browser appena avviato) conta
    come riuscito; se esce con errore, riporta il suo messaggio."""
    with tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=err, start_new_session=True)
        except OSError as exc:
            return False, f"{cmd[0]}: {exc}"
        try:
            code = proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            return True, ""
        if code == 0:
            return True, ""
        err.seek(0)
        text = err.read().decode(errors="replace").strip()
        return False, f"{cmd[0]}: {text or 'codice di uscita ' + str(code)}"


def open_external(target):
    """Apre una cartella, un file o un indirizzo web con il programma predefinito del
    sistema. Ritorna (ok, dettagli): i dettagli spiegano l'errore se ok è False."""
    target = str(target)
    if IS_WINDOWS:
        try:
            os.startfile(target)               # cartelle, file e indirizzi web
            return True, ""
        except OSError as exc:
            return False, str(exc)
    env = child_environment()
    if IS_MACOS:
        return _run_opener(["open", target], env)
    problems = []
    for cmd in (["xdg-open", target], ["gio", "open", target]):
        if shutil.which(cmd[0]):
            ok, details = _run_opener(cmd, env)
            if ok:
                return True, ""
            problems.append(details)
    return False, " | ".join(problems) or "né xdg-open né gio sono installati"
