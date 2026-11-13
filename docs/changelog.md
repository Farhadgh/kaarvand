# تغییرات (Changelog)

هر قدم با «شاهد» ثبت شده است؛ یعنی چیزی که واقعاً اجرا شده، نه ادعا.

## کاتالوگ مشتری: مدل با قیمت تومانی، بدون افشای پروایدر ✔

**مسئله:** `GET /v1/models` برای هر کاربر واردشده باز بود و شناسه/نام پروایدر، `base_url`،
قیمت دلاری و `markup` را برمی‌گرداند؛ یعنی مشتری می‌توانست هزینهٔ تمام‌شدهٔ ما را ببیند.
ضمناً حاشیهٔ سود ۳۰٪ در تنظیمات وجود داشت ولی هیچ‌جا اعمال نمی‌شد.

**نتیجه:** مشتری فقط `/v1/catalog/models` را می‌بیند: نام فارسی، قابلیت‌ها و قیمت
**تومان برای هر ۱ میلیون توکن**. `/v1/models` کاملاً ادمین شد و حاشیهٔ سود پیش‌فرض
۳۰٪ حالا هم در صورتحساب و هم در قیمت نمایشی اعمال می‌شود.

| فایل | تغییر |
|---|---|
| `billing/pricing.py` (جدید) | `effective_markup_percent` (markup مدل، وگرنه ۳۰٪ پیش‌فرض)، `toman_for` و `retail_prices` — یک منبع واحد برای قیمت فروش |
| `billing/cost.py` · `runtime/engine.py` · `audio/service.py` | صورتحساب از همان `effective_markup_percent` استفاده می‌کند (قیمت نمایشی = قیمت کسرشده) |
| `api/v1/catalog.py` (جدید) | `GET /v1/catalog/models` و `/v1/catalog/models/{id}`؛ فیلتر capability/modality/family/q؛ فقط مدل و پروایدر فعال |
| `schemas/catalog.py` (جدید) | پاسخ بدون `provider_id`، `base_url`، قیمت دلاری، `price_source`، `markup_percent` |
| `api/v1/models.py` | `GET /models`، `GET /models/{id}` و `GET /models/{id}/prices` به `require_admin` تغییر کرد (رفع افشا) |
| `schemas/runs.py` · `api/v1/runs.py` | `cost_usd` (هزینهٔ دلاری ما) برای مشتری `null` می‌شود؛ ادمین همان عدد را می‌بیند |
| `apps/client/src/pages/Models.tsx` (جدید) | کاتالوگ: جست‌وجو، فیلتر قابلیت، کارت مدل با قیمت تومانی و نشان «فارسی» |
| `apps/client/src/{App.tsx,lib/api.ts,lib/money.ts}` | مسیر `/models`، تایپ `CatalogModel`، `api.catalog`، `formatTomanValue` |
| `tests/test_catalog.py` (جدید) | ۸ تست: افشانشدن پروایدر/دلار، ریاضی تومان، اولویت markup، پنهان‌بودن مدل/پروایدر غیرفعال، فیلترها، ۴۰۱/۴۰۳ |

**شاهد:** `pytest tests/test_catalog.py` سبز (۸ تست) · کل مجموعه **۲۹۴ passed** ·
`ruff check app tests` پاک · `npm run build` در `apps/client` و `apps/web` سبز.

**شاهد زنده (سرور تولید، بعد از `reset --hard 59d7062` + مایگریشن ۰۰۱۴/۰۰۱۵):**

```
POST /v1/auth/otp/request   → {"sent":true,…}            (شمارهٔ واقعی، حساب user + کیف پول ساخته شد)
GET  /v1/catalog/models     → [{"name":"AionLabs: Aion-2.0",…,"price_input_toman":270400,
                                "price_output_toman":540800,"price_known":true}, …]
grep provider_id|base_url|input_price|price_source → 0 مورد
GET  /v1/models (مشتری)     → 403
GET  /v1/wallet             → {"balance_irr":0,"usd_irr":2600000,"markup_percent":30,
                                "min_topup_toman":10000,"topup_enabled":false}
```

عدد ۲۷۰٬۴۰۰ همان ۰٫۸ دلار × ۲٫۶ میلیون تومان × ۱٫۳ ÷ ۱۰ است؛ یعنی قیمت نمایشی و
صورتحساب از یک فرمول می‌آیند. `topup_enabled:false` طبیعی است چون در prod هنوز
`APP_PAYMENT_GATEWAY=noop` است (منتظر `APP_ZARINPAL_MERCHANT_ID`).

## شارژ کیف پول با زرین‌پال + حسابداری ادمین ✔

**مسئله:** فاز ۱ کیف پول داشت ولی هیچ راهی برای پر کردنش نبود؛ `PaymentGateway` فقط یک
پورت با `noop` بود. مشتری نمی‌توانست پول بریزد و ادمین هیچ گزارشی از درآمد نداشت.

**نتیجه:** مشتری مبلغ را به تومان انتخاب می‌کند، به درگاه زرین‌پال می‌رود، برمی‌گردد و کیف پولش
(در صورت تأیید) یک‌بار شارژ می‌شود. ادمین در پنل «پرداخت‌ها» درآمد تسویه‌شده، پرداخت‌های
در انتظار و ناموفق را می‌بیند.

| فایل | تغییر |
|---|---|
| `alembic/versions/0015_payments.py` (جدید) | جدول `payments` (authority یکتا با gateway، مبلغ ریالی، status، reference، `meta`، `paid_at`) + RLS |
| `db/models/billing.py` | مدل `Payment` (سند وضعیت‌ها و قاعدهٔ «یک‌بار شارژ») |
| `billing/zarinpal.py` (جدید) | آداپتور REST v4: `request.json` → `StartPay/{authority}` → `verify.json`؛ کد `100`/`101` = پرداخت‌شده، `sandbox` با یک فلگ |
| `billing/registry.py` | `GATEWAYS = {noop, zarinpal}` و پاس‌دادن `Settings` به آداپتور |
| `billing/topup.py` (جدید) | `start_topup` (حداقل مبلغ، ساخت ردیف pending، دریافت `redirect_url`) و `apply_callback` (قفل ردیف، تأیید، شارژ یک‌بار، `return_url`) |
| `api/v1/wallet.py` | `POST /v1/wallet/topup` · `GET /v1/wallet/payments` · `GET /v1/wallet/topup/callback` (عمومی، ۳۰۳ به deep link)؛ `GET /v1/wallet` حالا `min_topup_*` و `topup_enabled` هم می‌دهد |
| `api/v1/payments.py` (جدید) | `GET /v1/payments` (فیلتر status/user_id + نام و موبایل) · `GET /v1/payments/summary` (درآمد، امروز، در انتظار، ناموفق) — فقط ادمین |
| `core/config.py` · `.env.example` | `APP_ZARINPAL_*`، `APP_PAYMENT_CALLBACK_URL`، `APP_PAYMENT_RETURN_URL`، `APP_PAYMENT_TIMEOUT_SECONDS` |
| `apps/client/src/pages/Wallet.tsx` (جدید) | انتخاب مبلغ (۵۰/۱۰۰/۲۰۰/۵۰۰ هزار تومان یا دستی)، دکمهٔ پرداخت، پیام بازگشت، فهرست پرداخت‌ها |
| `apps/client/src/lib/desktop.ts` (جدید) | پل Electron: `openExternal`، `onDeepLink`، `parseDeepLink` (در مرورگر به رفتار وب برمی‌گردد) |
| `apps/client/src/App.tsx` | مسیر `/wallet` واقعی شد + `DeepLinkBridge` برای `kaarvand://wallet?status=…` |
| `apps/web/app/(panel)/payments/page.tsx` (جدید) | صفحهٔ حسابداری: چهار کارت آماری، فیلتر وضعیت، بازهٔ ۷/۳۰/۹۰ روز، جدول پرداخت‌ها |
| `apps/web/lib/{types,copy}.ts` · `components/{shell,ui}.tsx` | تایپ `Payment`/`PaymentSummary`، برچسب‌های `paid`/`canceled`، آیتم منو، رنگ Badge |
| `tests/test_topup.py` (جدید) | ۱۳ تست: شارژ یک‌باره، تکرار callback، لغو، تأیید ناموفق، حداقل مبلغ، جداسازی کاربران، دسترسی ادمین، پارس آداپتور زرین‌پال (بدون شبکه) |

