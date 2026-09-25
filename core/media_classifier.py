#!/usr/bin/env python3
"""
core/media_classifier.py - Triage automatico Film / Serie TV, senza rete.

Riusa core/series_classifier.py (via core/series_handler.scan_path_for_episodes)
per riconoscere episodi/clip, e core/movie_handler.guess_title_year per il
guessing di titolo/anno dei film. Nessuna chiamata TMDB qui: solo euristiche
locali sul nome del file/cartella, così può girare prima ancora di aprire le
schede Film/Serie.

Regole:
  * un file con codice episodio riconosciuto (o "extra" dentro una cartella che
    ne contiene già altri con codice) -> Serie
  * un file senza codice episodio ma con un anno plausibile nel nome -> Film
  * un file senza codice episodio e senza anno -> Ambiguo: si chiede all'utente
  * le clip (sample/trailer/extra) vengono sempre ignorate, come oggi
"""
from dataclasses import dataclass, field
from pathlib import Path

from core.movie_handler import guess_title_year
from core.series_handler import scan_path_for_episodes


@dataclass
class ClassifiedFile:
    path: Path
    kind: str  # "movie" | "series" | "ambiguous"
    release_dir: Path = None

    # Serie (valorizzati se kind in ("series", "ambiguous"))
    season: int = None
    episodes: tuple = ()
    show_guess: str = ""
    year_guess: int = None
    reason: str = ""

    # Film (valorizzati se kind in ("movie", "ambiguous"))
    title_guess: str = ""
    movie_year_guess: int = None


def classify_source(path):
    """Classifica ogni file video trovato in path (file singolo o cartella di
    release/collezione). Ritorna una lista di ClassifiedFile, escludendo le clip."""
    path = Path(path)
    release_dir = path if path.is_dir() else None
    infos = scan_path_for_episodes(path)
    has_episode = any(info.kind == "episode" for info, _ in infos)

    out = []
    for info, abs_path in infos:
        if info.kind == "clip":
            continue

        if info.kind == "episode" or (info.kind == "unknown" and has_episode):
            # Codice riconosciuto, oppure file "extra" dentro una cartella che
            # contiene già altri episodi con codice: quasi certamente serie.
            out.append(ClassifiedFile(
                path=abs_path, kind="series", release_dir=release_dir,
                season=info.season, episodes=info.episodes,
                show_guess=info.show, year_guess=info.year, reason=info.reason,
            ))
            continue

        # info.kind == "unknown" e nessun altro episodio nella stessa cartella:
        # genuinamente ambiguo tra film isolato e episodio non riconosciuto.
        title, year = guess_title_year(abs_path.name)
        if not year and release_dir:
            t2, y2 = guess_title_year(release_dir.name)
            if t2 and y2:
                title, year = t2, y2

        if year:
            out.append(ClassifiedFile(
                path=abs_path, kind="movie", release_dir=release_dir,
                title_guess=title, movie_year_guess=year,
            ))
        else:
            out.append(ClassifiedFile(
                path=abs_path, kind="ambiguous", release_dir=release_dir,
                title_guess=title, movie_year_guess=year,
                show_guess=info.show, year_guess=info.year, reason=info.reason,
            ))
    return out


def classify_paths(paths):
    """Applica classify_source a più percorsi trascinati insieme, in ordine."""
    result = []
    for p in paths:
        result.extend(classify_source(p))
    return result


def to_series_item(cf: ClassifiedFile):
    """Converte un ClassifiedFile (kind 'series', o 'ambiguous' risolto come serie
    dall'utente) nello stesso formato item che usa core/series_handler.py, riusando
    make_item così la scheda Serie TV non deve sapere nulla del classificatore."""
    from core.series_classifier import VideoInfo
    from core.series_handler import make_item

    info = VideoInfo(
        path=str(cf.path), size=0, kind="episode",
        season=cf.season, episodes=cf.episodes,
        show=cf.show_guess, year=cf.year_guess, reason=cf.reason,
    )
    return make_item(info, cf.path, cf.release_dir)
