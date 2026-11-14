"""IranPayamak (FarazSMS v2) SMS client for OTP delivery.

Docs: https://docs.iranpayamak.com — base ``https://api.iranpayamak.com`` and the
API key travels in the ``Api-Key`` header.

Two call shapes:

* pattern (recommended): ``POST /ws/v1/sms/pattern`` sends an approved template,
  so the text is fixed by the operator and the code is only an attribute; it
  cannot be flagged as spam and needs no dedicated line per message;
* simple: ``POST /ws/v1/sms/simple`` sends free text, used only when no pattern
  code is configured (dev / testing).

A 2xx status is **not** enough: the gateway answers ``{"status": "success"}`` when
it accepts the message and ``{"status": "error", "messages": [...]}`` otherwise
(an unknown line number or an unapproved pattern arrives with HTTP 200). The body
is therefore checked as well.

The function never raises: the OTP row is already stored, and a provider outage
must surface as ``sms_delivered: false`` instead of a 500 page.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

PATTERN_PATH = "/ws/v1/sms/pattern"
SIMPLE_PATH = "/ws/v1/sms/simple"
BALANCE_PATH = "/ws/v1/account/balance"
LINES_PATH = "/ws/v1/lines/accessible"
PATTERNS_PATH = "/ws/v1/patterns"


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "Api-Key": settings.farazsms_api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _message_text(code: str, settings: Settings) -> str:
    minutes = max(1, settings.otp_ttl_seconds // 60)
    return f"کاروند\nکد ورود شما: {code}\nاعتبار: {minutes} دقیقه"


def _pattern_payload(phone: str, code: str, settings: Settings) -> dict[str, Any]:
    return {
        "code": settings.farazsms_otp_pattern,
        "recipient": phone,
        "attributes": {settings.farazsms_otp_pattern_var: code},
        "line_number": settings.farazsms_sender,
        "number_format": "english",
    }


def _simple_payload(phone: str, code: str, settings: Settings) -> dict[str, Any]:
    return {
        "text": _message_text(code, settings),
        "line_number": settings.farazsms_sender,
        "recipients": [phone],
        "number_format": "english",
        "schedule": None,
    }


def _accepted(response: httpx.Response) -> bool:
    """The gateway reports business errors in the body, often with HTTP 200."""
    if response.status_code >= 400:
        return False
    try:
        body = response.json()
    except ValueError:
        return True  # 2xx without JSON: nothing to contradict acceptance
    if isinstance(body, dict) and "status" in body:
        return body.get("status") == "success"
    return True


def _message_of(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(body, dict):
        return str(body.get("messages") or body.get("message") or body)[:300]
    return str(body)[:300]


async def send_otp(
    phone: str,
    code: str,
    *,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Deliver ``code`` to ``phone``; returns False when it was not accepted."""
    cfg = settings or get_settings()

    if not cfg.sms_enabled or not cfg.farazsms_api_key:
        # Dev / free mode: the code is in the logs and, if enabled, in the
        # response body, so the flow stays testable without credits.
        logger.warning("SMS disabled; OTP for %s is %s", phone, code)
        return False

    if not cfg.farazsms_sender:
        logger.warning("SMS enabled but no line number (APP_FARAZSMS_SENDER); OTP for %s", phone)
        return False

    if cfg.farazsms_otp_pattern:
        path = PATTERN_PATH
        payload = _pattern_payload(phone, code, cfg)
    else:
        path = SIMPLE_PATH
        payload = _simple_payload(phone, code, cfg)

    url = f"{cfg.farazsms_base_url.rstrip('/')}{path}"
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=cfg.sms_timeout_seconds)
    try:
        response = await http.post(url, json=payload, headers=_headers(cfg))
    except httpx.HTTPError as exc:  # network, DNS, timeout
        logger.warning("IranPayamak request failed for %s: %s", phone, exc)
        return False
    finally:
        if owns_client:
            await http.aclose()

    if not _accepted(response):
        logger.warning(
            "IranPayamak rejected OTP for %s: %s %s",
            phone,
            response.status_code,
            _message_of(response),
        )
        return False

    logger.info("OTP sent to %s via %s", phone, path)
    return True


async def account_report(
    settings: Settings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Balance, accessible lines and patterns — what ``python -m app.cli sms-check`` prints.

    A wrong key answers ``401`` with ``{"status": "error"}``; ``raise_for_status``
    lets the caller show that instead of a vague "SMS failed".
    """
    cfg = settings or get_settings()
    base = cfg.farazsms_base_url.rstrip("/")

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=cfg.sms_timeout_seconds)
    try:
        report: dict[str, Any] = {}
        for name, path in (
            ("balance", BALANCE_PATH),
            ("lines", LINES_PATH),
            ("patterns", PATTERNS_PATH),
        ):
            response = await http.get(f"{base}{path}", headers=_headers(cfg))
            response.raise_for_status()
            report[name] = response.json().get("data")
        return report
    finally:
        if owns_client:
            await http.aclose()
