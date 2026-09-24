#!/usr/bin/env python3
"""
core/movie_handler.py - Logica di dominio per i film: guessing titolo/anno da nome
file, ricerca/valutazione TMDB, costruzione nome cartella/file, e MovieWorker
(QThread) che esegue Test/Sposta/Copia in background dialogando con la GUI tramite
segnali Qt (stessa logica del vecchio MovieTidy, isolata dalla UI).
"""
import difflib
import re
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

from config import CONFIG
from localization import tr
from media_operations import (
    VIDEO_EXT, cleanup_old_logs, download_poster, find_fstab_mountpoint,
    get_dir_size, format_size, is_inplace_source, is_remote, is_same_file,
    log_csv_row, log_event, mount_share, move_or_copy_file, target_exists,
    unmount_share,
)
from text_utils import format_title, sanitize_title
from tmdb_client import get_movie_details_by_id, search_movie

from qtpy.QtCore import QThread, Signal

JUNK = re.compile(
    r"\b(480p|576p|720p|1080p|2160p|4k|uhd|bluray|bdrip|brrip|webrip|web-dl|webdl|"
    r"hdrip|dvdrip|hdtv|x264|x265|h264|h265|hevc|xvid|ita|eng|multi|sub|ac3|dts|aac)\b.*",
    re.I,
)
SIMILARITY_THRESHOLD = 0.85

# --------------------------------------------------------------------------- #
#  Stati degli item: si salvano CHIAVI, la traduzione avviene solo in visualizzazione
# --------------------------------------------------------------------------- #
READY_KEYS = frozenset({
    "status_ready", "status_ready_inplace", "status_ready_custom",
    "status_ready_overwrite", "status_ready_suffix",
})
DONE_KEYS = frozenset({"status_done_moved", "status_done_copied", "status_done_inplace"})
SKIP_KEYS = frozenset({"status_skipped", "status_skipped_dup"})
ERROR_KEYS = frozenset({"status_error", "status_tmdb_error"})

CSV_HEADER = ["Data e ora", "File originale", "Titolo originale TMDB",
              "Titolo localizzato TMDB", "Anno", "ID TMDB",
              "Nome finale", "Cartella destinazione", "Esito", "Dettaglio"]


def set_status(it, key, detail=""):
    from media_operations import redact
    it["status"] = key
    it["status_detail"] = redact(detail) if detail else ""


def status_text(it):
    text = tr(it.get("status", "status_to_test"))
    detail = it.get("status_detail")
    return f"{text}: {detail}" if detail else text


def is_ready(it):
    return it.get("status") in READY_KEYS


def is_done(it):
    return it.get("status") in DONE_KEYS


def is_sample(f):
    try:
        small = f.stat().st_size < 100 * 1024 * 1024
    except OSError:
        small = False
    return "sample" in f.stem.lower() and small


def find_videos(path):
    import os
    path = Path(path)
    if path.is_file():
        return [path] if path.suffix.lower() in VIDEO_EXT else []
    found = []
    for root, _dirs, files in os.walk(path):
        _dirs.sort()
        for name in sorted(files):
            f = Path(root) / name
            if f.suffix.lower() in VIDEO_EXT and not is_sample(f):
                found.append(f)
    return found


def guess_title_year(filename):
    name = re.sub(r"[._]", " ", Path(filename).stem if Path(filename).suffix.lower() in VIDEO_EXT else str(filename))
    year = None
    bracketed = re.search(r"[\[\(]\s*(19\d{2}|20\d{2})\s*[\]\)]", name)
    if bracketed and name[: bracketed.start()].strip():
        year = int(bracketed.group(1))
        name = name[: bracketed.start()]
    name = re.sub(r"[\[\(].*?[\]\)]", " ", name)
    years = list(re.finditer(r"\b(19\d{2}|20\d{2})\b", name))
    if year is None and years and name[: years[-1].start()].strip():
        year = int(years[-1].group(1))
        name = name[: years[-1].start()]
    name = JUNK.sub("", name)
    return re.sub(r"\s+", " ", name).strip(" -"), year


