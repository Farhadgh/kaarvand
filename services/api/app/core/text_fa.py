"""Persian text helpers: normalisation, digits, money formatting.

Why this module exists: Persian users type Arabic yeh/kaf, Arabic-Indic digits
and ZWNJ inconsistently. Every search / uniqueness check / prompt variable must
see the same normalised form.
"""

from __future__ import annotations

import re
import unicodedata

ARABIC_TO_PERSIAN = {
    "\u064a": "\u06cc",  # ي -> ی
    "\u0649": "\u06cc",  # ى -> ی
    "\u0643": "\u06a9",  # ك -> ک
    "\u0629": "\u0647",  # ة -> ه
    "\u06c0": "\u0647\u0654",  # ۀ
    "\u0640": "",  # tatweel
}

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
LATIN_DIGITS = "0123456789"

_DIGIT_MAP = {ord(c): str(i) for i, c in enumerate(PERSIAN_DIGITS)}
_DIGIT_MAP.update({ord(c): str(i) for i, c in enumerate(ARABIC_DIGITS)})

_DIACRITICS = re.compile(r"[\u064b-\u0652\u0670]")
_SPACES = re.compile(r"\s+")


def to_latin_digits(text: str) -> str:
    """Convert Persian/Arabic digits to ASCII digits."""
    return text.translate(_DIGIT_MAP)


def to_persian_digits(text: str) -> str:
    """Convert ASCII digits to Persian digits (display only)."""
    return text.translate({ord(c): PERSIAN_DIGITS[i] for i, c in enumerate(LATIN_DIGITS)})


def normalize_fa(text: str) -> str:
    """Normalise Persian text for storage, comparison and search."""
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    for src, dst in ARABIC_TO_PERSIAN.items():
        out = out.replace(src, dst)
    out = _DIACRITICS.sub("", out)
    out = to_latin_digits(out)
    out = out.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    out = out.replace("\u00a0", " ")
    return _SPACES.sub(" ", out).strip()


def search_norm(text: str) -> str:
    """Aggressive form used for ILIKE style search keys."""
    return normalize_fa(text).casefold()


def format_irr(amount: int, *, digits: str = "fa", unit: str = "ریال") -> str:
    """Format an amount with Persian separators (stored unit is IRR/Rial)."""
    sign = "-" if amount < 0 else ""
    raw = f"{abs(int(amount)):,}".replace(",", "\u066c")
    if digits == "fa":
        raw = to_persian_digits(raw)
    return f"{sign}{raw} {unit}".strip()


_FA_PHONE = re.compile(r"^09\d{9}$")
_FA_NATIONAL_ID = re.compile(r"^\d{10}$")
_SHEBA = re.compile(r"^IR\d{24}$", re.IGNORECASE)


def is_iran_mobile(value: str) -> bool:
    return bool(_FA_PHONE.match(to_latin_digits(value).replace(" ", "").replace("-", "")))


def is_iran_national_id(value: str) -> bool:
    return bool(_FA_NATIONAL_ID.match(to_latin_digits(value)))


def is_sheba(value: str) -> bool:
    return bool(_SHEBA.match(to_latin_digits(value).replace(" ", "")))
