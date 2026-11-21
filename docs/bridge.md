# پل مرورگر (Browser Bridge)

> هدف: ایجنت «به‌جای خودِ مشتری» در حساب‌های شخصی‌اش کار کند — بدون API key، بدون
> بازبینی اپ متا، و بدون اینکه رمز یا کوکی به سرور برسد.

## ۱) چرا این راه

| راه | فیسبوک پروفایل شخصی | تلگرام | مانع |
|---|---|---|---|
| OAuth رسمی | ❌ متا `publish_actions` را حذف کرده | بات، نه خودِ کاربر | بازبینی اپ |
| Session پروتکل (MTProto) | ندارد | ✅ | `api_id` + نگهداری نشست روی سرور |
| **پل مرورگر** | ✅ | ✅ (Telegram Web) | اپ باید باز باشد؛ UI عوض شود |

## ۲) اجزا

```
┌─────────── اپ کاروند (Electron) ───────────┐
│ پنجرهٔ هر سایت با partition پایدار        │  persist:kv-facebook
│   ↕ CDP/executeJavaScript                  │  persist:kv-telegram_web
│ bridge.cjs  (goto/wait_for/click/type/...) │
│ device.ts   (WebSocket کانکتور)            │
└───────────────┬────────────────────────────┘
                │ wss://…/v1/ws/connector?token=…
        ┌───────▼────────┐
        │ API کاروند      │  account_links + tools(kind=connector)
        └────────────────┘
```

- **نشست** (کوکی‌ها) در پروفایل کرومیوم روی دستگاه می‌ماند؛ سرور فقط دستور می‌فرستد.
- **ابزار ایجنت** یک ردیف معمولی `tools` با `kind='connector'` است؛ پس تأیید انسانی،
  سقف نرخ، حسابرسی و هزینه بدون تغییر کار می‌کنند.
- **کشف و مالکیت**: هر ابزار با `created_by = صاحب حساب` ساخته می‌شود و مشتری دیگر
  حتی آن را در کاتالوگ نمی‌بیند (`tool.not_found`).

## ۳) پروتکل دستگاه

| فریم | جهت | بدنه |
|---|---|---|
| `hello` | دستگاه → سرور | `{name, os, version, manifest:{ops:[…]}}` |
| `link.command` | سرور → دستگاه | `{action:"open"\|"probe"\|"wipe"\|"stop", provider, site_url, login_check}` |
| `link.result` | دستگاه → سرور | `{ok, logged_in, display_name, screenshot, error, step}` |
| `script.run` | سرور → دستگاه | `{tool, steps, timeout}` |
| `script.result` | دستگاه → سرور | `{ok, output:[…], artifacts:[png-base64]}` |
| `ping`/`pong` | هر دو | نگه‌داشتن اتصال |

`provider` از پیشوند اسلاگ ابزار استخراج می‌شود: `facebook.<link8>.post` → `facebook`.

## ۴) Recipe = داده

هر ابزار یک لیست گام است (همان opهای کانکتور):

```json
{"op": "browser.goto",     "url": "https://www.facebook.com/"}
{"op": "browser.wait_for", "selector": "[role='button']", "contains": "What's on your mind", "timeout": 30000}
{"op": "browser.click",    "selector": "[role='button']", "contains": "What's on your mind"}
{"op": "browser.wait_for", "selector": "div[role='dialog']", "gone": true}
{"op": "browser.type",     "selector": "div[role='dialog'] div[contenteditable='true']", "text": "{{input.text}}"}
{"op": "browser.press",    "key": "Enter"}
{"op": "screenshot"}
```

- `{{input.x}}` را `connector/executor.py` جای‌گذاری می‌کند (مثل اسکریپت اکسل).
- فیلدهای اختیاری: `contains` (تطبیق متن عنصر)، `gone` (انتظار برای ناپدید شدن)،
  `settle_ms`، `max_chars`، `timeout`.
- **سایت تازه = یک ورودی در `app/links/providers.py`** (بدون تغییر موتور اجرا).

## ۵) چرخهٔ «یک‌بار اجازه»

1. `POST /v1/links {provider}` → ردیف `pending` + فرمان `open` به دستگاه.
2. پنجرهٔ همان سایت **دیده می‌شود**؛ مشتری خودش لاگین/2FA را انجام می‌دهد.
3. `POST /v1/links/{id}/probe` → دستگاه `login_check` را اجرا می‌کند
   (`url_not_contains` + `selector` + `name_js`).
4. اگر لاگین بود: `status=active`، `display_name` ذخیره، ابزارها ساخته می‌شوند.
5. `POST /v1/links/{id}/stop` → توقف فوری؛ `DELETE` → پاک‌کردن کامل پروفایل.

## ۶) محدودیت‌ها (صادقانه)

| محدودیت | رفتار فعلی | مهار آینده |
|---|---|---|
| اپ باید باز باشد | خطای `link.device_offline` با پیام فارسی | سرویس پس‌زمینه/tray |
| UI سایت عوض شود | `wait_for` تایم‌اوت می‌دهد + اسکرین‌شات برای مشتری | health-check روزانه + به‌روزرسانی recipe |
| کپچا/چالش امنیتی | متوقف می‌شود؛ پنجره را مشتری حل می‌کند | — |
| خودکارسازی UI خلاف شرایط سایت است | پیش‌فرض: تأیید انسانی هر عمل، سقف ۱۰–۲۰ در ساعت | — |
| موبایل | فعلاً فقط دسکتاپ | WebView/Accessibility در فاز بعد |
