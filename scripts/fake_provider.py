"""A local fake OpenAI-compatible provider.

Lets you exercise the whole "dynamic provider" flow (add provider -> sync models
-> sync prices -> test -> probe) without any real API key or internet access.

Run:
    python scripts/fake_provider.py
    # then in the panel / API use base_url = http://127.0.0.1:8020/v1
"""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

app = FastAPI(title="Fake OpenAI-compatible provider")

MODELS = [
    {
        "id": "fake-whisper-stt",
        "owned_by": "fake",
        "pricing": {"prompt": "0.006", "completion": "0"},
    },
    {
        "id": "fake-tts-voice",
        "owned_by": "fake",
        "pricing": {"prompt": "0", "completion": "0.015"},
    },
    {
        "id": "fake-vision-vl",
        "owned_by": "fake",
        "context_length": 64000,
        "pricing": {"prompt": "0.000001", "completion": "0.000004"},
    },
    {
        "id": "fake-chat",
        "owned_by": "fake",
        "context_length": 32000,
        "pricing": {"prompt": "0.0000005", "completion": "0.0000015"},
    },
    {"id": "fake-embedding-3", "owned_by": "fake"},
]

ANSWER = "سلام! این پاسخ پروایدر آزمایشی است."


@app.get("/v1/models")
async def models() -> dict:
    return {"object": "list", "data": MODELS}


@app.post("/echo")
async def echo(request: Request) -> dict:
    """Endpoint used by the tool demo (declarative HTTP tool)."""
    body = await request.json()
    return {"ok": True, "result": {"id": "m-123", "echo": body.get("text", "")}}


@app.post("/v1/audio/transcriptions")
async def audio_transcriptions(request: Request) -> dict:
    """Fake speech-to-text: returns fixed text + a duration so cost can be checked."""
    form = await request.form()
    uploaded = form.get("file")
    size = 0
    if uploaded is not None and hasattr(uploaded, "read"):
        size = len(await uploaded.read())
    return {
        "text": ANSWER,
        "language": form.get("language") or "fa",
        "duration": 6.0,
        "bytes_received": size,
    }


@app.post("/v1/audio/speech")
async def audio_speech(request: Request) -> Response:
    """Fake text-to-speech: one second of silent WAV."""
    body = await request.json()
    fmt = str(body.get("response_format") or "mp3")
    mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/ogg"}.get(fmt, "audio/mpeg")
    payload = b"RIFF$\x00\x00\x00WAVEfmt " if fmt == "wav" else b"ID3\x03\x00\x00\x00fake"
    return Response(content=payload, media_type=mime)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> StreamingResponse:
    """Fake provider: answers, or calls the first offered tool once, then answers."""
    body = await request.json()
    messages = body.get("messages") or []
    tools = body.get("tools") or []
    used_tool = any(message.get("role") == "tool" for message in messages)

    if tools and not used_tool:
        function = (tools[0] or {}).get("function") or {}
        required = ((function.get("parameters") or {}).get("required")) or []
        arguments = json.dumps({key: "demo" for key in required}, ensure_ascii=False)
        return StreamingResponse(
            _tool_call_events(str(function.get("name") or ""), arguments),
            media_type="text/event-stream",
        )

    prompt_tokens = len(str(messages)) // 4 + 1
    return StreamingResponse(_text_events(prompt_tokens), media_type="text/event-stream")


async def _text_events(prompt_tokens: int):
    for word in ANSWER.split():
        payload = {"choices": [{"delta": {"content": f"{word} "}}]}
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.02)
    usage = {
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": len(ANSWER.split()),
        }
    }
    yield f"data: {json.dumps(usage)}\n\n"
    yield "data: [DONE]\n\n"


async def _tool_call_events(name: str, arguments: str):
    delta = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_fake_1",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ]
                }
            }
        ]
    }
    yield f"data: {json.dumps(delta, ensure_ascii=False)}\n\n"
    yield f'data: {json.dumps({"usage": {"prompt_tokens": 12, "completion_tokens": 6}})}\n\n'
    yield "data: [DONE]\n\n"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8020, log_level="warning")
