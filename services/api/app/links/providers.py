"""Which providers a customer can link, and what an agent may do with them.

The registry is *data*: adding a site means adding an entry here (plus a recipe
step list), not touching the run engine. Every tool becomes an ordinary
``tools`` row of ``kind='connector'``, so approvals, rate limits, audit and
cost accounting keep working unchanged.

Recipes drive the desktop app's browser profile through the fixed op set in
``app/tools/actions.py`` (``browser.goto`` / ``wait_for`` / ``click`` / ``type``
/ ``press`` / ``extract``). ``{{input.x}}`` is substituted by the connector
executor, exactly like an Excel action script.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LinkTool:
    name: str
    title_fa: str
    description_fa: str
    input_schema: dict[str, Any]
    steps: tuple[dict[str, Any], ...]
    risk_level: str = "high"
    approval_policy: str = "confirm"


@dataclass(frozen=True)
class LinkProvider:
    slug: str
    title_fa: str
    auth_kind: str
    site_url: str
    login_hint_fa: str
    login_check: dict[str, Any]
    tools: tuple[LinkTool, ...] = field(default_factory=tuple)
    rate_limit_per_hour: int = 10
    notes_fa: str = ""
    available: bool = True


_TEXT_INPUT = {
    "type": "object",
    "properties": {"text": {"type": "string", "description": "متن آمادهٔ انتشار"}},
    "required": ["text"],
}


def _facebook_post() -> LinkTool:
    return LinkTool(
        name="post",
        title_fa="انتشار پست در فیسبوک",
        description_fa="یک پست متنی در صفحهٔ خانهٔ فیسبوکِ کاربر منتشر می‌کند.",
        input_schema=_TEXT_INPUT,
        steps=(
            {"op": "browser.goto", "url": "https://www.facebook.com/"},
            {
                "op": "browser.wait_for",
                "selector": "[role='button']",
                "contains": "What's on your mind",
                "timeout": 30000,
            },
            {
                "op": "browser.click",
                "selector": "[role='button']",
                "contains": "What's on your mind",
            },
            {"op": "browser.wait_for", "selector": "div[role='dialog']", "timeout": 20000},
            {"op": "browser.click", "selector": "div[role='dialog'] div[contenteditable='true']"},
            {
                "op": "browser.type",
                "selector": "div[role='dialog'] div[contenteditable='true']",
                "text": "{{input.text}}",
            },
            {"op": "browser.wait", "ms": 1500},
            {"op": "browser.click", "selector": "div[role='dialog'] [aria-label='Post']"},
            {
                "op": "browser.wait_for",
                "selector": "div[role='dialog']",
                "gone": True,
                "timeout": 25000,
            },
            {"op": "screenshot"},
        ),
    )


def _facebook_notifications() -> LinkTool:
    return LinkTool(
        name="notifications",
        title_fa="خواندن اعلان‌های فیسبوک",
        description_fa="متن اعلان‌های تازهٔ صفحهٔ فیسبوک کاربر را برمی‌گرداند.",
        input_schema={"type": "object", "properties": {}},
        risk_level="low",
        approval_policy="auto",
        steps=(
            {"op": "browser.goto", "url": "https://www.facebook.com/notifications"},
            {"op": "browser.wait_for", "selector": "div[role='main']", "timeout": 30000},
            {"op": "browser.extract", "selector": "div[role='main']", "max_chars": 4000},
        ),
    )


def _telegram_send() -> LinkTool:
    return LinkTool(
        name="send",
        title_fa="ارسال پیام در تلگرام (وب)",
        description_fa="در تلگرام وب، به یک مخاطب یا کانال با شناسهٔ @username پیام می‌فرستد.",
        input_schema={
            "type": "object",
            "properties": {
                "chat": {"type": "string", "description": "شناسه مثل @username یا شماره"},
                "text": {"type": "string", "description": "متن پیام"},
            },
            "required": ["chat", "text"],
        },
        steps=(
            {"op": "browser.goto", "url": "https://web.telegram.org/k/#@{{input.chat}}"},
            {
                "op": "browser.wait_for",
                "selector": "div[contenteditable='true']",
                "timeout": 30000,
            },
            {"op": "browser.click", "selector": "div[contenteditable='true']"},
            {
                "op": "browser.type",
                "selector": "div[contenteditable='true']",
                "text": "{{input.text}}",
            },
            {"op": "browser.wait", "ms": 600},
            {"op": "browser.press", "key": "Enter"},
            {"op": "browser.wait", "ms": 1500},
            {"op": "screenshot"},
        ),
    )


def _telegram_read() -> LinkTool:
    return LinkTool(
        name="read",
        title_fa="خواندن پیام‌های تلگرام (وب)",
        description_fa="آخرین پیام‌های یک گفت‌وگو در تلگرام وب را برمی‌گرداند.",
        input_schema={
            "type": "object",
            "properties": {"chat": {"type": "string", "description": "شناسه مثل @username"}},
            "required": ["chat"],
        },
        risk_level="medium",
        approval_policy="auto",
        steps=(
            {"op": "browser.goto", "url": "https://web.telegram.org/k/#@{{input.chat}}"},
            {"op": "browser.wait_for", "selector": ".bubbles", "timeout": 30000},
            {"op": "browser.extract", "selector": ".bubbles", "max_chars": 4000},
        ),
    )


def _whatsapp_send() -> LinkTool:
    return LinkTool(
        name="send",
        title_fa="ارسال پیام در واتساپ (وب)",
        description_fa="در واتساپ وب، به شمارهٔ مقصد پیام می‌فرستد (کد کشور بدون +).",
        input_schema={
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "مثل 989121234567"},
                "text": {"type": "string", "description": "متن پیام"},
            },
            "required": ["phone", "text"],
        },
        steps=(
            {
                "op": "browser.goto",
                "url": "https://web.whatsapp.com/send?phone={{input.phone}}",
            },
            {
                "op": "browser.wait_for",
                "selector": "div[contenteditable='true']",
                "timeout": 45000,
            },
            {"op": "browser.click", "selector": "div[contenteditable='true']"},
            {
                "op": "browser.type",
                "selector": "div[contenteditable='true']",
                "text": "{{input.text}}",
            },
            {"op": "browser.wait", "ms": 600},
            {"op": "browser.press", "key": "Enter"},
            {"op": "browser.wait", "ms": 1500},
            {"op": "screenshot"},
        ),
    )

PROVIDERS: dict[str, LinkProvider] = {
    "facebook": LinkProvider(
        slug="facebook",
        title_fa="فیسبوک",
        auth_kind="browser",
        site_url="https://www.facebook.com/",
        login_hint_fa="در پنجره‌ای که باز می‌شود با حساب خودتان وارد شوید (رمز را ما نمی‌بینیم).",
        login_check={
            "url_not_contains": ["/login", "/checkpoint", "/recover"],
            "selector": "[role='navigation']",
        },
        tools=(_facebook_post(), _facebook_notifications()),
        rate_limit_per_hour=10,
        notes_fa=(
            "پست در پروفایل شخصی از طریق مرورگر انجام می‌شود؛ متا API آن را بسته است. "
            "برای صفحهٔ کسب‌وکار (Page) بعداً مسیر رسمی OAuth اضافه می‌شود."
        ),
    ),
    "telegram_web": LinkProvider(
        slug="telegram_web",
        title_fa="تلگرام (وب)",
        auth_kind="browser",
        site_url="https://web.telegram.org/k/",
        login_hint_fa="کد ورود تلگرام را در همان پنجره وارد کنید؛ نشست روی همین دستگاه می‌ماند.",
        login_check={
            "url_not_contains": ["/login"],
            "selector": ".chatlist, .chat-list, #column-left",
        },
        tools=(_telegram_send(), _telegram_read()),
        rate_limit_per_hour=20,
        notes_fa=(
            "نسخهٔ وب برای ارسال و خواندن پیام کافی است. نسخهٔ کامل (MTProto با شماره و کد) "
            "در فاز بعد اضافه می‌شود و به هیچ مرورگری نیاز ندارد."
        ),
    ),
    "whatsapp_web": LinkProvider(
        slug="whatsapp_web",
        title_fa="واتساپ (وب)",
        auth_kind="browser",
        site_url="https://web.whatsapp.com/",
        login_hint_fa="QR واتساپ را با گوشی خودتان اسکن کنید.",
        login_check={
            "url_not_contains": ["/qr"],
            "selector": "div[contenteditable='true'], #pane-side",
        },
        tools=(_whatsapp_send(),),
        rate_limit_per_hour=10,
        notes_fa="ارسال انبوه انجام نمی‌شود؛ هر پیام یک تأیید انسانی دارد.",
    ),
    "instagram": LinkProvider(
        slug="instagram",
        title_fa="اینستاگرام",
        auth_kind="browser",
        site_url="https://www.instagram.com/",
        login_hint_fa="در پنجرهٔ بازشده وارد شوید.",
        login_check={"url_not_contains": ["/accounts/login"], "selector": "main, nav"},
        tools=(),
        rate_limit_per_hour=5,
        notes_fa="انتشار در اینستاگرام وب در فاز بعد اضافه می‌شود.",
        available=False,
    ),
}


def get_provider(slug: str) -> LinkProvider | None:
    return PROVIDERS.get((slug or "").strip().lower())


def catalog() -> list[LinkProvider]:
    """Available providers first, then the ones announced for later."""
    return sorted(PROVIDERS.values(), key=lambda item: (not item.available, item.slug))

