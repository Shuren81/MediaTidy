#!/usr/bin/env python3
"""
core/series_handler.py - Logica di dominio per le serie TV: scansione delle cartelle
di release (tramite core/series_classifier.py), ricerca/valutazione TMDB, costruzione
nome cartella/file "Serie (Anno) {tmdb-ID}/Season NN/Serie - SxxEyy - Titolo.ext",
e SeriesWorker (QThread) che esegue Test/Sposta/Copia in background.

Struttura di destinazione (decisa dall'utente):
  "Serie (Anno) {tmdb-ID}/Season 01/Serie - S01E02 - Titolo episodio.mkv"
I sottotitoli non vengono gestiti; i sample/trailer/extra vengono ignorati; un file
senza codice episodio riconosciuto resta in stato "series_status_unknown_ep" finché
l'utente non lo corregge manualmente (mai una decisione presa in silenzio).
"""
import difflib
import threading
from datetime import datetime
from pathlib import Path

from config import CONFIG
from localization import tr
from media_operations import (
    cleanup_old_logs, find_fstab_mountpoint, get_dir_size, format_size,
    is_inplace_source, is_remote, is_same_file, log_csv_row, log_event,
    mount_share, move_or_copy_file, target_exists, unmount_share,
)
from text_utils import format_title, sanitize_title
from tmdb_client import get_episode_title, get_tv_details_by_id, search_tv

from core.movie_handler import (  # riuso: stessi stati/norma/soglia di similarità dei film
    DONE_KEYS, ERROR_KEYS, READY_KEYS, SIMILARITY_THRESHOLD, SKIP_KEYS,
    is_done, norm, set_status, status_text,
)
from core.series_classifier import classify_directory, scan_release_dir

from qtpy.QtCore import QThread, Signal

CSV_HEADER = ["Data e ora", "File originale", "Serie (originale)", "Serie (localizzato)",
              "Anno", "ID TMDB", "Stagione", "Episodi", "Nome finale",
              "Cartella destinazione", "Esito", "Dettaglio"]


def is_ready(it):
    return it.get("status") in READY_KEYS


# --------------------------------------------------------------------------- #
#  Scansione file/cartelle di release -> item della tabella
# --------------------------------------------------------------------------- #
def scan_path_for_episodes(path):
    """Ritorna [(VideoInfo, percorso_assoluto), ...] per un singolo file video o
    per una cartella di release (che può contenere uno o più episodi)."""
    path = Path(path)
    if path.is_file():
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        infos = classify_directory([(path.name, size)], dir_name=path.parent.name)
        return [(info, path) for info in infos]
    results = []
    for info in scan_release_dir(path):
        results.append((info, path / info.path))
    return results


def make_item(info, abs_path, release_dir):
    recognized = bool(info.season and info.episodes)
    return {
        "path": abs_path,
        "release_dir": release_dir,
        "season": info.season,
        "episodes": info.episodes,
        "show_guess": info.show,
        "year_guess": info.year,
        "tmdb_id": "",
        "tmdb_original": "",
        "tmdb_localized": "",
        "tmdb_year": "",
        "folder": "",
        "newname": "",
        "status": "status_to_test" if recognized else "series_status_unknown_ep",
        "status_detail": "" if recognized else info.reason,
        "poster_path": None,
        "custom_override": False,
        "force_overwrite": False,
        "lang": None,
    }


def collect_items_for_path(path, known_paths):
    """Nuovi item (dict) per il drag&drop di un file o di una cartella di release.
    I file già presenti (known_paths) e le clip (sample/trailer/extra...) sono ignorati."""
    new_items = []
    release_dir = path if Path(path).is_dir() else None
    for info, abs_path in scan_path_for_episodes(path):
        if info.kind == "clip" or abs_path in known_paths:
            continue
        new_items.append(make_item(info, abs_path, release_dir))
    return new_items


# --------------------------------------------------------------------------- #
#  TMDB: valutazione dei risultati di ricerca (stessa logica dei film, campi TV)
# --------------------------------------------------------------------------- #
def similarity_tv(title, show):
    t = norm(title)
    if not t:
        return 0.0
    return max(
        difflib.SequenceMatcher(None, t, norm(show.get(k))).ratio()
        for k in ("name", "original_name")
    )


