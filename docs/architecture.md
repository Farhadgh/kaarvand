# معماری

## ۱) نمای کلی

```
                         ┌───────────────────────────┐
   مرورگر (فارسی/RTL)    │  پنل Next.js  (قدم ۷)      │
                         │  BFF: کوکی httpOnly        │
                         └────────────┬──────────────┘
                                      │ REST + SSE
┌─────────────────────────────────────▼──────────────────────────────────────┐
│ FastAPI  (services/api)                                                     │
│                                                                             │
│  api/v1/   auth · providers · models · prompts · agents · tools · runs ·     │
│            devices · connector_ws · billing · meta                          │
│                                                                             │
│  runtime/  engine.py (حلقه‌ی tool-calling) · budget.py · tools_binding.py     │
│  providers/ gateway.py · registry.py · adapters/{openai,anthropic,gemini,     │
│            declarative} · sync.py · capabilities.py                          │
│  tools/    service.py · policy.py · http_exec.py · mcp.py · builtin.py        │
│  connector/ hub.py · pairing.py · executor.py                                │
│  prompts/  render.py · service.py        agents/ workflow.py · service.py    │
│  billing/  cost.py · gateway.py (پورت) · noop.py                             │
│  core/     config · errors · security · crypto · jalali · text_fa · deps     │
└───────────┬─────────────────────────┬───────────────────────┬───────────────┘
            │ SQLAlchemy async        │ WebSocket (خروجی)      │ HTTPS
      ┌─────▼──────┐            ┌─────▼────────────┐   ┌──────▼─────────────┐
      │ PostgreSQL │            │ کانکتور ماشین     │   │ پروایدرهای مدل      │
      │ 16+pgvector│            │ (اکسل/فایل/چاپ/… )│   │ OpenAI/Anthropic/…  │
      │ +RLS       │            └──────────────────┘   └────────────────────┘
      └────────────┘
```

## ۲) جریان یک درخواست اجرا (مهم‌ترین مسیر)

```
POST /v1/agents/{id}/runs
  ├─ احراز: JWT → org_id → SET LOCAL app.org_id  (RLS)
  ├─ ساخت رکورد Run (status=queued) و commit
  ├─ session مستقل موتور باز می‌شود (RunEngine)
  │    ├─ load_context: agent/org/user از شناسه‌ها
  │    ├─ effective_prompt: پرامپت سازمان > سراسری، رندر با {{org.name}}/{{today_jalali}}
  │    ├─ ensure_budget: مصرف ماه جلالی < سقف
  │    └─ messages = [system, history…, user]
  ├─ حلقه (حداکثر ۸ گام):
  │    ├─ stream_model → SSE: text/tool_call/usage/error
  │    ├─ اگر tool_call داشت:
  │    │    ├─ policy.decide(risk × permission × approval_policy)
  │    │    ├─ deny → نتیجه‌ی خطا به مدل
  │    │    ├─ confirm → state.pending در DB + status=waiting_approval + توقف
  │    │    └─ allow → execute_tool (builtin/http/mcp/connector) → نتیجه به مدل
  │    └─ بدون tool_call → پاسخ نهایی
  └─ finish: قیمت × markup × نرخ ارز → usage_ledger + messages + status=completed
```

**تأیید انسانی:** `POST /v1/runs/{id}/approve` همان state ذخیره‌شده را برمی‌دارد،
ابزارهای pending را با `force=True` اجرا می‌کند و حلقه را ادامه می‌دهد.

## ۳) تصمیم‌های فنی و دلیلشان

| تصمیم | دلیل | جایگزینی که رد شد |
|---|---|---|
| موتور اجرای اختصاصی، نه LangGraph | state باید در DB و قابل بازپخش/حسابرسی باشد؛ وابستگی سنگین در هسته‌ی محصول ریسک است | LangGraph (ایمپورت سنگین، state مخفی) |
| استریم بومی با httpx، نه SDK/LiteLLM | تجربه‌ی واقعی: `import litellm` = ۳۹ ثانیه؛ الآن استارتاپ فوری است | litellm در مسیر داغ (فقط به‌عنوان جدول قیمت اختیاری) |
| `trust_env=False` در همه‌ی کلاینت‌های خروجی | پروکسی سیستمی (رایج در ایران) نباید ترافیک مدل را بی‌صدا تغییر دهد؛ پروکسی per-provider از `meta.proxy` | رفتار پیش‌فرض httpx |
| همه‌چیز در DB: پروایدر، مدل، قیمت، پرامپت، ابزار | الزام محصول: افزودن بدون کد + تست ضدرگرسیون | فایل کانفیگ/کد |
| RLS + نقش غیرسوپریوزر | جداسازی سخت مستأجر، حتی در برابر باگ کوئری | فقط فیلتر در لایه‌ی اپ |
| موتور با session مستقل | commitهای میان‌درخواستی، آبجکت‌های درخواست را expire می‌کردند | استفاده از session درخواست |
| فایل‌های env نسبت به پکیج | اسکریپت‌ها از ریشه هم درست کار کنند | path نسبی به cwd |
| پیام خطا = کد، نه متن | i18n واقعی و تست‌پذیری | پیام فارسی در API |

## ۴) نقشه‌ی ماژول‌ها

