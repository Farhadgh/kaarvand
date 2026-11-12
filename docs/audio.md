# صدا و گفتار (STT / TTS)

کاروند مدل‌های صوتی را مثل مدل‌های متنی مدیریت می‌کند: مدل در کاتالوگ پروایدر ثبت می‌شود،
قیمتش در `models` ذخیره می‌شود و هر فراخوانی در `usage_ledger` با واحد درست (ثانیه/نویسه)
ثبت می‌شود. هیچ نام مدلی در کد هاردکد نشده است.

## ۱) مدل از کجا می‌آید؟

سه راه:

| راه | مسیر | مناسب برای |
|---|---|---|
| سینک پروایدر | «پروایدرها» → «سینک مدل‌ها» | پروایدرهایی که مدل صوتی را در `/models` می‌آورند (OpenRouter، OpenAI، Groq، Together…) |
| مدل آماده | `/audio` یا `/models` → «افزودن مدل صوتی» → مدل‌های آماده | سریع‌ترین راه؛ قیمت رسمی از پیش پر است |
| مدل دلخواه | `/audio` → «مدل دلخواه» | ریسلر ایرانی یا مدل محلی با نام خاص |

**در سینک، نوع مدل از خود کاتالوگ پروایدر خوانده می‌شود، نه از حدس روی نام:**

- OpenRouter مدل‌های اختصاصی گفتار را با `architecture.output_modalities` مشخص می‌کند
  (`transcription` → **STT**، `speech` → **TTS**). در فهرست پیش‌فرض `/api/v1/models` مقدار
  `architecture` برای این مدل‌ها `null` است، بنابراین کاروند دو فهرست فیلترشده را هم می‌خواند:
  `/api/v1/models?output_modalities=transcription` و `…=speech` — و مدل‌هایی که فقط در
  همان دو فهرست هستند را هم می‌سازد.
- مدل‌هایی که صرفاً ورودی صوتی می‌گیرند (مثل `google/gemini-2.5-flash` با
  `input_modalities: [text, audio]`) «**صوتی (چت)**» علامت می‌خورند: در `/models` دیده
  می‌شوند و در چت/ایجنت قابل استفاده‌اند، ولی endpoint اختصاصی گفتار ندارند و در `/audio`
  پیشنهاد نمی‌شوند.
- اگر هیچ‌کدام نبود، `meta.audio_kind` (ست‌شده دستی) و بعد الگوی شناسه
  (`whisper*`, `transcribe*`, `stt`, `asr`, `scribe`, `parakeet`, `chirp` → **STT**؛
  `tts*`, `*voice`, `eleven*`, `kokoro`, `aura-*`, `speech` → **TTS**) بررسی می‌شود.

## ۲) مدل‌های آماده

| مدل | نوع | قیمت رسمی |
|---|---|---|
| `whisper-1` | STT | ۰٫۰۰۶ دلار / دقیقه |
| `gpt-4o-transcribe` | STT | ۰٫۰۰۶ دلار / دقیقه |
| `gpt-4o-mini-transcribe` | STT | ۰٫۰۰۳ دلار / دقیقه |
| `openai/whisper-1` (OpenRouter) | STT | ۰٫۰۰۶ دلار / دقیقه |
| `openai/whisper-large-v3-turbo` | STT | ۰٫۰۰۰۲ دلار / دقیقه |
| `deepgram/nova-3` | STT | ۰٫۰۰۴۳ دلار / دقیقه |
| `elevenlabs/scribe-v2` | STT | ۰٫۰۰۳۶۷ دلار / دقیقه |
| `qwen/qwen3-asr-1.7b` | STT | ۰٫۰۰۰۴۵ دلار / دقیقه |
| `mistralai/voxtral-mini-transcribe` | STT | ۰٫۰۰۳ دلار / دقیقه |
| `tts-1` | TTS | ۰٫۰۱۵ دلار / ۱۰۰۰ نویسه |
| `tts-1-hd` | TTS | ۰٫۰۳ دلار / ۱۰۰۰ نویسه |
| `gpt-4o-mini-tts` | TTS | ۰٫۰۱۵ دلار / ۱۰۰۰ نویسه |
| `elevenlabs/eleven-v3` | TTS | ۰٫۰۸ دلار / ۱۰۰۰ نویسه |
| `deepgram/aura-2` | TTS | ۰٫۰۳ دلار / ۱۰۰۰ نویسه |
| `google/gemini-3.8-flash-tts` | TTS | ۰٫۰۰۰۵ دلار / ۱۰۰۰ نویسه |
| `hexgrad/kokoro-82m` | TTS | ۰٫۰۰۰۶۲ دلار / ۱۰۰۰ نویسه |
| `minimax/speech-2.8-hd` | TTS | ۰٫۱ دلار / ۱۰۰۰ نویسه |
| `qwen/qwen-audio-3.0-tts-flash` | TTS | ۰٫۰۱۵ دلار / ۱۰۰۰ نویسه |

