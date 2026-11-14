# مرجع API

پیشوند همه‌ی مسیرها: `/v1` — مستند تعاملی: `GET /docs` (Swagger) و `GET /openapi.json`.

## ۰) قراردادهای عمومی

| موضوع | قاعده |
|---|---|
| احراز | `Authorization: Bearer <access_token>` |
| خطا | `{"error": {"code": "provider.sync_failed", "params": {...}}}` + کد HTTP مناسب |
| تاریخ | ISO‑8601 با timezone (UTC ذخیره، نمایش جلالی در فرانت) |
| صفحه‌بندی | `limit` (پیش‌فرض ۵۰) و `offset` |
| شناسه‌ها | UUID |
| `X-Request-Id` | در همه‌ی پاسخ‌ها برمی‌گردد و در لاگ‌ها هست |
| Rate limit | فعلاً وجود ندارد (roadmap) |

**کدهای وضعیت پرکاربرد:** ۲۰۰/۲۰۱/۲۰۴ · ۴۰۱ احراز · ۴۰۳ نقش یا سیاست · ۴۰۴ نبود
· ۴۰۵ (کار ندارد) · ۴۰۹ تعارض/تأیید لازم · ۴۲۲ اعتبارسنجی · ۵۰۲ خطای پروایدر/دستگاه · ۵۰۴ timeout دستگاه

## ۱) سلامت و متادیتا

| متد | مسیر | توضیح |
|---|---|---|
| GET | `/healthz` | `{status, db, version}` — برای orchestrator |
| GET | `/v1/healthz` | همان، در نسخه‌ی API |
| GET | `/v1/meta` | locale/calendar/currency/digits، `free_mode`, `billing_enabled`, `payment_gateway`, `fx_usd_irr` |

```json
GET /v1/meta
{"app_name":"OpenBot API","version":"0.1.0","env":"dev","locale":"fa",
 "timezone":"Asia/Tehran","calendar":"jalali","currency":"IRR","digits":"fa",
 "free_mode":true,"billing_enabled":false,"payment_gateway":"noop",
 "payment_gateway_enabled":false,"fx_usd_irr":1000000,"api_prefix":"/v1"}
```

## ۲) احراز هویت

دو مسیر ورود وجود دارد: **موبایل + OTP** برای مشتری، **ایمیل + رمز** برای ادمین پلتفرم.
هر دو یک جفت توکن یکسان برمی‌گردانند.

| متد | مسیر | بدنه/خروجی |
|---|---|---|
| POST | `/v1/auth/otp/request` | `{phone}` → `{sent, expires_in, resend_in, sms_delivered, debug_code?}` |
| POST | `/v1/auth/otp/verify` | `{phone, code}` → `{access_token, refresh_token, token_type, expires_in, is_new_user, user}` |
| POST | `/v1/auth/login` | `{email, password, org_slug?}` → `{access_token, refresh_token, token_type, expires_in, user}` |
| POST | `/v1/auth/refresh` | `{refresh_token}` → جفت توکن جدید (توکن قبلی باطل می‌شود) |
| GET | `/v1/auth/me` | کاربر فعلی |
| POST | `/v1/auth/logout` | `{refresh_token?}` → `{ok: true}` |

قواعد OTP: کد ۵ رقمی، اعتبار ۱۲۰ ثانیه، ارسال دوباره پس از ۶۰ ثانیه، حداکثر ۵ تلاش،
سقف ۱۰ پیامک در روز برای هر شماره و ۳۰ برای هر IP. شماره‌های `۰۹۱۲…`، `+98912…` و `0098912…`
همه به شکل `09xxxxxxxxx` نرمال می‌شوند. اگر `APP_SMS_ENABLED=false` باشد، کد در لاگ سرور
(و در صورت `APP_OTP_DEBUG_CODE=true` در پاسخ) دیده می‌شود.

