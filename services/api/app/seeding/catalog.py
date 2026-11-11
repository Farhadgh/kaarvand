"""Seed catalog: provider adapter kinds and capability inference rules.

This is *catalog* data, not business data: an operator can disable a row or add
new rows from the panel. No provider/model id is ever hardcoded in logic.
"""

from __future__ import annotations

from typing import Any

DECLARATIVE_SPEC: dict[str, Any] = {
    "chat": {
        "method": "POST",
        "url": "{{base_url}}/v1/chat/completions",
        "headers": {"Authorization": "Bearer {{api_key}}"},
        "body": {"model": "{{model}}", "messages": "{{messages}}", "stream": "{{stream}}"},
    },
    "response_map": {
        "text": "$.choices[0].message.content",
        "tool_calls": "$.choices[0].message.tool_calls",
        "usage_in": "$.usage.prompt_tokens",
        "usage_out": "$.usage.completion_tokens",
        "stream_delta": "$.choices[0].delta.content",
    },
    "models_url": "{{base_url}}/v1/models",
    "models_map": {"id": "$.data[*].id"},
}

PROVIDER_ADAPTERS: list[dict[str, Any]] = [
    {
        "kind": "openai",
        "title_fa": "OpenAI",
        "description_fa": "مدل‌های GPT از سرویس رسمی OpenAI",
    },
    {
        "kind": "openai_compatible",
        "title_fa": "سازگار با OpenAI",
        "description_fa": "هر سرویسی با endpoint سازگار: ریسلرهای ایرانی، Together، Groq و…",
    },
    {
        "kind": "openrouter",
        "title_fa": "OpenRouter",
        "description_fa": "دسترسی یکجا به مدل‌های چند سازنده",
    },
    {
        "kind": "anthropic",
        "title_fa": "Anthropic",
        "description_fa": "مدل‌های Claude",
    },
    {
        "kind": "gemini",
        "title_fa": "Google Gemini",
        "description_fa": "مدل‌های Gemini",
    },
    {
        "kind": "azure_openai",
        "title_fa": "Azure OpenAI",
        "description_fa": "استقرار سازمانی OpenAI روی Azure",
    },
    {
        "kind": "groq",
        "title_fa": "Groq",
        "description_fa": "استنتاج بسیار سریع",
    },
    {
        "kind": "deepseek",
        "title_fa": "DeepSeek",
        "description_fa": "مدل‌های DeepSeek",
    },
    {
        "kind": "mistral",
        "title_fa": "Mistral",
        "description_fa": "مدل‌های Mistral",
    },
    {
        "kind": "ollama",
        "title_fa": "Ollama (محلی)",
        "description_fa": "مدل‌های محلی روی سرور یا ماشین خودتان",
    },
    {
        "kind": "declarative",
        "title_fa": "آداپتور توصیفی (بدون کد)",
        "description_fa": "پروتکل دلخواه را با دو JSON توصیف کنید؛ کد لازم نیست",
        "spec_schema": DECLARATIVE_SPEC,
    },
]

CAPABILITY_RULES: list[dict[str, Any]] = [
    {
        "pattern": "vision|vl|4o|gemini|claude-3|pixtral|qwen-vl",
        "flags": {"supports_vision": True},
        "priority": 10,
    },
    {
        "pattern": "o1|o3|o4|r1|reason|thinking|deepseek-r",
        "flags": {"supports_reasoning": True},
        "priority": 20,
    },
    {
        "pattern": "whisper|transcrib|tts|audio|speech",
        "flags": {
            "supports_audio": True,
            "supports_tools": False,
            "supports_stream": False,
        },
        "priority": 30,
    },
    {
        "pattern": "embed|embedding",
        "flags": {"supports_tools": False, "supports_stream": False},
        "priority": 40,
    },
    {
        "pattern": ".",
        "flags": {"supports_tools": True, "supports_stream": True},
        "priority": 1000,
    },
]