**شاهد:** `pytest tests/test_topup.py` → **۱۳ passed** · `ruff check app tests` → پاک ·
`npm run build` در `apps/client` و `next build` در `apps/web` سبز.

## ورود با موبایل (OTP) + کیف پول هر کاربر + نقش‌های تازه ✔

**مسئله:** ورود مشتری با ایمیل/رمز برای محصولی که مخاطبش کاربر عادی ایرانی است مناسب نبود، و
کیف پول به کل سازمان تعلق داشت نه به شخص. نقش‌ها هم پنج‌تا بودند (`owner/admin/operator/editor/viewer`)
که با مدل «ادمین پلتفرم در برابر مشتری» نمی‌خواند.

**نتیجه:** مشتری فقط شماره موبایل وارد می‌کند، کد پیامکی می‌گیرد و وارد می‌شود؛ در همان لحظه
حساب و کیف پول تومانی‌اش ساخته می‌شود. ادمین پلتفرم همان ورود ایمیل/رمز قبلی را دارد.

| فایل | تغییر |
|---|---|
| `alembic/versions/0014_otp_and_user_wallets.py` (جدید) | `users.email`/`password_hash` nullable + `is_phone_verified` + ایندکس یکتای جزئی روی موبایل؛ `wallets.user_id` جای `uq_wallets_org_id`؛ جدول `otp_codes`؛ `login_attempts.phone`؛ تبدیل نقش‌ها (`owner→admin`، بقیه→`user`) |
| `db/models/core.py` · `billing.py` · `auth.py` | مدل‌های به‌روز + `OtpCode` + `User.has_password`/`is_admin` |
| `auth/otp.py` (جدید) | تولید کد، هش HMAC-SHA256، انقضای ۱۲۰ ثانیه، سقف ۵ تلاش، کول‌داون ۶۰ ثانیه، سهمیهٔ روزانه موبایل/آی‌پی؛ شمارندهٔ تلاش در تراکنش جدا commit می‌شود |
| `auth/accounts.py` (جدید) | `resolve_org`، `find_or_create_by_phone` (ساخت کیف پول در اولین ورود) |
| `auth/sessions.py` (جدید) | `issue_tokens`، `record_login_attempt`، `digest` — مشترک بین ورود رمزی و OTP |
| `notifications/sms.py` (جدید) | فراز اس‌ام‌اس: حالت «الگو» و «متن ساده»؛ بدون کلید/غیرفعال → فقط لاگ (قابل تست) |
| `api/v1/otp.py` (جدید) | `POST /v1/auth/otp/request` · `POST /v1/auth/otp/verify` (پاسخ: جفت توکن + `is_new_user`) |
| `api/v1/wallet.py` (جدید) | `GET /v1/wallet` (ریال + تومان + نرخ دلار + درصد سود) · `GET /v1/wallet/transactions` |
| `billing/wallet.py` (جدید) | `get_or_create_wallet`، `credit`/`debit` با ثبت `wallet_transactions`، خطای `wallet.insufficient_balance` |
| `core/deps.py` | `require_admin` / `require_member` / `owns_or_admin` — فقط دو نقش |
| `api/v1/*` | درها باز شد برای مشتری (ایجنت، ابزار، اپ، کانال، اجرا) و بسته شد برای داده‌های پلتفرم (پروایدرها، `provider-adapters`، مدل‌ها، تنظیمات، کاربران) |
| `apps/web` | `Role = "admin" \| "user"`، برچسب‌های نقش، منوی پنل، فرم ساخت کاربر |
| `apps/client` (جدید) | اپ React+Vite با ورود OTP، کیف پول، پوستهٔ Electron و Capacitor |
| `.github/workflows/android.yml` · `desktop.yml` (جدید) | ساخت APK و نصب‌کنندهٔ ویندوز روی رانرهای گیت‌هاب (بدون نصب ابزار روی سیستم توسعه) |

**شاهد:** `pytest` → **۲۷۲ تست سبز** (۲۷ تست در `test_otp.py`/`test_users_api.py`/`test_auth.py`)،
`ruff` پاک، `alembic upgrade head` روی دیتابیس محلی (`revision: 0014`)، و `tsc --noEmit` پنل وب بدون خطا.

## مدل‌های صوتی: خطای شفاف، voice واقعی، پشتیبانی pcm و برچسب «فارسی» ✔

**مسئله:** در `/audio` برای بعضی مدل‌ها فقط «خطای نامشخص رخ داد.» دیده می‌شد. ریشه سه‌لایه بود:

1. `google/gemini-3.8-flash-tts` فقط `response_format="pcm"` می‌پذیرد؛ پنل `mp3` می‌فرستاد →
   `400` از OpenRouter.
2. آداپتور هر ۴xx را به `provider.http_400` تبدیل می‌کرد و آن کد در `errors-fa.ts` نبود →
   fallback «خطای نامشخص».
3. voice پیش‌فرض `alloy` برای همهٔ مدل‌ها فرستاده می‌شد، در حالی که ElevenLabs/MiniMax صداهای
   خودشان را می‌خواهند و کاتالوگ `supported_voices` را می‌دهد که ذخیره نمی‌شد.

**نتیجه:** فقط چند مدل TTS فارسی را روان می‌خوانند؛ حالا همان‌ها با برچسب «فارسی ✓» مشخص‌اند.

