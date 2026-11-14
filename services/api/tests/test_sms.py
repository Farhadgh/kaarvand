"""IranPayamak (FarazSMS v2) delivery: the exact payload the gateway documents.

The docs are explicit about the shape (https://docs.iranpayamak.com):

* ``POST /ws/v1/sms/pattern`` with ``code``, ``recipient``, ``attributes``,
  ``line_number`` and ``number_format``; the key travels in ``Api-Key``;
* the answer is ``{"status": "success"|"error", "data": …, "messages": …}``, and
  an error can arrive with **HTTP 200** — so the body decides.

These tests pin all of that, plus the rule that a broken provider never raises:
the OTP row is already stored and the caller reports ``sms_delivered: false``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.notifications.sms import account_report, send_otp

PHONE = "09121234567"
CODE = "54321"
LINE = "50002178584000"
PATTERN = "SJ3FgPrE0C"


def _settings(**overrides: Any) -> Any:
    from app.core.config import Settings

    base: dict[str, Any] = {
        "sms_enabled": True,
        "farazsms_api_key": "test-key",
        "farazsms_base_url": "https://api.iranpayamak.com",
        "farazsms_sender": LINE,
        "farazsms_otp_pattern": PATTERN,
        "otp_ttl_seconds": 120,
    }
    base.update(overrides)
    return Settings(**base)


def _client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_pattern_request_matches_the_documented_api() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"status": "success", "data": 98765, "messages": None})

    async with _client(handler) as http:
        assert await send_otp(PHONE, CODE, settings=_settings(), client=http) is True

    assert seen["url"] == "https://api.iranpayamak.com/ws/v1/sms/pattern"
    assert seen["headers"]["api-key"] == "test-key"
    assert seen["body"] == {
        "code": PATTERN,
        "recipient": PHONE,
        "attributes": {"code": CODE},
        "line_number": LINE,
        "number_format": "english",
    }


async def test_pattern_variable_name_is_configurable() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"status": "success", "data": 1, "messages": None})

    settings = _settings(farazsms_otp_pattern_var="otp_code")
    async with _client(handler) as http:
        assert await send_otp(PHONE, CODE, settings=settings, client=http) is True

    assert seen["body"]["attributes"] == {"otp_code": CODE}


async def test_error_status_with_http_200_is_a_failure() -> None:
    """An unknown line or an unapproved pattern comes back as 200 + status=error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "error", "data": None, "messages": ["line is not accessible"]},
        )

    async with _client(handler) as http:
        assert await send_otp(PHONE, CODE, settings=_settings(), client=http) is False


async def test_simple_sms_is_used_when_no_pattern_is_configured() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"status": "success", "data": 1, "messages": None})

    settings = _settings(farazsms_otp_pattern="")
    async with _client(handler) as http:
        assert await send_otp(PHONE, CODE, settings=settings, client=http) is True

    assert seen["url"] == "https://api.iranpayamak.com/ws/v1/sms/simple"
    assert seen["body"]["recipients"] == [PHONE]
    assert seen["body"]["line_number"] == LINE
    assert seen["body"]["number_format"] == "english"
    assert CODE in seen["body"]["text"]
    assert seen["body"]["schedule"] is None


async def test_network_error_never_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async with _client(handler) as http:
        assert await send_otp(PHONE, CODE, settings=_settings(), client=http) is False


async def test_disabled_sms_does_not_call_the_gateway() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        nonlocal called
        called = True
        return httpx.Response(201, json={"status": "success", "data": 1, "messages": None})

    async with _client(handler) as http:
        assert (
            await send_otp(PHONE, CODE, settings=_settings(sms_enabled=False), client=http) is False
        )

    assert called is False


async def test_account_report_reads_balance_lines_and_patterns() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/ws/v1/account/balance":
            data: Any = {"balance_amount": "100000", "balance_count": "450.45"}
        elif request.url.path == "/ws/v1/lines/accessible":
            data = [{"number": "50002178584000", "is_dedicated": False}]
        else:
            data = {
                "data": [{"code": "tHtKn7CJSK", "status": "pending", "text": "…", "attributes": []}]
            }
        return httpx.Response(200, json={"status": "success", "message": "", "data": data})

    async with _client(handler) as http:
        report = await account_report(_settings(), client=http)

    assert seen == ["/ws/v1/account/balance", "/ws/v1/lines/accessible", "/ws/v1/patterns"]
    assert report["errors"] == {}
    assert report["balance"]["balance_amount"] == "100000"
    assert report["lines"][0]["number"] == "50002178584000"
    assert report["patterns"]["data"][0]["code"] == "tHtKn7CJSK"


async def test_account_report_keeps_the_other_endpoints_when_one_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ws/v1/lines/accessible":
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json={"status": "success", "message": "", "data": {"data": []}})

    async with _client(handler) as http:
        report = await account_report(_settings(), client=http)

    assert "lines" not in report
    assert report["errors"]["lines"].startswith("ReadTimeout")
    assert report["patterns"] == {"data": []}


async def test_missing_line_number_is_a_failure() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        nonlocal called
        called = True
        return httpx.Response(201, json={"status": "success", "data": 1, "messages": None})

    async with _client(handler) as http:
        assert (
            await send_otp(PHONE, CODE, settings=_settings(farazsms_sender=""), client=http)
            is False
        )

    assert called is False