def guess_for(path, from_dir):
    title, year = guess_title_year(path.name)
    if from_dir and not year:
        t2, y2 = guess_title_year(path.parent.name)
        if t2 and y2:
            return t2, y2
    return title, year


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    # \w (unicode) invece di a-z0-9: titoli giapponesi, russi ecc. non diventano stringa vuota
    return re.sub(r"[\W_]+", " ", s).strip()


def similarity(title, movie):
    t = norm(title)
    if not t:
        return 0.0
    return max(
        difflib.SequenceMatcher(None, t, norm(movie.get(k))).ratio()
        for k in ("title", "original_title")
    )


def evaluate(results, title, year):
    good = [r for r in results if similarity(title, r) >= SIMILARITY_THRESHOLD]
    if year:
        good = [r for r in good if (r.get("release_date") or "")[:4] == str(year)]
    if len(good) == 1:
        return good[0], True
    return None, False


def build_names(info, ext, cap_rule=None):
    if cap_rule is None:
        cap_rule = CONFIG.get("cap_rule", 2)

    titolo_str = format_title(info.get("original"), info.get("english_or_local"), cap_rule)

    year = info.get("year") or "XXXX"
    tmdb_id = info.get("id") or "0000"
    # Paese e regista NON passano da fix_apostrophes (O'Connor resta O'Connor).
    country = sanitize_title(info.get("country") or "XX", fix_apos=False)
    director = sanitize_title(info.get("director") or "Regista sconosciuto", fix_apos=False)

    base = f"{titolo_str} ({year})"
    folder = f"{base} {{tmdb-{tmdb_id}}} [{country}, {director}]"
    return folder, base + ext.lower()


