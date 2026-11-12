"""Persian (``fa``) support for speech models — the logic.

Vendor marketing is unreliable here: several TTS models that advertise
"40+ languages" still read Persian with a heavy Arabic accent, and a few answer
in an unrelated language. So instead of trusting ``description`` fields we use a
*probe table* produced by ``scripts/fa_audio_probe.py`` (see
``app/seeding/persian_probe.py`` for the measured numbers).

Levels:

======== ==========  =========================================
level    score       meaning
======== ==========  =========================================
verified >= 0.95     reads Persian fluently (probe verified)
good     >= 0.80     Persian with an accent, still usable
weak     >= 0.50     broken Persian / heavy Arabic accent
none     < 0.50      does not speak Persian at all
======== ==========  =========================================

A model missing from the table is *unknown* — never assume it works. An operator
can override any entry per model with ``models.meta.persian`` (a level string);
a fresh probe run can cache its own result in ``models.meta.persian_probe``.
"""

from __future__ import annotations

from typing import Any

from app.seeding.persian_probe import PERSIAN_STT, PERSIAN_TTS, PROBE_METHOD, PROBED_AT

__all__ = [
    "LEVELS",
    "LEVEL_LABELS_FA",
    "PROBED_AT",
    "PROBE_METHOD",
    "PERSIAN_STT",
    "PERSIAN_TTS",
    "level_label",
    "level_of_score",
    "persian_of",
]

#: Levels ordered from best to worst (also used by the panel for filtering).
LEVELS = ("verified", "good", "weak", "none")

#: Persian label for every level (the panel renders these verbatim).
LEVEL_LABELS_FA = {
    "verified": "فارسی را روان می‌خواند (آزمایش‌شده)",
    "good": "فارسی را با لهجه می‌خواند",
    "weak": "فارسی را شکسته می‌خواند",
    "none": "فارسی را پشتیبانی نمی‌کند",
    "unknown": "پشتیبانی فارسی بررسی نشده",
}


def level_of_score(score: float) -> str:
    """Map a probe similarity score to a level."""
    if score >= 0.95:
        return "verified"
    if score >= 0.80:
        return "good"
    if score >= 0.50:
        return "weak"
    return "none"


def _table_for(kind: str | None) -> dict[str, float]:
    if kind == "stt":
        return PERSIAN_STT
    if kind == "tts":
        return PERSIAN_TTS
    return {**PERSIAN_STT, **PERSIAN_TTS}


def persian_of(
    external_id: str,
    meta: dict[str, Any] | None = None,
    *,
    kind: str | None = None,
) -> dict[str, Any] | None:
    """Best known Persian verdict for a model, or ``None`` when nothing is known.

    Precedence: operator override (``meta.persian``) -> cached probe result
    (``meta.persian_probe``) -> the curated table shipped with this release.
    """
    meta = meta or {}

    manual = meta.get("persian")
    if isinstance(manual, str) and manual in LEVELS:
        return {
            "level": manual,
            "score": None,
            "label_fa": LEVEL_LABELS_FA[manual],
            "source": "manual",
            "checked_at": None,
        }

    cached = meta.get("persian_probe")
    if isinstance(cached, dict) and cached.get("level") in LEVELS:
        level = str(cached["level"])
        return {
            "level": level,
            "score": cached.get("score"),
            "label_fa": LEVEL_LABELS_FA[level],
            "source": "probe",
            "checked_at": cached.get("checked_at") or PROBED_AT,
        }

    score = _table_for(kind).get(external_id)
    if score is None:
        return None
    level = level_of_score(score)
    return {
        "level": level,
        "score": score,
        "label_fa": LEVEL_LABELS_FA[level],
        "source": "probe",
        "checked_at": PROBED_AT,
    }


def level_label(level: str | None) -> str:
    """Persian sentence for a level (``unknown`` when the level is missing)."""
    return LEVEL_LABELS_FA.get(level or "unknown", LEVEL_LABELS_FA["unknown"])