| فایل | تغییر |
|---|---|
| `providers/adapters/openai_chat.py` + `chat_common.py` | `provider.rejected` / `rate_limited` / `auth_failed` / `call_failed` به‌جای `provider.http_400` (برای صدا **و** چت)، لاگ `logger.warning` با متن پاک‌شدهٔ پروایدر، تلاش دوبارهٔ خودکار با فرمت خواسته‌شده |
| `providers/adapters/audio_pcm.py` (جدید) | بسته‌بندی PCM خام در WAV با نرخ/کانال از `content-type` |
| `providers/adapters/litellm_endpoints.py` + `litellm_catalog.py` | ذخیرهٔ `supported_voices` در `models.meta.voices` |
| `audio/service.py` | voice نامعتبر → اولین voice مجاز مدل؛ گزارش `format`/`voice` واقعی در پاسخ |
| `audio/languages.py` (جدید) | جدول سنجیدهٔ پشتیبانی فارسی (`PERSIAN_TTS`/`PERSIAN_STT`) + `persian_of()` با اولویت override دستی |
| `api/v1/audio.py` | فیلتر `?persian=`، مرتب‌سازی فارسی‌ها در ابتدا، `pcm` در قالب‌ها، هدرهای `X-Audio-Format`/`X-Audio-Voice` |
| `api/v1/models.py` + `schemas/*` | فیلد `persian` در کاتالوگ و امکان override با `PATCH /v1/models/{id}` |
| `seeding/audio_presets.py` | ۲۳ مدل آماده با برچسب فارسی (۶ مدل فارسی‌روان جدید: grok، voxtral tts، fish drama، minimax turbo، eleven-flash-v2.5…) |
| `scripts/fa_audio_probe.py` (جدید) | سنجش بازتولیدپذیر «TTS → رونویسی → امتیاز» برای TTS و STT |
| `apps/web` | بج «فارسی ✓/~ /ضعیف/✗» در `/audio` و `/models`، تیک «فقط مدل‌های فارسی»، هشدار `pcm`، نمایش کد در خطاهای ناشناخته |

**شاهد سنجش (۳۹ مدل TTS + ۳۱ مدل STT):** ۱۲ مدل `verified` (امتیاز ۰٫۹۸: eleven-v3/v4،
gemini-flash-tts، minimax، voxtral-mini-tts-3، grok-voice، fish drama-3)، ۴ مدل `good`، ۱۰ مدل
`weak` و ۱۰ مدل `none` (از جمله `kokoro-82m` با امتیاز ۰٫۰۰ و `aura-2` با ۰٫۱۴). همهٔ ۳۱ مدل STT
امتیاز ۰٫۹۸ گرفتند.

**شاهد زنده (روی `https://kaarvand.amigok.cloud` پس از دیپلوی):**

| بررسی | نتیجه |
|---|---|
| `GET /v1/audio/meta` | `formats = [mp3, wav, opus, aac, flac, pcm]` + `persian_levels` |
| `GET /v1/audio/models` | ۷۱ مدل، فارسی‌بلدها اول؛ ۴۴ مدل `verified` (۳۲ STT + ۱۲ TTS) |
| `GET /v1/models?limit=500` | ۶۸ از ۷۱ مدل صوتی فیلد `persian` دارند |
| `POST /v1/audio/speech` روی `google/gemini-3.8-flash-tts` (همان مدلی که خطا می‌داد) | **۲۰۰** · `audio/wav` · `RIFF` · `X-Audio-Format=wav` · voice خودکار `alloy→Zephyr` |
| `POST /v1/audio/speech` روی `elevenlabs/eleven-v3` | **۲۰۰** · mp3 · voice خودکار `alloy→george` |
| `POST /v1/audio/speech` روی `hexgrad/kokoro-82m` | **۲۰۰** · mp3 · voice خودکار `alloy→af_alloy` |
| voice نامعتبر (پیش از اصلاح) | `provider.rejected` + متن «Unknown voice "alloy"» (نه «خطای نامشخص») |
| `POST /v1/providers/{id}/sync-models` | `updated=502` (حالا `meta.voices` هم ذخیره می‌شود) |
| HTML صفحهٔ `/models` | ۴۴ بج «فارسی ✓» و ۱۰ بج «فارسی ✗» |
| HTML صفحهٔ `/audio` | راهنمای «آزمایش‌شده» + ۴۸ تیک ✓ در فهرست مدل‌ها |
| تست‌ها | `pytest tests/test_audio.py` → **۲۲ passed** · `pytest tests` → **۲۶۱ passed** · `ruff check` → clean · `tsc --noEmit` → exit 0 |



**مسئله:** در OpenRouter با فیلتر `input_modalities=audio` ده‌ها مدل صوتی دیده می‌شد ولی
کاروند فقط ۱ مدل صوتی نشان می‌داد. علت سه‌لایه بود:

1. کاتالوگ، نوع مدل را از **قیمت** (`audio_input_price`/`audio_output_price`) و پرچم
   `supports_audio` می‌گرفت؛ سینک هیچ‌کدام را ست نمی‌کرد.
2. OpenRouter در فهرست پیش‌فرض `/api/v1/models` برای مدل‌های گفتاری `architecture` را `null`
   می‌دهد؛ فقط `?output_modalities=transcription|speech` آن‌ها را با معماری و قیمت برمی‌گرداند.
3. آداپتور، `openrouter` را پروایدر صوتی نمی‌شناخت و رونویسی multipart می‌فرستاد (OpenRouter
   JSON + base64 می‌خواهد).

| فایل | تغییر |
|---|---|
| `providers/adapters/litellm_endpoints.py` | `audio_kind` از `architecture.output_modalities` (transcription→stt، speech→tts) |
| `providers/adapters/litellm_catalog.py` | خواندن دو فهرست فیلترشده برای openrouter و ادغام آن‌ها؛ تبدیل قیمت «بر ثانیه»→«بر دقیقه» (×۶۰) و «بر نویسه»→«بر ۱۰۰۰ نویسه» (×۱۰۰۰) |
| `providers/sync.py` | `supports_audio=True` برای مدل‌های صوتی/چندرسانه‌ای، خاموش‌کردن `supports_tools/stream` برای مدل‌های اختصاصی گفتار، نوشتن قیمت صوتی در `models` و `price_history` |
| `api/v1/models.py` + `schemas/providers.py` | فیلد جدید `audio_chat` (مدل چت با ورودی صوتی، بدون endpoint گفتار) |
| `providers/adapters/openai_chat.py` | `openrouter` در `AUDIO_KINDS` + رونویسی JSON/base64 |
| `seeding/audio_presets.py` | ۱۲ مدل آمادهٔ OpenRouter (ویسپر، nova-3، scribe-v2، eleven-v3، aura-2، kokoro…) |
| `apps/web` (صفحهٔ مدل‌ها) | نشان «صوتی (چت)» جدا از «گفتار→متن»/«متن→گفتار»؛ قیمت و «آزمایش صدا» فقط برای مدل‌های اختصاصی گفتار |

**شاهد زنده (روی همین سرویس):**

| بررسی | نتیجه |
|---|---|
| `POST /v1/providers/{id}/sync-models` (openrouter) | `created=70` · `updated=432` · `total=502` |
| `POST /v1/providers/{id}/sync-prices` | `updated=73` |
| `GET /v1/models?capability=audio` | **۱۱۹** مدل: `stt=32`, `tts=39`, `audio_chat=48` (قبلاً ۱) |
| `GET /v1/audio/models` | `71` مدل قابل استفاده در `/audio` (۳۲ STT + ۳۹ TTS) |
| `GET /v1/audio/presets` | `18` مدل آماده (۹ STT + ۹ TTS) |
| نمونهٔ قیمت | `deepgram/nova-3` = `0.0043 $/دقیقه` · `elevenlabs/eleven-v3` = `0.08 $/۱۰۰۰ نویسه` |
| HTML صفحهٔ `/models` | ۳۲ نشان «گفتار→متن» · ۳۹ نشان «متن→گفتار» · ۴۸ نشان «صوتی (چت)» |
| تست‌ها | `pytest tests/test_providers_sync.py tests/test_audio.py` → **۲۱ passed** |

