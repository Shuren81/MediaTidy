#!/usr/bin/env python3
"""
tmdb_client.py - Chiamate alle API di TMDB, per film e per serie TV.

Un'unica funzione tmdb() di basso livello (usata anche da media_operations per lo
scaricamento del poster tramite l'URL restituito qui) piu' le funzioni specifiche
per film ("/movie", "/search/movie") e per serie TV ("/tv", "/search/tv",
"/tv/{id}/season/{s}/episode/{e}" per il titolo del singolo episodio).
"""
from config import CONFIG
from media_operations import redact

import requests


def tmdb(path, **params):
    params["api_key"] = CONFIG["api_key"]
    try:
        r = requests.get(f"https://api.themoviedb.org/3{path}", params=params, timeout=15)
        if r.status_code == 401:
            raise RuntimeError("Chiave API TMDB non valida")
        r.raise_for_status()
    except requests.RequestException as e:
        # L'URL contenuto nell'eccezione include api_key: non deve mai arrivare a UI/log/CSV.
        raise RuntimeError(redact(e)) from None
    return r.json()


# --------------------------------------------------------------------------- #
#  Film
# --------------------------------------------------------------------------- #
def get_movie_details_by_id(movie_id, lang=None):
    language = lang or CONFIG["lang"]
    d = tmdb(f"/movie/{movie_id}", language=language, append_to_response="credits")

    directors = [c["name"] for c in d.get("credits", {}).get("crew", [])
                 if c.get("job") == "Director" and c.get("name")]
    director_str = ", ".join(directors) if directors else "Regista sconosciuto"

    countries = d.get("origin_country", [])
    if not countries and d.get("production_countries"):
        countries = [c.get("iso_3166_1") for c in d["production_countries"] if c.get("iso_3166_1")]
    country_str = ", ".join(countries) if countries else "XX"

    original_title = d.get("original_title") or ""
    localized_title = d.get("title") or original_title

    return {
        "id": d.get("id"),
        "original": original_title,
        "english_or_local": localized_title,
        "year": (d.get("release_date") or "")[:4] or "XXXX",
        "director": director_str,
        "country": country_str,
        "poster_path": d.get("poster_path"),
    }


def search_movie(title, year, lang=None, limit=5):
    language = lang or CONFIG["lang"]
    params = {"query": title, "language": language}
    if year:
        params["year"] = year
    results = tmdb("/search/movie", **params).get("results", [])
    if not results and year:
        params.pop("year")
        results = tmdb("/search/movie", **params).get("results", [])
    return results[:limit]


# --------------------------------------------------------------------------- #
#  Serie TV
# --------------------------------------------------------------------------- #

def get_tv_details_by_id(tv_id, lang=None):
    language = lang or CONFIG["lang"]
    d = tmdb(f"/tv/{tv_id}", language=language, append_to_response="credits")

    creators = [c.get("name") for c in d.get("created_by", []) if c.get("name")]
    creator_str = ", ".join(creators) if creators else "Ideatore sconosciuto"

    countries = d.get("origin_country", [])
    if not countries and d.get("production_countries"):
        countries = [c.get("iso_3166_1") for c in d["production_countries"] if c.get("iso_3166_1")]
    country_str = ", ".join(countries) if countries else "XX"

    original_name = d.get("original_name") or ""
    localized_name = d.get("name") or original_name

    return {
        "id": d.get("id"),
        "original": original_name,
        "english_or_local": localized_name,
        "year": (d.get("first_air_date") or "")[:4] or "XXXX",
        "creator": creator_str,
        "country": country_str,
        "poster_path": d.get("poster_path"),
        "number_of_seasons": d.get("number_of_seasons"),
    }

def get_season_details(tv_id, season_number, lang=None):
    """Recupera i dettagli di una stagione specifica."""
    language = lang or CONFIG["lang"]
    try:
        return tmdb(f"/tv/{tv_id}/season/{season_number}", language=language)
    except RuntimeError:
        return {}

def search_tv(title, year=None, lang=None, limit=5):
    language = lang or CONFIG["lang"]
    params = {"query": title, "language": language}
    if year:
        params["first_air_date_year"] = year
    results = tmdb("/search/tv", **params).get("results", [])
    if not results and year:
        params.pop("first_air_date_year")
        results = tmdb("/search/tv", **params).get("results", [])
    return results[:limit]


def get_episode_title(tv_id, season, episode, lang=None):
    """Titolo del singolo episodio (usato nel nome file). Non blocca la rinomina se manca."""
    language = lang or CONFIG["lang"]
    try:
        d = tmdb(f"/tv/{tv_id}/season/{season}/episode/{episode}", language=language)
    except RuntimeError:
        return ""
    return d.get("name") or ""