**ارسال پیامک (ایران‌پیامک / FarazSMS v2 — https://docs.iranpayamak.com):** کلید در هدر
`Api-Key` و بدنهٔ پاسخ تعیین‌کننده است، نه کد HTTP (خطاها معمولاً با `200` و
`{"status":"error"}` می‌آیند):

| مسیر | کاربرد |
|---|---|
| `POST /ws/v1/sms/pattern` | الگوی تأییدشده: `{code, recipient, attributes:{code}, line_number, number_format}` — روش اصلی OTP |
| `POST /ws/v1/sms/simple` | متن آزاد (فقط آزمایشی؛ در خطوط اشتراکی «در انتظار تأیید» می‌ماند) |
| `GET /ws/v1/account/balance` · `/ws/v1/lines/accessible` · `/ws/v1/patterns` | بررسی اعتبار، خطوط و الگوها |

> **الگو باید approved باشد:** تا وقتی الگوی `%code%` تأیید نشده، `/ws/v1/sms/pattern` با
> «داده درخواستی یافت نشد» رد می‌شود و `sms_delivered:false` برمی‌گردد. بررسی سریع:
> `python -m app.cli sms-check` و ارسال آزمایشی: `python -m app.cli sms-test 0912…`.

خطاها: `auth.invalid_phone` · `auth.invalid_credentials` · `auth.org_not_found` · `auth.user_inactive` ·
`auth.missing_token` · `auth.token_expired` · `auth.session_expired` · `auth.insufficient_role` ·
`otp.code_invalid` · `otp.code_expired` · `otp.code_not_found` · `otp.too_many_requests` ·
`otp.too_many_attempts` · `otp.daily_limit`

## ۲.۱) کیف پول و شارژ با زرین‌پال

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| GET | `/v1/wallet` | user | `{balance_irr, balance_toman, currency, is_enabled, usd_irr, markup_percent, min_topup_irr, min_topup_toman, topup_enabled}` |
| GET | `/v1/wallet/transactions?limit=50` | user | صورت‌حساب (هر ردیف `amount_irr` + `amount_toman`) |
| POST | `/v1/wallet/topup` | user | `{amount_toman, description_fa?}` → `{payment_id, amount_irr, amount_toman, gateway, authority, redirect_url, status}` |
| GET | `/v1/wallet/payments?limit=20` | user | پرداخت‌های خود کاربر |
| GET | `/v1/wallet/topup/callback?Authority=…&Status=OK\|NOK` | عمومی | بازگشت درگاه؛ پاسخ **۳۰۳** به `APP_PAYMENT_RETURN_URL` (`kaarvand://wallet?status=paid&payment=…&ref=…`) |
| GET | `/v1/payments?status=&user_id=&limit=` | admin | حسابداری: همهٔ پرداخت‌ها + نام/موبایل کاربر |
| GET | `/v1/payments/summary?days=30` | admin | `paid_count/paid_irr`، `pending_count`، `failed_count`، `canceled_count`، `today_paid_irr` |
| POST | `/v1/payments/{id}/verify` | admin | استعلام دستی از درگاه برای پرداخت جامانده (callback گم‌شده)؛ تکرارش موجودی را دوباره زیاد نمی‌کند |

```json
POST /v1/wallet/topup   {"amount_toman": 200000}
→ 201 {"payment_id":"…","amount_irr":2000000,"amount_toman":200000,
       "gateway":"zarinpal","authority":"A000…","status":"pending",
       "redirect_url":"https://payment.zarinpal.com/pg/StartPay/A000…"}
```

قواعد:
- موجودی به **ریال** ذخیره می‌شود (واحد زرین‌پال) و کلاینت آن را به تومان نشان می‌دهد.
  ورودی API تومان است و یک‌بار در سرور تبدیل می‌شود.
- مبلغ کمتر از `APP_MIN_TOPUP_IRR` (پیش‌فرض ۱۰٬۰۰۰ تومان) → `422 wallet.amount_below_min`.
- پرداخت فقط با `Status=OK` **و** تأیید `verify` (کد `100` یا `101`) و **یک‌بار** کیف پول را شارژ
  می‌کند؛ تکرار callback (رفرش صفحه) موجودی را دوباره زیاد نمی‌کند.
- `Status=NOK` → `canceled`، تأیید ناموفق → `failed`؛ هیچ‌کدام موجودی نمی‌سازند.
- با `APP_PAYMENT_GATEWAY=noop` (پیش‌فرض) پاسخ `409 billing.disabled` است و
  `topup_enabled=false` در کیف پول برمی‌گردد.

خطاها: `wallet.amount_below_min` · `wallet.disabled` · `wallet.insufficient_balance` ·
`billing.disabled` · `billing.gateway_not_configured` · `billing.gateway_unreachable` ·
`billing.gateway_error` · `billing.gateway_bad_response` · `payment.not_found` ·
`payment.amount_mismatch` · `payment.missing_authority`

## ۳) پروایدرها

> داده‌های پروایدر **فقط برای ادمین** است؛ مشتری هرگز نام پروایدر، کلید یا قیمت دلاری را نمی‌بیند.

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| GET | `/v1/provider-adapters` | admin | کاتالوگ ۱۲ آداپتور با عنوان فارسی |
| GET | `/v1/providers` | admin | فهرست سازمان |
| POST | `/v1/providers` | admin | ساخت؛ کلید رمزنگاری می‌شود |
| GET | `/v1/providers/{id}` | admin | جزئیات + `has_credentials`, `api_key_masked` |
| PATCH | `/v1/providers/{id}` | admin | ویرایش؛ `api_key` جدید = چرخش کلید |
| DELETE | `/v1/providers/{id}` | admin | حذف همراه مدل‌ها |
| POST | `/v1/providers/{id}/test` | admin | تست اتصال + شمارش مدل‌ها |
| POST | `/v1/providers/{id}/sync-models` | admin | `{created, updated, total}` |
| POST | `/v1/providers/{id}/sync-prices` | admin | `{updated, source}` |


```json
POST /v1/providers
{"name":"اوپن‌روتر","kind":"openrouter","base_url":"https://openrouter.ai/api/v1",
 "api_key":"sk-or-...", "priority":10}
→ 201 {"id":"…","slug":"openrouter","kind":"openrouter","health":"unknown",
       "has_credentials":true,"api_key_masked":"sk-o…4f2a", …}
```

انواع `kind`: `openai` · `openai_compatible` · `openrouter` · `anthropic` · `gemini` ·
`azure_openai` · `groq` · `deepseek` · `mistral` · `together` · `ollama` · `declarative`

برای `declarative` دو فیلد `chat_spec` و `response_map` (JSON) می‌آید — نمونه در
[tool-contract.md](tool-contract.md) — بخش «آداپتور توصیفی پروایدر».

## ۴) مدل‌ها

> `/v1/models` **فقط ادمین** است (قیمت دلاری، شناسهٔ پروایدر و وضعیت سینک). مشتری از
> `/v1/catalog/models` استفاده می‌کند که همان مدل‌ها را با **نام فارسی و قیمت تومانی** و
> بدون هیچ نشانی از پروایدر برمی‌گرداند.

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| GET | `/v1/models` | admin | فیلتر: `provider_id`, `capability=tools|vision|audio|reasoning|stream`, `q`, `enabled_only`, `limit`, `offset` |
| GET | `/v1/models/{id}` | admin | جزئیات |
| PATCH | `/v1/models/{id}` | admin | نام فارسی، فعال/غیرفعال، markup، context، قابلیت‌ها |
| POST | `/v1/models/{id}/price` | admin | قیمت دستی + ثبت در تاریخچه |
| GET | `/v1/models/{id}/prices` | admin | تاریخچه‌ی قیمت |
| POST | `/v1/models/{id}/probe` | admin | یک فراخوانی واقعی: متن + توکن + هزینه‌ی دلار و تومان |
| GET | `/v1/catalog/models` | user | کاتالوگ مشتری: فیلتر `capability`, `modality=text|image|audio`, `family`, `q` |
| GET | `/v1/catalog/models/{id}` | user | جزئیات همان کاتالوگ |

```json
GET /v1/catalog/models?capability=vision
[{"id":"…","name":"جمینای ۲.۵ پرو","family":"gemini","context_window":1000000,
  "modalities":["text","image"],"capabilities":["tools","vision","stream"],
  "audio_kind":null,"billing_unit":"per_1m_tokens",
  "price_input_toman":52000,"price_output_toman":130000,"price_known":true}]
```

**قیمت فروش** = قیمت دلاری × نرخ ارز × (۱ + حاشیهٔ سود) ÷ ۱۰، نمایش به‌صورت
«تومان برای هر ۱ میلیون توکن» (صدا: هر دقیقه / هر ۱۰۰۰ کاراکتر). حاشیهٔ سود مدل
(`markup_percent`) اولویت دارد؛ اگر صفر باشد `APP_PLATFORM_MARKUP_PERCENT` (پیش‌فرض ۳۰٪)
اعمال می‌شود — همان تابعی که صورتحساب اجرا از آن استفاده می‌کند، پس قیمت نمایشی و
قیمت کسرشده یکی است.

هیچ‌کدام از این‌ها در پاسخ مشتری نیست: `provider_id`, نام/`base_url` پروایدر،
`input_price`/`output_price` دلاری، `price_currency`, `price_source`, `external_id`,
`markup_percent`. مدل غیرفعال یا پروایدر غیرفعال در کاتالوگ دیده نمی‌شود (و جزئیاتش ۴۰۴).


```json
POST /v1/models/9f…/probe {"prompt":"سلام","max_tokens":64}
→ {"text":"سلام! …","tokens_in":14,"tokens_out":6,
   "cost_usd":"0.00001600","cost_irr":16,"fx_rate":1000000,"fallback_used":false}
```

قاعده‌ی قیمت: `prices_url` → pricing موجود در `/models` → جدول آفلاین → **قیمت دستی (همیشه برنده)**.

## ۵) پرامپت‌ها

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| GET | `/v1/prompts` | همه | فیلتر: `kind`, `status`, `locale`, `q` (سراسری + سازمان) |
| POST | `/v1/prompts` | admin/owner/operator | ساخت سازمانی؛ `publish` برای انتشار فوری |
| GET | `/v1/prompts/resolve/{key}` | همه | رندر پرامپت مؤثر؛ `agent_id` اختیاری |
| GET | `/v1/prompts/{id}` | همه | جزئیات |
| PUT | `/v1/prompts/{id}` | admin/owner/operator | ویرایش = نسخه‌ی جدید (`current_version + 1`) |
| POST | `/v1/prompts/{id}/publish` | admin/owner/operator | انتشار |
| POST | `/v1/prompts/{id}/rollback` | admin/owner/operator | `{version}` → **نسخه‌ی جدید** با متن قدیم |
| GET | `/v1/prompts/{id}/versions` | همه | تاریخچه |
| POST | `/v1/prompts/{id}/preview` | همه | رندر با `values` دلخواه + `missing` |

```json
GET /v1/prompts/resolve/agent.system.accountant?agent_id=… 
→ {"key":"agent.system.accountant","version":1,
   "rendered":"تو «حسابدار ارشد»، حسابدار رسمی «سازمان نمونه» هستی. امروز ۱۸ آبان ۱۴۰۵ است. …",
   "variables":["agent.name","org.name","today_jalali"],"missing":[]}
```

خطاها: `prompt.not_found` · `prompt.duplicate_key` (409) · `prompt.global_readonly` (403)
· `prompt.not_accessible` (403) · `prompt.version_not_found` · `prompt.missing_variables` (422)

## ۶) ایجنت‌ها

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| GET | `/v1/agents` | همه | فیلتر `is_active`, `q`, صفحه‌بندی |
| POST | `/v1/agents` | admin/owner | ساخت؛ `system_prompt_key` و `model_id` اعتبارسنجی می‌شوند |
| GET | `/v1/agents/{id}` | همه | جزئیات + نام مدل |
| PATCH | `/v1/agents/{id}` | admin/owner | ویرایش |
| DELETE | `/v1/agents/{id}` | admin/owner | حذف |
| GET | `/v1/agents/{id}/prompt` | همه | پرامپت مؤثر رندرشده (همان چیزی که مدل می‌بیند) |
| GET | `/v1/agents/{id}/tasks` | همه | وظایف + `next_run_at` (محاسبه‌شده) |
| POST | `/v1/agents/{id}/tasks` | admin/owner | `prompt_key` یا `prompt_template` الزامی |
| PATCH | `/v1/agents/{id}/tasks/{task_id}` | admin/owner | ویرایش (از جمله `schedule_cron` و `is_active`) |
| POST | `/v1/agents/{id}/tasks/{task_id}/run` | operator+ | اجرای فوری وظیفه؛ `trigger="task"` |
| DELETE | `/v1/agents/{id}/tasks/{task_id}` | admin/owner | حذف |
| GET | `/v1/agents/{id}/tools` | همه | ابزارهای متصل |
| PUT | `/v1/agents/{id}/tools` | admin/owner | **جایگزینی کل فهرست** (dedupe خودکار) |
| GET | `/v1/agents/{id}/workflow` | همه | گراف فعال |
| PUT | `/v1/agents/{id}/workflow` | admin/owner | نسخه‌ی جدید گراف + اعتبارسنجی |

```json
POST /v1/agents
{"name":"حسابدار ارشد","role":"accountant","system_prompt_key":"agent.system.accountant",
 "model_id":"…","temperature":"0.2","max_tokens":2048,"monthly_budget_irr":5000000}
→ 201 {"id":"…","system_prompt_key":"agent.system.accountant","is_active":true,…}
```

**وظیفه (Task):**

```json
POST /v1/agents/{id}/tasks
{"name":"گزارش روزانه فروش","prompt_key":"agent.task.daily_sales_report",
 "trigger_type":"schedule","schedule_cron":"0 8 * * *","requires_approval":true,
 "inputs_schema":{"type":"object","properties":{"data":{"type":"string"}}}}
```

`trigger_type`: `manual` · `schedule` · `webhook` · `event` · `inbound_call`
(اگر `schedule` باشد، `schedule_cron` با ۵ فیلد الزامی و اعتبارسنجی می‌شود).

خطاها: `agent.not_found` · `model.not_found` · `model.disabled` · `task.not_found`
· `task.prompt_required` · `task.schedule_required` · `workflow.invalid`

## ۷) ابزارها و MCP

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| GET | `/v1/tools` | همه | فیلتر `kind`, `category`, `q`, `enabled_only` |
| POST | `/v1/tools` | admin/owner/operator | اعتبارسنجی بر اساس `kind` (پایین) |
| GET | `/v1/tools/{id}` | همه | جزئیات + `has_secret`, `secret_masked` |
| PATCH | `/v1/tools/{id}` | admin/owner/operator | ویرایش + چرخش `secret` |
| DELETE | `/v1/tools/{id}` | admin/owner/operator | حذف |
| POST | `/v1/tools/{id}/clone` | admin/owner/operator | کپی سازمانی از ابزار سراسری (توکن همراه کپی نمی‌شود) |
| GET | `/v1/tools/ops` | همه | کاتالوگ ۲۴ عملیات اسکریپت اقدام |
| GET | `/v1/tools/llm-schemas` | همه | `?agent_id=` → دقیقاً همان چیزی که مدل می‌بیند |
| POST | `/v1/tools/{id}/test` | admin/owner/operator | اجرای آزمایشی (سیاست دور زده می‌شود) |
| GET | `/v1/mcp-servers` | همه | فهرست |
| POST | `/v1/mcp-servers` | admin/owner/operator | ثبت سرور (+`token`) |
| POST | `/v1/mcp-servers/{id}/sync` | admin/owner/operator | `tools/list` → `tools_cache` |
| DELETE | `/v1/mcp-servers/{id}` | admin/owner/operator | حذف |

**قواعد ساخت ابزار به تفکیک `kind`:**

| kind | الزامات |
|---|---|
| `http` | `config.url` + `config.allowed_domains` + متد مجاز |
| `mcp` | `config.mcp_server_id` (+ `remote_name` اختیاری) |
| `connector` | `actions` غیرخالی و معتبر (۲۴ op) |
| `builtin` | `slug` باید در رجیستری بیلتین باشد (`system.now_jalali`, `http.request`) |

خطاها: `tool.missing_url` · `tool.domain_not_configured` · `tool.domain_not_allowed` (403)
· `tool.invalid_arguments` (با `params.path`) · `tool.invalid_header` · `tool.invalid_actions`
· `tool.unknown_builtin` · `tool.duplicate_slug` (409) · `tool.global_readonly` (403)
· `tool.secret_missing` · `tool.device_offline` (409) · `tool.device_timeout` (504)
· `tool.device_error` (502) · `tool.approval_required` (409)

## ۸) اجرای ایجنت (REST + SSE)

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| POST | `/v1/agents/{id}/runs` | admin/owner/operator | `stream=true` → SSE (پیش‌فرض)، `false` → JSON |
| POST | `/v1/runs/{id}/approve` | admin/owner/operator | ادامه‌ی اجرای متوقف‌شده |
| GET | `/v1/runs` | همه | فیلتر `agent_id`, `status` |
| GET | `/v1/runs/{id}` | همه | وضعیت/توکن/هزینه |
| POST | `/v1/runs/{id}/cancel` | admin/owner/operator | فقط وضعیت را تغییر می‌دهد |
| GET | `/v1/runs/{id}/invocations` | همه | فراخوانی ابزارها |

```json
POST /v1/agents/{id}/runs
{"input":"امروز چندم است؟","stream":true,"max_tokens":2000,"conversation_id":null}
```

**بدون استریم** → `{run: {...}, text: "...", events: [...]}`

**با استریم** → `Content-Type: text/event-stream` و هر خط `data: {json}`:

| رخداد | معنا |
|---|---|
| `run.started` | شروع؛ `run_id` |
| `llm.start` | شروع یک گام مدل (`step`, `model`) |
| `token` | تکه متن مدل |
| `notice` | اطلاع (مثلاً fallback به پروایدر دیگر) |
| `tool.call` | اجرای ابزار (`tool`, `arguments`) |
| `tool.result` | نتیجه‌ی ابزار (`result`, `invocation_id`) |
| `tool.error` | خطای ابزار (`code`) |
| `tool.denied` | سیاست اجازه نداد |
| `approval.required` | نیاز به تأیید انسان (`tool`, `risk`, `arguments`) |
| `run.waiting_approval` | اجرا متوقف و ذخیره شد (`pending`) |
| `run.completed` | پایان موفق (`text`, `tokens_in/out`, `cost_usd`, `cost_irr`, `steps`) |
| `run.failed` | پایان ناموفق (`code`, `params`) |

```text
data: {"event":"run.started","data":{"run_id":"…","status":"queued"}}
data: {"event":"llm.start","data":{"step":1,"model":"runner-model"}}
data: {"event":"token","data":{"text":"سلام! "}}
data: {"event":"run.completed","data":{"text":"…","tokens_in":246,"tokens_out":12,"cost_irr":141,…}}
```

خطاها: `run.not_found` · `run.not_waiting_approval` (409) · `run.max_steps` (409)
· `budget.agent_exceeded` / `budget.org_exceeded` (409) · `budget.token_limit` (409)
· `provider.call_failed` (502) · `agent.model_required`

## ۹) دستگاه‌ها (کانکتور)

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| POST | `/v1/devices` | admin/owner | ساخت + کد ۸ کاراکتری (۱۰ دقیقه) |
| POST | `/v1/devices/pair` | **بدون احراز** | کانکتور: `{code, pubkey, os, version}` → `{device_id, device_token, ws_url}` |
| GET | `/v1/devices` | همه | فهرست |
| GET | `/v1/devices/{id}` | همه | جزئیات |
| GET | `/v1/devices/{id}/ops` | همه | `{online, ops, manifest}` |
| PATCH | `/v1/devices/{id}` | admin/owner | نام، `allowed_paths`، فعال/غیرفعال |
| POST | `/v1/devices/{id}/rotate-code` | admin/owner | کد جدید |
| DELETE | `/v1/devices/{id}` | admin/owner | حذف و قطع اتصال |
| WS | `/v1/ws/connector?token=` | دستگاه | کانال خروجی |

خطاها: `device.invalid_code` (401) · `device.code_expired` (410) · `device.disabled` (403)
· `device.not_found` · `device.invalid_token` (401)

**پروتکل WebSocket:**

```jsonc
// کانکتور → سرور
{"type":"hello","name":"PC-1","os":"Windows","version":"0.1.0",
 "manifest":{"ops":["fs.write","office.cells"]}}
{"type":"script.progress","call_id":"…","step":0,"op":"fs.write"}
{"type":"script.result","call_id":"…","ok":true,"output":[…],"artifacts":[]}

// سرور → کانکتور
{"type":"hello.ack","device_id":"…","server_time":"…"}
{"type":"script.run","call_id":"…","tool":"office.excel.append_row",
 "steps":[{…}],"allow_paths":["D:/data"],"timeout":60}
```

## ۱۰) صورتحساب (فاز اول: غیرفعال)

| متد | مسیر | خروجی |
|---|---|---|
| GET | `/v1/billing/status` | `{gateway:"noop", gateway_enabled:false, free_mode:true, billing_enabled:false}` |
| POST | `/v1/billing/checkout` | همیشه `409 billing.disabled` (اثبات آماده بودن پورت) |

## ۱۱) مصرف، کاربران و تنظیمات (مصرف پنل)

| متد | مسیر | توضیح |
|---|---|---|
| GET | `/v1/usage/summary?days=30` | `totals` (اجرا/توکن/دلار/ریال) + `by_day` + `by_agent` + `by_model` + شمارش وضعیت اجراها + `budget` + دستگاه‌های آنلاین |
| GET | `/v1/usage/export.xlsx?days=30` | فایل اکسل: شیت RTL، سرصفحه‌ی فارسی، تاریخ جلالی، `Content-Disposition: attachment` |
| GET | `/v1/users` | فیلتر `role`، `is_active`، `q` (نیازمند `admin`/`owner`) |
| POST | `/v1/users` | ساخت کاربر؛ نقش `admin`/`owner` فقط توسط `owner` |
| GET | `/v1/users/{id}` | جزئیات یک کاربر |
| PATCH | `/v1/users/{id}` | نام، تلفن، نقش، فعال/غیرفعال؛ تغییر نقش خود ممنوع (`409 user.cannot_modify_self`) |
| POST | `/v1/users/{id}/reset-password` | رمز جدید + باطل‌کردن همه‌ی نشست‌های کاربر |
| DELETE | `/v1/users/{id}` | غیرفعال‌سازی (بدون حذف رکورد، مخصوص `owner`) |
| GET | `/v1/settings` | سازمان + کاربر + نرخ ارز + پرچم‌های حالت رایگان |
| PATCH | `/v1/settings/org` | نام، منطقه‌زمانی، تقویم، ارقام، مالیات، پیش‌شماره‌ی فاکتور، سقف بودجه |
| PATCH | `/v1/settings/me` | نام نمایشی، locale، شکل ارقام |
| PATCH | `/v1/settings/fx` | نرخ دلار به ریال؛ روی همه‌ی محاسبات آینده اثر دارد (سطرهای قبلی دفتر تغییر نمی‌کنند) |

نمونه:

```json
// GET /v1/usage/summary?days=7
{
  "days": 7,
  "fx_rate": 1000000,
  "range_from": "2026-11-02",
  "range_to": "2026-11-09",
  "totals": {"runs": 42, "tokens_in": 51200, "tokens_out": 18400,
             "cost_usd": "0.01820000", "cost_irr": 18200},
  "by_day": [{"key": "2026-11-08", "label": "۱۴۰۵/۰۸/۱۷", "runs": 12,
              "tokens_in": 14000, "tokens_out": 5000,
              "cost_usd": "0.00510000", "cost_irr": 5100}],
  "runs": {"running": 0, "waiting_approval": 1, "failed": 2, "completed": 39},
  "budget": {"org_monthly_irr": 100000000, "org_spent_irr": 18200}
}
```

> ارقام پولی همیشه **ریال** (`cost_irr`) ذخیره و برگردانده می‌شوند؛ پنل آن‌ها را برای نمایش
> به تومان تقسیم بر ۱۰ می‌کند.

## ۱۲) زمان‌بند (cron)

worker جدا از API اجرا می‌شود و همان موتور اجرا را صدا می‌زند:

```powershell
python -m app.workers.scheduler      # هر APP_SCHEDULER_TICK_SECONDS ثانیه یک پاس
```

| متغیر | پیش‌فرض | کار |
|---|---|---|
| `APP_SCHEDULER_TICK_SECONDS` | ۳۰ | فاصله‌ی پاس‌ها |
| `APP_SCHEDULER_MIN_GAP_SECONDS` | ۵۰ | کمترین فاصله بین دو اجرای یک وظیفه (ضد تکرار) |
| `APP_SCHEDULER_MAX_CONCURRENCY` | ۲ | سقف اجرای هم‌زمان |
| `APP_SCHEDULER_LOCK_KEY` | `982451653` | کلید advisory lock (تک‌مجرا شدن) |
| `APP_SCHEDULER_TIMEZONE` | `Asia/Tehran` | منطقه‌ی زمانی تطبیق cron |

قواعد cron (۵ فیلد): `دقیقه ساعت روز-ماه ماه روز-هفته`

| عبارت | معنا |
|---|---|
| `0 8 * * *` | هر روز ۸:۰۰ صبح |
| `*/15 9-18 * * sat-thu` | هر ۱۵ دقیقه، ۹ تا ۱۸، شنبه تا پنجشنبه |
| `30 23 1 * *` | ساعت ۲۳:۳۰ روز اول هر ماه |
| `0 8 * * 6` | شنبه‌ها ۸ صبح (۰=یکشنبه … ۶=شنبه) |

> اگر هم روز-ماه و هم روز-هفته محدود شوند، قاعده‌ی POSIX است: هر کدام تطبیق دهد اجرا می‌شود.
> خروجی `next_run_at` در `GET /v1/agents/{id}/tasks` همیشه UTC است (نمایش جلالی در پنل).

## ۱۳) برنامه‌ها (App Catalog)

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| GET | `/v1/apps` | همه | فیلتر `category`, `runtime`, `q`؛ شمارش «نصب‌شده/دستگاه» |
| GET | `/v1/apps/{slug}` | همه | جزئیات + `credentials` + قالب config/actions |
| POST | `/v1/apps/{slug}/install` | admin/owner/operator | ساخت ابزار از قالب + اتصال به ایجنت (idempotent) |
| DELETE | `/v1/apps/{slug}/install` | admin/owner/operator | `?agent_id=` → حذف ابزار و اتصال |
| GET | `/v1/devices/{id}/apps` | همه | برنامه‌های شناسایی‌شده روی دستگاه |
| POST | `/v1/devices/{id}/scan-apps` | admin/owner/operator | اسکن دستگاه از طریق کانکتور (`apps.scan`) |
| PATCH | `/v1/devices/{id}/apps/{slug}` | admin/owner/operator | `{"is_granted": true}` |

بدنه‌ی نصب:

```jsonc
{
  "agent_id": "…",                 // الزامی
  "permission_level": "confirm",   // auto | confirm | deny
  "secret": "توکن",                // اگر برنامه اعتبارنامه‌ی سرّی دارد
  "variables": {"chat_id": "…"},   // فیلدهای غیرسرّی ویزارد
  "device_id": "…",                // برای برنامه‌های دسکتاپ الزامی
  "force": false                   // نصب حتی اگر روی دستگاه شناسایی نشده باشد
}
→ 201 {"tool_id","slug","agent_id","permission_level","device_id","warnings":[]}
```

- `slug` ابزار = `<app>.<۸ کاراکتر اول agent_id>`؛ نصب دوباره = به‌روزرسانی همان ابزار.
- خطاها: `app.not_found` · `app.missing_secret` · `app.missing_field` (`params.field`) ·
  `app.device_required` · `app.device_offline` (409) · `app.not_detected` (409) ·
  `app.scan_failed` (502) · `app.not_installed` · `app.install_conflict` (409).
- راهنمای کامل: [apps.md](apps.md)

## ۱۴) کانال‌های ورودی (وبهوک)

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| POST | `/v1/inbound/telegram/{slug}` | عمومی | هدر `X-Telegram-Bot-Api-Secret-Token` |
| GET | `/v1/inbound/whatsapp/{slug}` | عمومی | `hub.mode`/`hub.verify_token`/`hub.challenge` |
| POST | `/v1/inbound/whatsapp/{slug}` | عمومی | امضای `X-Hub-Signature-256` (HMAC کل بدنه) |
| GET | `/v1/channels` | همه | فهرست کانال‌ها + آدرس وبهوک |
| POST | `/v1/channels` | owner/admin | ساخت کانال (secret رمزنگاری می‌شود) |
| PATCH | `/v1/channels/{id}` | owner/admin | تغییر ایجنت/ابزار/حالت پاسخ/چرخش secret |
| DELETE | `/v1/channels/{id}` | owner/admin | حذف کانال و رویدادهایش |
| GET | `/v1/channels/{id}/events` | همه | آخرین رویدادهای دریافتی (حداکثر ۲۰۰) |
| POST | `/v1/channels/{id}/test` | owner/admin | تزریق پیام ساختگی → اجرا + پاسخ (بدون امضا) |
| POST | `/v1/channels/{id}/register-webhook` | owner/admin | `setWebhook` تلگرام با توکن همان ابزار |

```jsonc
POST /v1/channels
{
  "name_fa": "پشتیبانی واتساپ",
  "provider": "whatsapp",           // telegram | whatsapp
  "agent_id": "…",
  "tool_id": "…",                   // ابزار پاسخ (اختیاری)
  "reply_mode": "auto",             // off | auto
  "verify_secret": "app-secret",    // تلگرام: secret_token — واتساپ: App Secret
  "verify_token": "verify-me"       // فقط واتساپ
}
→ 201 {"slug":"whatsapp-1a2b3c4d","webhook_path":"/v1/inbound/whatsapp/whatsapp-1a2b3c4d", …}

پاسخ وبهوک: {"ok":true,"status":"accepted|duplicate|ignored|disabled|failed","run_id":"…"}
```

خطاها: `inbound.channel_not_found` · `inbound.invalid_signature` (401) ·
`inbound.invalid_verify_token` (403) · `inbound.invalid_mode` · `inbound.invalid_payload` ·
`inbound.secret_required` · `inbound.verify_token_required` · `inbound.tool_not_http` ·
`inbound.tool_provider_mismatch`.

راهنمای کامل: [inbound.md](inbound.md)

## ۱۵) صدا و گفتار (STT / TTS)

تبدیل گفتار به متن و متن به گفتار با مدل‌هایی که `supports_audio=true` دارند. نوع مدل
(`stt` یا `tts`) از `meta.audio_kind` خوانده می‌شود و اگر نبود از شناسهٔ مدل استنتاج می‌شود
(`whisper*`, `transcribe*` → STT؛ `tts*`, `*voice`, `speech` → TTS).

| متد | مسیر | نقش | توضیح |
|---|---|---|---|
| GET | `/audio/meta` | همه | محدودیت‌ها: `max_upload_mb`, `max_tts_chars`, `voices`, `formats`, `persian_levels` |
| GET | `/audio/presets` | همه | فهرست مدل‌های آماده با برچسب فارسی (`persian`) |
| GET | `/audio/models?kind=stt\|tts&persian=verified\|good\|weak\|none\|any` | همه | فهرست اختصاصی مدل‌های صوتی؛ فارسی‌بلدها اول برمی‌گردند |
| GET | `/models?capability=audio` | همه | همان فهرست مدل‌ها با `audio_kind`، قیمت صوتی و `persian` (صفحهٔ `/models`) |
| POST | `/audio/transcriptions` | operator | `multipart/form-data`: `file`, `model_id`, `language?`, `prompt?` |
| POST | `/audio/speech` | operator | JSON: `model_id`, `text` (≤ ۴۰۰۰), `voice`, `format` (`mp3\|wav\|opus\|aac\|flac\|pcm`), `speed?` → فایل صوتی |
| GET | `/audio/speech/estimate` | همه | برآورد هزینه بدون فراخوانی پروایدر |
| POST | `/models` | owner/admin | افزودن دستی مدل (شامل `audio_kind`، قیمت‌های صوتی و `persian`) |
| PATCH | `/models/{id}` | owner/admin | از جمله `persian` برای اصلاح دستی برچسب فارسی |
| DELETE | `/models/{id}` | owner/admin | حذف مدل از کاتالوگ |

**برچسب فارسی:** هر مدل صوتی فیلد `persian` (سطح سنجیده‌شده)، `persian_score` (امتیاز ۰..۱
آزمایش رفت‌وبرگشتی) و `persian_note_fa` (جملهٔ فارسی آمادهٔ نمایش) دارد. جزئیات و جدول کامل
مدل‌ها: [audio.md](audio.md#۷-پشتیبانی-فارسی--سنجیده-نه-حدسزده).

**پاسخ `/audio/speech`:** بدنهٔ صوتی + هدرهای `X-Audio-Format` (قالب واقعی؛ اگر مدل فقط `pcm`
بدهد `wav` است)، `X-Audio-Voice` (voice واقعی پس از اصلاح)، `X-Cost-Usd`، `X-Cost-Irr`،
`X-Fx-Rate`، `X-Chars` و `Content-Disposition`.


**هزینه‌گذاری:** STT بر اساس **دقیقهٔ صدا** (`models.audio_input_price`، دلار بر دقیقه،
`ceil` روی ثانیه) و TTS بر اساس **هزار نویسه** (`models.audio_output_price`). هر دو با
`markup_percent` و نرخ ارز به ریال تبدیل و در `usage_ledger` با ستون‌های `audio_seconds` /
`audio_chars` ثبت می‌شوند. اگر قیمت مدل صفر باشد، هزینهٔ صفر ثبت می‌شود (نه خطا).

**نمونه (PowerShell):**

```powershell
$h = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod "http://127.0.0.1:8000/v1/audio/transcriptions" -Method Post -Headers $h `
  -Form @{ model_id = $sttModelId; language = "fa"; file = Get-Item .\voice.m4a }

Invoke-WebRequest "http://127.0.0.1:8000/v1/audio/speech" -Method Post -Headers $h `
  -ContentType "application/json" `
  -Body (@{ model_id = $ttsModelId; text = "سلام، این یک نمونه است." } | ConvertTo-Json) `
  -OutFile .\speech.mp3
```

**خطاهای اختصاصی:** `audio.not_audio_model` · `audio.unknown_kind` · `audio.wrong_kind` ·
`audio.unsupported_provider` · `audio.empty_file` · `audio.file_too_large` ·
`audio.empty_text` · `audio.text_too_long` · `model.exists` · ۵۰۲ برای خطای پروایدر.

## ۱۶) شروع سریع با PowerShell

```powershell
$api = "http://127.0.0.1:8010"
$login = Invoke-RestMethod "$api/v1/auth/login" -Method Post -ContentType 'application/json' `
    -Body ([Text.Encoding]::UTF8.GetBytes('{"email":"admin@openbot.local","password":"admin12345"}'))
$h = @{ Authorization = "Bearer $($login.access_token)" }

Invoke-RestMethod "$api/v1/meta" -Headers $h | ConvertTo-Json -Compress
Invoke-RestMethod "$api/v1/provider-adapters" -Headers $h | Select-Object -First 3
Invoke-RestMethod "$api/v1/healthz" | ConvertTo-Json -Compress
```


