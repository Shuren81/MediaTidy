#!/usr/bin/env python3
"""
config.py - Configurazione condivisa e persistente di MediaTidy (film + serie).

Impostazioni GLOBALI (Opzioni): chiave API, lingua ricerca TMDB, capitalizzazione,
smontaggio automatico, pulizia cartelle di origine, lingua interfaccia, cartella log.

Impostazioni PER SCHEDA (Formato Nomi): destinazione, azione Sposta/Copia, modalità
titolo (originale/localizzato/entrambi) e i toggle di cosa includere nel nome/cartella
— indipendenti tra Film e Serie TV.
"""
import os
from pathlib import Path

from qtpy.QtCore import QSettings

APP_NAME = "MediaTidy"
VERSION = "1.0.1"

DEFAULT_LOGS_DIR = str(Path.home() / ".local" / "share" / "MediaTidy" / "logs")

# Modalità titolo valide per "movie_title_mode"/"series_title_mode":
#   "original"  -> solo il titolo originale
#   "localized" -> solo il titolo nella lingua di ricerca (con fallback sull'originale se mancante)
#   "orig_loc"  -> "Originale (Localizzato)"
#   "loc_orig"  -> "Localizzato (Originale)"
TITLE_MODES = ("original", "localized", "orig_loc", "loc_orig")

CONFIG = {
    # --- Opzioni (globali) ---
    "api_key": "",
    "lang": "en-US",
    "cap_rule": 2,
    "unmount": True,
    "clean_parent_dir": False,
    "gui_lang": "it",
    "logs_dir": DEFAULT_LOGS_DIR,

    # --- Formato Nomi: Film ---
    "dest_movies": "",
    "action_movies": "move",
    "movie_title_mode": "orig_loc",
    "movie_include_tmdb_id": True,
    "movie_include_country": True,
    "movie_include_director": True,
    "movie_download_poster": True,

    # --- Formato Nomi: Serie TV ---
    "dest_series": "",
    "action_series": "move",
    "series_title_mode": "orig_loc",
    "series_include_tmdb_id": True,
    "series_include_country": True,
    "series_include_episode_title": True,
    "series_download_show_poster": True,
    "series_download_season_poster": True,
}

_settings = QSettings("MediaTidy", "gui")


def load_config():
    """Carica CONFIG da QSettings, con migrazione dalle chiavi delle versioni precedenti."""
    CONFIG["gui_lang"] = _settings.value("gui_lang", "it")
    CONFIG["api_key"] = _settings.value("api_key", os.environ.get("TMDB_API_KEY", ""))
    CONFIG["lang"] = _settings.value("lang", "en-US")
    CONFIG["cap_rule"] = int(_settings.value("cap_rule", 2))
    CONFIG["unmount"] = _settings.value("unmount", True, type=bool)
    CONFIG["clean_parent_dir"] = _settings.value("clean_parent_dir", False, type=bool)
    CONFIG["logs_dir"] = _settings.value("logs_dir", DEFAULT_LOGS_DIR)

    # Migrazione: v0.1 aveva un'unica "dest", v0.3 un'unica "action" condivisa.
    old_dest = _settings.value("dest", "")
    old_action = _settings.value("action", "move")
    CONFIG["dest_movies"] = _settings.value("dest_movies", old_dest or os.environ.get("MEDIA_DEST", ""))
    CONFIG["dest_series"] = _settings.value("dest_series", "")
    CONFIG["action_movies"] = _settings.value("action_movies", old_action)
    CONFIG["action_series"] = _settings.value("action_series", old_action)

    CONFIG["movie_title_mode"] = _settings.value("movie_title_mode", "orig_loc")
    CONFIG["movie_include_tmdb_id"] = _settings.value("movie_include_tmdb_id", True, type=bool)
    CONFIG["movie_include_country"] = _settings.value("movie_include_country", True, type=bool)
    CONFIG["movie_include_director"] = _settings.value("movie_include_director", True, type=bool)
    CONFIG["movie_download_poster"] = _settings.value("movie_download_poster", True, type=bool)

    CONFIG["series_title_mode"] = _settings.value("series_title_mode", "orig_loc")
    CONFIG["series_include_tmdb_id"] = _settings.value("series_include_tmdb_id", True, type=bool)
    CONFIG["series_include_country"] = _settings.value("series_include_country", True, type=bool)
    CONFIG["series_include_episode_title"] = _settings.value("series_include_episode_title", True, type=bool)
    CONFIG["series_download_show_poster"] = _settings.value("series_download_show_poster", True, type=bool)
    CONFIG["series_download_season_poster"] = _settings.value("series_download_season_poster", True, type=bool)


def save_config():
    """Salva l'intero CONFIG in QSettings."""
    for key, value in CONFIG.items():
        _settings.setValue(key, value)
