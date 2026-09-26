#!/usr/bin/env python3
"""
media_operations.py - Log, mount/smontaggio disco, spostamento/copia file, duplicati.

Modulo condiviso da core/movie_handler.py e core/series_handler.py: non contiene
nulla di specifico per film o serie, solo operazioni sul filesystem/rete.
"""
import collections
import csv
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from config import CONFIG

VIDEO_EXT = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".mpg", ".mpeg", ".ts"}

# Nomi di sottocartelle "di scarto" tipiche di una release scene (corrispondenza
# esatta, case-insensitive): se TUTTE le sottocartelle rimaste in una cartella di
# origine hanno uno di questi nomi, la pulizia può ancora proporla (con conferma);
# se anche una sola sottocartella ha un nome diverso, la cartella non viene mai
# più proposta (vedi _cleanup_source_dirs in movie_handler.py/series_handler.py).
JUNK_SUBFOLDER_NAMES = frozenset({
    "sample", "screens", "screenshots", "proof", "subs", "subtitles",
    "extras", "featurettes", "artwork", "covers", "scans",
})
COPY_CHUNK = 4 * 1024 * 1024

LOG_RETENTION_DAYS = 10

_TMDB_ID_RE = re.compile(r"\{tmdb-(\d+)\}", re.I)


def extract_tmdb_id(*names):
    """Cerca un codice {tmdb-XXXX} in una sequenza di nomi (es. file, cartella
    genitore, cartella nonna...), nell'ordine dato. Ritorna la stringa dell'ID
    trovato per primo, o None se nessuno dei nomi lo contiene. Usato per
    riconoscere in automatico un file/cartella già rinominato da MediaTidy
    (o comunque nel formato "{tmdb-ID}"), senza dover rifare la ricerca."""
    for name in names:
        if not name:
            continue
        m = _TMDB_ID_RE.search(str(name))
        if m:
            return m.group(1)
    return None

def get_log_dir():
    """Restituisce la cartella dei log configurata dall'utente."""
    configured_path = (CONFIG.get("logs_dir") or "").strip()

    if configured_path:
        return Path(configured_path).expanduser()

    return Path.home() / ".local" / "share" / "MediaTidy" / "logs"

def redact(text):
    """Nasconde la chiave API TMDB in qualsiasi testo destinato a UI, log o CSV."""
    text = str(text)
    key = (CONFIG.get("api_key") or "").strip()
    return text.replace(key, "***") if len(key) >= 8 else text


def _daily_log_path():
    return get_log_dir() / f"MediaTidy_{date.today().isoformat()}.log"


def log_event(level, message):
    """Scrive nel log giornaliero senza interrompere il programma."""
    try:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
        with _daily_log_path().open("a", encoding="utf-8") as file:
            file.write(f"[{stamp}] {level.upper()} - {redact(message)}\n")
    except Exception:
        pass


def cleanup_old_logs():
    """Conserva log e CSV degli ultimi 10 giorni, compreso oggi."""
    try:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        cutoff = date.today() - timedelta(days=LOG_RETENTION_DAYS - 1)

        for path in log_dir.iterdir():
            match = re.fullmatch(
                r"MediaTidy_(?:movies_|series_)?(\d{4}-\d{2}-\d{2})\.(?:log|csv)",
                path.name
            )
            if not match:
                continue

            try:
                if date.fromisoformat(match.group(1)) < cutoff:
                    path.unlink()
            except (ValueError, OSError):
                continue
    except Exception:
        pass


def log_csv_row(kind, header, values):
    """Registra una riga CSV in un file giornaliero per film o serie."""
    try:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        csv_path = log_dir / f"MediaTidy_{kind}_{date.today().isoformat()}.csv"
        new_file = not csv_path.exists() or csv_path.stat().st_size == 0

        with csv_path.open("a", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)

            if new_file:
                writer.writerow(header)

            writer.writerow(values)

    except Exception as error:
        log_event("ERROR", f"Impossibile aggiornare il CSV {kind}: {error}")