## رفع باگ — حلقهٔ ریدایرکت نشست (`/` ↔ `/login`) ✔

**نشانه:** پنل با مرورگری که قبلاً لاگین شده بود باز نمی‌شد (صفحهٔ سفید یا
`ERR_TOO_MANY_REDIRECTS`) ولی مرورگر تازه/ناشناس درست کار می‌کرد. لاگ nginx:
۸۵ × `GET /` با `307` و ۸۲ × `GET /login` با `307`.

**علت:** عمر کوکی `ob_access` ۶۰ دقیقه بود ولی عمر توکن access فقط ۱۵ دقیقه
(`access_token_ttl_min`)، و هیچ مسیر تازه‌سازی وجود نداشت. نتیجه: `middleware`
وجود کوکی را «لاگین» می‌دید و `/login` را به `/` می‌فرستاد، ولی layout پنل از
`/auth/me` پاسخ `401` می‌گرفت و به `/login` برمی‌گشت → حلقه، تا ۷ روز (عمر کوکی
refresh).

| فایل | تغییر |
|---|---|
| `apps/web/middleware.ts` | کوکی access نیست ولی refresh هست → `/api/auth/refresh`؛ `/login` فقط با کوکی access و بدون `?next` به `/` می‌پرد |
| `apps/web/app/api/auth/refresh/route.ts` | **جدید** — تازه‌سازی بی‌صدا با `POST /v1/auth/refresh` و ست‌کردن کوکی‌ها روی همان `307` (Location نسبی، مستقل از دامنه/پروکسی) |
| `apps/web/app/api/auth/expired/route.ts` | **جدید** — پاک‌کردن هر دو کوکی و رفتن به `/login?next=…` |
| `apps/web/app/(panel)/layout.tsx` | `401` → `/api/auth/expired`؛ خطای شبکه → کارت «ارتباط با سرور برقرار نشد» بدون ریدایرکت (حلقه ممکن نیست) |
| `apps/web/app/api/auth/login/route.ts` | `maxAge` کوکی access از `expires_in` پاسخ API (۹۰۰−۶۰ = ۸۴۰ ثانیه) به‌جای ۳۶۰۰ ثابت |
| `apps/web/lib/api-config.ts` | `accessMaxAge()` و `safeNextPath()` (جلوگیری از open-redirect در `?next`) |

**شاهد زنده (روی `https://kaarvand.amigok.cloud`، بعد از دیپلوی):**

| بررسی | نتیجه |
|---|---|
| `GET /` با کوکی کهنهٔ `ob_refresh` | `307 → /api/auth/refresh?next=%2F` (یک گام، نه حلقه) |
| `GET /api/auth/refresh` با refresh نامعتبر | `307 → /login?next=%2F` + پاک‌شدن هر دو کوکی |
| `GET /login` بدون کوکی | `200` |
| `GET /models` با کوکی access کهنه | `307 → /api/auth/expired` → `307 → /login?next=%2Fmodels` |
| `GET /api/auth/refresh` با نشست معتبر | `307 → /models` + دو کوکی تازه؛ سپس `/models` = `200` |
| `/models` با نشست معتبر | `200` · نشان «صوتی · گفتار→متن» · کلید میان‌بر «صوتی:» · لینک «آزمایش صدا» |

## قدم ۱۴ — مدل‌های صوتی (STT + TTS) ✔

**انجام شد:** تبدیل گفتار به متن و متن به گفتار، با همان زیرساخت پروایدر/قیمت/دفتر مصرف.

| فایل | تغییر |
|---|---|
| `db/models/llm_models.py` | `audio_input_price` (دلار/دقیقه، STT) و `audio_output_price` (دلار/۱۰۰۰ نویسه، TTS) روی `models` و `price_history` |
| `db/models/usage.py` | `audio_seconds` و `audio_chars` روی `usage_ledger` |
| `alembic/versions/0013_audio.py` | مایگریشن `0012 → 0013` |
| `billing/cost.py` | `compute_audio_cost` و `price_audio_usage` (گرد کردن در مرز، مثل توکن) |
| `providers/adapters/openai_chat.py` | `transcribe()` (multipart) و `speech()` (JSON) برای `openai`, `openai_compatible`, `groq`, `together`, `azure_openai` |
| `audio/service.py` | تفکیک STT/TTS، سقف حجم/طول، بودجه، ثبت در ledger |
| `audio/presets.py` | ۶ مدل آماده با قیمت رسمی (whisper-1، gpt-4o-transcribe، tts-1، …) |
| `api/v1/audio.py` | ۶ مسیر: `meta`, `presets`, `models`, `transcriptions`, `speech`, `speech/estimate` |
| `api/v1/models.py` | `POST /models` و `DELETE /models/{id}` برای افزودن دستی مدل صوتی؛ `ModelOut` حالا `audio_kind` و قیمت‌های صوتی را هم برمی‌گرداند |
| `apps/web` (صفحهٔ مدل‌ها) | فیلتر «صوتی» + نشان «صوتی · گفتار→متن / متن→گفتار» + ستون قیمت صوتی + دکمهٔ «افزودن مدل صوتی» در همان جدول |
| `apps/web` | مسیر **`/audio`** («صدا و گفتار») + پروکسی دودویی `/api/audio/transcriptions` |
| `seeding/catalog.py` | مدل‌های صوتی دیگر `supports_tools`/`stream` نمی‌گیرند |
| `scripts/fake_provider.py` | endpointهای صوتی برای تست محلی |

**شاهد زنده (روی همین سرویس‌های در حال اجرا):**

| بررسی | نتیجه |
|---|---|
| `POST /v1/audio/transcriptions` روی پروایدر آزمایشی | `200` · متن + `seconds=6.0` · `cost_usd=0.0006` · `cost_irr=600` |
| `POST /v1/audio/speech` (۱۱۹۹ نویسه) | `200` · `audio/mpeg` · `x-cost-usd=0.017985` · `x-chars=1199` |
| `GET /v1/audio/speech/estimate` | `200` · ۱۰ نویسه → `0.00015` دلار (بدون فراخوانی پروایدر) |
| `GET /v1/usage/summary` | هزینهٔ صوتی در مجموع ماه دیده می‌شود (ledger مشترک) |
| `pytest tests/test_audio.py` | **۱۵ تست سبز** |

**مستندات:** [audio.md](audio.md).



**انجام شد:** نصب کامل روی همان VPS که اپ دیگری (`Amigook`) را سرو می‌کند، بدون دست‌زدن به آن.

