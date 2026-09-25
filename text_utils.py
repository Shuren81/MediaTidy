#!/usr/bin/env python3
"""
text_utils.py - Formattazione e sanificazione dei titoli, condivisa da film e serie TV.

Regole (invariate da MovieTidy):
  ':' -> ' - ' ; '/' e '\\' -> '-' ; rimossi ? * " < > ! | e caratteri di controllo;
  apostrofo italiano di elisione a fine parola (perche' -> perché) senza toccare
  "You've"/"Charlie's"/"O'Connor"; numeri romani maiuscoli a fine titolo o prima di
  ) : , -; tre regole di capitalizzazione configurabili.
"""
import re

_APOSTROPHE_VOWELS = {
    "a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù",
    "A": "À", "E": "È", "I": "Ì", "O": "Ò", "U": "Ù",
}
# Solo apostrofo a fine parola (perche' -> perché). Non tocca "You've", "Charlie's",
# "I'm", "O'Connor" né le elisioni italiane ("un'amica", "l'uomo").
_APOSTROPHE_RE = re.compile(r"([aeiouAEIOU])'(?![A-Za-z0-9])")


def fix_apostrophes(text):
    if not text:
        return text
    return _APOSTROPHE_RE.sub(lambda m: _APOSTROPHE_VOWELS[m.group(1)], text)


def sanitize_title(title, fix_apos=True):
    if not title:
        return ""
    if fix_apos:
        title = fix_apostrophes(title)
    title = re.sub(r":\s*-\s*", " - ", title)
    title = re.sub(r"\s*:\s*", " - ", title)
    title = re.sub(r"[/\\]", "-", title)
    title = re.sub(r'[\?\*"<>\!|]', "", title)
    title = re.sub(r"[\x00-\x1f]", "", title)
    return re.sub(r"\s+", " ", title).strip()


_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "nor", "for", "so", "yet",
    "at", "by", "in", "of", "on", "to", "with", "from",
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
    "di", "da", "con", "su", "per", "tra", "fra",
    "del", "dello", "della", "dei", "degli", "delle",
    "al", "allo", "alla", "ai", "agli", "alle",
    "dal", "dallo", "dalla", "dai", "dagli", "dalle",
    "nel", "nello", "nella", "nei", "negli", "nelle",
    "sul", "sullo", "sulla", "sui", "sugli", "sulle",
    "e", "ed", "o", "od", "ma", "se", "perché", "poiché",
})


def _capitalize_word(word):
    """Maiuscola la prima lettera della parola e dopo ogni trattino, senza toccare il resto."""
    return re.sub(r"((?:^|-)[\W_]*)([^\W\d_])",
                   lambda m: m.group(1) + m.group(2).upper(), word)


def apply_capitalization(text, rule):
    if not text:
        return text

    if rule == 1:
        return text[0].upper() + text[1:] if len(text) > 1 else text.upper()

    if rule not in (2, 3):
        return text

    # Le parole con maiuscole miste (McDonald, WALL-E, DC, E.T.) restano com'erano;
    # si "normalizza" solo se la parola è tutta minuscola o l'intero titolo (2+ parole) è in maiuscolo.
    all_upper = text.isupper() and " " in text  # una sola parola in maiuscolo (WALL-E, IT) resta com'è
    res = []
    for i, w in enumerate(text.split(" ")):
        lw = w.lower()
        if rule == 3 and i > 0 and lw in _STOPWORDS and w != "I":
            res.append(lw)
        elif all_upper:
            res.append(_capitalize_word(lw))
        elif w == lw:
            res.append(_capitalize_word(w))
        else:
            res.append(w)
    return " ".join(res)


def capitalize_title_start(text):
    if not text:
        return text
    # Maiuscola la prima lettera del titolo e la prima lettera dopo ogni parentesi tonda aperta.
    return re.sub(
        r"(^|\()(\s*)([^\W\d_])",
        lambda match: match.group(1) + match.group(2) + match.group(3).upper(),
        text
    )


# Numeri romani: solo a fine titolo o prima di ")", ":", ",", "-" (Rocky II, Star Wars: Episode IV: ...).
# Parole comuni che sono anche numeri romani validi sono escluse.
_ROMAN_EXCLUDE = frozenset({"di", "mi", "ci", "li", "mix", "dix", "lix"})
_ROMAN_RE = re.compile(
    r"(?<![\w'])(?=[MDCLXVI])"
    r"M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
    r"(?=\s*(?:$|[):,\-–]))",
    re.IGNORECASE,
)


def uppercase_roman_numerals(text):
    if not text:
        return text
    return _ROMAN_RE.sub(
        lambda m: m.group(0) if m.group(0).lower() in _ROMAN_EXCLUDE else m.group(0).upper(),
        text,
    )


def format_title(original, localized, cap_rule, title_mode="orig_loc"):
    """Combina titolo originale/localizzato secondo title_mode:
      "original"  -> solo l'originale
      "localized" -> solo il localizzato
      "orig_loc"  -> "Originale (Localizzato)"
      "loc_orig"  -> "Localizzato (Originale)"
    Se uno dei due manca si usa sempre l'altro (mai un titolo vuoto), e se i due
    titoli coincidono si mostra una sola volta anche in modalità "entrambi".
    Applica poi capitalizzazione, numeri romani e sanificazione. Usato sia per film
    (titolo del film) sia per serie TV (nome della serie)."""
    to = (original or "").strip()
    tl = (localized or "").strip()
    # Nessuno dei due deve mai restare vuoto se l'altro è disponibile.
    if not to:
        to = tl
    if not tl:
        tl = to

    same = to.casefold() == tl.casefold()
    if title_mode == "original":
        titolo_str = to
    elif title_mode == "localized":
        titolo_str = tl
    elif title_mode == "loc_orig":
        titolo_str = tl if same else f"{tl} ({to})"
    else:  # "orig_loc", anche come ripiego per valori non riconosciuti
        titolo_str = to if same else f"{to} ({tl})"

    titolo_str = apply_capitalization(titolo_str, cap_rule)
    titolo_str = uppercase_roman_numerals(titolo_str)
    titolo_str = capitalize_title_start(titolo_str)
    return sanitize_title(titolo_str)