def is_remote(dest):
    return ":" in dest and not dest.startswith("/")


def _remote_parts(dest, folder, filename=None):
    host, path = dest.split(":", 1)
    remote = f"{path.rstrip('/')}/{folder}"
    return host, remote, (f"{remote}/{filename}" if filename else remote)


def target_exists(dest, folder, filename):
    if is_remote(dest):
        host, _dir, full = _remote_parts(dest, folder, filename)
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", host, "test", "-e", shlex.quote(full)],
            capture_output=True, timeout=20,
        )
        if r.returncode == 0:
            return True
        if r.returncode == 1:
            return False
        raise RuntimeError("Host remoto non raggiungibile via SSH")
    return (Path(dest) / folder / filename).exists()


def is_inplace_source(src_path, dest_base):
    if not dest_base or is_remote(dest_base):
        return False
    try:
        return Path(dest_base).resolve() in Path(src_path).resolve().parents
    except Exception:
        return False


def is_same_file(src_path, dest, folder, filename):
    """True se il file sorgente è già esattamente nel percorso di destinazione finale."""
    if not is_inplace_source(src_path, dest):
        return False
    try:
        return Path(src_path).resolve() == (Path(dest) / folder / filename).resolve()
    except OSError:
        return False


def download_poster(poster_path, target_folder_path, dest):
    if not poster_path:
        return
    url = f"https://image.tmdb.org/t/p/w500{poster_path}"
    tmp_name = None
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return
        if is_remote(dest):
            host, remote_dir, _full = _remote_parts(dest, target_folder_path)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(r.content)
                tmp_name = tmp.name
            res = subprocess.run(
                ["rsync", "-a", "--chmod=F644", "--protect-args", "-e", "ssh -o BatchMode=yes",
                 tmp_name, f"{host}:{remote_dir}/poster.jpg"],
                capture_output=True, text=True, timeout=60,
            )
            if res.returncode != 0:
                log_event("WARNING", f"Poster non caricato: {res.stderr.strip()}")
        else:
            (Path(dest) / target_folder_path / "poster.jpg").write_bytes(r.content)
    except Exception as e:
        log_event("WARNING", f"Download poster fallito: {e}")
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def get_dir_size(dir_path):
    total_size = 0
    for p in Path(dir_path).rglob('*'):
        if p.is_file():
            try:
                total_size += p.stat().st_size
            except OSError:
                pass
    return total_size


def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def _rsync_to_remote(src_path, dest, folder, filename, action, report):
    host, remote_dir, _full = _remote_parts(dest, folder)
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, "mkdir", "-p", shlex.quote(remote_dir)],
        check=True, capture_output=True,
    )
    cmd = ["rsync", "-a", "--partial", "--info=progress2", "--protect-args",
           "-e", "ssh -o BatchMode=yes"]
    if action == "move":
        cmd.append("--remove-source-files")
    cmd.extend([str(src_path), f"{host}:{remote_dir}/{filename}"])

    # stderr unito a stdout: una sola pipe, nessun rischio di deadlock
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1)
    tail = collections.deque(maxlen=10)
    for line in proc.stdout:
        match = re.search(r"(\d+)%", line)
        if match:
            report(int(match.group(1)))
        elif line.strip():
            tail.append(line.strip())
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Errore rsync: {' '.join(tail)}")
    report(100)