class MovieWorker(QThread):
    row_update = Signal(int)
    progress = Signal(int, int)
    file_progress = Signal(int)
    ask = Signal(int, list, str)
    ask_duplicate = Signal(int)
    ask_non_empty_dir = Signal(int, str, str)
    status = Signal(str)
    error = Signal(str)
    mounted = Signal(str)
    unmounted = Signal()
    all_done = Signal()

    def __init__(self, items, rows, mode, action="move", unmount_after=False, clean_parent=False, mounted_by_us=None):
        super().__init__()
        self.items = items
        self.rows = rows
        self.mode = mode
        self.action = action
        self.unmount_after = unmount_after
        self.clean_parent = clean_parent
        self.mounted_by_us = mounted_by_us
        self.did_unmount = False

        self._evt = threading.Event()
        self._answer = None
        self.default_dup_action = None
        self.default_non_empty_action = None
        self._cleanup_dirs = {}  # cartella d'origine -> riga (per selezionarla nel dialogo)

    def provide(self, movie):
        self._answer = movie
        self._evt.set()

    def provide_dup_choice(self, choice, apply_to_all):
        self._answer = choice
        # "custom" richiede un intervento per ogni file: non ha senso "applica a tutti"
        if apply_to_all and choice != "custom":
            self.default_dup_action = choice
        self._evt.set()

    def provide_non_empty_choice(self, choice, apply_to_all):
        self._answer = choice
        if apply_to_all:
            self.default_non_empty_action = choice
        self._evt.set()

    def _ask_user(self, row, results, title):
        self._answer = None
        self._evt.clear()
        self.ask.emit(row, results, title)
        self._evt.wait()
        return self._answer

    def _ask_duplicate(self, row):
        if self.default_dup_action:
            return self.default_dup_action
        self._answer = None
        self._evt.clear()
        self.ask_duplicate.emit(row)
        self._evt.wait()
        return self._answer

    def _ask_non_empty_dir(self, row, folder_path, size_str):
        if self.default_non_empty_action:
            return self.default_non_empty_action
        self._answer = None
        self._evt.clear()
        self.ask_non_empty_dir.emit(row, folder_path, size_str)
        self._evt.wait()
        return self._answer

    def _prepare(self):
        import os
        import subprocess
        dest = CONFIG["dest_movies"]
        if is_remote(dest):
            # Un solo controllo iniziale invece di un timeout da 20 s per ogni file
            host = dest.split(":", 1)[0]
            try:
                r = subprocess.run(
                    ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "true"],
                    capture_output=True, timeout=30,
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError("Host remoto non raggiungibile via SSH") from None
            if r.returncode != 0:
                raise RuntimeError("Host remoto non raggiungibile via SSH")
            return
        mp = find_fstab_mountpoint(dest)
        if mp and not os.path.ismount(mp):
            self.status.emit(f"Montaggio di {mp}…")
            mount_share(mp)
            self.mounted_by_us = mp
            self.mounted.emit(mp)
        if not Path(dest).is_dir():
            raise RuntimeError(f"La cartella di destinazione non esiste: {dest}")

    def run(self):
        cleanup_old_logs()
        log_event("INFO", f"[Film] Avvio esecuzione: modalità={self.mode}, azione={self.action}, file in coda={len(self.rows)}")
        try:
            self._prepare()
        except Exception as e:
            log_event("ERROR", f"[Film] Preparazione fallita: {e}")
            self.error.emit(str(e))
            return
        total = len(self.rows)
        succeeded = skipped = errors = 0
        for n, i in enumerate(self.rows, 1):
            it = self.items[i]
            self.progress.emit(n, total)
            try:
                if self.mode == "test":
                    self._test(i, it)
                else:
                    self._process(i, it)
            except Exception as e:
                set_status(it, "status_error", str(e))
                log_event("ERROR", f"[Film] {it.get('path', '')}: {e}")
            key = it.get("status", "")
            if key in ERROR_KEYS:
                errors += 1
            elif key in SKIP_KEYS:
                skipped += 1
            elif self.mode == "action" and key in DONE_KEYS:
                succeeded += 1
            text = status_text(it)
            log_event("INFO", f"[Film] File={it.get('path', '')} | Nuovo nome={it.get('newname', '')} | Cartella={it.get('folder', '')} | Stato={text}")
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            log_csv_row("movies", CSV_HEADER,
                        [now, str(it.get("path", "")), it.get("tmdb_original", ""),
                         it.get("tmdb_localized", ""), it.get("tmdb_year", ""),
                         it.get("tmdb_id", ""), it.get("newname", ""),
                         it.get("folder", ""), tr(key) if key else "", it.get("status_detail", "")])
            self.row_update.emit(i)

        if self.mode == "action" and self.clean_parent and self.action == "move":
            try:
                self._cleanup_source_dirs()
            except Exception as e:
                log_event("WARNING", f"[Film] Pulizia cartelle di origine non riuscita: {e}")

        if self.mode == "action" and self.unmount_after and self.mounted_by_us:
            try:
                self.status.emit(f"Smontaggio di {self.mounted_by_us}…")
                unmount_share(self.mounted_by_us)
                self.did_unmount = True
                self.unmounted.emit()
            except Exception as e:
                self.status.emit(f"Smontaggio non riuscito: {e}")
        log_event("INFO", f"[Film] Fine esecuzione: elaborati={total}, riusciti={succeeded}, saltati={skipped}, errori={errors}")
        self.all_done.emit()

    def _has_pending_files(self, folder):
        """True se nella cartella (o sotto) c'è ancora un file della lista non elaborato."""
        for it in self.items:
            if is_done(it):
                continue
            try:
                p = Path(it["path"])
                if p.exists() and folder in p.resolve().parents:
                    return True
            except OSError:
                continue
        return False

    def _is_target_folder(self, folder):
        """True se la cartella è (o contiene) la posizione finale di un file già elaborato."""
        dest = CONFIG["dest_movies"]
        if is_remote(dest):
            return False
        for it in self.items:
            if not is_done(it) or not it.get("newname"):
                continue
            try:
                target = (Path(dest) / it.get("folder", "") / it["newname"]).resolve()
            except OSError:
                continue
            if folder == target.parent or folder in target.parents:
                return True
        return False

    def _cleanup_source_dirs(self):
        """Rimuove le cartelle di origine rimaste vuote (o, previa conferma, con residui).
        Non tocca mai: la destinazione o un suo antenato, la home, la radice di un mount,
        cartelle con file ancora da elaborare."""
        import os
        import shutil
        dest = CONFIG["dest_movies"]
        dest_root = None if is_remote(dest) else Path(dest).resolve()
        home = Path.home().resolve()
        for folder, row in sorted(self._cleanup_dirs.items(),
                                   key=lambda kv: len(kv[0].parts), reverse=True):
            try:
                folder = folder.resolve()
                if not folder.is_dir() or folder == folder.parent or folder == home:
                    continue
                if os.path.ismount(folder):
                    continue
                if dest_root and (folder == dest_root or folder in dest_root.parents):
                    continue
                if self._has_pending_files(folder) or self._is_target_folder(folder):
                    continue
                if not any(folder.iterdir()):
                    folder.rmdir()
                    log_event("INFO", f"[Film] Cartella di origine vuota rimossa: {folder}")
                    continue
                choice = self._ask_non_empty_dir(row, str(folder), format_size(get_dir_size(folder)))
                if choice == "yes":
                    shutil.rmtree(folder)
                    log_event("INFO", f"[Film] Cartella di origine rimossa con residui: {folder}")
            except Exception as e:
                log_event("WARNING", f"[Film] Pulizia di {folder} non riuscita: {e}")

    def _test(self, i, it):
        set_status(it, "status_testing")
        self.row_update.emit(i)

        if it.get("tmdb_id"):
            try:
                movie_info = get_movie_details_by_id(it["tmdb_id"], lang=it.get("lang"))
            except Exception as e:
                set_status(it, "status_tmdb_error", str(e))
                return
        else:
            title, year = guess_for(it["path"], it["from_dir"])
            results = search_movie(title, year, lang=it.get("lang"), limit=8) if title else []
            movie, sure = evaluate(results, title, year)
            if not sure:
                movie = self._ask_user(i, results, title)
                if movie is None:
                    set_status(it, "status_skipped")
                    return
            it["tmdb_id"] = str(movie["id"])
            movie_info = get_movie_details_by_id(movie["id"], lang=it.get("lang"))

        it["tmdb_original"] = movie_info.get("original", "")
        it["tmdb_localized"] = movie_info.get("english_or_local", "")
        it["tmdb_year"] = movie_info.get("year", "")
        it["poster_path"] = movie_info.get("poster_path")
        if not it.get("custom_override"):
            folder, newname = build_names(movie_info, it["path"].suffix)
            it["folder"], it["newname"] = folder, newname

        dest = CONFIG["dest_movies"]
        inplace = is_inplace_source(it["path"], dest)
        target_ex = target_exists(dest, it["folder"], it["newname"])

        if is_same_file(it["path"], dest, it["folder"], it["newname"]):
            set_status(it, "status_ready_inplace")
        elif target_ex:
            set_status(it, "status_already_exists")
        elif inplace:
            set_status(it, "status_ready_inplace")
        else:
            set_status(it, "status_ready")

    def _process(self, i, it):
        dest = CONFIG["dest_movies"]
        while True:
            if (is_same_file(it["path"], dest, it["folder"], it["newname"])
                    or it.get("force_overwrite")
                    or not target_exists(dest, it["folder"], it["newname"])):
                break

            dup_choice = self._ask_duplicate(i)
            if dup_choice == "custom":
                # La GUI ha già applicato (o annullato -> "skip") la modifica: si ricontrolla
                # che il nuovo nome non esista a sua volta.
                continue
            if dup_choice == "suffix":
                p = Path(it["newname"])
                base = p.stem
                ext = p.suffix
                count = 1
                while target_exists(dest, it["folder"], f"{base}_{count}{ext}"):
                    count += 1
                it["newname"] = f"{base}_{count}{ext}"
                break
            if dup_choice == "overwrite":
                break
            set_status(it, "status_skipped_dup")  # "skip" o dialogo chiuso
            return

        inplace = is_inplace_source(it["path"], dest)
        rename = inplace and (self.action == "move" or is_same_file(it["path"], dest, it["folder"], it["newname"]))
        if rename:
            set_status(it, "status_renaming")
        else:
            set_status(it, "status_moving" if self.action == "move" else "status_copying")
        self.row_update.emit(i)

        src_parent = Path(it["path"]).parent
        move_or_copy_file(
            it["path"], dest, it["folder"], it["newname"],
            poster_path=it.get("poster_path"),
            action=self.action,
            progress_callback=self.file_progress.emit,
        )
        if rename:
            set_status(it, "status_done_inplace")
        else:
            set_status(it, "status_done_moved" if self.action == "move" else "status_done_copied")

        if self.clean_parent and self.action == "move":
            self._cleanup_dirs.setdefault(src_parent, i)
