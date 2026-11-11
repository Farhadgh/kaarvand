# دموهای آماده (پنج سناریو)

همه‌ی دموها روی ماشین محلی و **بدون کلید واقعی AI** اجرا می‌شوند (پروایدر آزمایشی محلی).
پیش‌نیاز مشترک:

```powershell
python scripts\fake_provider.py        # پروایدر آزمایشی روی :8020
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -Reload   # API روی :8000
```

> دموها به‌طور پیش‌فرض به `http://127.0.0.1:8010` وصل می‌شوند؛ اگر API را روی ۸۰۰۰
> بالا آورده‌اید یا پورت را در `API` داخل اسکریپت عوض کنید یا API را روی ۸۰۱۰ اجرا کنید:
> `python -m uvicorn app.main:app --port 8010`

## دموی ۱ — پروایدر داینامیک

```powershell
python scripts\demo_provider_flow.py
```

می‌بینید: ساخت پروایدر → تست اتصال (`models_seen: 3`) → سینک ۳ مدل → سینک ۲ قیمت →
استنتاج قابلیت (vision/tools) → اجرای یک فراخوانی واقعی با هزینه‌ی تومان.

## دموی ۲ — پرامپت قابل ویرایش

```powershell
python scripts\demo_agent_flow.py
```

ایجنت «حسابدار ارشد» ساخته می‌شود؛ پرامپت سراسری رندر می‌شود؛ سپس نسخه‌ی سازمانی
override می‌کند، ویرایش → نسخه ۲ → بازگشت → نسخه ۳. **ایجنت دست نخورده، رفتار عوض شده.**

## دموی ۳ — اجرای ایجنت با ابزار و تأیید

```powershell
python scripts\demo_run_flow.py
```

ترتیب رخدادهای SSE: `run.started → llm.start → tool.call → tool.result → llm.start →
token… → run.completed`؛ سپس یک ابزار پرخطر → `waiting_approval` → `approve` → `completed`.

## دموی ۴ — کانکتور دسکتاپ

```powershell
python scripts\demo_connector_flow.py
```

دستگاه ساخته و جفت می‌شود، ۱۵ عملیات اعلام می‌کند، ابزار `fs.write` فایل
`گزارش فروش آبان ۱۴۰۵` را **واقعاً** روی دیسک می‌نویسد و تلاش برای نوشتن در
`C:\Windows\System32` با `PermissionError` بلاک می‌شود.

## دموی ۵ — ابزار HTTP و MCP

```powershell
python scripts\demo_tool_flow.py
```

۲۴ عملیات اسکریپت اقدام، ساخت ابزار HTTP از API یا پنل (`/apps` → «افزودن ابزار من»)،
اجرا و `response_map`، اتصال دو ابزار به ایجنت با سطوح دسترسی متفاوت، و ثبت یک سرور MCP.

## دموی ۶ — پنل فارسی (قدم ۷)

```powershell
# ترمینال ۱
python scripts\fake_provider.py          # پروایدر آزمایشی روی 8020

# ترمینال ۲
cd services\api; python -m uvicorn app.main:app --port 8000

# ترمینال ۳
cd apps\web; npm install; npm run dev     # http://localhost:3000
```

مسیر پیشنهادی برای نمایش:

1. ورود با `admin@openbot.local` / `admin12345` → داشبورد (کارت‌های مصرف، هزینه به تومان،
   اجراهای در انتظار تأیید).
2. `پروایدرها` → افزودن پروایدر با `http://127.0.0.1:8020/v1` → «تست» → «سینک مدل» →
   `مدل‌ها` → انتخاب `fake-chat` → «اجرا» (پاسخ و هزینه‌ی همان فراخوانی).
3. `ایجنت‌ها` → ساخت ایجنت → تب تنظیمات: انتخاب مدل → تب ابزارها: سطح دسترسی «با تأیید» →
   `آزمایشگاه` → ارسال پیام → کارت زرد تأیید → «تأیید و ادامه».
4. `اجراها` → انتخاب همان اجرا → مشاهده‌ی آرگومان/نتیجه‌ی هر فراخوانی ابزار.
5. `مصرف و هزینه` → بازه‌ی ۷/۳۰/۹۰ روز → «خروجی اکسل» (شیت RTL با تاریخ جلالی).
6. `تنظیمات` → تغییر نرخ ارز → بازگشت به داشبورد: هزینه‌های بعدی با نرخ جدید محاسبه می‌شوند.

