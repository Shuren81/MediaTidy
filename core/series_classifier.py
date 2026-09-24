"""
series_classifier.py - Riconoscimento di episodi e clip nelle cartelle di release delle serie TV.

Modulo puro (solo libreria standard, nessuna GUI, nessuna rete): pensato per essere importato
dal futuro programma "MovieTidy per le serie" e testato da solo.

Regole (in base a come sono fatte le tue cartelle di origine):
  * Cartella con PIÙ episodi diversi (stagione intera): niente sample. Ogni file con codice
    SxxEyy è un episodio; un file senza codice è "unknown" (da confermare), salvo che sia in una
    sottocartella tipo Sample/Extras o abbia nel nome parole da clip (sample, trailer, ...).
  * Cartella con UN solo episodio: possono esserci sample. Tra file con lo stesso codice vince il
    più grande; un file senza codice molto più piccolo dell'episodio è una clip.
  * Nel dubbio il file è "unknown": il programma deve chiedere, mai decidere in silenzio.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePath

# VIDEO_EXT condiviso con il resto di MediaTidy (media_operations.py)
from media_operations import VIDEO_EXT

# Un file senza codice più piccolo di questa frazione dell'episodio è considerato una clip
SMALL_RATIO = 0.25
# Range "S01E01-E03" espanso solo se ragionevole (evita di interpretare numeri a caso)
MAX_RANGE = 5

_B = r"(?<![A-Za-z0-9])"          # "inizio parola"
_MAIN_RE = re.compile(_B + r"S(\d{1,2})[ ._-]?E(\d{1,3})", re.I)
_EXTRA_E_RE = re.compile(r"([-._ ]?)E(\d{1,3})", re.I)
_EXTRA_RANGE_RE = re.compile(r"-(\d{2,3})(?![A-Za-z0-9])")
_NXM_RE = re.compile(_B + r"(\d{1,2})x(\d{2,3})(?![A-Za-z0-9])", re.I)
_WORDS_RE = re.compile(
    _B + r"(?:season|stagione)[ ._-]*(\d{1,2})[ ._-]*(?:episode|episodio|ep)[ ._-]*(\d{1,3})(?![A-Za-z0-9])",
    re.I,
)
_SEASON_ONLY_RE = re.compile(_B + r"S(\d{1,2})(?![A-Za-z0-9])", re.I)
_YEAR_END_RE = re.compile(r"[\s(\[]*((?:19[5-9]\d|20[0-3]\d))[\s)\]]*$")

_CLIP_RE = re.compile(
    _B + r"(?:sample|trailer|featurettes?|extras?|behind[ ._-]?the[ ._-]?scenes|proof|promo|"
    r"teaser|bonus|deleted[ ._-]?scenes?)(?![A-Za-z0-9])",
    re.I,
)


@dataclass
class VideoInfo:
    path: str
    size: int
    kind: str                  # "episode" | "clip" | "unknown"
    season: int = None
    episodes: tuple = ()
    show: str = ""
    year: int = None
    reason: str = ""


def _expand(eps, n, sep):
    """Aggiunge l'episodio n; con separatore '-' espande i range brevi (E01-E03 -> 1,2,3)."""
    last = eps[-1]
    if sep == "-" and last < n <= last + MAX_RANGE:
        eps.extend(range(last + 1, n + 1))
    else:
        eps.append(n)


def parse_episode(text):
    """Ritorna (stagione, (episodi...)) oppure None."""
    if not text:
        return None
    m = _MAIN_RE.search(text)
    if m:
        season = int(m.group(1))
        eps = [int(m.group(2))]
        pos = m.end()
        while True:
            m2 = _EXTRA_E_RE.match(text, pos)
            if m2:
                _expand(eps, int(m2.group(2)), m2.group(1))
                pos = m2.end()
                continue
            m3 = _EXTRA_RANGE_RE.match(text, pos)
            if m3:
                _expand(eps, int(m3.group(1)), "-")
                pos = m3.end()
                continue
            break
        return season, tuple(sorted(set(eps)))
    for rx in (_WORDS_RE, _NXM_RE):
        m = rx.search(text)
        if m:
            return int(m.group(1)), (int(m.group(2)),)
    return None