| مورد | مقدار |
|---|---|
| کد | `/opt/kaarvand` (git، commit `da3ee50`) با کاربر `kaarvand` |
| دیتابیس | `kaarvand` + نقش `kaarvand_app` + `pgvector` |
| سرویس‌ها | `kaarvand-api` (8100) · `kaarvand-web` (3100) · `kaarvand-scheduler` |
| وب‌سرور | nginx vhost + **Let's Encrypt** (ریدایرکت HTTP→HTTPS) |
| اجرا | `alembic upgrade head` + seed (ادمین `admin@kaarvand.amigok.cloud`) + build پنل |

**شاهد زنده:**
- `https://kaarvand.amigok.cloud/healthz` → `{"status":"ok","db":"ok"}`
- `https://kaarvand.amigok.cloud/v1/meta` → `app_name=کاروند`, `env=prod`
- ورود پنل از طریق HTTPS/BFF → `200` (نقش owner) و صفحات `/apps` `/channels` `/runs` `/tools` → `200`
- `http://` → `301` به `https://`
- سایت‌های قبلی سرور (`amigok.cloud`, `admin.amigok.cloud`) → `301` و سالم

**پنج باگ واقعی که استقرار لو داد و رفع شد:**
۱) `openpyxl` در dependencies نبود → خروجی اکسل روی نصب تازه ۵۰۰ می‌داد.
۲) `jsonschema` در dependencies نبود → API اصلاً import نمی‌شد.
۳) `pip install -e .` با layout مسطح شکست می‌خورد → `[build-system]` و
`[tool.setuptools.packages.find]` اضافه شد.
۴) `APP_ENV` **بی‌اثر** بود: با پیشوند `APP_`، نام درست `APP_APP_ENV` است؛ `.env.example`،
`docs/install.md` و `conftest.py` اصلاح شدند.
۵) مقدار `test` در `Literal` فیلد `app_env` نبود → مسیر NullPool تست‌ها مرده بود؛ اضافه شد.

**مستندات:** [deploy.md](deploy.md) (چیدمان، به‌روزرسانی، بکاپ، TLS، عیب‌یابی).

## قدم ۱۲ — تغییر برند به «کاروند» (Kaarvand) ✔

**تغییرات:**

| فایل | تغییر |
|---|---|
| `services/api/app/core/config.py:27` | `app_name = "کاروند"` → `/v1/meta` و عنوان FastAPI |
| `services/api/.env.example` | افزودن `APP_APP_NAME=کاروند` (قابل override در سرور) |
| `apps/web/app/layout.tsx:15-17` | `title: "کاروند — پنل مدیریت"` + description کاروند |
| `apps/web/app/(auth)/login/page.tsx:6` | `title: "ورود — کاروند"` |
| `apps/web/components/shell.tsx:79-82,134` | نشان «ک» + «کاروند» در سایدبار و fallback هدر |
| `apps/web/package.json` | `@kaarvand/web` (+ همگام‌سازی `package-lock.json`) |
| `services/api/pyproject.toml` | `kaarvand-api` + description |
| `services/api/app/api/v1/usage.py:290` | نام فایل خروجی: `kaarvand-usage-*.xlsx` |
| `app/__init__.py`, `app/main.py` | docstring → Kaarvand |
| `app/tools/mcp.py:90` | `clientInfo.name = "kaarvand"` |
| `app/providers/adapters/openai_chat.py:75-76` | `HTTP-Referer: https://kaarvand.ir` · `X-Title: Kaarvand` |

**عمداً تغییر نکرد:** نام دیتابیس/نقش (`openbot_app`, `openbot`, `openbot_test`)، ایمیل ادمین پیش‌فرض
(`admin@openbot.local` — روی سرور با `OPENBOT_ADMIN_EMAIL` قبل از seed عوض می‌شود) و نام لاگرها
(`openbot.*`) تا داده و فیلترهای لاگ نشکنند.

**شاهد:** `GET /v1/meta` → `app_name=کاروند`؛ `<title>` صفحهٔ ورود «ورود — کاروند»؛ هدر پنل «کاروند»؛
هدر `Content-Disposition` خروجی اکسل `kaarvand-usage-…xlsx`؛ `ruff` پاک و کل تست‌ها سبز.

## قدم ۱۱ — تست آسان وبهوک و استقرار ✔

**ساخته شد:** `POST /v1/channels/{id}/test`، `POST /v1/channels/{id}/register-webhook`،
`APP_PUBLIC_BASE_URL`، `webhook_url`/`last_event_status`/`last_reply_status`/`last_error` در پاسخ
کانال، و دو دکمهٔ تازه در پنل.

- **«تست وبهوک»**: یک پیام ساختگی از همان مسیر پارسر → dedupe → اجرا → پاسخ رد می‌شود و نتیجه
  (وضعیت اجرا، وضعیت پاسخ، متن ایجنت، لینک اجرا) همان‌جا در کارت کانال نشان داده می‌شود.
  بدون گوشی و بدون تلگرام. اگر ابزاری نیاز به تأیید داشته باشد، `needs_approval=true` برمی‌گردد
  و پیام «منتظر تأیید» نمایش داده می‌شود (پاسخی ارسال نمی‌شود).
- **«ثبت وبهوک در تلگرام»**: سرور با توکن رمزنگاری‌شدهٔ ابزار تلگرام، `setWebhook` را با
  `url`، `secret_token` و `allowed_updates=["message"]` صدا می‌زند و `description` تلگرام را
  برمی‌گرداند. برای واتساپ `422 inbound.register_unsupported` (پیکربندی فقط از پنل متا).
- **`APP_PUBLIC_BASE_URL`**: اگر ست شود، `webhook_url` مطلق از همان دامنه ساخته می‌شود
  (`https://bot.example.com/v1/inbound/...`)؛ وگرنه از آدرس درخواست و با پرچم
  `public_base_url=false` (هشدار «دامنهٔ عمومی نیست» در پنل).
- **نمای آخرین رویداد** در فهرست کانال‌ها: وضعیت، وضعیت پاسخ و آخرین خطا بدون درخواست دوم.

**شاهد زنده:**
- `POST /test` روی کانال واقعی → `run=completed`, `reply=sent` و متن پاسخ ایجنت.
- با ابزار تأییددار → `run=waiting_approval`, `needs_approval=true`, پاسخی ارسال نشد.
- `POST /register-webhook` → URL درست ساخته شد و درخواست واقعی به `api.telegram.org` رفت
  (اینجا `ConnectTimeout` چون شبکهٔ این ماشین به تلگرام دسترسی ندارد — همان چیزی که روی سرور
  ایرانی هم رخ می‌دهد؛ با دامنهٔ عمومی + سرور خارج یا `proxy` روی ابزار حل می‌شود).
- با `APP_PUBLIC_BASE_URL=https://bot.example.com` → `webhook_url` همان دامنه را نشان داد.

**باگ رفع‌شده در مسیر:** seed کاتالوگ روی دیتابیس موجود با `KeyError: 'requires_device'`
می‌شکست (کلید در helper `_bot_api` نبود). هم کلید اضافه شد، هم `seed_apps` نسبت به کلیدهای
اختیاری مقاوم شد و تست idempotent برای re-seed اضافه شد.

## قدم ۱۰ — کانال‌های ورودی (وبهوک تلگرام/واتساپ) ✔

