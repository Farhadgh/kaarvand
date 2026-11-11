"""Action script (connector) op catalog and validation.

The op *set* is fixed (the connector executes it); the *composition* is data, so
adding "append a row to Excel and screenshot it" needs no code.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import AppError

OPS: dict[str, dict[str, Any]] = {
    "office.open": {
        "title_fa": "باز کردن فایل آفیس",
        "required": ["app", "path"],
    },
    "office.cells": {
        "title_fa": "نوشتن در سلول‌های اکسل",
        "required": ["sheet"],
    },
    "office.save": {"title_fa": "ذخیره فایل آفیس", "required": []},
    "com.invoke": {
        "title_fa": "فراخوانی COM (نرم‌افزارهای ویندوزی)",
        "required": ["prog_id", "method"],
    },
    "shell.run": {"title_fa": "اجرای فرمان مجاز", "required": ["command"]},
    "fs.read": {"title_fa": "خواندن فایل", "required": ["path"]},
    "fs.write": {"title_fa": "نوشتن فایل", "required": ["path", "content"]},
    "fs.list": {"title_fa": "فهرست پوشه", "required": ["path"]},
    "http.request": {"title_fa": "درخواست HTTP از ماشین", "required": ["url"]},
    "browser.open": {"title_fa": "باز کردن آدرس در مرورگر", "required": ["url"]},
    "browser.click": {"title_fa": "کلیک روی عنصر صفحه", "required": ["selector"]},
    "browser.extract": {"title_fa": "استخراج متن از صفحه", "required": ["selector"]},
    "wait": {"title_fa": "توقف کوتاه", "required": []},
    "keyboard.type": {"title_fa": "تایپ متن", "required": ["text"]},
    "screenshot": {"title_fa": "گرفتن تصویر از صفحه", "required": []},
    "print": {"title_fa": "ارسال به چاپگر", "required": []},
    "phone.dial": {"title_fa": "برقراری تماس", "required": ["number"]},
    # --- driving an installed application (desktop apps / app catalog) --------
    "app.launch": {"title_fa": "اجرای برنامه", "required": ["app"]},
    "app.focus": {"title_fa": "آوردن پنجره‌ی برنامه به جلو", "required": ["app"]},
    "app.windows": {"title_fa": "فهرست پنجره‌های باز", "required": []},
    "ui.invoke": {"title_fa": "فراخوانی عنصر رابط کاربری", "required": ["name"]},
    "clipboard.set": {"title_fa": "نوشتن در کلیپ‌بورد", "required": ["text"]},
    "clipboard.get": {"title_fa": "خواندن کلیپ‌بورد", "required": []},
    "keyboard.hotkey": {"title_fa": "فشار کلید ترکیبی", "required": ["keys"]},
}

MAX_STEPS = 40


def validate_actions(actions: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not actions:
        return []
    if not isinstance(actions, list):
        raise AppError(code="tool.invalid_actions", status_code=422, params={"reason": "not_list"})
    if len(actions) > MAX_STEPS:
        raise AppError(
            code="tool.invalid_actions",
            status_code=422,
            params={"reason": "too_many_steps", "max": MAX_STEPS},
        )

    for index, step in enumerate(actions):
        if not isinstance(step, dict) or not step.get("op"):
            raise AppError(
                code="tool.invalid_actions",
                status_code=422,
                params={"reason": "missing_op", "step": index},
            )
        spec = OPS.get(str(step["op"]))
        if spec is None:
            raise AppError(
                code="tool.invalid_actions",
                status_code=422,
                params={"reason": "unknown_op", "op": step["op"], "step": index},
            )
        for field in spec["required"]:
            if field not in step:
                raise AppError(
                    code="tool.invalid_actions",
                    status_code=422,
                    params={"reason": "missing_field", "field": field, "step": index},
                )
    return actions


def catalog() -> list[dict[str, Any]]:
    return [
        {"op": op, "title_fa": spec["title_fa"], "required": spec["required"]}
        for op, spec in OPS.items()
    ]
