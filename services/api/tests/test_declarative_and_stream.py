"""Declarative adapter and SSE streaming (no SDK, no network)."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import respx

from app.providers.adapters.openai_chat import OpenAICompatibleAdapter

DECLARATIVE_SPEC = {
    "chat": {
        "method": "POST",
        "url": "{{base_url}}/generate",
        "headers": {"Authorization": "Bearer {{api_key}}"},
        "body": {"model": "{{model}}", "prompt": "{{messages_flat}}"},
    },
    "response_map": {
        "text": "$.output[0].content",
        "usage_in": "$.usage.input",
        "usage_out": "$.usage.output",
    },
    "models_url": "{{base_url}}/catalog",
    "models_map": {"id": "$.result[*].key", "context": "$.result[*].ctx"},
}


async def _declarative_provider(client: Any, headers: dict[str, str]) -> dict[str, Any]:
    payload = {
        "name": f"decl-{uuid.uuid4().hex[:6]}",
        "kind": "declarative",
        "base_url": "https://decl.test",
        "api_key": "secret-decl-key",
        "chat_spec": DECLARATIVE_SPEC,
        "response_map": DECLARATIVE_SPEC["response_map"],
    }
    response = await client.post("/v1/providers", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@respx.mock
async def test_declarative_provider_syncs_custom_json(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await _declarative_provider(client, auth_headers)
    respx.get("https://decl.test/catalog").mock(
        return_value=httpx.Response(
            200, json={"result": [{"key": "nova-1", "ctx": 32000}, {"key": "nova-2"}]}
        )
    )

    response = await client.post(
        f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 2

    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=auth_headers)
    ).json()
    first = next(model for model in models if model["external_id"] == "nova-1")
    assert first["context_window"] == 32000


@respx.mock
async def test_openai_stream_is_parsed_into_chunks() -> None:
    events = (
        'data: {"choices":[{"delta":{"content":"سلام"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":" دنیا"}}]}\n\n'
        'data: {"usage":{"prompt_tokens":12,"completion_tokens":3}}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post("https://api.stream.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=events, headers={"content-type": "text/event-stream"})
    )

    class FakeProvider:
        kind = "openai_compatible"
        base_url = "https://api.stream.test/v1"
        auth_type = "bearer"
        extra_headers: dict[str, str] = {}
        meta: dict[str, Any] = {}
        credentials_enc = None

    from app.core.crypto import SecretBox, generate_master_key
    from app.providers import credentials

    box = SecretBox(generate_master_key())
    blob = box.encrypt("sk-stream", aad="provider:")

    class ProviderWithKey(FakeProvider):
        credentials_enc = blob
        slug = ""

    adapter = OpenAICompatibleAdapter("openai_compatible")
    original = credentials.get_secret_box
    try:
        credentials.get_secret_box = lambda settings=None: box  # type: ignore[assignment]
        chunks = [
            chunk
            async for chunk in adapter.stream_chat(
                ProviderWithKey(),
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
            )
        ]
    finally:
        credentials.get_secret_box = original  # type: ignore[assignment]

    assert [chunk.type for chunk in chunks] == ["text", "text", "usage", "done"]
    assert "".join(chunk.text or "" for chunk in chunks) == "سلام دنیا"
    assert chunks[2].tokens_in == 12
    assert chunks[2].tokens_out == 3


def test_anthropic_event_parser() -> None:
    from app.providers.adapters.anthropic_chat import _parse_event

    start = _parse_event({"type": "message_start", "message": {"usage": {"input_tokens": 21}}})
    text = _parse_event(
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "سلام"}}
    )
    tool = _parse_event(
        {
            "type": "content_block_start",
            "content_block": {"type": "tool_use", "id": "tu_1", "name": "office.excel"},
        }
    )
    end = _parse_event({"type": "message_delta", "usage": {"output_tokens": 7}})
    failure = _parse_event({"type": "error", "error": {"message": "boom"}})

    assert start[0].type == "usage" and start[0].tokens_in == 21
    assert text[0].type == "text" and text[0].text == "سلام"
    assert tool[0].type == "tool_call" and tool[0].tool_call["name"] == "office.excel"
    assert end[0].tokens_out == 7
    assert failure[0].type == "error"


def test_gemini_event_parser() -> None:
    from app.providers.adapters.gemini_chat import _parse_event

    chunks = _parse_event(
        {
            "candidates": [{"content": {"parts": [{"text": "پاسخ"}]}}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2},
        }
    )
    assert [chunk.type for chunk in chunks] == ["text", "usage"]
    assert chunks[0].text == "پاسخ"
    assert chunks[1].tokens_in == 5
    assert chunks[1].tokens_out == 2

    tool_chunks = _parse_event(
        {
            "candidates": [
                {"content": {"parts": [{"functionCall": {"name": "web.search", "args": {}}}]}}
            ]
        }
    )
    assert tool_chunks[0].type == "tool_call"
    assert tool_chunks[0].tool_call["name"] == "web.search"
