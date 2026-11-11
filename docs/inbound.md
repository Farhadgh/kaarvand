# کانال‌های ورودی (Inbound)

تا قدم ۹ ایجنت فقط «صدا زده می‌شد» (پنل، cron، API). از قدم ۱۰ می‌تواند **پیام دریافت کند**:
هر پیام واتساپ یا تلگرام یک **اجرا** با `trigger="webhook"` می‌سازد و اگر خواسته باشید، ایجنت
پاسخش را از همان ابزار برنامه به فرستنده برمی‌گرداند.

```
Telegram / WhatsApp ──POST وبهوک──► /v1/inbound/{provider}/{slug}
                                        │ ۱) بررسی امضا
                                        │ ۲) dedupe (رویداد تکراری = نادیده)
                                        │ ۳) runs(trigger="webhook")
                                        ▼
                                  همان موتور اجرا (بودجه، تأیید، هزینه)
                                        │
                                        └─ reply_mode=auto ─► ابزار پاسخ (telegram/واتساپ)
```

## ۱) ساخت کانال در پنل

`کانال‌های ورودی` (`/channels`) → «+ کانال جدید»:

| فیلد | توضیح |
|---|---|
| پیام‌رسان | تلگرام یا واتساپ (Cloud API) |
| ایجنت | ایجنتی که به پیام جواب می‌دهد |
| ابزار پاسخ | ابزار برنامه‌ی همان پیام‌رسان (از `/apps` نصب کرده‌اید) |
| حالت پاسخ | `بدون ارسال` (فقط اجرا) یا `ارسال خودکار` |
| Secret Token | تلگرام: همان `secret_token` در `setWebhook` — واتساپ: App Secret متا |
| Verify Token | فقط واتساپ: مقدار `hub.verify_token` برای تأیید اولیه |

پس از ساخت، کارت کانال آدرس وبهوک را نشان می‌دهد و دکمه‌ی کپی دارد.

## ۲) ثبت وبهوک در سمت پیام‌رسان

**تلگرام:**

```powershell
$token = "<توکن ربات>"
$secret = "<همان Secret Token که در پنل وارد کردید>"
$url = "https://<دامنه-عمومی>/v1/inbound/telegram/<slug>"
Invoke-RestMethod "https://api.telegram.org/bot$token/setWebhook" -Method Post `
  -Body @{ url = $url; secret_token = $secret }
```

**واتساپ (Meta → WhatsApp → Configuration → Webhook):**

- Callback URL: `https://<دامنه-عمومی>/v1/inbound/whatsapp/<slug>`
- Verify token: همان مقدار «Verify Token» در پنل
- Subscribe to: `messages`

> وبهوک باید روی **HTTPS عمومی** باشد. برای تست محلی از `ngrok http 8000` یا `cloudflared`
> استفاده کنید و آدرس عمومی را در پنل به‌جای `127.0.0.1` بگذارید (یا `API_BASE_URL` پنل را
> همان دامنه‌ی عمومی قرار دهید تا کارت کانال آدرس درست را نشان دهد).

## ۳) امنیت

| لایه | تلگرام | واتساپ |
|---|---|---|
| احراز وبهوک | هدر `X-Telegram-Bot-Api-Secret-Token` با مقایسه‌ی constant-time | `X-Hub-Signature-256` = HMAC-SHA256 کل بدنه با App Secret |
| تأیید اولیه | — | GET با `hub.mode=subscribe` + `hub.verify_token` |
| جلوگیری از تکرار | یکتا بودن `(channel_id, external_id)` روی `tg:<update_id>` | روی `wa:<message id>` |
| کلید | با AES-GCM و AAD `inbound:<slug>` رمز می‌شود؛ هرگز در پاسخ API برنمی‌گردد | همان |
| محدودیت‌ها | فقط پیام متنی پردازش می‌شود؛ بقیه ۲۰۰ + `ignored` | فقط `text`؛ بقیه نادیده |

هر رویداد در `inbound_events` ثبت می‌شود (وضعیت، اجرا، متن، فرستنده، نتیجه‌ی پاسخ) و در کارت
کانال با دکمه‌ی «رویدادها» دیده می‌شود.

## ۴) پاسخ خودکار و تأیید انسانی

- `reply_mode=auto`: اگر اجرا **موفق** تمام شود، پاسخ از ابزار انتخاب‌شده ارسال می‌شود
  (حداکثر ۳۵۰۰ کاراکتر) و در `tool_invocations` با `approved_by=null` و `run_id` همان اجرا
  ثبت می‌شود؛ اگر پیام‌رسان خطا بدهد (`ok=false` یا استثنا) وضعیت `failed`/`error:*` ذخیره
  می‌شود.
