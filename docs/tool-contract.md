# قرارداد ابزار (Tool Contract)

ابزار = یک قرارداد JSON Schema + یک روش اجرا. مدل فقط `name`, `description`, `parameters`
را می‌بیند؛ بقیه (نوع اجرا، ریسک، تأیید، اعتبارنامه) در دیتابیس است.

## ۱) اسکلت یک ابزار

```json
{
  "slug": "office.excel.append_row",
  "name_fa": "افزودن ردیف به اکسل",
  "description_fa": "یک ردیف به انتهای شیت اضافه می‌کند",
  "kind": "connector",
  "input_schema": {
    "type": "object",
    "properties": {
      "file":   {"type": "string", "description": "مسیر فایل"},
      "sheet":  {"type": "string"},
      "values": {"type": "array", "items": {}}
    },
    "required": ["file", "sheet", "values"]
  },
  "output_schema": {},
  "config": {},
  "actions": [
    {"op": "office.open", "app": "excel", "path": "{{input.file}}"},
    {"op": "office.cells", "sheet": "{{input.sheet}}", "append": "{{input.values}}"},
    {"op": "office.save"}
  ],
  "risk_level": "medium",
  "approval_policy": "confirm",
  "category": "office",
  "is_enabled": true
}
```

**نام‌گذاری `slug`:** `حوزه.زیرحوزه.عمل` با حروف کوچک، عدد، نقطه، خط تیره (۲ تا ۱۲۰ کاراکتر).
چون نام تابع مدل نمی‌تواند نقطه داشته باشد، تبدیل خودکار انجام می‌شود:
`office.excel.append_row` → `office_excel_append_row` (نقشه‌ی معکوس نگه داشته می‌شود).

## ۲) چهار نوع ابزار

| kind | اجرا در | افزودن از پنل | الزامات |
|---|---|---|---|
| `http` | سرور (httpx) | کامل، بدون کد | `config.url` + `config.allowed_domains` |
| `mcp` | سرور | کامل (کشف خودکار) | `config.mcp_server_id` |
| `connector` | ماشین کاربر | کامل (اسکریپت اقدام) | `actions` معتبر |
| `builtin` | سرور | فقط فعال/غیرفعال | `slug` در رجیستری بیلتین |

### الف) ابزار HTTP توصیفی

```json
"config": {
  "method": "POST",
  "url": "https://api.telegram.org/bot{{secret}}/sendMessage",
  "allowed_domains": ["api.telegram.org"],
  "headers": {"Content-Type": "application/json"},
  "query": {},
  "body": {"chat_id": "{{chat_id}}", "text": "{{text}}"},
  "response_map": {"message_id": "$.result.message_id", "ok": "$.ok"},
  "auth": {"type": "bearer"},
  "timeout": 20,
  "proxy": null
}
```

- جایگذاری: `{{secret}}` (اعتبارنامه‌ی رمزنگاری‌شده) و `{{نام‌ورودی}}` از ورودی‌های مدل.
- `auth.type`: `none` | `bearer` | `header` (با `header`) | `query` (با `param`).
- `allowed_domains`: اجباری؛ دامنه‌ی خارج از فهرست → `403 tool.domain_not_allowed`.
- `response_map`: JSONPath سبک؛ خروجی در `result.mapped`.
- مقدار هدر باید ASCII باشد وگرنه `422 tool.invalid_header`.
- خروجی اجرا: `{ok, status_code, text[:4000], json?, mapped?}`.

### ب) ابزار MCP

```json
{"slug":"mcp.search","kind":"mcp","description_fa":"جست‌وجو در دانش",
 "input_schema":{"type":"object","properties":{"q":{"type":"string"}},"required":["q"]},
 "config":{"mcp_server_id":"<uuid>","remote_name":"search"}}
```

- ثبت سرور: `POST /v1/mcp-servers` با `url` (+`token`) → `POST /{id}/sync` برای `tools/list`.
- ترانسپورت فعلی: **HTTP/JSON‑RPC** (SSE نیز پشتیبانی می‌شود). `stdio` ذخیره می‌شود ولی اجرا ندارد.

### ج) اسکریپت اقدام (کانکتور) — ۲۴ عملیات

| op | فیلدهای الزامی | کار |
|---|---|---|
| `office.open` | app, path | باز کردن فایل در اکسل/ورد |
| `office.cells` | sheet | نوشتن/افزودن سلول‌ها |
| `office.save` | — | ذخیره |
| `com.invoke` | prog_id, method | فراخوانی COM (نرم‌افزارهای ویندوزی) |
| `shell.run` | command | اجرای فرمان مجاز |
| `fs.read` | path | خواندن فایل |
| `fs.write` | path, content | نوشتن فایل |
| `fs.list` | path | فهرست پوشه |
| `http.request` | url | درخواست HTTP از ماشین کاربر |
| `browser.open` | url | باز کردن مرورگر |
| `browser.click` | selector | کلیک روی عنصر |
| `browser.extract` | selector | استخراج متن |
| `wait` | — | توقف کوتاه |
| `keyboard.type` | text | تایپ متن |
| `screenshot` | — | تصویر از صفحه |
| `print` | — | ارسال به چاپگر |
| `phone.dial` | number | برقراری تماس (سافت‌فون) |
| `app.launch` | app | اجرای برنامه‌ی کاتالوگ با slug (نه مسیر دلخواه) |
| `app.focus` | app | آوردن پنجره‌ی برنامه به جلو |
| `app.windows` | — | فهرست پنجره‌های باز |
| `ui.invoke` | name | فراخوانی عنصر رابط کاربری (UI Automation) |
| `clipboard.set` | text | نوشتن در کلیپ‌بورد |
| `clipboard.get` | — | خواندن کلیپ‌بورد |
| `keyboard.hotkey` | keys | فشار کلید ترکیبی (مثل `["ENTER"]`) |

