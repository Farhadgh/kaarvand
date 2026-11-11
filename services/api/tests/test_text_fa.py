"""Persian text helpers."""

from __future__ import annotations

from app.core.text_fa import (
    format_irr,
    is_iran_mobile,
    is_iran_national_id,
    is_sheba,
    normalize_fa,
    search_norm,
    to_latin_digits,
    to_persian_digits,
)


def test_normalize_arabic_letters() -> None:
    assert normalize_fa("علي كريمي") == "علی کریمی"


def test_normalize_diacritics_and_space() -> None:
    assert normalize_fa("مُحَمَّد") == "محمد"
    assert normalize_fa("می\u200cخواهم") == "می خواهم"
    assert normalize_fa("  سلام   دنیا  ") == "سلام دنیا"


def test_digits_conversion() -> None:
    assert to_latin_digits("۰۱۲۳۴۵۶۷۸۹") == "0123456789"
    assert to_latin_digits("٤٥٦") == "456"
    assert to_persian_digits("1404") == "۱۴۰۴"


def test_normalize_converts_digits_to_ascii() -> None:
    assert normalize_fa("کد ۱۲۳") == "کد 123"


def test_format_irr_uses_persian_digits_and_separator() -> None:
    assert format_irr(1234567) == "۱٬۲۳۴٬۵۶۷ ریال"
    assert format_irr(-5000) == "-۵٬۰۰۰ ریال"
    assert format_irr(1234567, unit="تومان") == "۱٬۲۳۴٬۵۶۷ تومان"


def test_search_norm_is_casefolded() -> None:
    assert search_norm("Report علي") == "report علی"


def test_iran_mobile() -> None:
    assert is_iran_mobile("۰۹۱۲۳۴۵۶۷۸۹")
    assert is_iran_mobile("0912 345 6789")
    assert not is_iran_mobile("12345")
    assert not is_iran_mobile("+989123456789")


def test_iran_national_id_and_sheba() -> None:
    assert is_iran_national_id("۰۰۱۲۳۴۵۶۷۸")
    assert is_sheba("IR062960000000100324200001")
    assert not is_sheba("IR123")