- ابزار پاسخ می‌تواند یک **ابزار HTTP سفارشی** هم باشد؛ فقط اگر `config.app_slug` داشته باشد
  و با نوع کانال نخواند، رد می‌شود.
- اگر اجرا در `waiting_approval` پارک شود (ابزاری نیاز به تأیید دارد)، **پاسخی ارسال نمی‌شود**؛
  در «اجراها» تأیید می‌کنید و پاسخ را دستی می‌فرستید.
- `reply_mode=off`: فقط اجرا و ثبت؛ برای ایجنت‌هایی که کار داخلی انجام می‌دهند و نباید به
  مشتری جواب بدهند.

## ۵) API

| متد | مسیر | نقش |
|---|---|---|
| POST | `/v1/inbound/telegram/{slug}` | عمومی (امضا) |
| GET | `/v1/inbound/whatsapp/{slug}` | عمومی (verify token) |
| POST | `/v1/inbound/whatsapp/{slug}` | عمومی (HMAC) |
| GET | `/v1/channels` | همه |
| POST | `/v1/channels` | owner/admin |
| PATCH | `/v1/channels/{id}` | owner/admin |
| DELETE | `/v1/channels/{id}` | owner/admin |
| GET | `/v1/channels/{id}/events` | همه |

پاسخ وبهوک همیشه `200` است با یکی از وضعیت‌ها: `accepted` · `duplicate` · `ignored` ·
`disabled` · `failed` — تا پیام‌رسان بی‌نهایت retry نکند. امضای غلط `401` می‌گیرد.

## ۷) تست بدون گوشی و ثبت خودکار وبهوک (قدم ۱۱)

**دکمهٔ «تست وبهوک»** در کارت کانال همان مسیر واقعی را اجرا می‌کند:

```jsonc
POST /v1/channels/{id}/test
{"text": "سلام", "chat_id": "test-chat"}          // همه اختیاری
→ {"ok": true, "status": "accepted", "run_id": "…", "run_status": "completed",
   "reply_status": "sent", "needs_approval": false, "text": "پاسخ ایجنت…"}
```

- امضا دور زده می‌شود چون فراخوان، ادمین احراز‌شده است؛ ولی **همان** `accept_message` و
  `execute_plan` اجرا می‌شوند (رویداد با `external_id` شروع‌شده با `test:` ثبت می‌شود).
- اگر ابزاری نیاز به تأیید داشته باشد: `run_status="waiting_approval"`، `needs_approval=true` و
  **پاسخی ارسال نمی‌شود** — پنل پیام مناسب نشان می‌دهد و لینک اجرا را می‌دهد.
- کانال غیرفعال → `409 inbound.channel_disabled`.

**دکمهٔ «ثبت وبهوک در تلگرام»**:

```jsonc
POST /v1/channels/{id}/register-webhook
→ {"ok": true, "url": "https://bot.example.com/v1/inbound/telegram/<slug>",
   "detail": "Webhook was set", "public_base_url": true}
```

- توکن از `tools.secret_enc` همان ابزار پاسخ رمزگشایی و فقط سمت سرور استفاده می‌شود.
- خطاها: `422 inbound.register_unsupported` (واتساپ)، `422 inbound.reply_tool_required`
  (ابزار وصل نیست)، `422 tool.secret_missing`.
- اگر `APP_PUBLIC_BASE_URL` ست نشده باشد، آدرس از درخواست ساخته می‌شود و
  `public_base_url=false` برمی‌گردد؛ تلگرام چنین آدرسی (`127.0.0.1`) را رد می‌کند، پس روی سرور
  این متغیر را ست کنید.

```powershell
# services/api/.env.local
APP_PUBLIC_BASE_URL=https://bot.example.com
```

## ۸) محدودیت‌های شناخته‌شده

1. پردازش **در پس‌زمینه‌ی همان پروسه** انجام می‌شود (`asyncio.create_task`)؛ با چند worker هم
   کار می‌کند چون هر درخواست کامل به یک worker می‌رسد، ولی اجرای طولانی بعد از ری‌استارت از
   دست می‌رود.
2. فقط **متن** پردازش می‌شود؛ عکس/فایل/ویس فعلاً نادیده گرفته می‌شوند.
3. حافظه‌ی گفتگو بین پیام‌های یک کاربر ساخته نمی‌شود (هر پیام یک اجرای مستقل است). پیوند دادن
   به `conversations` قدم بعدی است.
4. نرخ‌محدودی روی وبهوک نداریم؛ اگر لازم شد، در لبه (nginx/Cloudflare) یا با شمارنده‌ی
   Redis اضافه می‌شود.
5. اگر ایجنت مدل نداشته باشد، اجرا ناموفق ثبت می‌شود ولی رویداد و متن پیام از دست نمی‌رود.