**ساخته شد (بک‌اند):** `db/models/inbound.py`، مایگریشن `0012_inbound.py`،
`runtime/inbound.py`، `api/v1/inbound.py` (۸ مسیر)

- **کانال = پل وبهوک به ایجنت**: `inbound_channels` با `slug` یکتای سراسری، ایجنت، ابزار پاسخ
  و `reply_mode` (`off|auto`). کلید وبهوک با AES‑GCM و AAD `inbound:<slug>` رمز می‌شود.
- **تأیید امضا**: تلگرام `X-Telegram-Bot-Api-Secret-Token`، واتساپ HMAC‑SHA256 روی بدنه‌ی خام
  (`X-Hub-Signature-256`) + هندشیک GET با `hub.verify_token`/`hub.challenge`.
- **ضد تکرار**: یکتایی `(channel_id, external_id)` روی `tg:<update_id>` / `wa:<message id>`؛
  تحویل تکراری `duplicate` برمی‌گرداند و اجرای دوم ساخته نمی‌شود.
- **هر پیام = یک اجرا** با `trigger="webhook"` (بودجه، تأیید، هزینه و سیاست ابزار دست‌نخورده)،
  و رویداد در `inbound_events` با `run_id` ثبت می‌شود.
- **پاسخ خودکار**: با `reply_mode=auto` و اجرای موفق، پاسخ از همان ابزار برنامه (تلگرام/واتساپ)
  ارسال و در `tool_invocations` ثبت می‌شود؛ اگر اجرا در `waiting_approval` پارک شود، پاسخی
  فرستاده نمی‌شود (تأیید انسانی).
- **پنل**: مسیر `/channels` با ساخت کانال، آدرس وبهوک قابل کپی، فعال/غیرفعال، حذف و جدول
  رویدادها.

**شاهد:** `tests/test_inbound.py` با ۱۴ تست (ساخت کانال و پوشاندن secret، الزام verify token،
ناسازگاری ابزار/پیام‌رسان، ابزار سفارشی بدون `app_slug`، RBAC، امضای غلط ۴۰۱، تحویل تکراری،
اجرای یکتا، پیام غیرمتنی، کانال غیرفعال، هندشیک و امضای واتساپ، **اجرای کامل ایجنت + ارسال
پاسخ واقعی** با respx، و ثبت `failed` وقتی پیام‌رسان ۵xx می‌دهد) + تست رگرسیون قفل زمان‌بند در
`tests/test_scheduler.py`؛ `216 passed`→`231 passed` در کل مجموعه.

**رفع باگ‌ها در مسیر:**
۱) تلگرام/بله/ایتا/روبیکا فیلد «chat_id پیش‌فرض» را به‌عنوان اعتبارنامه‌ی نصب داشتند و همان
`{{chat_id}}` را در قالب config از پیش پر می‌کرد؛ نتیجه این بود که پاسخ خودکار به‌جای فرستنده‌ی
واقعی به چت پیش‌فرض می‌رفت. آن اعتبارنامه حذف شد (توکن کافی است) و `{{chat_id}}` یک ورودی
زمان‌اجراست.
۲) پس از `IntegrityError` در dedupe، نشست بدون `rollback` مانده بود و پاسخ ۵۰۰ می‌شد.
۳) **باگ جدی در زمان‌بند (قدم ۸):** اتصال نگه‌دارنده‌ی advisory lock فقط در یک متغیر محلی بود؛
با GC شدن آن، قفل **بی‌صدا آزاد** می‌شد و «تک‌مجرا بودن» از بین می‌رفت (احتمال اجرای تکراری با
دو worker). حالا در `_lock_connection` زنده نگه داشته و در shutdown آزاد می‌شود؛ تست رگرسیون +
اثبات زنده: نمونه‌ی دوم `another scheduler holds the lock; exiting` می‌دهد.
۴) اگر پیام‌رسان ۵xx برمی‌گرداند، `reply_status` قبلاً `sent` ثبت می‌شد (چون ابزار HTTP خطا
پرتاب نمی‌کند)؛ حالا `ok=false` → `failed`.
۵) ابزار پاسخ سفارشی که `config.app_slug` ندارد رد می‌شد؛ حالا فقط **ناسازگاری** رد می‌شود
(ابزار سفارشی مجاز است).
۶) `deliver_reply` حالا `run_id` را به `execute_tool` می‌دهد تا invocation به همان اجرا وصل باشد.

**اثبات زنده (غیر mock):** پیام واقعی روی کانال تلگرام → ران اجرا شد → پاسخ از ابزار
`demo.local_reply` به `POST /echo` روی `127.0.0.1:8020` رفت → `status: ok`, `http 200`,
`args = {"chat_id": "777", "text": "سلام! این پاسخ پروایدر آزمایشی است."}` و رویداد با
`reply=sent` ثبت شد.

## قدم ۹ — «برنامه‌ها»: کاتالوگ اتصال با آیکون برند ✔

**ساخته شد (بک‌اند):** `db/models/apps.py`، مایگریشن `0011_apps.py`، `seeding/apps_seed.py`
(۲۵ برنامه)، `api/v1/apps.py` (۷ مسیر)، `POST /v1/tools/{id}/clone`

- **کاتالوگ داده‌محور**: هر برنامه یک ردیف `app_catalog` است (آیکون، رنگ برند، runtime،
  قالب `config`/`actions`، `credentials` ویزارد، `detect`، پیش‌نیازها). افزودن برنامه‌ی
  جدید = یک ردیف دیتابیس، بدون کد.
- **نصب = کپی قالب**: `POST /v1/apps/{slug}/install` یک `tools` سازمانی با slug
  `<app>.<agent8>` می‌سازد (یا به‌روزرسانی می‌کند)، اعتبارنامه را رمزنگاری می‌کند و
  `agent_tools` را با `permission_level` می‌نویسد.
- **برنامه‌های دسکتاپ**: فقط روی دستگاه آنلاین نصب می‌شوند و باید در `device_tools` شناسایی
  شده باشند (`force=true` برای رد کردن بررسی تشخیص).
- **کشف برنامه‌های دستگاه**: `POST /v1/devices/{id}/scan-apps` → پیام `apps.scan` روی WSS →
  کانکتور با `psutil`/`tasklist`، `HKCR\<prog_id>` و مسیر `Program Files` تشخیص می‌دهد →
  `apps.result` → تطبیق با `detect` و ذخیره در `device_tools` (+ مجوز `is_granted`).
- **۷ عملیات تازه** برای کنترل برنامه‌ها: `app.launch`, `app.focus`, `app.windows`,
  `ui.invoke`, `clipboard.set/get`, `keyboard.hotkey` (کاتالوگ ۱۷ → ۲۴).
- **پنل**: مسیر `/apps` با کارت‌های لوگودار و فیلتر دسته، ویزارد اتصال (ایجنت → دستگاه →
  توکن/شناسه → سطح دسترسی)، «افزودن ابزار من» (HTTP سفارشی یا اسکریپت دستگاه)، کارت
  «برنامه‌ها و شبکه‌ها» در صفحه‌ی ایجنت، و کارت «برنامه‌های دستگاه» با اسکن و مجوز در `/devices`.