def _copy_local(src_path, target_dir, filename, action, report):
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / filename

    # Sorgente e destinazione coincidono: aprire il file in scrittura lo azzererebbe.
    if target_file.exists() and os.path.samefile(src_path, target_file):
        return

    if action == "move":
        try:
            os.replace(src_path, target_file)  # stesso filesystem: istantaneo
            report(100)
            return
        except OSError:
            pass  # filesystem diversi: si copia e poi si elimina l'originale

    tmp_file = target_file.with_name(target_file.name + ".part")
    total_size = src_path.stat().st_size
    copied = 0
    try:
        with open(src_path, "rb") as fsrc, open(tmp_file, "wb") as fdst:
            while True:
                buf = fsrc.read(COPY_CHUNK)
                if not buf:
                    break
                fdst.write(buf)
                copied += len(buf)
                if total_size > 0:
                    report(min(int(copied / total_size * 100), 99))
            fdst.flush()
            os.fsync(fdst.fileno())
        if tmp_file.stat().st_size != total_size:
            raise OSError("Copia incompleta: dimensione diversa dall'originale")
        shutil.copystat(str(src_path), str(tmp_file))
        os.replace(tmp_file, target_file)  # il file finale compare solo a copia completata
    except BaseException:
        try:
            tmp_file.unlink()
        except OSError:
            pass
        raise

    report(100)
    if action == "move":
        src_path.unlink()


def move_or_copy_file(src, dest, folder, filename, poster_path=None, action="move", progress_callback=None):
    """Sposta/copia (o rinomina in-place) un file video verso dest/folder/filename.
    La pulizia della cartella d'origine NON avviene qui ma a fine esecuzione."""
    src_path = Path(src)

    def report(pct):
        if progress_callback:
            progress_callback(pct)

    inplace = is_inplace_source(src_path, dest)
    same = inplace and src_path.resolve() == (Path(dest) / folder / filename).resolve()
    # In-place: rinomina solo in modalità Sposta (o se il file è già al suo posto).
    rename_inplace = inplace and (action == "move" or same)

    if rename_inplace:
        target_dir = Path(dest) / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / filename
        report(50)
        if not same:
            if target_file.exists():
                target_file.unlink()
            shutil.move(str(src_path), str(target_file))
        report(100)
    elif is_remote(dest):
        _rsync_to_remote(src_path, dest, folder, filename, action, report)
    else:
        _copy_local(src_path, Path(dest) / folder, filename, action, report)

    if poster_path:
        download_poster(poster_path, folder, dest)


def find_fstab_mountpoint(dest, fstab="/etc/fstab"):
    dest = os.path.abspath(dest)
    try:
        lines = Path(fstab).read_text().splitlines()
    except OSError:
        return None
    best = None
    for line in lines:
        parts = line.split("#", 1)[0].split()
        if len(parts) < 2 or not parts[1].startswith("/") or parts[1] == "/":
            continue
        mp = os.path.abspath(parts[1].replace("\\040", " "))
        if (dest == mp or dest.startswith(mp + "/")) and (best is None or len(mp) > len(best)):
            best = mp
    return best


def mount_share(mp):
    r = subprocess.run(["mount", mp], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"Montaggio di {mp} non riuscito: {(r.stderr or r.stdout).strip()}")


def unmount_share(mp):
    r = subprocess.run(["umount", mp], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip() or "Umount non riuscito")


def play_system_sound():
    sound_files = [
        "/usr/share/sounds/freedesktop/stereo/complete.oga",
        "/usr/share/sounds/mint/complete.oga",
        "/usr/share/sounds/ubuntu/notifications/bell.ogg",
        "/usr/share/sounds/freedesktop/stereo/bell.oga",
    ]
    for sound in sound_files:
        if os.path.exists(sound):
            try:
                subprocess.Popen(["paplay", sound], stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                try:
                    subprocess.Popen(["canberra-gtk-play", "-f", sound], stderr=subprocess.DEVNULL)
                    return
                except FileNotFoundError:
                    pass
    try:
        subprocess.Popen(["play", "-n", "synth", "0.1", "sin", "800"], stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("\a")


def send_mint_notification(title, message):
    try:
        subprocess.Popen(
            ["notify-send", "-i", "video-x-generic", "-a", "MediaTidy", title, message],
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        pass
