"""
Indic transliteration helper for the geography master tables.

Why this exists
---------------
The web Master forms (Add / Edit State / District / Centre / Area) accept
only an English name from the admin. The mobile FLP survey app, however,
displays those names in the surveyor's chosen language — Hindi, Bengali
or Tamil — by reading the `*_name_hi / _bn / _ta` columns on each
master row (added in migration 046).

To keep the web form a single-field entry, the backend transliterates
the English name into the three Indic scripts on every save. The work
happens on the rare write path (geography is added a handful of rows at
a time), never on the hot read path.

Implementation choice
---------------------
We call Google's Input Tools transliteration endpoint with one HTTP GET
per word, joining the results back into the phrase. This avoids pulling
in a multi-hundred-MB ML model (AI4Bharat IndicXlit, etc.) onto the API
server for what is genuinely a low-volume operation.

The endpoint expects a single token at a time and is happiest with that
shape ("Kailash Nagar" goes in as "Kailash", "Nagar"). For names that
embed English words like "East Delhi" it produces a phonetic rendering
("ईस्ट दिल्ली") rather than the "proper" translated form ("पूर्वी दिल्ली");
that tradeoff was accepted by the project (no admin override) so this
helper just delivers what the endpoint returns.

On any failure (network drop, timeout, malformed response) we return the
original English text untouched, so the calling code can safely store
whatever this function returns — the row is never written with NULL or
blank language columns.

Stdlib-only (urllib + json) — no new pip dependency.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

_GOOGLE_INPUT_TOOLS = "https://inputtools.google.com/request"

# Google Input Tools uses BCP-47-ish locale codes with a transliteration
# suffix; these three cover everything we localise the mobile app into.
_LANG_ITC = {
    "hi": "hi-t-i0-und",
    "bn": "bn-t-i0-und",
    "ta": "ta-t-i0-und",
}


def _transliterate_word(word: str, itc: str, timeout: float = 5.0) -> str:
    """Transliterate a single token; on any error fall back to the input.

    Falling back (rather than raising) is deliberate — callers feed this
    into a database write, and "stored as English" is a better failure
    mode than "row could not be saved at all".
    """
    if not word:
        return word
    params = {
        "text": word,
        "itc": itc,
        "num": 1,
        "cp": 0,
        "cs": 1,
        "ie": "utf-8",
        "oe": "utf-8",
    }
    url = f"{_GOOGLE_INPUT_TOOLS}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        # Response shape:
        #   ["SUCCESS", [["<input>", ["<output1>", "<output2>", ...], [], {...}]]]
        if payload and payload[0] == "SUCCESS":
            candidates = payload[1][0][1]
            if candidates:
                return candidates[0]
    except Exception:
        # Swallow EVERYTHING — see docstring; English fallback is the
        # intentional failure mode.
        pass
    return word


def transliterate(text: str, lang: str) -> str:
    """Transliterate `text` into the script of `lang` (hi / bn / ta).

    Splits on whitespace and joins so multi-word place names like
    "Kailash Nagar" are handled correctly. Returns `text` unchanged
    for unsupported lang codes or empty input.
    """
    if not text or not text.strip():
        return text or ""
    itc = _LANG_ITC.get(lang)
    if not itc:
        return text
    words = text.split()
    return " ".join(_transliterate_word(w, itc) for w in words)


def transliterate_all(text: str) -> dict:
    """Return {'hi': ..., 'bn': ..., 'ta': ...} for one English text.

    Used by the geography CRUD endpoints — one call per save populates
    all three language columns at once.
    """
    return {lang: transliterate(text, lang) for lang in ("hi", "bn", "ta")}
