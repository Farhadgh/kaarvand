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

**متن به گفتار:** انتخاب مدل TTS، voice، متن (حداکثر ۴۰۰۰ نویسه)، قالب
(mp3/wav/opus/aac/flac/pcm) و سرعت → پخش‌کنندهٔ صوتی در همان صفحه + دکمهٔ دانلود + هزینهٔ
ثبت‌شده. دکمهٔ «برآورد هزینه» بدون فراخوانی پروایدر قیمت را نشان می‌دهد.

کنار انتخاب مدل، وضعیت فارسی همان مدل نوشته می‌شود (بخش ۷) و تیک «فقط مدل‌هایی که فارسی را
می‌خوانند» فهرست را به مدل‌های تأییدشده محدود می‌کند. فهرست مدل‌ها هم از سمت API طوری مرتب
می‌شود که مدل‌های فارسی‌بلد اول بیایند.

**voice از خود کاتالوگ می‌آید:** `supported_voices` پروایدر در `models.meta.voices` ذخیره
می‌شود و پنل همان‌ها را نشان می‌دهد (پیش‌فرض `alloy` مخصوص OpenAI است و مثلاً ElevenLabs آن را
رد می‌کند). اگر کلاینتی voice نامعتبر بفرستد، سرویس به‌جای شکست، اولین voice مجاز مدل را
استفاده می‌کند و نام واقعی را در هدر `X-Audio-Voice` برمی‌گرداند.

> **نکتهٔ ارتقا:** مدل‌هایی که پیش از این نسخه سینک شده‌اند `meta.voices` ندارند؛ یک‌بار
> «سینک مدل‌ها» را بزنید تا فهرست صداهای هر مدل پر شود (بدون آن، voice پیش‌فرض `alloy` فرستاده
> می‌شود و مدل‌هایی مثل ElevenLabs/Gemini خطای ۴۰۰ می‌دهند).

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

## ۷) پشتیبانی فارسی — سنجیده، نه حدس‌زده

«۴۰+ زبان» در توضیحات سازنده به معنای فارسیِ خوب نیست. چند مدل معروف فارسی را با لهجهٔ عربی
می‌خوانند و بعضی صدای بی‌ربط تولید می‌کنند. پس کاروند به‌جای اعتماد به متن تبلیغاتی، خودش
آزمایش می‌کند:

```
متن فارسی → TTS مدل → رونویسی با ویسپر → مقایسهٔ متن رونویسی با متن اصلی (امتیاز ۰..۱)
```

اسکریپت: `scripts/fa_audio_probe.py` (بازتولیدپذیر):

```bash
cd services/api
OPENROUTER_API_KEY=sk-or-... python ../../scripts/fa_audio_probe.py            # TTS + STT
OPENROUTER_API_KEY=... python ../../scripts/fa_audio_probe.py --kind tts --json /tmp/fa.json
OPENROUTER_API_KEY=... python ../../scripts/fa_audio_probe.py --write-meta     # روی سرور
```

| سطح | امتیاز | معنی | برچسب پنل |
|---|---|---|---|
| `verified` | ≥ ۰٫۹۵ | فارسی را روان می‌خواند (آزمایش‌شده) | «فارسی ✓» سبز |
| `good` | ≥ ۰٫۸۰ | فارسی با لهجهٔ کم | «فارسی ~» فیروزه‌ای |
| `weak` | ≥ ۰٫۵۰ | فارسی شکسته/عربی‌شده | «فارسی ضعیف» کهربایی |
| `none` | < ۰٫۵۰ | فارسی را پشتیبانی نمی‌کند | «فارسی ✗» قرمز |

**نتیجهٔ سنجش ۱۲ نوامبر ۲۰۲۶ (۳۹ مدل TTS و ۳۱ مدل STT):** فقط ۱۲ مدل از ۳۹ مدل TTS فارسی را
واقعاً روان می‌خوانند؛ در سمت STT همهٔ ۳۱ مدل متن فارسی را درست نوشتند.

