#!/usr/bin/env python3
"""
config.py - Configurazione condivisa e persistente di MediaTidy (film + serie).
"""
import os
from qtpy.QtCore import QSettings

APP_NAME = "MediaTidy"
VERSION = "0.1.0"

CONFIG = {
    "api_key": "",
    "dest_movies": "",
    "dest_series": "",
    "lang": "en-US",
    "cap_rule": 2,
    "action": "move",
    "unmount": True,
    "clean_parent_dir": False,
    "gui_lang": "it",
}

_settings = QSettings("MediaTidy", "gui")

def load_config():
    """Carica CONFIG da QSettings."""
    CONFIG["gui_lang"] = _settings.value("gui_lang", "it")
    CONFIG["api_key"] = _settings.value("api_key", os.environ.get("TMDB_API_KEY", ""))
    
    # Carica destinazioni separate
    old_dest = _settings.value("dest", "")
    CONFIG["dest_movies"] = _settings.value("dest_movies", old_dest or os.environ.get("MEDIA_DEST", ""))
    CONFIG["dest_series"] = _settings.value("dest_series", "")
    
    CONFIG["lang"] = _settings.value("lang", "en-US")
    CONFIG["cap_rule"] = int(_settings.value("cap_rule", 2))
    CONFIG["action"] = _settings.value("action", "move")
    CONFIG["unmount"] = _settings.value("unmount", True, type=bool)
    CONFIG["clean_parent_dir"] = _settings.value("clean_parent_dir", False, type=bool)

def save_config():
    """Salva l'intero CONFIG in QSettings."""
    for key, value in CONFIG.items():
        _settings.setValue(key, value)
