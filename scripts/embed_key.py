#!/usr/bin/env python3
"""
scripts/embed_key.py - Incorpora nella build la chiave TMDB predefinita.

Legge la chiave dalla variabile d'ambiente TMDB_API_KEY (in GitHub Actions viene dal
secret omonimo del repository) e scrive _runtime_data.py nella radice del progetto, con
la chiave mascherata. Quel file è ignorato da git e non va MAI committato.
Non stampa mai la chiave.

  --require   esce con errore se la chiave manca (usato per le release: una release senza
              chiave predefinita non deve partire in silenzio)
"""
import argparse
import base64
import os
import re
import secrets
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "_runtime_data.py"
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,}$")


def module_text(key):
    raw = key.encode("ascii")
    mask = secrets.token_bytes(len(raw))
    blob = bytes(a ^ b for a, b in zip(raw, mask))
    return (
        "# File generato dalla build (scripts/embed_key.py): NON va committato.\n"
        f'_A = "{base64.b64encode(mask).decode()}"\n'
        f'_B = "{base64.b64encode(blob).decode()}"\n'
    )


def main(argv=None, out=OUT, env=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--require", action="store_true")
    args = parser.parse_args(argv)
    key = ((env if env is not None else os.environ).get("TMDB_API_KEY") or "").strip()
    if not key:
        if args.require:
            print("ERRORE: TMDB_API_KEY mancante: aggiungila ai secret del repository.", file=sys.stderr)
            return 1
        print("Nessuna chiave TMDB predefinita: la build non ne conterrà una.")
        return 0
    if not _VALID.match(key):
        print("ERRORE: la chiave TMDB ha un formato non valido.", file=sys.stderr)
        return 1
    Path(out).write_text(module_text(key), encoding="utf-8")
    print(f"Chiave TMDB predefinita incorporata ({len(key)} caratteri).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
