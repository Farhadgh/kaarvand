# کاروند (Kaarvand) — پلتفرم ایجنت هوش مصنوعی فارسی

## وضعیت: **قدم ۱ تا ۱۳ انجام شده** — نسخهٔ زنده روی <https://kaarvand.amigok.cloud>

| قدم | محتوا | وضعیت |
|---|---|---|
| ۱ | بک‌اند + اسکیما (۴۰ جدول، ۱۲ مایگریشن، RLS) | ✅ |
| ۲ | پروایدر/مدل/سینک قیمت + گیتوی استریم + محاسبه هزینه | ✅ |
| ۳ | ایجنت‌ها + پرامپت نسخه‌دار + وظایف | ✅ |
| ۴ | رجیستری ابزار (HTTP/MCP/کانکتور) + سیاست تأیید | ✅ |
| ۵ | اجرای ایجنت (موتور tool-calling + SSE + تأیید انسانی) | ✅ |
| ۶ | کانکتور دسکتاپ (جفت‌سازی + WebSocket + Action Script) | ✅ |
| ۷ | فرانت‌اند فارسی (پنل Next.js ۱۵ + RTL + جلالی) | ✅ |
| ۸ | زمان‌بند cron (worker مستقل + اجرای فوری + ویرایش از پنل) | ✅ |
| ۹ | کاتالوگ برنامه‌ها (۲۵ اپ با آیکون برند + ویزارد اتصال + افزودن ابزار سفارشی) | ✅ |
| ۱۰ | کانال‌های ورودی (وبهوک تلگرام/واتساپ + پاسخ خودکار ایجنت + ضد تکرار) | ✅ |
| ۱۱ | تست وبهوک از پنل + ثبت خودکار setWebhook + `APP_PUBLIC_BASE_URL` | ✅ |
| ۱۲ | تغییر برند به «کاروند (Kaarvand)» + آماده‌سازی ریپوی گیت‌هاب | ✅ |
| ۱۳ | استقرار روی سرور: systemd + nginx + Let's Encrypt → `https://kaarvand.amigok.cloud` | ✅ |

### اجرای سریع پنل

```powershell
# ترمینال ۱ — بک‌اند
cd services/api; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# ترمینال ۲ — پنل
cd apps/web; npm install; npm run dev   # http://localhost:3000
```

ورود توسعه: `admin@openbot.local` / `admin12345`.
توکن‌ها در کوکی `httpOnly` می‌مانند (BFF در `app/api/[...path]/route.ts`) و به مرورگر نمی‌رسند.

## مستندات

| سند | محتوا |
|---|---|
| [docs/README.md](docs/README.md) | فهرست مستندات و وضعیت در یک نگاه |
| [docs/PRD.md](docs/PRD.md) | نیازمندی محصول، پرسونا، معیارهای پذیرش |
| [docs/architecture.md](docs/architecture.md) | معماری و تصمیم‌های فنی |
| [docs/data-model.md](docs/data-model.md) | ۴۰ جدول + RLS |
| [docs/inbound.md](docs/inbound.md) | کانال‌های ورودی: وبهوک تلگرام/واتساپ + پاسخ خودکار |
| [docs/deploy.md](docs/deploy.md) | استقرار روی سرور: systemd، nginx، TLS، بکاپ |
| [docs/apps.md](docs/apps.md) | کاتالوگ برنامه‌ها: واتساپ، تلگرام، آفیس، برنامه‌های دستگاه |
| [docs/api.md](docs/api.md) | ۱۰۴ عملیات REST + SSE + WebSocket |
| [docs/tool-contract.md](docs/tool-contract.md) | چهار نوع ابزار، اسکریپت اقدام، ماتریس ریسک |
| [docs/prompts.md](docs/prompts.md) | پرامپت‌ها، متغیرها، نسخه‌بندی |
| [docs/security.md](docs/security.md) | RLS، رمزنگاری، RBAC، مدل تهدید |
| [docs/install.md](docs/install.md) | نصب و استقرار |
| [docs/roadmap.md](docs/roadmap.md) | کارهای باقی‌مانده و محدودیت‌ها |
| [docs/changelog.md](docs/changelog.md) | تاریخ شش قدم با شواهد |
| [docs/demo.md](docs/demo.md) | شش دموی آماده (شامل پنل) |