**رفع باگ‌های قبلی در همین قدم:** نمایش ابزارهای غیرفعال در `/tools` (`enabled_only=false`)،
و امکان ویرایش ابزارهای سراسری با `POST /tools/{id}/clone` (پیش‌تر `tool.global_readonly`
راه فرار نداشت). `category` ابزارها دو مقدار `productivity` و `devices` گرفت.

**شاهد:** `tests/test_apps_api.py` با ۱۴ تست (seed و آیکون‌ها، فیلترها، نصب/به‌روزرسانی/حذف،
اعتبارسنجی اعتبارنامه و دستگاه، اسکن و تطبیق exe، مجوز، clone، دیدن ابزار در `llm-schemas`)؛
`npx tsc --noEmit` و `npm run build` پنل پاک؛ `ruff` پاک.

**باگ‌های رفع‌شده در مسیر:**
۱) `created_at`/`updated_at` جدول تازه بدون `server_default` ساخته شده بود → seed با
`NotNullViolation` می‌شکست.
۲) `simple-icons` دیگر لوگوی LinkedIn و Slack را ندارد → کلید آیکون `mono:in` و
`lucide:hash` گذاشته شد و کامپوننت `app-icons.tsx` برای هر کلید ناشناس، مونوگرام رنگی می‌سازد.
۳) seed کاتالوگ، ردیف‌های موجود را هم به‌روزرسانی می‌کند تا اصلاح آیکون/متن/قالب به نصب‌های
موجود هم برسد.

## قدم ۸ — زمان‌بند cron ✔

**ساخته شد (بک‌اند):** `runtime/cron.py`، `runtime/starter.py`، `workers/scheduler.py`،
`POST /v1/agents/{id}/tasks/{task_id}/run`، فیلد محاسبه‌شده `next_run_at`

- **پارسر cron بدون وابستگی**: `*`, `*/n`, `a-b`, `a-b/n`, `a/n`, لیست، نام روز/ماه (`sat`, `jan`)؛
  معناشناسی POSIX برای روز-ماه/روز-هفته؛ منطقه‌ی زمانی `Asia/Tehran`؛ خطا با `CronError`.
- **worker مستقل**: `python -m app.workers.scheduler` — قفل advisory پستگرس (تک‌مجرا)،
  claim اتمیک روی `last_run_at` (ضد اجرای تکراری)، رد کردن وظیفه‌ای که اجرای فعال دارد،
  سقف هم‌زمانی، اجرا با همان موتور/دفتر مصرف/تأیید انسانی.
- **اجرای فوری**: `POST .../tasks/{id}/run` با همان `prepare_task_run` (trigger=`task`).
- **تأیید در سطح وظیفه**: وظیفه‌ی `requires_approval` به‌جای اجرا در `waiting_approval` پارک
  می‌شود و `/runs/{id}/approve` آن را با همان متن وظیفه اجرا می‌کند.
- **پنل**: کارت «وظایف و زمان‌بندی» با ستون‌های اجرای بعدی/آخرین اجرا، ویرایش cron،
  فعال/غیرفعال، «اجرای فوری» و نمایش نتیجه.

**شاهد:** `202 passed` (۱۱ تست cron + ۷ تست زمان‌بند) و `ruff` پاک؛ `next_run_at` برای
`0 8 * * *` در پاسخ API برمی‌گردد؛ در تست، `tick` در یک دقیقه فقط یک اجرا می‌سازد و اجرای
تکراری همان دقیقه صفر اجرا برمی‌گرداند.

**شاهد زنده (اجرای واقعی روی همین ماشین):** با `fake_provider` + API + پنل:

- ساخت وظیفه‌ی `* * * * *` از پنل → پاسخ `next_run_at: 2026-11-09T18:01:00Z` (۲۱:۳۱ تهران).
- «اجرای فوری» → `200`، اجرا با `trigger=task`، `task_id` پر، `cost_irr=105`، وضعیت `completed`.
- دو `tick` پشت‌سرهم: `tick1 1` و `tick2 0` → بدون اجرای تکراری؛ اجرای زمان‌بندی‌شده هم
  `trigger=task` و `completed` ثبت شد.

**باگ‌های رفع‌شده:**
۱) نگاشت نام روزهای هفته با ایندکس اشتباه (۶ به‌جای ۴) → همه‌ی `mon..sun` ها خطا می‌دادند.
۲) تست‌های بدون `@respx.mock` سینک مدل را واقعاً به DNS می‌فرستادند (`getaddrinfo failed`).
۳) اگر نرخ ارز هم در دیتابیس و هم در env صفر بود، `cost_irr` بی‌صدا صفر ثبت می‌شد
   (`cost_usd=0.0001045` ولی `cost_irr=0`) → هشدار سرخ در داشبورد و صفحه‌ی مصرف + مستند
   شدن `APP_FX_USD_IRR` در `install.md`.
۴) نام وظیفه با `Invoke-RestMethod` در ویندوز mojibake می‌شد؛ در اسکریپت‌های تست باید
   بدنه‌ی UTF-8 صریح فرستاد (اشکال ابزار تست، نه محصول).

## قدم ۷ — API تکمیلی پنل + فرانت‌اند فارسی ✔

**ساخته شد (بک‌اند):** `api/v1/usage.py`، `api/v1/users.py`، `api/v1/settings.py`،
`billing/fx.py`، `schemas/{usage,users,settings}.py`

- `GET /v1/usage/summary` — تجمیع مصرف: بازه، totals، به‌تفکیک روز/ایجنت/مدل، شمارش وضعیت اجراها، بودجه و دستگاه‌های آنلاین
- `GET /v1/usage/export.xlsx` — شیت RTL، سرصفحه‌ی فارسی، تاریخ جلالی، فرمت عددی واقعی (openpyxl)
- `GET/POST/PATCH/DELETE /v1/users` + `POST /v1/users/{id}/reset-password` — نقش‌ها، منع
  escalate غیرمالک، غیرفعال‌سازی به‌جای حذف، باطل‌کردن نشست‌ها با تغییر رمز
- `GET/PATCH /v1/settings`, `/settings/org`, `/settings/me`, `/settings/fx` — نرخ ارز از دیتابیس
  خوانده می‌شود (`billing/fx.py`) و موتور اجرا/پروب مدل از همان استفاده می‌کنند

**ساخته شد (فرانت):** `apps/web` — Next.js 15 + TS + Tailwind (RTL) با ۱۶ مسیر:
`/login`, `/`, `/playground`, `/agents`, `/agents/[id]`, `/providers`, `/models`, `/prompts`,
`/tools`, `/devices`, `/runs`, `/runs/[id]`, `/usage`, `/users`, `/settings` + BFF

- JWT فقط در کوکی `httpOnly`؛ پروکسی `/api/[...path]` رفرش خودکار و عبور SSE بدون بافر
- تمام متن‌ها از `lib/copy.ts` و نقشه‌ی «کد خطا → جمله‌ی فارسی» (`lib/errors-fa.ts`)
- تبدیل جلالی و ارقام فارسی سمت کلاینت (`lib/format.ts`)؛ مبالغ ریال ذخیره، تومان نمایش
- آزمایشگاه با استریم زنده و کارت تأیید انسانی روی `run.waiting_approval`

