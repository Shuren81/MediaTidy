#!/usr/bin/env python3
"""
tmdb_key.py - Quale chiave API TMDB usare.

- Se l'utente ne ha inserita una nelle Opzioni, usa quella.
- Altrimenti usa la chiave PREDEFINITA dello sviluppatore, incorporata nella build.

La chiave predefinita NON sta nel repository: la crea la build (scripts/embed_key.py, a
partire dal secret TMDB_API_KEY di GitHub) in un file generato, ignorato da git
(_runtime_data.py), e vi è memorizzata mascherata, non in chiaro. Da sorgente il file non
esiste e serve la propria chiave nelle Opzioni.

Non viene mai scritta in CONFIG, nelle impostazioni, nei log o mostrata nell'interfaccia.
Resta però recuperabile da chi analizza il programma o il traffico di rete (deve pur
arrivare a TMDB): la mascheratura serve contro la ricerca casuale e i bot, non contro un
attacco mirato.
"""
import base64

from config import CONFIG

try:
    import _runtime_data as _rd  # generato dalla build, mai nel repository
except ImportError:
    _rd = None

_cache = None


def _decode():
    if _rd is None:
        return ""
    try:
        mask = base64.b64decode(_rd._A)
        blob = base64.b64decode(_rd._B)
        return bytes(b ^ m for b, m in zip(blob, mask)).decode("ascii")
    except Exception:
        return ""


def default_api_key():
    """Chiave predefinita della build ("" se non incorporata)."""
    global _cache
    if _cache is None:
        _cache = _decode()
    return _cache


def effective_api_key():
    """Chiave da usare nelle richieste: quella dell'utente se presente, altrimenti la predefinita."""
    return (CONFIG.get("api_key") or "").strip() or default_api_key()


def has_api_key():
    return bool(effective_api_key())


def secret_keys():
    """Tutte le chiavi che non devono mai comparire in log, CSV o messaggi."""
    keys = ((CONFIG.get("api_key") or "").strip(), default_api_key())
    return [k for k in keys if len(k) >= 8]