def extract_show(text):
    """Ritorna (titolo serie, anno) dalla parte di nome che precede il codice episodio/stagione."""
    if not text:
        return "", None
    cut = len(text)
    for rx in (_MAIN_RE, _WORDS_RE, _NXM_RE, _SEASON_ONLY_RE):
        m = rx.search(text)
        if m:
            cut = min(cut, m.start())
    prefix = re.sub(r"[._]+", " ", text[:cut])
    prefix = re.sub(r"\s+", " ", prefix).strip(" -([")
    year = None
    m = _YEAR_END_RE.search(prefix)
    if m and prefix[:m.start()].strip():
        year = int(m.group(1))
        prefix = prefix[:m.start()].strip(" -([")
    return prefix, year


def _is_clip_word(text):
    return bool(_CLIP_RE.search(text))


def classify_directory(files, dir_name=""):
    """
    files: iterabile di (percorso_relativo_alla_cartella_di_release, dimensione_in_byte)
    dir_name: nome della cartella di release (usato come ripiego per codice e titolo)
    Ritorna una lista di VideoInfo nello stesso ordine di ingresso.
    """
    entries = []
    for path, size in files:
        p = PurePath(path)
        own = parse_episode(p.stem)
        entries.append({
            "path": str(path), "size": size, "stem": p.stem, "own": own,
            "folder_clip": any(_is_clip_word(part) for part in p.parts[:-1]),
            "name_clip": _is_clip_word(p.stem),
        })

    dir_code = parse_episode(dir_name)
    own_codes = {e["own"] for e in entries if e["own"] and not e["folder_clip"]}
    is_pack = len(own_codes) >= 2

    results = {}

    def put(e, kind, reason, code=None, show_src=None):
        code = code or e["own"]
        show, year = extract_show(show_src if show_src is not None else e["stem"])
        if not show and dir_name:
            show, year = extract_show(dir_name)
        results[e["path"]] = VideoInfo(
            path=e["path"], size=e["size"], kind=kind,
            season=code[0] if code else None,
            episodes=code[1] if code else (),
            show=show, year=year, reason=reason,
        )

    pending = []
    for e in entries:
        if e["folder_clip"]:
            put(e, "clip", "in una sottocartella tipo Sample/Extras")
        elif e["name_clip"] and not e["own"]:
            put(e, "clip", "il nome contiene una parola da clip (sample, trailer, ...)")
        else:
            pending.append(e)

    # File con codice proprio: uno per episodio, gli altri con lo stesso codice sono clip
    by_code = {}
    for e in pending:
        if e["own"]:
            by_code.setdefault(e["own"], []).append(e)
    main_sizes = []
    for code, group in by_code.items():
        group.sort(key=lambda x: x["size"], reverse=True)
        put(group[0], "episode", "codice episodio nel nome del file")
        main_sizes.append(group[0]["size"])
        for other in group[1:]:
            put(other, "clip", "stesso episodio di un file più grande (probabile sample)")

    # File senza codice proprio
    nocode = [e for e in pending if not e["own"]]
    if nocode:
        if is_pack:
            # Stagione intera: niente sample, quindi niente euristica sulla dimensione
            for e in nocode:
                put(e, "unknown", "nessun codice episodio in una cartella con più episodi", show_src=dir_name)
        else:
            reference = max(main_sizes) if main_sizes else max(e["size"] for e in nocode)
            nocode.sort(key=lambda x: x["size"], reverse=True)
            main_taken = bool(main_sizes)
            for e in nocode:
                if not main_taken and dir_code:
                    put(e, "episode", "codice episodio preso dal nome della cartella",
                        code=dir_code, show_src=dir_name)
                    main_taken = True
                elif e["size"] < SMALL_RATIO * reference:
                    put(e, "clip", "molto più piccolo dell'episodio", code=dir_code, show_src=dir_name)
                else:
                    put(e, "unknown", "nessun codice episodio e dimensione non decisiva", show_src=dir_name)

    return [results[str(path)] for path, _ in files]


def scan_release_dir(path):
    """Comodità: scansiona una cartella di release reale e classifica i video trovati."""
    root = Path(path)
    files = []
    for cur, _dirs, names in os.walk(root):
        for name in sorted(names):
            f = Path(cur) / name
            if f.suffix.lower() in VIDEO_EXT:
                try:
                    files.append((str(f.relative_to(root)), f.stat().st_size))
                except OSError:
                    continue
    return classify_directory(files, dir_name=root.name)
