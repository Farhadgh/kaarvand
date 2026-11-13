"""FarazSMS client for OTP delivery.

Two call shapes are supported, both against ``farazsms_base_url``:

* pattern based (recommended): the approved template carries the code variable,
  so the message text is not free form and cannot be blocked as spam;
* plain text: used only when no pattern code is configured (dev / testing).

The function never raises: the OTP row is already stored, and a provider outage
must surface as ``otp.sms_unavailable`` instead of a 500 page.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": settings.farazsms_api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _message_text(code: str, settings: Settings) -> str:
    minutes = max(1, settings.otp_ttl_seconds // 60)
    return f"کاروند\nکد ورود شما: {code}\nاعتبار: {minutes} دقیقه"


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

    if cfg.farazsms_otp_pattern:
        url = f"{cfg.farazsms_base_url.rstrip('/')}/send/pattern"
        payload: dict[str, object] = {
            "pattern_code": cfg.farazsms_otp_pattern,
            "originator": cfg.farazsms_sender,
            "recipient": phone,
            "values": {"code": code},
        }
    else:
        url = f"{cfg.farazsms_base_url.rstrip('/')}/send/sms"
        payload = {
            "originator": cfg.farazsms_sender,
            "recipient": phone,
            "message": _message_text(code, cfg),
        }

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=cfg.sms_timeout_seconds)
    try:
        response = await http.post(url, json=payload, headers=_headers(cfg))
    except httpx.HTTPError as exc:  # network, DNS, timeout
        logger.warning("FarazSMS request failed for %s: %s", phone, exc)
        return False
    finally:
        if owns_client:
            await http.aclose()

    if response.status_code >= 400:
        logger.warning(
            "FarazSMS rejected OTP for %s: %s %s",
            phone,
            response.status_code,
            response.text[:300],
        )
        return False
    return True