def evaluate_tv(results, title, year):
    good = [r for r in results if similarity_tv(title, r) >= SIMILARITY_THRESHOLD]
    if year:
        good = [r for r in good if (r.get("first_air_date") or "")[:4] == str(year)]
    if len(good) == 1:
        return good[0], True
    return None, False


# --------------------------------------------------------------------------- #
#  Costruzione nomi
# --------------------------------------------------------------------------- #
def build_show_folder(show_info, cap_rule=None):
    if cap_rule is None:
        cap_rule = CONFIG.get("cap_rule", 2)
    titolo = format_title(show_info.get("original"), show_info.get("english_or_local"), cap_rule)
    year = show_info.get("year") or "XXXX"
    tmdb_id = show_info.get("id") or "0000"
    return titolo, f"{titolo} ({year}) {{tmdb-{tmdb_id}}}"


def build_episode_name(show_title, season, episodes, ep_title, ext):
    if len(episodes) > 1:
        code = f"S{season:02d}E{episodes[0]:02d}-E{episodes[-1]:02d}"
    else:
        code = f"S{season:02d}E{episodes[0]:02d}"
    name = f"{show_title} - {code}"
    if ep_title:
        name += f" - {sanitize_title(ep_title)}"
    return name + ext.lower()


class SeriesWorker(QThread):
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
        self._downloaded_shows = set()

        self._evt = threading.Event()
        self._answer = None
        self.default_dup_action = None
        self.default_non_empty_action = None
        self._cleanup_dirs = {}

    def provide(self, show):
        self._answer = show
        self._evt.set()

    def provide_dup_choice(self, choice, apply_to_all):
        self._answer = choice
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
        dest = CONFIG["dest_series"]
        if is_remote(dest):
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
        log_event("INFO", f"[Serie] Avvio esecuzione: modalità={self.mode}, azione={self.action}, file in coda={len(self.rows)}")
        try:
            self._prepare()
        except Exception as e:
            log_event("ERROR", f"[Serie] Preparazione fallita: {e}")
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
                log_event("ERROR", f"[Serie] {it.get('path', '')}: {e}")
            key = it.get("status", "")
            if key in ERROR_KEYS:
                errors += 1
            elif key in SKIP_KEYS:
                skipped += 1
            elif self.mode == "action" and key in DONE_KEYS:
                succeeded += 1
            text = status_text(it)
            log_event("INFO", f"[Serie] File={it.get('path', '')} | Nuovo nome={it.get('newname', '')} | Cartella={it.get('folder', '')} | Stato={text}")
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            log_csv_row("series", CSV_HEADER,
                        [now, str(it.get("path", "")), it.get("tmdb_original", ""),
                         it.get("tmdb_localized", ""), it.get("tmdb_year", ""),
                         it.get("tmdb_id", ""), it.get("season", ""),
                         ",".join(str(e) for e in it.get("episodes", ())),
                         it.get("newname", ""), it.get("folder", ""),
                         tr(key) if key else "", it.get("status_detail", "")])
            self.row_update.emit(i)

        if self.mode == "action" and self.clean_parent and self.action == "move":
            try:
                self._cleanup_source_dirs()
            except Exception as e:
                log_event("WARNING", f"[Serie] Pulizia cartelle di origine non riuscita: {e}")

        if self.mode == "action" and self.unmount_after and self.mounted_by_us:
            try:
                self.status.emit(f"Smontaggio di {self.mounted_by_us}…")
                unmount_share(self.mounted_by_us)
                self.did_unmount = True
                self.unmounted.emit()
            except Exception as e:
                self.status.emit(f"Smontaggio non riuscito: {e}")
        log_event("INFO", f"[Serie] Fine esecuzione: elaborati={total}, riusciti={succeeded}, saltati={skipped}, errori={errors}")
        self.all_done.emit()

    def _has_pending_files(self, folder):
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
        dest = CONFIG["dest_series"]
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
        import os
        import shutil
        dest = CONFIG["dest_series"]
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
                    log_event("INFO", f"[Serie] Cartella di origine vuota rimossa: {folder}")
                    continue
                choice = self._ask_non_empty_dir(row, str(folder), format_size(get_dir_size(folder)))
                if choice == "yes":
                    shutil.rmtree(folder)
                    log_event("INFO", f"[Serie] Cartella di origine rimossa con residui: {folder}")
            except Exception as e:
                log_event("WARNING", f"[Serie] Pulizia di {folder} non riuscita: {e}")

    def _test(self, i, it):
        set_status(it, "status_testing")
        self.row_update.emit(i)

        if it.get("tmdb_id"):
            try:
                show_info = get_tv_details_by_id(it["tmdb_id"], lang=it.get("lang"))
            except Exception as e:
                set_status(it, "status_tmdb_error", str(e))
                return
        else:
            title, year = it.get("show_guess") or "", it.get("year_guess")
            results = search_tv(title, year, lang=it.get("lang"), limit=8) if title else []
            show, sure = evaluate_tv(results, title, year)
            if not sure:
                show = self._ask_user(i, results, title)
                if show is None:
                    set_status(it, "status_skipped")
                    return
            it["tmdb_id"] = str(show["id"])
            show_info = get_tv_details_by_id(show["id"], lang=it.get("lang"))

        it["tmdb_original"] = show_info.get("original", "")
        it["tmdb_localized"] = show_info.get("english_or_local", "")
        it["tmdb_year"] = show_info.get("year", "")
        it["poster_path"] = show_info.get("poster_path")

        # Scarica poster della stagione
        try:
            from tmdb_client import get_season_details
            season_info = get_season_details(it["tmdb_id"], it["season"], lang=it.get("lang"))
            it["season_poster_path"] = season_info.get("poster_path") if season_info else None
        except Exception:
            it["season_poster_path"] = None

        if not it.get("season") or not it.get("episodes"):
        
            # Codice episodio non riconosciuto: l'utente deve correggerlo a mano
            # (menu contestuale "Modifica Stagione/Episodio..."), mai una scelta silenziosa.
            set_status(it, "series_status_unknown_ep")
            return

        if not it.get("custom_override"):
            titolo, show_folder = build_show_folder(show_info)
            season_folder = f"Season {it['season']:02d}"
            try:
                ep_title = get_episode_title(it["tmdb_id"], it["season"], it["episodes"][0], lang=it.get("lang"))
            except Exception:
                ep_title = ""
            it["folder"] = f"{show_folder}/{season_folder}"
            it["newname"] = build_episode_name(titolo, it["season"], it["episodes"], ep_title, it["path"].suffix)

        dest = CONFIG["dest_series"]
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
        dest = CONFIG["dest_series"]
        while True:
            if (is_same_file(it["path"], dest, it["folder"], it["newname"])
                    or it.get("force_overwrite")
                    or not target_exists(dest, it["folder"], it["newname"])):
                break

            dup_choice = self._ask_duplicate(i)
            if dup_choice == "custom":
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
            set_status(it, "status_skipped_dup")
            return

        inplace = is_inplace_source(it["path"], dest)
        rename = inplace and (self.action == "move" or is_same_file(it["path"], dest, it["folder"], it["newname"]))
        if rename:
            set_status(it, "status_renaming")
        else:
            set_status(it, "status_moving" if self.action == "move" else "status_copying")
        self.row_update.emit(i)

        src_parent = Path(it["path"]).parent.resolve()
        move_or_copy_file(
            it["path"], dest, it["folder"], it["newname"],
            poster_path=it.get("poster_path"),
            action=self.action,
            progress_callback=self.file_progress.emit,
		)
        
        # Scarica poster della stagione dopo aver copiato/spostato il file
        if it.get("season_poster_path"):
            from media_operations import download_poster
            season_folder_path = f"{it['folder'].rsplit('/', 1)[0]}/Season {it['season']:02d}"
            download_poster(it["season_poster_path"], season_folder_path, dest)
        
        if rename:
            set_status(it, "status_done_inplace")
        else:
            set_status(it, "status_done_moved" if self.action == "move" else "status_done_copied")

        if self.clean_parent and self.action == "move":
            self._cleanup_dirs.setdefault(src_parent, i)
        # Scarica poster della serie nella cartella principale (una volta sola)
        show_folder_path = it['folder'].rsplit('/', 1)[0]
        if it.get("poster_path") and it["tmdb_id"] not in self._downloaded_shows:
            from media_operations import download_poster
            download_poster(it["poster_path"], show_folder_path, dest)
            self._downloaded_shows.add(it["tmdb_id"])