| مسیر | مسئولیت | به کدام وابسته نیست |
|---|---|---|
| `core/` | تنظیمات، خطا، امنیت، رمزنگاری، جلالی، متن فارسی | به هیچ ماژول دامنه‌ای |
| `db/` | Base، مدل‌ها، session + تنانت | به API |
| `providers/` | کشف مدل/قیمت، استریم، fallback | به runtime |
| `tools/` | رجیستری، سیاست، اجرا، MCP | به runtime |
| `connector/` | جفت‌سازی، هاب، اجرای اسکریپت | به tools |
| `runtime/` | حلقه‌ی ایجنت، بودجه، اتصال ابزار | به api |
| `api/v1/` | لایه‌ی HTTP نازک | — |

## ۵) نقطه‌های توسعه (بدون تغییر معماری)

| می‌خواهید… | کجا |
|---|---|
| پروتکل پروایدر جدید | `providers/adapters/` یک کلاس، یا `kind=declarative` بدون کد |
| نوع ابزار جدید | `tools/` یک executor + `Tool.kind` |
| عملیات کانکتور جدید | `tools/actions.py` (کاتالوگ) + `op` در کانکتور |
| نوع نود گراف جدید | `agents/workflow.py` رجیستری |
| درگاه پرداخت | `billing/gateway.py` (پورت) + ثبت در `GATEWAYS` |
| گزارش مصرف | `usage_ledger` + endpoint جدید |

## ۶) لایه‌ی پنل (قدم ۷)

```
مرورگر ──► Next.js Server Component ──► FastAPI      (serverFetch + کوکی httpOnly)
   │                 ▲
   └── /api/* ───────┘   BFF: Bearer از کوکی، رفرش خودکار، عبور SSE بدون بافر
```

| تصمیم | دلیل |
|---|---|
| JWT در کوکی `httpOnly` + BFF به‌جای تماس مستقیم مرورگر با API | هیچ توکنی در `localStorage`/JS نیست؛ XSS نمی‌تواند توکن بدزدد |
| پروکسی عمومی `app/api/[...path]/route.ts` | یک نقطه برای احراز، چرخش توکن، CORS و استریم |
| بیشتر صفحه‌ها Server Component | داده‌ی اولیه در سرور گرفته می‌شود؛ آبشار درخواست در مرورگر حذف می‌شود |
| فقط اکشن‌ها Client Component | کمترین کد کلاینت؛ `router.refresh()` پس از هر تغییر |
| متن‌ها در `lib/copy.ts` + `lib/errors-fa.ts` | بک‌اند فقط کد خطا می‌دهد؛ جمله‌ی فارسی یک‌جا نگهداری می‌شود |
| تبدیل جلالی/ارقام در `lib/format.ts` | بدون وابستگی سنگین تقویم؛ همان الگوریتم بک‌اند |

## ۷) زمان‌بند (قدم ۸)

```
agent_tasks ──► scheduler worker (cron) ──► runs(trigger="task") ──► همان موتور اجرا
```

| تصمیم | دلیل |
|---|---|
| پارسر cron اختصاصی (`runtime/cron.py`) بدون `croniter` | وابستگی صفر؛ همان کد در API (`next_run_at`) و worker |
| worker جدا از API (`python -m app.workers.scheduler`) | ری‌استارت API اجرای در جریان را نمی‌کشد |
| advisory lock + claim اتمیک `last_run_at` | تک‌مجرا شدن و صفر شدن اجرای تکراری، حتی با چند نمونه |
| رد کردن وظیفه‌ی دارای اجرای فعال | جلوگیری از انبار شدن اجراها |
| وظیفه‌ی `requires_approval` در `waiting_approval` پارک می‌شود | همان مسیر تأیید انسانی، بدون کد جدید |
| شروع اجرا با «مالک سازمان» وقتی تریگر انسانی ندارد | موتور و بودجه به کاربر وابسته‌اند |

## ۸) کاتالوگ برنامه‌ها (قدم ۹)

```
app_catalog (قالب) ──install──► tools (کپی سازمانی) ──binding──► agent_tools ──► همان حلقه‌ی اجرا
                                   ▲
device_tools ◄── apps.scan ── connector (روی دستگاه مشتری)
```

| تصمیم | دلیل |
|---|---|
| کاتالوگ یک **جدول داده** است، نه فهرست کد | افزودن واتساپ/تلگرام/اکسل تازه = یک ردیف، بدون دیپلوی |
| «نصب» = کپی قالب در `tools` | موتور اجرا، ماتریس ریسک، تأیید و دفتر مصرف دست‌نخورده می‌مانند |
| `slug` ابزار = `<app>.<agent8>` | یک ابزار به‌ازای هر (برنامه، ایجنت) و نصب دوباره = به‌روزرسانی |
| `{{secret}}` در قالب می‌ماند و در زمان اجرا پر می‌شود | اعتبارنامه هرگز داخل `config` ذخیره نمی‌شود |
| قاعده‌ی تشخیص برنامه در سرور است و به کانکتور فرستاده می‌شود | کانکتور بدون آپدیت، برنامه‌های تازه را می‌شناسد |
| `app.launch` فقط slug می‌گیرد | مدل نمی‌تواند فایل اجرایی دلخواه را اجرا کند |
| `device_tools` برای «کشف‌شده‌ها» + `is_granted` | تفکیک «نصب است» از «اجازه‌ی استفاده دارد» |

## ۹) استقرار

| محیط | اجزا |
|---|---|
| توسعه | PostgreSQL تعبیه‌شده (`pgserver`) + uvicorn + `scripts/dev.ps1` + `npm run dev` |
| عملیاتی | PostgreSQL 16 + pgvector، ۲+ worker uvicorn، Next.js (`npm run build`), Caddy/Nginx، بکاپ روزانه |
| چند-worker | ⚠️ هاب کانکتور درون‌پروسه است → bus مشترک لازم است (roadmap) |