**شاهد:** `184 passed` در بک‌اند + `ruff` پاک؛ `npm run build` با ۱۶ مسیر و typecheck پاک؛
ورود واقعی و رندر داشبورد/پروایدر/مدل/ایجنت/آزمایشگاه با کد ۲۰۰ از سرور production.

**باگ‌های رفع‌شده:**
۱) `app_settings.fx` با مقدار صفر seed می‌شد و نرخ واقعی را می‌بلعید → صفر = «تنظیم‌نشده» و fallback به env.
۲) برچسب `format_irr` «تومان» بود ولی مقدار ریال → واحد «ریال» شد و UI تومان می‌سازد.
۳) کوکی `secure` در production روی HTTP self-host از کار می‌افتاد → از پروتکل درخواست تبعیت می‌کند.
۴) import شدن `next/headers` در زنجیره‌ی کلاینت (build می‌شکست) → جداسازی `lib/api-server.ts`.

## قدم ۶ — کانکتور دسکتاپ ✔

**ساخته شد:** `app/connector/{hub,pairing,executor}.py`، `api/v1/devices.py`،
`api/v1/connector_ws.py`، `scripts/connector_client.py`، `scripts/demo_connector_flow.py`

- جفت‌سازی با کد ۸ کاراکتری (۱۰ دقیقه) + توکن دستگاه
- کانال WebSocket خروجی + `hello/manifest/progress/result`
- اجرای اسکریپت اقدام با جایگذاری `{{input.x}}` و `{{run_id}}`
- لایه‌ی ایمنی دوطرفه: `allowed_paths` و allowlist فرمان

**شاهد:** نوشتن فایل واقعی `گزارش فروش آبان ۱۴۰۵` روی دیسک از طریق ابزار، و بلاک شدن
`C:\Windows\System32\evil.txt` با `PermissionError`؛ `168 passed`؛ ۱۵ عملیات اعلام‌شده توسط دستگاه.

**باگ‌های رفع‌شده:** ۱) مرگ کد قدیمی `tool.device_unavailable` → `tool.device_offline`؛
۲) یک فایل تست به‌خاطر تبدیل رمزگذاری PowerShell خراب شد و بازنویسی شد.

## قدم ۵ — اجرای ایجنت ✔

**ساخته شد:** `app/runtime/{engine,events,budget,tools_binding}.py`، `api/v1/runs.py`،
`schemas/runs.py`، مایگریشن `0010` (`runs.state`, `runs.steps_taken`)

- حلقه‌ی tool-calling با حداکثر ۸ گام، استریم SSE، بودجه‌ی ماه جلالی
- توقف برای تأیید انسانی و ادامه از همان نقطه
- ثبت هزینه‌ی دلار و تومان در `usage_ledger`
- ابزارها: ورودی tool-call در پیام‌های مدل حفظ می‌شود

**شاهد:** `run.completed` با `steps=2`, `cost_irr=141`؛ `waiting_approval` → `approve` →
`completed`؛ `159 passed`.

**باگ‌های رفع‌شده:** ۱) `SET LOCAL` بعد از commit پاک می‌شد و RLS کوئری بعدی را می‌بست؛
۲) `state` (JSONB) با اختصاص همان dict ذخیره نمی‌شد (`flag_modified`)؛
۳) موتور نباید از session درخواست استفاده کند (خطای `MissingGreenlet`).

## قدم ۴ — رجیستری ابزار ✔

**ساخته شد:** `app/tools/{names,schema,policy,actions,net,secrets,builtin,http_exec,mcp,service}.py`،
`api/v1/tools.py`، `schemas/tools.py`، مایگریشن `0009` (اعتبارنامه‌ی رمزی ابزار)

- چهار نوع ابزار + اعتبارسنجی JSON Schema + ماتریس ریسک
- ابزار HTTP توصیفی (template/auth/response_map/allowlist) و کلاینت MCP
- اسکریپت اقدام با ۱۷ عملیات + کاتالوگ فارسی
- آزمون ابزار و «آنچه مدل می‌بیند»

**شاهد:** ۴۱ تست ابزار؛ `tool.invalid_header` و `tool.domain_not_allowed` کشف و پیاده شد.

**باگ‌های رفع‌شده:** ۱) هدر غیر‑ASCII باعث کرش می‌شد؛ ۲) لاگ خطای ابزار با rollback
درخواست پاک می‌شد (الآن تراکنش جدا)؛ ۳) شناسه‌ی تکراری در اتصال ابزار خطای ۵۰۰ می‌داد.

## قدم ۳ — پرامپت و ایجنت ✔

**ساخته شد:** `app/prompts/{render,service}.py`، `app/agents/{workflow,service}.py`،
`app/core/jalali.py`، `api/v1/{prompts,agents}.py`، ۴ پرامپت نقش جدید (حسابدار/فروشنده/منشی/گزارش)

- نسخه‌بندی، انتشار، بازگشت افزودنی، اولویت سازمان بر سراسری
- تبدیل تقویم جلالی (بدون وابستگی) + `{{today_jalali}}` با ارقام فارسی
- وظایف با اعتبارسنجی cron و گراف جریان (داده + اعتبارسنجی)

**شاهد:** «۱۸ آبان ۱۴۰۵» در پرامپت مؤثر؛ v1→v2→v3 با یادداشت «بازگشت به نسخه 1»؛ `110 passed`.

## قدم ۲ — پروایدر و مدل ✔

**ساخته شد:** `app/providers/*` (آداپتورهای بومی OpenAI/Anthropic/Gemini + declarative)،
`app/billing/cost.py`، `api/v1/{providers,models}.py`، `scripts/fake_provider.py`

- کشف مدل/قیمت، استنتاج قابلیت از قواعد DB، تاریخچه‌ی قیمت، قیمت دستی
- استریم بومی با httpx و fallback بین پروایدرها

**شاهد:** `sync-models created=3`، `sync-prices updated=2`، probe با `cost_irr=16`؛ `76 passed`.

**تصمیم‌های مهم:** حذف `litellm` از مسیر داغ (ایمپورت ۳۹ ثانیه) و `trust_env=False`.

## قدم ۱ — بک‌اند و اسکیما ✔

**ساخته شد:** ۳۹ جدول در ۱۰ مایگریشن + RLS + احراز هویت + متن/اعداد فارسی +
`/healthz` و `/v1/meta`، پورت درگاه پرداخت (noop)

**شاهد:** `downgrade base` → `upgrade head` بدون خطا؛ ۱۷ جدول RLS با `FORCE`؛ `55 passed`.

**محیط:** PostgreSQL 16.2 تعبیه‌شده (`pgserver`) بدون نصب/ادمین؛ نقش غیرسوپریوزر برای اپ.

## وضعیت کلی پس از شش قدم

| سنجه | مقدار |
|---|---|
| جداول | ۳۹ |
| مایگریشن | ۱۱ |
| عملیات API | ۷۲ (+۱ WebSocket) |
| تست | ۱۶۸ |
| پرامپت پیش‌فرض | ۱۳ |
| دموی آماده | ۵ |
