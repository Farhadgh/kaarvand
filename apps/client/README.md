# کلاینت کاروند (دسکتاپ + اندروید)

یک کدبیس React + Vite که در سه شکل اجرا می‌شود:

| خروجی | ابزار | فایل بیلد |
|---|---|---|
| وب (فقط برای تست/دمو) | `npm run build` | `dist/` |
| ویندوز | Electron + electron-builder | `release/Kaarvand-Setup-<version>.exe` |
| اندروید | Capacitor + Gradle | `android/app/build/outputs/apk/debug/app-debug.apk` |

## اجرای محلی

```powershell
cd apps/client
npm install
copy .env.example .env        # VITE_API_BASE_URL را روی آدرس API بگذارید
npm run dev                   # http://localhost:5173
```

برای اجرای همان صفحه داخل پنجرهٔ Electron:

```powershell
$env:VITE_DEV_SERVER_URL="http://localhost:5173"
npm run desktop
```

## ساخت بدون نصب هیچ ابزاری (گیت‌هاب اکشنز)

هیچ‌کدام از این دو کار به JDK، Android SDK، Rust یا Visual Studio روی سیستم شما نیاز ندارد:

| workflow | خروجی | محل دریافت |
|---|---|---|
| `.github/workflows/android.yml` | `app-debug.apk` | Actions → artifact «kaarvand-debug-apk» |
| `.github/workflows/desktop.yml` | `Kaarvand-Setup-*.exe` | Actions → artifact «kaarvand-windows-installer» |

هر دو با `workflow_dispatch` دستی اجرا می‌شوند و با ساختن تگ `v*` همان فایل‌ها به
GitHub Release چسبانده می‌شوند (لینک پایدار برای صفحهٔ دانلود).

APK نسخهٔ **debug** است: بدون keystore نصب می‌شود ولی برای انتشار در مارکت‌ها باید
نسخهٔ signed ساخته شود (فاز ۹ب).

## متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | آدرس API بدون `/` انتهایی. برای تولید: `https://kaarvand.amigok.cloud` (همان دامنه‌ای که `/v1/` را سرو می‌کند) |

> مقدار در زمان **build** پخته می‌شود؛ در GitHub Actions از
> `vars.VITE_API_BASE_URL` خوانده می‌شود و اگر ست نشده باشد روی
> `https://kaarvand.amigok.cloud` می‌افتد. برای عوض‌کردن دامنه، همان متغیر مخزن را
> ست کنید و workflow را دوباره اجرا کنید.

## ساختار

```
src/lib/api.ts        فراخوانی API + رفرش خودکار توکن
src/lib/auth.ts       نگهداری نشست (localStorage)
src/lib/money.ts      ریال→تومان، ارقام فارسی، نرمال‌سازی شماره
src/lib/desktop.ts    پل دسکتاپ/موبایل: بازکردن مرورگر، deep-link «kaarvand://»
src/lib/errors-fa.ts  ترجمهٔ کدهای خطای API به فارسی
src/pages/Login.tsx   ورود با موبایل + OTP
src/pages/Home.tsx    کیف پول و ورودی بخش‌ها
src/pages/Models.tsx  کاتالوگ مدل‌ها با قیمت تومانی (بدون نام پروایدر)
src/pages/Wallet.tsx  موجودی، شارژ با زرین‌پال، تاریخ تراکنش‌ها
electron/main.cjs     پنجره، deep-link «kaarvand://»، بازکردن لینک در مرورگر سیستم
electron/preload.cjs  سطح تماس محدود (contextBridge)
capacitor.config.ts   appId: cloud.amigok.kaarvand
```

## امنیت

توکن‌ها در `localStorage` نگه داشته می‌شوند (در Electron با `contextIsolation` و
`sandbox` و در اندروید داخل WebView اختصاصی). برای سخت‌سازی بیشتر در فاز بعد:
`safeStorage` در Electron و `@capacitor/preferences` در اندروید.
