# مدل داده

۴۲ جدول در ۱۳ مایگریشن (`0000` تا `0012`). ستون‌های مشترک همه‌ی جدول‌های دامنه:
`id UUID` (پیش‌فرض `uuid4`)، `created_at`, `updated_at` (به‌جز جدول‌های append-only).

## ۱) هسته و چند-مستأجری

| جدول | ستون‌های کلیدی | نکته |
|---|---|---|
| `organizations` | name, slug, timezone, calendar, currency, digits, tax_rate, monthly_budget_irr, settings | پیش‌فرض فارسی: `Asia/Tehran` + `jalali` + `IRR` + ارقام فارسی |
| `users` | org_id, email, phone, full_name, password_hash (Argon2), role, locale, digits_pref | یکتا: (org_id, email) |
| `memberships` | org_id, user_id, role | برای کاربر چندسازمانی |
| `api_keys` | org_id, prefix, hash, scopes | کلید خام هرگز ذخیره نمی‌شود |
| `sessions` | user_id, refresh_hash, expires_at, revoked_at | چرخش refresh در هر استفاده |
| `user_mfa` | secret_enc, is_enabled | TOTP (پیاده‌سازی نهایی: roadmap) |
| `login_attempts` | email, ip, success | audit ورود ناموفق |
| `app_settings` | key, value(JSONB) | تنظیمات سراسری: `fx`, `product` |
| `translations` | locale, key, value | متن قابل ویرایش توسط ادمین |

## ۲) پروایدر، مدل، قیمت

| جدول | نکته |
|---|---|
| `provider_adapters` | کاتالوگ ۱۲ نوع (seed) با عنوان فارسی و `spec_schema` |
| `providers` | kind, base_url, auth_type, **credentials_enc**(AES-GCM), extra_headers, `chat_spec`/`response_map` برای declarative, models_url, prices_url, priority, health |
| `models` | یکتا (provider_id, external_id)، قابلیت‌ها، ۴ قیمت، markup، `is_enabled` |
| `price_history` | append-only؛ `effective_from` + منبع (`provider`/`litellm`/`manual`) + قیمت صوتی (`audio_input_price` دلار/دقیقه، `audio_output_price` دلار/۱۰۰۰ نویسه) |
| `capability_rules` | regex → قابلیت (استنتاج هنگام سینک) |

## ۳) پرامپت

| جدول | نکته |
|---|---|
| `prompts` | org_id (NULL = سراسری)، key, locale, kind, template, variables, status(draft/published), current_version |
| `prompt_versions` | append-only، یکتا (prompt_id, version) |
| `prompt_examples` | few-shot (آماده، بدون API) |

قاعده‌ی حل: **پرامپت سازمان بر پرامپت سراسری مقدم است**؛ پرامپت سراسری فقط‌خواندنی.

## ۴) ایجنت و وظایف

| جدول | نکته |
|---|---|
| `agents` | name, role, `system_prompt_key` (نه متن)، model_id, temperature, max_tokens, memory_mode, guardrails, monthly_budget_irr |
| `agent_workflows` | graph(JSONB) نسخه‌دار؛ نودهای مجاز در `agents/workflow.py` |
| `agent_tasks` | prompt_key یا prompt_template، inputs_schema، steps، trigger_type، schedule_cron، requires_approval |
| `agent_tools` | اتصال ایجنت↔ابزار با `permission_level` مستقل (auto/confirm/deny) |

## ۵) ابزار و دستگاه

| جدول | نکته |
|---|---|
| `tools` | kind(builtin/http/mcp/connector)، input_schema(JSON Schema)، config، actions(اسکریپت اقدام)، risk_level، approval_policy، **secret_enc** |
| `mcp_servers` | url/command، auth_enc، tools_cache |
| `devices` | name, os, version, pubkey, status, pairing_code، `allowed_paths`، last_seen_at |
| `device_tools` | برنامه‌های شناسایی‌شده‌ی دستگاه (`tool_slug` = slug کاتالوگ، `capabilities` = exe/prog_id/version، `is_granted`) |
| `app_catalog` | کاتالوگ سراسری برنامه‌ها: icon/color، `runtime` (cloud/desktop)، قالب `config`/`actions`، `credentials`، `detect`، پیش‌نیازها |
| `inbound_channels` | کانال وبهوک: `slug` (یکتای سراسری)، provider، agent، ابزار پاسخ، `reply_mode`، `verify_secret_enc`/`verify_token_enc`، شمارنده |
| `inbound_events` | هر تحویل دریافتی: `external_id` (یکتا با channel)، وضعیت، `run_id`، متن/فرستنده، نتیجه‌ی پاسخ |

## ۶) اجرا و حسابداری

| جدول | نکته |
|---|---|
| `conversations` / `messages` | تاریخچه‌ی گفتگو؛ `messages.cost_irr` برای نمایش هزینه‌ی هر پیام |
| `runs` | status(queued/running/waiting_approval/completed/failed/cancelled)، steps_taken، tokens، cost_usd/cost_irr/**fx_rate**، **state(JSONB)** برای ادامه‌ی اجرا |
| `trace_spans` | گام‌های ریز برای دیباگ |
| `tool_invocations` | args/result/status/risk/latency/**approved_by** — حتی برای خطاها (تراکنش جدا) |
| `usage_ledger` | append-only: tokens، cost_usd، markup، **fx_rate**، cost_irr، billable، `audio_seconds` (STT) و `audio_chars` (TTS) |
| `audit_logs` | زنجیره‌ی هش (`prev_hash`, `hash`) |

**چرا `fx_rate` در هر ردیف مصرف؟** فاکتور ماه بعد نباید با تغییر نرخ ارز به‌هم بریزد.

## ۷) دانش (آماده، بدون پیاده‌سازی)

`knowledge_bases` → `documents` → `chunks(embedding vector(1536))` — افزونه‌ی `vector`
در مایگریشن `0000` نصب می‌شود؛ API و بازیابی در roadmap.

## ۸) صورتحساب (غیرفعال در فاز اول)

`plans` (پلن `free` seed شده)، `wallets` (با `is_enabled=false`)، `wallet_transactions`،
`feature_flags`. جداول `invoices`/`payments`/`licenses` **عمداً ساخته نشده‌اند**؛
پورت `PaymentGateway` جای آن‌ها را باز نگه داشته است.

## ۹) امنیت سطح ردیف (RLS)

۱۷ جدول با سیاست `tenant_isolation` و `FORCE ROW LEVEL SECURITY`:

```
agents, api_keys, audit_logs, conversations, devices, knowledge_bases, mcp_servers,
memberships, prompts, providers, runs, sessions, tool_invocations, tools,
usage_ledger, users, wallets
```

گزاره:

```sql
current_setting('app.bypass_rls', true) = 'on'
OR org_id IS NULL                       -- داده‌ی سراسری (پرامپت/ابزار پیش‌فرض)
OR org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
```

نتیجه‌ی مهم: **نبودِ context یعنی صفر ردیف** (امن به‌صورت پیش‌فرض). اپلیکیشن با نقش
غیرسوپریوزر `openbot_app` وصل می‌شود تا سیاست‌ها واقعاً اعمال شوند.

## ۱۰) نگهداشت پیشنهادی (عملیاتی)

| داده | نگهداشت | روش |
|---|---|---|
| `runs`, `trace_spans`, `tool_invocations` | ۹۰ روز | job پاک‌سازی (roadmap) |
| `messages` | ۱۸۰ روز | آرشیو به فایل |
| `usage_ledger`, `audit_logs` | دائمی | append-only، بدون UPDATE |
| `login_attempts` | ۳۰ روز | — |
