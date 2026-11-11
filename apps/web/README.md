# پنل وب OpenBot

پنل مدیریت فارسی (RTL، تقویم جلالی، تومان) روی Next.js 15.

## اجرا

```powershell
# ۱) بک‌اند
cd services/api
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# ۲) پنل
cd apps/web
npm install
npm run dev        # http://localhost:3000
```

آدرس بک‌اند با `API_BASE_URL` تنظیم می‌شود (پیش‌فرض `http://127.0.0.1:8000`).
ورود پیش‌فرض محیط توسعه: `admin@openbot.local` / `admin12345`.

## معماری

```
مرورگر ──► Next.js (Server Components) ──► FastAPI
   │              ▲
   └── /api/* ────┘   BFF: کوکی httpOnly → Bearer، رفرش خودکار، استریم SSE
```

- توکن JWT هرگز به مرورگر نمی‌رسد؛ فقط کوکی `httpOnly` (`ob_access` / `ob_refresh`).
- مسیر `app/api/[...path]/route.ts` پروکسی عمومی است: هدر `Authorization` را می‌سازد،
  در صورت `401` یک‌بار با refresh token توکن را می‌چرخاند و جریان SSE را بدون بافر عبور می‌دهد.
- فرم‌ها و دکمه‌ها با `clientFetch` روی همان پروکسی کار می‌کنند؛ داده‌ها در Server Components
  با `serverFetch` گرفته می‌شود (بدون آبشار درخواست در مرورگر).

## ساختار

| مسیر | توضیح |
| --- | --- |
| `app/(auth)/login` | ورود |
| `app/(panel)/` | داشبورد (`/usage/summary`) |
| `app/(panel)/playground` | اجرای ایجنت با SSE + کارت تأیید انسانی |
| `app/(panel)/agents/[id]` | تنظیمات، ابزارها، وظایف، پیش‌نمایش پرامپت |
| `app/(panel)/providers`,`/models` | پروایدر/مدل، سینک، تست، قیمت |
| `app/(panel)/prompts` | ویرایشگر نسخه‌دار پرامپت + بازگردانی |
| `app/(panel)/tools`,`/devices` | رجیستری ابزار و کانکتور دسکتاپ |
| `app/(panel)/runs` | لیست/جزئیات اجرا + تأیید + فراخوانی ابزارها |
| `app/(panel)/usage` | گزارش مصرف + خروجی اکسل |
| `app/(panel)/users`,`/settings` | کاربران، سازمان، نرخ ارز |

## قواعد فارسی‌سازی

- همه‌ی متن‌ها از `lib/copy.ts` و `lib/errors-fa.ts` می‌آیند (کلید خطا → جمله‌ی فارسی).
- اعداد با `lib/format.ts` به ارقام فارسی و جداکننده‌ی `٬` تبدیل می‌شوند.
- مبالغ در دیتابیس «ریال» ذخیره می‌شوند و در پنل «تومان» نشان داده می‌شوند (`formatMoney`).
- تاریخ‌ها با تبدیل جلالی داخلی (`lib/format.ts`) و ساعت به وقت `Asia/Tehran`.
- شناسه‌ها و JSON با کلاس `ltr` چپ‌به‌راست نمایش داده می‌شوند تا در RTL نشکنند.

## محدودیت‌های فعلی

- تک‌زبانه (fa)؛ لایه‌ی i18n چندزبانه اضافه نشده است.
- نمودارها CSS-محور هستند (بدون کتابخانه‌ی چارت).
- تست E2E مرورگری ندارد؛ صحت با build + typecheck + بررسی دستی صفحات تأیید می‌شود.
