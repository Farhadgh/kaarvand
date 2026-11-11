# نصب و استقرار

## ۱) پیش‌نیازها

| ابزار | نسخه | یادداشت |
|---|---|---|
| Python | 3.12+ | بک‌اند |
| Node.js | 20+ | پنل وب (`apps/web`) |
| PostgreSQL | 16 + `pgvector` | در توسعه لازم نیست: `pgserver` خودش سرور را می‌آورد |
| RAM | ۲GB+ | توسعه |

## ۲) راه‌اندازی توسعه (ویندوز، بدون Docker)

### ۲.۱) پنل وب

```powershell
cd apps\web
npm install
npm run dev        # http://localhost:3000
```

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `API_BASE_URL` | `http://127.0.0.1:8000` | آدرس بک‌اند برای Server Components و پروکسی |
| `COOKIE_SECURE` | خودکار | `true` اگر پشت HTTPS هستید؛ پیش‌فرض از پروتکل درخواست تبعیت می‌کند |

برای اجرای عملیاتی:

```powershell
cd apps\web; npm run build; npm run start   # پورت ۳۰۰۰
```

> توکن‌ها در کوکی `httpOnly` نگه داشته می‌شوند و به کد مرورگر نمی‌رسند؛ برای همین اگر پنل را
> روی دامنه‌ی دیگری سرو می‌کنید، `APP_CORS_ORIGINS` در بک‌اند باید همان دامنه را داشته باشد.

### ۲.۲) زمان‌بند cron (اختیاری)

```powershell
cd services\api
python -m app.workers.scheduler
```

- یک worker کافی است؛ اگر دو نسخه اجرا شود، دومی با advisory lock بیرون می‌ماند.
- هر پاس، وظایف `trigger_type=schedule` را با ساعت `Asia/Tehran` تطبیق می‌دهد.
- اجراها در همان `runs`/`usage_ledger` ثبت می‌شوند (`trigger="task"`).

### ۲.۳) بک‌اند

```powershell
# ۱) وابستگی‌های پایتون
pip install fastapi "uvicorn[standard]" pydantic-settings "sqlalchemy[asyncio]" asyncpg `
            alembic pgvector pgserver pyjwt argon2-cffi cryptography structlog httpx `
            jsonschema tzdata websockets pytest pytest-asyncio respx ruff

# ۲) دیتابیس محلی + ساخت .env.local (یک‌بار؛ قابل تکرار)
python scripts\devdb.py

# ۳) مایگریشن + داده‌ی پیش‌فرض
cd services\api
python -m alembic upgrade head
python -m app.seeding

# ۴) اجرا
python -m uvicorn app.main:app --reload --port 8000
```

یا یک‌جا:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -Reload
```

- API: <http://127.0.0.1:8000> — مستندات: `/docs`
- ورود پیش‌فرض: `admin@openbot.local` / `admin12345` (قابل تغییر در `.env`)
- `python scripts\devdb.py --info` آدرس‌های فعلی دیتابیس را نشان می‌دهد.

## ۳) متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `APP_ENV` | `dev` | `dev`/`test`/`prod` |
| `APP_DATABASE_URL` | — | نقش اپ (غیرسوپریوزر، RLS فعال) |
| `APP_MIGRATION_DATABASE_URL` | — | نقش postgres برای مایگریشن/افزونه |
| `APP_JWT_SECRET` | — | کلید امضای توکن |
| `APP_MASTER_KEY` | — | base64 از ۳۲ بایت برای AES‑GCM کلیدها |
| `APP_ACCESS_TOKEN_TTL_MIN` | ۱۵ | عمر access |
| `APP_REFRESH_TOKEN_TTL_DAYS` | ۷ | عمر refresh |
| `APP_DEFAULT_LOCALE/CALENDAR/CURRENCY/DIGITS` | `fa`/`jalali`/`IRR`/`fa` | پیش‌فرض فارسی |
| `APP_FX_USD_IRR` | `0` | نرخ دلار به ریال. اگر صفر بماند هزینه‌ی ریالی صفر ثبت می‌شود؛ یا اینجا یا در «تنظیمات → نرخ ارز» مقدار بدهید |
| `APP_FREE_MODE` | `true` | حالت آزمایشی رایگان |
| `APP_BILLING_ENABLED` | `false` | خاموش‌بودن همه‌ی مسیرهای پرداخت |
| `APP_PAYMENT_GATEWAY` | `noop` | درگاه فعلی |
| `APP_CORS_ORIGINS` | `["http://localhost:3000"]` | دامنه‌ی فرانت |
| `APP_PUBLIC_BASE_URL` | — | دامنه‌ی عمومی برای ساخت آدرس وبهوک (`https://bot.example.com`)؛ بدون آن آدرس از درخواست ساخته می‌شود و برای تلگرام/متا بی‌فایده است |

