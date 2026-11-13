# استقرار (Deploy)

این سند همان استقراری است که واقعاً انجام شد: **کاروند روی سروری که از قبل اپ دیگری
(Amigook) را سرو می‌کند**، بدون دست‌زدن به آن.

## ۱) چیدمان سرور

| مورد | مقدار |
|---|---|
| دامنه | `https://kaarvand.amigok.cloud` (Let's Encrypt، ریدایرکت خودکار از HTTP) |
| کد | `/opt/kaarvand` (git، کاربر `kaarvand`) |
| venv | `/opt/kaarvand/services/api/.venv` |
| دیتابیس | `kaarvand` · نقش `kaarvand_app` (نه superuser، RLS فعال) |
| API | `127.0.0.1:8100` — `kaarvand-api.service` |
| پنل | `127.0.0.1:3100` — `kaarvand-web.service` |
| زمان‌بند | `kaarvand-scheduler.service` (بدون پورت) |
| لاگ‌ها | `/var/log/kaarvand-{api,web,scheduler}.log` |
| nginx | `/etc/nginx/sites-available/kaarvand.conf` |

**چرا پورت ۸۱۰۰/۳۱۰۰؟** چون روی همین سرور `8000` و `80/443` در اختیار اپ قبلی است.

### نقشهٔ nginx

```
kaarvand.amigok.cloud
├── location = /healthz   → 127.0.0.1:8100/healthz   (برای مانیتورینگ)
├── location /v1/         → 127.0.0.1:8100           (REST + SSE + WS کانکتور، buffering off)
└── location /            → 127.0.0.1:3100           (پنل Next.js + BFF /api/*)
```

`X-Forwarded-Proto` ست می‌شود تا کوکی‌های `secure` درست ثبت شوند (`COOKIE_SECURE=true` هم
در سرویس پنل ست شده).

## ۲) متغیرهای محیطی

`/opt/kaarvand/services/api/.env` (چmod 600، مالک `kaarvand`):

```ini
APP_APP_ENV=prod          # ← نام درست همین است، APP_ENV بی‌اثر است
APP_DEBUG=false
APP_APP_NAME=کاروند
APP_DATABASE_URL=postgresql+asyncpg://kaarvand_app:***@127.0.0.1:5432/kaarvand
APP_MIGRATION_DATABASE_URL=...   # همان (نقش، مالک اسکیما است)
APP_JWT_SECRET=***               # ۴۸ کاراکتر تصادفی
APP_MASTER_KEY=***               # base64 از ۳۲ بایت
APP_FX_USD_IRR=1000000
APP_CORS_ORIGINS=["https://kaarvand.amigok.cloud"]
APP_PUBLIC_BASE_URL=https://kaarvand.amigok.cloud

# --- ورود با موبایل و پیامک (از مایگریشن 0014 لازم است) --------------------
APP_OTP_TTL_SECONDS=120
APP_OTP_LENGTH=5
APP_OTP_MAX_ATTEMPTS=5
APP_OTP_RESEND_COOLDOWN_SECONDS=60
APP_OTP_DAILY_LIMIT_PER_PHONE=10
APP_OTP_DAILY_LIMIT_PER_IP=30
APP_OTP_DEBUG_CODE=false        # در prod باید false بماند
APP_SMS_ENABLED=true            # تا کلید فراز اس‌ام‌اس نرسیده، false بگذارید
APP_FARAZSMS_API_KEY=***
APP_FARAZSMS_SENDER=+98...
APP_FARAZSMS_OTP_PATTERN=***    # کد الگوی تأییدشده؛ خالی = متن ساده

# --- قیمت‌گذاری تومانی -----------------------------------------------------
APP_PLATFORM_MARKUP_PERCENT=30
APP_MIN_TOPUP_IRR=100000

# --- درگاه پرداخت زرین‌پال (شارژ کیف پول) ---------------------------------
APP_PAYMENT_GATEWAY=zarinpal      # noop = درگاه خاموش (تست/آزمایشی)
APP_ZARINPAL_MERCHANT_ID=***      # کد ۳۶ کاراکتری پنل زرین‌پال
APP_ZARINPAL_SANDBOX=false        # true = sandbox.zarinpal.com
APP_PAYMENT_TIMEOUT_SECONDS=15
# آدرسی که زرین‌پال مشتری را به آن برمی‌گرداند
APP_PAYMENT_CALLBACK_URL=https://kaarvand.amigok.cloud/v1/wallet/topup/callback
# بعد از تأیید، مشتری به این آدرس (deep link اپ) می‌رود
APP_PAYMENT_RETURN_URL=kaarvand://wallet
```

> **مهم:** با `APP_SMS_ENABLED=false` کد ورود فقط در لاگ سرور
> (`journalctl -u kaarvand-api | grep OTP`) دیده می‌شود؛ برای کاربر واقعی حتماً پیامک را
> فعال کنید. هر شماره‌ای که با OTP وارد شود، خودش حساب `user` و کیف پول می‌گیرد.

پنل: `/opt/kaarvand/apps/web/.env.production` → `API_BASE_URL=http://127.0.0.1:8100` و
`COOKIE_SECURE=true`.

## ۳) به‌روزرسانی نسخه (deploy یک تغییر)

```bash
sudo -u kaarvand git -C /opt/kaarvand fetch origin
sudo -u kaarvand git -C /opt/kaarvand reset --hard origin/main

# بک‌اند (اگر pyproject یا کد عوض شده)
sudo -u kaarvand /opt/kaarvand/services/api/.venv/bin/pip install -q -e /opt/kaarvand/services/api
cd /opt/kaarvand/services/api && sudo -u kaarvand .venv/bin/python -m alembic upgrade head

# پنل (اگر کد فرانت عوض شده)
cd /opt/kaarvand/apps/web && sudo -u kaarvand npm ci --no-audit --no-fund && sudo -u kaarvand npm run build

sudo systemctl restart kaarvand-api kaarvand-web kaarvand-scheduler
```

## ۴) دستورهای روزمره

```bash
systemctl status kaarvand-api kaarvand-web kaarvand-scheduler
journalctl -u kaarvand-api -n 50 --no-pager      # یا tail /var/log/kaarvand-api.log
curl -s https://kaarvand.amigok.cloud/healthz
systemctl restart kaarvand-api
```

**بکاپ دیتابیس:**

```bash
sudo -u postgres pg_dump -Fc kaarvand > /root/kaarvand-$(date +%F).dump
# بازیابی:
sudo -u postgres pg_restore -d kaarvand --clean /root/kaarvand-YYYY-MM-DD.dump
```

**TLS:** certbot یک تایمر systemd نصب کرده (`systemctl list-timers | grep certbot`) و گواهی
خودکار تمدید می‌شود. تست: `certbot renew --dry-run`.

## ۵) نکته‌های عملیاتی

1. **یک worker برای API**: هاب کانکتور درون‌پروسه است؛ اگر `--workers` را زیاد کنید،
   دستگاه‌های کانکتور فقط به یکی از workerها وصل می‌شوند. برای مقیاس، bus مشترک لازم است.
2. **زمان‌بند جدا اجرا می‌شود** و با advisory lock تک‌مجراست؛ دو نمونه همزمان بی‌خطر است
   (دومی خودش خارج می‌شود).
3. **دسترسی تلگرام از سرور ایران**: اگر `api.telegram.org` در دسترس نباشد، پاسخ خودکار
   ارسال نمی‌شود؛ راه‌حل `proxy` در `config` ابزار تلگرام است (کلاینت‌ها `trust_env=False`
   هستند و پروکسی سیستم را نمی‌خوانند).
4. **رمز ادمین اولیه** را بعد از اولین ورود از «کاربران → بازنشانی رمز» عوض کنید.
5. **تا وقتی پیامک فعال نشده** (`APP_SMS_ENABLED=false`) روی سرور `APP_OTP_DEBUG_CODE=true`
   گذاشته شده تا مشتری بتواند وارد شود؛ در این حالت کد در پاسخ همان درخواست برمی‌گردد.
   به‌محض رسیدن کلید فراز اس‌ام‌اس، `APP_SMS_ENABLED=true` و `APP_OTP_DEBUG_CODE=false`
   را با هم ست کنید و سرویس را ری‌استارت کنید.
6. **کلاینت** (`apps/client`) هیچ ارجاعی به پروایدر/قیمت دلاری ندارد؛ فقط
   `/v1/catalog/models`، `/v1/wallet*` و اجراها را صدا می‌زند. اگر مسیر جدیدی اضافه
   کردید، همان قاعده را نگه دارید (تست `test_catalog.py` این را قفل می‌کند).
5. `APP_APP_ENV` را از `dev` به `prod` تغییر ندهید مگر آگاهانه؛ `test` فقط برای تست‌ها است.

## ۶) عیب‌یابی سریع

| نشانه | علت رایج |
|---|---|
| `ModuleNotFoundError` بعد از نصب | وابستگی در `pyproject.toml` جا افتاده → `pip install -e .` دوباره و اضافه‌کردن به dependencies |
| `CREATE EXTENSION vector` خطا می‌دهد | `postgresql-16-pgvector` نصب نیست |
| `pip install -e .` با خطای package discovery | بلوک `[build-system]` + `[tool.setuptools.packages.find]` لازم است |
| `env` در `/v1/meta` هنوز `dev` است | متغیر را `APP_APP_ENV` بگذارید (نه `APP_ENV`) |
| پنل ۴۰۴ روی `/healthz` | `location = /healthz` در بلاک ۴۴۳ nginx لازم است |
| کوکی ست نمی‌شود | `X-Forwarded-Proto` در nginx یا `COOKIE_SECURE` |
| `/` و `/login` پشت‌سرهم `307` می‌دهند (صفحهٔ سفید) | کوکی کهنه در مرورگر؛ `ob_access`/`ob_refresh` را پاک کنید — از این نسخه، `middleware` نشست را خودکار تازه می‌کند و `401` به `/api/auth/expired` می‌رود |
