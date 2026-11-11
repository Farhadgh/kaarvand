"""Persian number-to-words (needed for invoices: "مبلغ به حروف")."""

from __future__ import annotations

ONES = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
TEENS = [
    "ده",
    "یازده",
    "دوازده",
    "سیزده",
    "چهارده",
    "پانزده",
    "شانزده",
    "هفده",
    "هجده",
    "نوزده",
]
TENS = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
HUNDREDS = [
    "",
    "یکصد",
    "دویست",
    "سیصد",
    "چهارصد",
    "پانصد",
    "ششصد",
    "هفتصد",
    "هشتصد",
    "نهصد",
]
SCALES = ["", "هزار", "میلیون", "میلیارد", "هزار میلیارد", "میلیون میلیارد"]

MAX_SUPPORTED = 10**18


def _three_digits_to_words(num: int) -> str:
    parts: list[str] = []
    hundreds, rest = divmod(num, 100)
    if hundreds:
        parts.append(HUNDREDS[hundreds])
    if 10 <= rest <= 19:
        parts.append(TEENS[rest - 10])
    else:
        tens, ones = divmod(rest, 10)
        if tens:
            parts.append(TENS[tens])
        if ones:
            parts.append(ONES[ones])
    return " و ".join(parts)


def int_to_words_fa(number: int) -> str:
    """Return the Persian words for a non-negative integer."""
    if number < 0:
        return "منفی " + int_to_words_fa(-number)
    if number == 0:
        return "صفر"
    if number >= MAX_SUPPORTED:
        raise ValueError("number too large")

    groups: list[str] = []
    scale_index = 0
    remaining = number
    while remaining > 0:
        remaining, group = divmod(remaining, 1000)
        if group:
            chunk = _three_digits_to_words(group)
            if scale_index:
                chunk = f"{chunk} {SCALES[scale_index]}"
            groups.append(chunk)
        scale_index += 1
    return " و ".join(reversed(groups))


def amount_to_words_fa(amount: int, *, unit: str = "ریال", sub_unit: str | None = None) -> str:
    """Invoice helper: 120000 -> "یکصد و بیست هزار ریال"."""
    words = int_to_words_fa(int(amount))
    return f"{words} {unit}".strip() if unit else words


def toman_to_words_fa(amount_toman: int) -> str:
    return amount_to_words_fa(amount_toman, unit="تومان")