فایل‌ها از **پکیج** خوانده می‌شوند (`services/api/.env`, `.env.local`)، نه از پوشه‌ی جاری —
پس اجرا از هر مسیری درست کار می‌کند.

## ۴) دستورهای روزمره

```powershell
cd services\api
python -m alembic upgrade head          # اعمال مایگریشن‌ها
python -m alembic current               # نسخه‌ی فعلی
python -m alembic downgrade -1          # یک قدم عقب
python -m app.seeding                   # داده‌ی پیش‌فرض (idempotent)
python scripts\mkmig.py runtime 0011 x  # مایگریشن جدید برای گروه runtime
python -m pytest -q                     # ۱۸۴ تست
python -m ruff check app tests          # کیفیت کد
python scripts\check_schema.py          # رفت‌وبرگشت مایگریشن + گزارش RLS
```

## ۵) استقرار عملیاتی (خلاصه)

```text
[HTTPS] → Caddy/Nginx → uvicorn (۲+ worker)
                     → PostgreSQL 16 + pgvector (بکاپ روزانه)
                     → کانکتورها (outbound WSS از ماشین کاربران)
```

| مورد | توصیه |
|---|---|
| اجرا | `uvicorn app.main:app --workers 2 --host 127.0.0.1 --port 8000` |
| مایگریشن | قبل از بالا آمدن نسخه‌ی جدید: `alembic upgrade head` |
| سلامت | `GET /healthz` در liveness/readiness |
| بکاپ | `pg_dump` روزانه + آرشیو WAL + تست بازیابی ماهانه |
| لاگ | جمع‌آوری JSON stdout در یک سرویس متمرکز |
| Secrets | متغیر محیطی از مدیر مخفی (نه فایل داخل ریپو) |
| کانکتور | نصب به‌صورت سرویس ویندوز/LaunchAgent + آپدیت از پنل |

**هشدار چند-worker:** هاب کانکتور درون‌پروسه است؛ با `--workers > 1` یک دستگاه ممکن است
روی worker دیگری وصل باشد. تا اضافه‌شدن bus مشترک (roadmap)، تک‌worker استفاده کنید.

## ۶) عیب‌یابی

| نشانه | علت رایج | راه‌حل |
|---|---|---|
| `ConnectionRefusedError` به پورت ۵۸۴xx | دیتابیس تعبیه‌شده خاموش شده | `python scripts\devdb.py` |
| `Server disconnected` در اسکریپت‌ها | پروکسی سیستمی | در کد `trust_env=False` است؛ در اسکریپت خودتان هم همان را بگذارید |
| `MissingGreenlet` | دسترسی به آبجکت expire‌شده | از `session_scope` / شناسه‌ی ساده استفاده کنید |
| متن فارسی در کنسول خراب است | کد‌پیج ویندوز | `$env:PYTHONIOENCODING='utf-8'` |
| `prompt.not_found` در ساخت ایجنت | پرامپت seed نشده | `python -m app.seeding` |
| `tool.device_offline` | کانکتور وصل نیست | `python scripts\connector_client.py --code …` |
| ۵۰۳ در `/healthz` | دیتابیس در دسترس نیست | `APP_DATABASE_URL` را بررسی کنید |