## دموی ۷ — زمان‌بندی cron (قدم ۸)

```powershell
# ترمینال ۱ — worker زمان‌بند (جدا از API)
cd services\api; python -m app.workers.scheduler
```

1. `ایجنت‌ها` → یک ایجنت با مدل → کارت «وظایف و زمان‌بندی» → «وظیفه‌ی جدید»:
   نام + پرامپت + `* * * * *` (هر دقیقه) → «افزودن».
2. در جدول: ستون «اجرای بعدی» زمان جلالی را نشان می‌دهد؛ «اجرا» دکمه اجرای فوری است.
3. تا یک دقیقه صبر کنید: `اجراها` یک ردیف تازه با وضعیت تکمیل‌شده نشان می‌دهد.
4. برای اثبات «بدون اجرای تکراری»: در همان دقیقه دو بار `tick` بزنید —

```powershell
cd services\api
python -c "import asyncio; from app.workers.scheduler import tick; print(len(asyncio.run(tick())))"
```

بار اول `1` و بار دوم `0` برمی‌گرداند.
5. اگر «نیازمند تأیید» را تیک بزنید، اجرا در `waiting_approval` می‌ماند و از صفحه‌ی
   اجراها با «تأیید» شروع می‌شود.

## دموی ۸ — اتصال برنامه از پنل (قدم ۹)

1. منوی **برنامه‌ها** (`/apps`) → تب «شبکه‌های اجتماعی» → کارت **تلگرام** → «اتصال».
2. ویزارد: ایجنت را انتخاب کنید، توکن ربات (از BotFather) و `chat_id` را وارد کنید، سطح
   دسترسی را روی «با تأیید» بگذارید → «اتصال برنامه».
3. صفحه‌ی همان ایجنت → کارت **«برنامه‌ها و شبکه‌ها»**: تلگرام با لوگو و سطح دسترسی دیده می‌شود.
4. `ابزارها` → ابزار `telegram.<agent8>` → «تست ابزار» با
   `{"chat_id": "...", "text": "سلام"}` → پیام واقعی می‌رود.
5. اجرای ایجنت: مدل ابزار را صدا می‌زند؛ چون `confirm` است، اجرا در «در انتظار تأیید» می‌ماند.

**برنامه‌ی روی دستگاه (اکسل/تلگرام دسکتاپ):**

```powershell
cd services\api; python scripts\..\..\scripts\connector_client.py `
  --server http://127.0.0.1:8000 --code <کد جفت‌سازی> --allow-dir D:\data
```

1. `/devices` → «اسکن برنامه‌ها» روی دستگاه → فهرست برنامه‌های شناسایی‌شده + «مجاز کن».
2. `/apps` → تب «برنامه‌های ویندوز» → اکسل → انتخاب دستگاه → اتصال.
3. اجرا با تأیید: گام‌ها روی دستگاه اجرا می‌شوند و در `tool_invocations` ثبت می‌شوند.

**افزودن ابزار دلخواه:** `/apps` → «+ افزودن ابزار من» → حالت HTTP یا اسکریپت دستگاه →
JSON را پر کنید → «افزودن». ابزار بلافاصله در `/tools` و در کارت ابزارهای ایجنت ظاهر می‌شود.

## دموی ۹ — دریافت پیام و پاسخ خودکار (قدم ۱۰)

**۱) آماده‌سازی:** در `/apps` برنامه **تلگرام** را برای ایجنتی که مدل دارد نصب کنید (توکن ربات).

**۲) ساخت کانال:** `/channels` → «+ کانال جدید» → تلگرام، همان ایجنت، ابزار پاسخ =
`telegram.<agent8>`، حالت پاسخ = «ارسال خودکار»، Secret Token = یک رشته‌ی دلخواه مثل
`demo-secret-123`.

**۳) ثبت وبهوک:** آدرس کپی‌شده از کارت کانال را در تلگرام ثبت کنید
(برای تست محلی: `ngrok http 8000` و آدرس عمومی):

```powershell
$token = "<توکن ربات>"
Invoke-RestMethod "https://api.telegram.org/bot$token/setWebhook" -Method Post `
  -Body @{ url = "https://<ngrok>/v1/inbound/telegram/<slug>"; secret_token = "demo-secret-123" }
```