| مدل TTS | امتیاز | سطح |
|---|---|---|
| `elevenlabs/eleven-v3` · `eleven-v3-conversational` · `eleven-v4` · `eleven-v4-turbo` | ۰٫۹۸ | verified |
| `google/gemini-3.1-flash-tts-preview` · `gemini-3.8-flash-tts` · `gemini-3.8-flash-lite-tts` | ۰٫۹۸ | verified |
| `minimax/speech-2.8-hd` · `speech-2.8-turbo` | ۰٫۹۸ | verified |
| `mistralai/voxtral-mini-tts-3-0` | ۰٫۹۸ | verified |
| `x-ai/grok-voice-tts-1.0` | ۰٫۹۸ | verified |
| `fish-audio/drama-3` | ۰٫۹۸ | verified |
| `fish-audio/s2-pro` | ۰٫۹۴ | good |
| `elevenlabs/eleven-flash-v2.5` | ۰٫۹۳ | good |
| `elevenlabs/eleven-turbo-v2.5` | ۰٫۹۲ | good |
| `elevenlabs/eleven-multilingual-v2` | ۰٫۸۵ | good |
| `fish-audio/s2.1-pro` · `s2.1-pro-free` · `s1` | ۰٫۷۵–۰٫۷۹ | weak |
| `microsoft/mai-voice-2` · `2.1` · `2-flash` · `2.1-flash` | ۰٫۶۷–۰٫۷۱ | weak |
| `qwen/qwen-audio-3.0-tts-flash` · `tts-plus` | ۰٫۶۲–۰٫۶۸ | weak |
| `mistralai/voxtral-mini-tts-2603` | ۰٫۵۶ | weak |
| `bytedance-seed/seed-audio-1-0` | ۰٫۴۱ | none |
| `elevenlabs/eleven-flash-v2` · `eleven-turbo-v2` | ۰٫۱۵–۰٫۱۷ | none |
| `speechify/simba-3.5` · `deepgram/flux-tts` | ۰٫۱۶ | none |
| `sesame/csm-1b` · `deepgram/aura-2` · `assemblyai/assemblyai-tts-1` | ۰٫۱۲–۰٫۱۵ | none |
| `canopylabs/orpheus-3b-0.1-ft` · `hexgrad/kokoro-82m` | ۰٫۰۰–۰٫۰۸ | none |
| `heygen/heygen-voice-1*` | — | خطای ۴۰۰ روی mp3؛ با `pcm` کار می‌کند |

**چطور این اطلاعات به پنل می‌رسد؟**

- جدول بالا در `services/api/app/audio/languages.py` نگه‌داری می‌شود
  (`PERSIAN_TTS` / `PERSIAN_STT` + `PROBED_AT`).
- `GET /v1/audio/models` برای هر مدل `persian`، `persian_score` و `persian_note_fa` می‌دهد؛
  فیلتر `?persian=verified|good|weak|none|any` هم دارد.
- `GET /v1/models` (صفحهٔ مدل‌ها) هم فیلد `persian` را برمی‌گرداند و پنل بج «فارسی ✓» را کنار
  مدل‌های صوتی نشان می‌دهد.
- **override دستی:** `PATCH /v1/models/{id}` با `{"persian": "good"}` (یا `none`/`unknown` برای
  پاک‌کردن) در `meta.persian` ذخیره می‌شود و بر جدول اولویت دارد. نتیجهٔ سنجش تازه هم می‌تواند در
  `meta.persian_probe` بنشیند (`--write-meta`).

## ۸) وقتی مدل فقط `pcm` می‌دهد

بعضی مدل‌ها (`google/gemini-*-tts`، `heygen/*`) فقط `response_format="pcm"` را قبول می‌کنند و
برای بقیه `400` برمی‌گردانند. آداپتور:

1. پیام خطا را می‌خواند و فرمت خواسته‌شده را استخراج می‌کند،
2. **یک‌بار** با همان فرمت دوباره تلاش می‌کند،
3. اگر پاسخ `audio/pcm` بود، نمونه‌های خام را با هدر WAV بسته‌بندی می‌کند
   (`providers/adapters/audio_pcm.py`؛ نرخ/کانال از `content-type` مثل
   `audio/pcm;rate=24000;channels=1`).

نتیجه: کاربر همیشه فایل قابل‌پخش می‌گیرد؛ قالب واقعی در هدر `X-Audio-Format` و پسوند فایل
`Content-Disposition` می‌آید (اگر `pcm` خواسته باشید، `wav` تحویل می‌گیرید).

**اگر پیام ۴۰۰ پروایدر کلی بود** (مثل `Provider returned 400` بدون نام فرمت)، علت معمولاً voice
است نه فرمت: مدل‌های Gemini صداهایی مثل `Zephyr`/`Kore` می‌خواهند. در این حالت سرویس با
`meta.voices` اولین voice مجاز را می‌فرستد؛ پس اگر هنوز خطا دیدید، یک‌بار «سینک مدل‌ها» بزنید.

## ۹) خطاهای شفاف

هر پاسخ ۴xx پروایدر با کد قابل‌ترجمه و متن خود پروایدر برمی‌گردد (و در لاگ با `logger.warning`
ثبت می‌شود):

| وضعیت پروایدر | کد | پیام فارسی پنل |
|---|---|---|
| ۴۰۱/۴۰۳ | `provider.auth_failed` | کلید پروایدر معتبر نیست. |
| ۴۲۹ | `provider.rate_limited` | محدودیت نرخ پروایدر فعال شد؛ چند لحظه بعد دوباره تلاش کنید. |
| بقیهٔ ۴xx | `provider.rejected` | پروایدر درخواست را رد کرد؛ متن خطای آن در پایین آمده است. |
| ۵xx | `provider.call_failed` | فراخوانی مدل ناموفق بود. |

متن انگلیسی پروایدر در `error.params.detail` می‌آید، پس دیگر «خطای نامشخص» بی‌اطلاع نمی‌بینید؛
اگر کدی در `errors-fa.ts` نباشد، خودِ کد هم در پیام نمایش داده می‌شود.

