#!/usr/bin/env python3
"""
platform_utils.py - Differenze tra Linux, Windows e macOS, raccolte in un solo punto.

Regole decise per la 1.1:
- le destinazioni remote (SSH/rsync) e il montaggio/smontaggio automatico da
  /etc/fstab esistono SOLO su Linux;
- su Windows e macOS la destinazione è sempre un percorso locale (disco interno,
  esterno o di rete già montato dal sistema, es. "D:\\Film" o "/Volumes/NAS/Film").
"""
import os
import re
import subprocess
import sys
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
