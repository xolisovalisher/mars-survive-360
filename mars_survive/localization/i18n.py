"""Multilingual System (module 24): ONE central translation service.

* Locale files: mars_survive/localization/locales/<code>.json (flat "key": "text").
* Fallback chain: selected language -> English -> the key itself (never crashes).
* Placeholders use str.format: t("route.found", n=3).
* Adding a language = adding one JSON file + one line in LANGUAGES (designed for 50+).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LOCALE_DIR = Path(__file__).resolve().parent / "locales"

# code: (native name, English name, right-to-left)
LANGUAGES = {
    "en": ("English", "English", False),
    "zh": ("中文", "Chinese", False),
    "es": ("Español", "Spanish", False),
    "ar": ("العربية", "Arabic", True),
    "fr": ("Français", "French", False),
    "hi": ("हिन्दी", "Hindi", False),
    "ru": ("Русский", "Russian", False),
    "de": ("Deutsch", "German", False),
    "ja": ("日本語", "Japanese", False),
    "tr": ("Türkçe", "Turkish", False),
    "ko": ("한국어", "Korean", False),
    "it": ("Italiano", "Italian", False),
    "vi": ("Tiếng Việt", "Vietnamese", False),
    "uk": ("Українська", "Ukrainian", False),
    "kk": ("Қазақша", "Kazakh", False),
    "uz": ("O‘zbekcha", "Uzbek", False),
    "ky": ("Кыргызча", "Kyrgyz", False),
    "tk": ("Türkmençe", "Turkmen", False),
}
DEFAULT = "en"


@lru_cache(maxsize=64)
def _load(code: str) -> dict:
    p = LOCALE_DIR / f"{code}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def reload():
    _load.cache_clear()


def t(key: str, lang: str = DEFAULT, **kw) -> str:
    s = _load(lang).get(key)
    if s is None:
        s = _load(DEFAULT).get(key, key)
    if kw:
        try:
            return s.format(**kw)
        except (KeyError, IndexError, ValueError):
            return s
    return s


def is_rtl(lang: str) -> bool:
    return LANGUAGES.get(lang, ("", "", False))[2]


def coverage() -> list[dict]:
    base = _load(DEFAULT)
    out = []
    for code, (native, eng, rtl) in LANGUAGES.items():
        d = _load(code)
        have = sum(1 for k in base if k in d and str(d[k]).strip())
        missing = [k for k in base if k not in d]
        out.append({"code": code, "language": native, "english": eng, "rtl": rtl, "keys": have, "total": len(base),
                    "coverage": have / len(base) if base else 0.0, "missing": missing[:10]})
    return out


class Translator:
    """Bound translator for one language: tr = Translator('uz'); tr('nav.dashboard')."""

    def __init__(self, lang: str):
        self.lang = lang if lang in LANGUAGES else DEFAULT

    def __call__(self, key: str, **kw) -> str:
        return t(key, self.lang, **kw)