- **برنامه‌های آماده:** بخش «برنامه‌ها» (`/v1/apps`) روی همین اسکریپت‌های اقدام و قالب‌های HTTP
  سوار شده است؛ راهنما: [apps.md](apps.md). `app.launch` فقط slug می‌گیرد و کانکتور خودش
  مسیر اجرایی را از نقشه‌ی داخلی پیدا می‌کند تا مدل نتواند فایل دلخواه اجرا کند.

- حداکثر ۴۰ گام در هر اسکریپت؛ `op` ناشناس یا فیلد ناقص → `422 tool.invalid_actions`.
- جایگذاری روی هر گام انجام می‌شود: `{{input.x}}`, `{{run_id}}`, `{{org_id}}`.
- **ایمنی:** همه‌ی `fs.*` و `office.open` باید داخل `devices.allowed_paths` باشند
  (هم سرور ارسال می‌کند و هم کانکتور مستقل بررسی می‌کند)؛ `shell.run` فقط با پیشوند مجاز.
- نتیجه: `{device_id, steps, output:[…], artifacts:[]}` یا خطای
  `tool.device_offline` / `tool.device_timeout` / `tool.device_error`.

### د) بیلتین‌های موجود

| slug | ورودی | خروجی |
|---|---|---|
| `system.now_jalali` | `timezone?` | `{timezone, iso, jalali, jalali_short}` با ارقام فارسی |
| `http.request` | `url, method?, headers?, body?` | `{status_code, content_type, text}` (محدود به `allowed_domains`) |

## ۳) سیاست اجرا (ماتریس ریسک)

| risk × permission | `auto` | `confirm` | `deny` |
|---|---|---|---|
| `low` | اجرا | تأیید | بلاک |
| `medium` | اجرا | تأیید | بلاک |
| `high` | **تأیید** | تأیید | بلاک |

`approval_policy` روی خود ابزار هم اعمال می‌شود: `deny` همیشه بلاک، `confirm` همیشه تأیید.
ابزار غیرفعال هرگز اجرا نمی‌شود (`tool.disabled`).

**جریان تأیید:** اجرا در `runs.state.pending` ذخیره می‌شود، `status=waiting_approval`،
رخداد `approval.required` می‌آید و پس از `POST /v1/runs/{id}/approve` ادامه می‌یابد.
هر اجرای تأییدشده با `approved_by` در `tool_invocations` ثبت می‌شود.

## ۴) آزمون ابزار

```powershell
POST /v1/tools/{id}/test   {"arguments": {"text": "سلام"}}
→ {"ok": true, "result": {…}, "invocation_id": "…"}
```

`/test` سیاست تأیید را **دور می‌زند** (چون ادمین دستی اجرا می‌کند) ولی schema را
اعتبارسنجی می‌کند و در `tool_invocations` ثبت می‌شود.

## ۵) آنچه مدل می‌بیند

```powershell
GET /v1/tools/llm-schemas?agent_id=…
→ [{"name":"office_excel_append_row","slug":"office.excel.append_row",
    "description":"افزودن ردیف به اکسل","parameters":{…}}]
```

فقط ابزارهای **متصل به همان ایجنت** و **فعال** برمی‌گردند؛ `permission_level` هر اتصال
مستقل تنظیم می‌شود.

## ۶) آداپتور توصیفی پروایدر

همان ایده برای پروایدر ناشناس (`providers.kind = "declarative"`):

```jsonc
{
  "chat": {
    "method": "POST",
    "url": "{{base_url}}/generate",
    "headers": {"Authorization": "Bearer {{api_key}}"},
    "body": {"model": "{{model}}", "prompt": "{{messages_flat}}"}
  },
  "response_map": {"text": "$.output[0].content",
                   "usage_in": "$.usage.input", "usage_out": "$.usage.output"},
  "models_url": "{{base_url}}/catalog",
  "models_map": {"id": "$.result[*].key", "context": "$.result[*].ctx"}
}
```

- جایگذاری: `{{base_url}}`, `{{api_key}}`, `{{model}}`, `{{messages}}`, `{{messages_flat}}`,
  `{{tools}}`, `{{temperature}}`, `{{max_tokens}}`, `{{stream}}`.
- `response_map` مسیرهای JSON را با JSONPath سبک (`$.a.b`, `$.list[*].x`) می‌خواند.
- `models_map` کشف مدل از همان پروتکل دلخواه را ممکن می‌کند.