## پیش‌نیازها


| ابزار | نسخه | توضیح |
|---|---|---|
| Python | 3.12+ | بک‌اند |
| Node.js | 20+ | پنل وب (`apps/web`) |
| PostgreSQL | 16 + `pgvector` | برای توسعه‌ی محلی نیازی به نصب نیست: `pgserver` خودش سرور را بالا می‌آورد |

## راه‌اندازی سریع (ویندوز)

```powershell
pip install fastapi "uvicorn[standard]" pydantic-settings "sqlalchemy[asyncio]" asyncpg alembic `
            pgvector pgserver pyjwt argon2-cffi cryptography structlog httpx tzdata `
            pytest pytest-asyncio ruff
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -Reload
```

- API: <http://127.0.0.1:8000> — مستندات OpenAPI: `/docs`
- `GET /healthz` → سلامت سرویس و دیتابیس
- `GET /v1/meta` → زبان/تقویم/ارز/حالت رایگان
- ورود پیش‌فرض: `admin@openbot.local` / `admin12345` (از `.env` قابل تغییر)

## دستورهای پرکاربرد

```powershell
python scripts\devdb.py                      # بالا آوردن دیتابیس محلی + ساخت .env.local
cd services\api
python -m alembic upgrade head               # اعمال مایگریشن‌ها
python -m alembic current                    # نسخه‌ی فعلی اسکیما
python -m app.seeding                        # داده‌های پیش‌فرض (idempotent)
python -m pytest -q                          # تست‌ها (روی دیتابیس واقعی)
python -m ruff check app tests               # کیفیت کد
python -m uvicorn app.main:app --reload      # اجرای API
```

## ساختار

```
services/api
├─ app/core        # تنظیمات، امنیت، رمزنگاری کلیدها، متن فارسی، اعداد به حروف، خطاها
├─ app/db          # Base + مدل‌ها + جلسه‌ی دیتابیس با RLS
├─ app/api/v1      # روترها (meta/auth/billing)
├─ app/billing     # پورت درگاه پرداخت (فعلاً noop)
├─ app/seeding     # کاتالوگ آداپتورها، پرامپت‌های فارسی، پلن رایگان
├─ alembic         # ۸ مایگریشن: core → locale → providers → prompts → agents → tools → runtime → RLS
└─ tests           # ۵۵ تست (auth, RLS, billing, فارسی‌سازی, دینامیک بودن)
```

## جریان پروایدر (قدم ۲)

```powershell
# ۱) یک پروایدر آزمایشی محلی بالا بیاور (بدون نیاز به کلید واقعی)
python scripts\fake_provider.py            # http://127.0.0.1:8020/v1

# ۲) API را با نرخ ارز اجرا کن (برای نمایش هزینه به تومان)
cd services\api; $env:APP_FX_USD_IRR=1000000; python -m uvicorn app.main:app --port 8010

# ۳) کل جریان را یک‌جا ببین: افزودن پروایدر → تست → سینک مدل → سینک قیمت → آزمایش مدل
python scripts\demo_provider_flow.py
```

مسیرهای API:

| متد | مسیر | کار |
|---|---|---|
| GET | `/v1/provider-adapters` | کاتالوگ آداپتورها (از دیتابیس، فارسی) |
| POST | `/v1/providers` | افزودن پروایدر (کلید رمزنگاری‌شده ذخیره می‌شود) |
| POST | `/v1/providers/{id}/test` | تست اتصال + شمارش مدل‌ها |
| POST | `/v1/providers/{id}/sync-models` | کشف مدل‌ها + استنتاج قابلیت‌ها |
| POST | `/v1/providers/{id}/sync-prices` | سینک قیمت + ثبت در `price_history` |
| GET | `/v1/models?capability=tools` | مدل‌های قابل استفاده |
| PATCH | `/v1/models/{id}` | فعال/غیرفعال، نام فارسی، markup |
| POST | `/v1/models/{id}/price` | قیمت دستی (بر قیمت پروایدر مقدم است) |
| POST | `/v1/models/{id}/probe` | یک فراخوانی واقعی + هزینه به دلار و تومان |