این قیمت‌ها **پیش‌فرض** هستند؛ با `POST /v1/models/{id}/price` (فیلدهای `audio_input_price` و
`audio_output_price`) یا `PATCH /v1/models/{id}` قابل تغییرند و در `price_history` ثبت می‌شوند.

**تبدیل واحد در سینک:** OpenRouter قیمت STT را «دلار بر ثانیهٔ صوت» و TTS را «دلار بر نویسه»
می‌دهد؛ کاروند آن‌ها را به «دلار بر دقیقه» (×۶۰) و «دلار بر ۱۰۰۰ نویسه» (×۱۰۰۰) تبدیل می‌کند.
مدل‌هایی که بر ثانیهٔ **تولید** حساب می‌شوند (مثل مدل‌های موسیقی) در این واحدها نمی‌گنجند، پس
قیمت صوتی نمی‌گیرند و باید دستی قیمت‌گذاری شوند.

## ۳) صفحهٔ «صدا و گفتار» در پنل

`/audio` دو تب دارد:

**گفتار به متن:** انتخاب مدل STT، زبان اختیاری (`fa`), انتخاب فایل صوتی (mp3/wav/m4a/ogg/webm،
حداکثر ۲۵ مگابایت) → متن استخراج‌شده، مدت‌زمان واقعی صوت، هزینه و دکمهٔ «کپی متن».

**متن به گفتار:** انتخاب مدل TTS، voice، متن (حداکثر ۴۰۰۰ نویسه)، قالب (mp3/opus/aac/flac/wav)
و سرعت → پخش‌کنندهٔ صوتی در همان صفحه + دکمهٔ دانلود + هزینهٔ ثبت‌شده. دکمهٔ «برآورد هزینه»
بدون فراخوانی پروایدر قیمت را نشان می‌دهد.

## ۴) هزینه‌گذاری

```
STT: cost_usd = ceil(seconds) / 60 * audio_input_price
TTS: cost_usd = chars / 1000 * audio_output_price
cost_irr = round(cost_usd * (1 + markup_percent/100) * fx_rate)
```

- مدت صوت از پاسخ پروایدر خوانده می‌شود (`duration`؛ اگر نبود بزرگ‌ترین `segments[].end`).
- ثانیه‌ها به بالا گرد می‌شوند (۹۰ ثانیه = ۱٫۵ دقیقه).
- اگر `free_mode` روشن باشد `billable=false` ثبت می‌شود.
- سقف بودجهٔ ماهانهٔ سازمان مثل گفتگو چک می‌شود (`budget.org_exceeded`).

## ۵) پروایدرهای پشتیبانی‌شده

آداپتور OpenAI-سازگار (`openai`, `openai_compatible`, `groq`, `together`, `azure_openai`,
`openrouter`) دو متد صوتی دارد:

- `POST {base_url}/audio/transcriptions` (multipart: `file`, `model`, `language`, `response_format=verbose_json`)
- `POST {base_url}/audio/speech` (JSON: `model`, `input`, `voice`, `response_format`, `speed`)

**OpenRouter دو تفاوت دارد:** شناسهٔ مدل‌ها namespace دارد (`openai/whisper-1` نه `whisper-1`) و
endpoint رونویسی JSON با صوت base64 می‌خواهد، نه multipart:

```json
{"model": "openai/whisper-1", "input_audio": {"data": "<base64>", "format": "wav"}}
```

آداپتور خودش این شکل را می‌سازد (فرمت از پسوند فایل یا MIME حدس زده می‌شود). TTS همان بدنهٔ
OpenAI را می‌پذیرد، فقط `model` را namespace‌دار بدهید.

روی Azure مسیر به‌صورت `/openai/deployments/{model}/audio/...` ساخته می‌شود. پروایدر
`anthropic`/`gemini` فعلاً صدا نمی‌دهند و خطای `audio.unsupported_provider` برمی‌گردانند
(می‌توانید با آداپتور توصیفی endpoint سفارشی بسازید).

**پروکسی:** همان `meta.proxy` پروایدر استفاده می‌شود؛ اگر سرور شما به `api.openai.com` دسترسی
ندارد، همان‌جا پروکسی را ست کنید.

## ۶) نکات عملی

- متن‌های طولانی را تکه‌تکه کنید؛ هر درخواست حداکثر ۴۰۰۰ نویسه است.
- برای فارسی، `whisper-1` با `language=fa` نتیجهٔ بهتری می‌دهد.
- فایل‌ها روی دیسک ذخیره **نمی‌شوند**؛ در حافظه خوانده و به پروایدر پاس می‌شوند.
- برای پیام صوتی در پیام‌رسان‌ها (قدم ۱۰) هنوز ورودی صوتی پردازش نمی‌شود؛ این کار با همین
  endpoint STT در قدم بعد قابل اتصال است (`audio.transcribe` → متن → اجرای ایجنت).
