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
import uuid
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
    """True se il file sorgente è già esattamente nel percorso di destinazione finale
    (stessa scrittura, maiuscole comprese): nessuna operazione da fare."""
    if not is_inplace_source(src_path, dest):
        return False
    try:
        return Path(src_path).resolve() == (Path(dest) / folder / filename).resolve()
    except OSError:
        return False


def _ensure_correct_case_dir(target_dir):
    """Se nella stessa cartella superiore esiste già una sottocartella con lo stesso
    nome a parte le maiuscole, la rinomina alla scrittura corretta invece di lasciarla
    con quella vecchia: mkdir(exist_ok=True) da solo accetterebbe silenziosamente la
    cartella già esistente (su un filesystem case-insensitive) senza mai correggerne
    le maiuscole, lasciando per sempre "qualcosa da rinominare" ad ogni Test successivo
    anche dopo aver già corretto il file al suo interno.

    Il controllo NON usa target_dir.exists(): su un vero filesystem case-insensitive
    (Windows/macOS di norma, o NTFS/exFAT via ntfs-3g anche su Linux) .exists() risulta
    sempre vero anche quando lo si chiede con la scrittura sbagliata, perché il sistema
    risolve il percorso ignorando le maiuscole — un controllo su .exists() uscirebbe
    subito convinto che non ci sia nulla da fare, lasciando la cartella con la grafia
    vecchia per sempre. iterdir() invece elenca sempre i nomi così come sono REALMENTE
    scritti sul disco, quale che sia la grafia con cui li si è cercati: è l'unico modo
    affidabile per scoprire la scrittura attuale e capire se va corretta.

    Solo locale (mai per destinazioni remote); non fa nulla se la scrittura è già
    corretta o se la cartella superiore non esiste ancora (destinazione tutta nuova)."""
    parent = target_dir.parent
    if not parent.is_dir():
        return False
    try:
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            if child.name == target_dir.name:
                return False  # scrittura già corretta, niente da fare
            if child.name.casefold() == target_dir.name.casefold():
                tmp = child.with_name(f".{child.name}.mediatidy-tmp-{uuid.uuid4().hex[:8]}")
                child.rename(tmp)
                tmp.rename(target_dir)
                return True
    except OSError:
        pass
    return False


def _paths_are_same_physical_file(src_path, target_path):
    """Confronto di basso livello, riusato sia da is_same_physical_file() sia da
    _copy_local(): vedi is_same_physical_file() per la spiegazione del fallback."""
    src_path = Path(src_path)
    target_path = Path(target_path)
    try:
        if os.path.samefile(src_path, target_path):
            return True
    except OSError:
        pass
    try:
        # Confronto sull'INTERO percorso ignorando le maiuscole, non solo sul nome del
        # file: se anche la cartella cambia scrittura nello stesso momento (tipico,
        # perché la stessa regola di capitalizzazione del titolo si applica sia al nome
        # cartella sia al nome file), un confronto sensibile alle maiuscole sulla sola
        # cartella genitore farebbe fallire il riconoscimento anche qui.
        if str(src_path.resolve()).casefold() != str(target_path.resolve()).casefold():
            return False
        s1 = src_path.stat()
        s2 = target_path.stat()
        return s1.st_size == s2.st_size and int(s1.st_mtime) == int(s2.st_mtime)
    except OSError:
        return False


def is_same_physical_file(src_path, dest, folder, filename):
    """True se target esiste e punta allo STESSO file fisico del sorgente, anche se
    la scrittura del nome è diversa (tipicamente solo le maiuscole). Capita normalmente
    su un filesystem case-insensitive: Windows e macOS di norma, e su Linux con dischi
    non nativi (NTFS/exFAT montati con ntfs-3g/exfat-fuse). Va distinto da un vero
    duplicato: qui non c'è nessun altro file da sovrascrivere, serve solo correggere
    la scrittura del nome — mai cancellare "la destinazione" in questo caso, è la
    stessa sorgente. Non applicabile a destinazioni remote (nessun accesso diretto
    al file per il confronto).

    Il confronto primario è os.path.samefile() (stesso inode); alcuni driver FUSE
    (es. ntfs-3g) non lo espongono in modo affidabile, quindi c'è un fallback: stesso
    percorso completo ignorando le maiuscole (cartella e nome file insieme — non solo
    il nome file, perché la stessa regola di capitalizzazione tocca entrambi), più
    stessa dimensione e stessa data di modifica — su un vero case-insensitive-FS
    coincidono sempre perché è la stessa voce di directory; due file DAVVERO diversi
    con lo stesso percorso (maiuscole a parte) avrebbero comunque bisogno di dimensione
    e istante di modifica identici, un caso praticamente impossibile per coincidenza."""
    if is_remote(dest):
        return False
    return _paths_are_same_physical_file(src_path, Path(dest) / folder / filename)


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


def format_duration(seconds):
    """Formatta una durata in secondi in una stringa breve tipo '38s', '4m 12s', '1h 05m'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


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
    _ensure_correct_case_dir(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / filename

    # Sorgente e destinazione coincidono: aprire il file in scrittura lo azzererebbe.
    if target_file.exists() and _paths_are_same_physical_file(src_path, target_file):
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
        old_parent_name = src_path.parent.name
        if (_ensure_correct_case_dir(target_dir)
                and old_parent_name.casefold() == target_dir.name.casefold()):
            # La cartella genitore del sorgente è quella appena rinominata (stessa voce
            # di directory, ora con la scrittura corretta): il file si è spostato
            # insieme a lei, src_path non esiste più con il vecchio percorso.
            src_path = target_dir / src_path.name
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / filename
        report(50)
        same_now = src_path.resolve() == target_file.resolve()
        if not same_now:
            if target_file.exists():
                same_physical = is_same_physical_file(src_path, dest, folder, filename)
                if same_physical:
                    # Stesso file fisico del sorgente, cambia solo la scrittura del nome
                    # (maiuscole/minuscole) su un filesystem case-insensitive: mai
                    # cancellare "la destinazione", sarebbe cancellare la sorgente stessa
                    # un attimo prima di spostarla. Si passa da un nome temporaneo, che
                    # su qualunque filesystem case-insensitive non collide con nessuno
                    # dei due nomi in gioco.
                    tmp_name = target_file.with_name(f".{target_file.name}.mediatidy-tmp-{uuid.uuid4().hex[:8]}")
                    src_path.rename(tmp_name)
                    tmp_name.rename(target_file)
                else:
                    target_file.unlink()
                    shutil.move(str(src_path), str(target_file))
            else:
                shutil.move(str(src_path), str(target_file))
        report(100)
    elif is_remote(dest):
        _rsync_to_remote(src_path, dest, folder, filename, action, report)
    else:
        _copy_local(src_path, Path(dest) / folder, filename, action, report)

    # Se il file era già esattamente al suo posto (nessuna operazione fatta sopra),
    # non ha senso riscaricare il poster ogni volta: non è cambiato nulla da aggiornare.
    if poster_path and not same:
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
