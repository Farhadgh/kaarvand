"""Seed examples for the tool registry (global, editable but read-only for tenants)."""

from __future__ import annotations

from typing import Any

SEED_TOOLS: list[dict[str, Any]] = [
    {
        "slug": "system.now_jalali",
        "name_fa": "تاریخ و ساعت جاری (جلالی)",
        "description_fa": "تاریخ و ساعت جاری را به تقویم جلالی و منطقه‌ی زمانی برمی‌گرداند.",
        "kind": "builtin",
        "category": "general",
        "risk_level": "low",
        "approval_policy": "auto",
        "is_enabled": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "منطقه‌ی زمانی، پیش‌فرض Asia/Tehran",
                }
            },
        },
        "output_schema": {"type": "object", "properties": {"jalali": {"type": "string"}}},
        "config": {},
        "actions": [],
    },
    {
        "slug": "telegram.send_message",
        "name_fa": "ارسال پیام تلگرام",
        "description_fa": "ارسال پیام متنی به یک چت تلگرام از طریق Bot API.",
        "kind": "http",
        "category": "social",
        "risk_level": "medium",
        "approval_policy": "confirm",
        "is_enabled": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "description": "شناسه‌ی چت مقصد"},
                "text": {"type": "string", "description": "متن پیام"},
            },
            "required": ["chat_id", "text"],
        },
        "output_schema": {},
        # token is stored encrypted in tools.secret_enc (auth.type=bearer not used here)
        "config": {
            "method": "POST",
            "url": "https://api.telegram.org/bot{{secret}}/sendMessage",
            "allowed_domains": ["api.telegram.org"],
            "headers": {"Content-Type": "application/json"},
            "body": {"chat_id": "{{chat_id}}", "text": "{{text}}"},
            "response_map": {"message_id": "$.result.message_id", "ok": "$.ok"},
            "auth": {"type": "none"},
            "timeout": 20,
        },
        "actions": [],
    },
    {
        "slug": "office.excel.append_row",
        "name_fa": "افزودن ردیف به اکسل",
        "description_fa": "یک ردیف به انتهای شیت اکسل روی ماشین کاربر اضافه می‌کند.",
        "kind": "connector",
        "category": "office",
        "risk_level": "medium",
        "approval_policy": "confirm",
        "is_enabled": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "مسیر فایل اکسل"},
                "sheet": {"type": "string", "description": "نام شیت"},
                "values": {"type": "array", "items": {}, "description": "مقادیر ردیف"},
            },
            "required": ["file", "sheet", "values"],
        },
        "output_schema": {},
        "config": {},
        "actions": [
            {"op": "office.open", "app": "excel", "path": "{{input.file}}"},
            {"op": "office.cells", "sheet": "{{input.sheet}}", "append": "{{input.values}}"},
            {"op": "office.save"},
            {"op": "screenshot", "save_as": "artifacts/{{run_id}}.png"},
        ],
    },
]