**۴) پیام بفرستید.** در `/channels` شمارنده‌ی «رویدادها» بالا می‌رود؛ «رویدادها» را بزنید:
ردیف با وضعیت `accepted`/`completed` و ستون پاسخ `sent`. در `اجراها` یک ردیف با تریگر
`webhook` می‌بینید؛ در `ابزارها` یک invocation برای `sendMessage`.

**تست بدون تلگرام واقعی (curl):**

```powershell
$body = '{"update_id":1001,"message":{"message_id":1,"from":{"id":555},"chat":{"id":555},"text":"سلام"}}'
Invoke-RestMethod "http://127.0.0.1:8000/v1/inbound/telegram/<slug>" -Method Post `
  -Headers @{ "X-Telegram-Bot-Api-Secret-Token" = "demo-secret-123" } `
  -ContentType "application/json" -Body ([Text.Encoding]::UTF8.GetBytes($body))
# → {"ok":true,"status":"accepted","run_id":"..."} ؛ تکرار همان update_id → "duplicate"
```

## دموی ۱۰ — تست وبهوک از خود پنل (قدم ۱۱)

بدون گوشی، بدون تلگرام، بدون ngrok:

1. `/apps` → **تلگرام** → متصل به یک ایجنت (توکن هر رشته‌ای).
2. `/channels` → «+ کانال جدید» → تلگرام، همان ایجنت، ابزار پاسخ = `telegram.<agent8>`،
   حالت پاسخ = «ارسال خودکار»، Secret Token = `demo-secret-123`.
3. در کارت کانال **«تست وبهوک»** را بزنید: یک پیام ساختگی از همان مسیر اجرا می‌شود و نتیجه
   (اجرا، پاسخ، متن ایجنت، لینک اجرا) همان‌جا می‌آید.
   - اگر ابزار/ایجنت نیاز به تأیید داشته باشد: کادر **کهربایی** «در انتظار تأیید» با لینک اجرا.
   - در حالت عادی: کادر **سبز** با `run=completed` و `reply=sent`.
4. **«ثبت وبهوک در تلگرام»**: سرور خودش `setWebhook` را با توکن همان ابزار صدا می‌زند.
   روی سرور عمومی: `APP_PUBLIC_BASE_URL=https://your-domain` را ست کنید تا آدرس درست ساخته شود؛
   بدون آن، پنل هشدار «آدرس محلی است» می‌دهد.

معادل خط فرمان:

```powershell
$api = "http://127.0.0.1:8000"
$login = Invoke-RestMethod "$api/v1/auth/login" -Method Post -ContentType 'application/json' `
  -Body '{"email":"admin@openbot.local","password":"admin12345"}'
$h = @{ Authorization = "Bearer $($login.access_token)" }
$ch = (Invoke-RestMethod "$api/v1/channels" -Headers $h)[0]
Invoke-RestMethod "$api/v1/channels/$($ch.id)/test" -Method Post -Headers $h -ContentType 'application/json' -Body '{}'
Invoke-RestMethod "$api/v1/channels/$($ch.id)/register-webhook" -Method Post -Headers $h
```

## اجرای تست‌ها

```powershell
cd services\api
$env:PYTHONIOENCODING='utf-8'
python -m pytest -q            # ۲۳۷ تست
python -m ruff check app tests # صفر خطا
python scripts\check_schema.py # رفت‌وبرگشت مایگریشن + گزارش RLS

cd ..\..\apps\web
npx tsc --noEmit               # typecheck پنل
npm run build                  # ۱۶ مسیر
```

## چه چیزی در دموها پوشش داده نمی‌شود

| مورد | دلیل |
|---|---|
| فراخوانی پروایدر واقعی (OpenAI/Anthropic/…) | نیاز به کلید کاربر |
| ابزار واقعی تلگرام/اینستاگرام | نیاز به توکن |
| Office/COM/چاپ واقعی روی ویندوز | کانکتور مرجع این گام‌ها را شبیه‌سازی می‌کند |
| تماس تلفنی | ماژول صدا در roadmap |
| محیط چند-worker | هاب درون‌پروسه است |