### نکته‌ی مهم درباره‌ی پروکسی

درخواست‌های خروجی به پروایدرها با `trust_env=False` ساخته می‌شوند: پروکسی سیستمی
(که در ایران رایج است) هرگز به‌صورت ناخواسته ترافیک مدل را تغییر نمی‌دهد. برای هر
## اجرای ایجنت (قدم ۵)

```powershell

## کانکتور دسکتاپ (قدم ۶)

```powershell
# ۱) در پنل یک دستگاه بساز و کد جفت‌سازی بگیر
# ۲) کانکتور را روی همان ماشین اجرا کن:
python scripts\connector_client.py --server http://127.0.0.1:8010 --code ABC12345 --allow-dir D:\data

# ۳) دموی کامل (خودش کانکتور را بالا می‌آورد و فایل واقعی می‌نویسد)
python scripts\demo_connector_flow.py
```

| متد | مسیر | کار |
|---|---|---|
| POST | `/v1/devices` | ساخت دستگاه + کد جفت‌سازی (۱۰ دقیقه اعتبار) |
| POST | `/v1/devices/pair` | کانکتور: کد + کلید عمومی → توکن دستگاه |
| GET | `/v1/devices/{id}/ops` | آنلاین بودن + عملیات اعلام‌شده |
| WS | `/v1/ws/connector?token=` | کانال خروجی کانکتور |

**مدل امنیتی:** کانکتور فقط خروجی وصل می‌شود (بدون پورت باز/IP ثابت)؛ هر مسیر فایل باید
داخل `allowed_paths` باشد (هم سرور و هم کانکتور بررسی می‌کند)؛ `shell.run` فقط با
پیشوندهای مجاز؛ و هر اجرا در `tool_invocations` ثبت می‌شود.

python scripts\fake_provider.py                 # :8020 (پاسخ + فراخوانی اولین ابزار)
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
python scripts\demo_run_flow.py                 # استریم SSE + ابزار + هزینه + تأیید انسانی
```

| متد | مسیر | کار |
|---|---|---|
| POST | `/v1/agents/{id}/runs` | اجرا؛ `stream=true` → SSE (پیش‌فرض) |
| POST | `/v1/runs/{id}/approve` | تأیید انسانی و ادامه‌ی اجرا |
| GET | `/v1/runs?agent_id=&status=` | فهرست اجراها |
| GET | `/v1/runs/{id}` | وضعیت/توکن/هزینه |
| GET | `/v1/runs/{id}/invocations` | فراخوانی ابزارها |
| POST | `/v1/runs/{id}/cancel` | لغو |

رخدادهای SSE: `run.started` → `llm.start` → `token` / `tool.call` / `tool.result` /
`approval.required` → `run.waiting_approval` یا `run.completed`.

## قراردادهای مهم

پروایدر می‌توان با `meta.proxy = "http://host:port"` خروجی را صریح تنظیم کرد.

## قراردادهای مهم

1. **هیچ داده‌ی تجاری در کد نیست**: پروایدر، مدل، قیمت، ابزار و پرامپت همه رکورد دیتابیس‌اند.
2. **خطاها کد دارند** (`{"error":{"code":"auth.invalid_credentials"}}`) و متن فارسی در فرانت ساخته می‌شود.
3. **جداسازی مستأجر** با PostgreSQL RLS (`app.org_id`) + فیلتر اپلیکیشنی.
4. **درگاه پرداخت** پشت `PaymentGateway` است؛ افزودن زرین‌پال = یک فایل + یک تنظیم.
