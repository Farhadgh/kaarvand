"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Card, CardHeader, EmptyState, ErrorBox, Field, Spinner } from "@/components/ui";
import { clientFetch, messageOf, toApiError } from "@/lib/api";
import type {
  AudioMeta,
  AudioModel,
  AudioPreset,
  Provider,
  SpeechEstimate,
  TranscriptionResult,
} from "@/lib/types";

type Tab = "stt" | "tts";

/** provider kinds whose adapter implements /audio/transcriptions + /audio/speech */
const AUDIO_CAPABLE_KINDS = ["openai", "openai_compatible", "groq", "together", "azure_openai"];

export function AudioClient({
  models,
  meta,
  presets,
  providers,
  canEdit,
}: {
  models: AudioModel[];
  meta: AudioMeta;
  presets: AudioPreset[];
  providers: Provider[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("stt");
  const sttModels = useMemo(() => models.filter((m) => m.kind === "stt"), [models]);
  const ttsModels = useMemo(() => models.filter((m) => m.kind === "tts"), [models]);

  const [error, setError] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      {error ? <ErrorBox message={error} /> : null}

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["stt", "گفتار به متن", "ویس یا فایل صوتی را بفرستید تا متن بگیرید"],
            ["tts", "متن به گفتار", "متن فارسی را به فایل صوتی تبدیل کنید"],
          ] as const
        ).map(([key, title, hint]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={
              tab === key
                ? "btn btn-primary flex-1 flex-col items-start py-3 text-right"
                : "btn btn-ghost flex-1 flex-col items-start py-3 text-right"
            }
          >
            <span className="font-bold">{title}</span>
            <span className="text-xs font-normal opacity-80">{hint}</span>
          </button>
        ))}
      </div>

      {tab === "stt" ? (
        <SttPanel
          models={sttModels}
          maxMb={meta.max_upload_mb}
          onError={setError}
          onDone={() => setError(null)}
        />
      ) : (
        <TtsPanel
          models={ttsModels}
          meta={meta}
          onError={setError}
          onDone={() => setError(null)}
        />
      )}

      <AddModelCard presets={presets} providers={providers} canEdit={canEdit} />

      {models.length === 0 ? (
        <Card>
          <EmptyState
            title="هیچ مدل صوتی فعالی ندارید"
            description="از کارت «افزودن مدل صوتی» یکی از مدل‌های آماده (ویسپر، TTS-1) را به پروایدر خود اضافه کنید، یا در صفحهٔ پروایدرها «سینک مدل‌ها» را بزنید."
          />
        </Card>
      ) : null}
    </div>
  );
}

function costLabel(irr: number, usd: string | number): string {
  return `${Number(usd).toFixed(6)} دلار · ${irr.toLocaleString("fa-IR")} ریال`;
}

function SttPanel({
  models,
  maxMb,
  onError,
  onDone,
}: {
  models: AudioModel[];
  maxMb: number;
  onError: (message: string) => void;
  onDone: () => void;
}) {
  const [modelId, setModelId] = useState(models[0]?.id ?? "");
  const [language, setLanguage] = useState("fa");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TranscriptionResult | null>(null);

  async function submit() {
    if (!file) {
      onError("اول یک فایل صوتی انتخاب کنید.");
      return;
    }
    if (!modelId) {
      onError("مدل گفتار به متن انتخاب نشده است.");
      return;
    }
    setBusy(true);
    onDone();
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("model_id", modelId);
      if (language.trim()) form.append("language", language.trim());

      const response = await fetch("/api/audio/transcriptions", {
        method: "POST",
        body: form,
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw toApiError(response.status, payload);
      }
      setResult(payload as TranscriptionResult);
    } catch (exc) {
      onError(messageOf(exc));
    } finally {
      setBusy(false);
    }
  }

  if (models.length === 0) {
    return (
      <Card>
        <CardHeader title="گفتار به متن" subtitle="هیچ مدل STT فعالی ثبت نشده است" />
        <div className="card-body muted">ابتدا از پایین صفحه یک مدل صوتی اضافه کنید.</div>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="گفتار به متن (STT)"
        subtitle={`حداکثر ${maxMb} مگابایت · هزینه بر اساس دقیقهٔ صدا`}
      />
      <div className="card-body space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="مدل">
            <select className="input" value={modelId} onChange={(e) => setModelId(e.target.value)}>
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.display_name_fa ?? model.external_id} — {model.provider_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="زبان (اختیاری)" hint="مثال: fa یا en — خالی بگذارید تا خودکار تشخیص دهد">
            <input className="input" value={language} onChange={(e) => setLanguage(e.target.value)} />
          </Field>
        </div>

        <Field label="فایل صوتی" hint="mp3, wav, m4a, ogg, webm — ضبط مستقیم از مرورگر هم مجاز است">
          <input
            className="input"
            type="file"
            accept="audio/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </Field>

        <button type="button" className="btn btn-primary" onClick={submit} disabled={busy}>
          {busy ? "در حال تبدیل…" : "تبدیل به متن"}
        </button>

        {busy ? <Spinner label="در حال پردازش صدا…" /> : null}

        {result ? (
          <div className="space-y-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <p className="whitespace-pre-wrap text-sm leading-7 text-ink-900">{result.text}</p>
            <p className="text-xs text-emerald-700">
              {result.seconds.toFixed(1)} ثانیه · {costLabel(result.cost_irr, result.cost_usd)}
              {result.language ? ` · زبان: ${result.language}` : ""}
            </p>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => navigator.clipboard.writeText(result.text)}
            >
              کپی متن
            </button>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function TtsPanel({
  models,
  meta,
  onError,
  onDone,
}: {
  models: AudioModel[];
  meta: AudioMeta;
  onError: (message: string) => void;
  onDone: () => void;
}) {
  const [modelId, setModelId] = useState(models[0]?.id ?? "");
  const [text, setText] = useState("");
  const [voice, setVoice] = useState(models[0]?.voices[0] ?? "alloy");
  const [format, setFormat] = useState("mp3");
  const [speed, setSpeed] = useState("1");
  const [busy, setBusy] = useState(false);
  const [estimate, setEstimate] = useState<SpeechEstimate | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [lastMeta, setLastMeta] = useState<SpeechEstimate | null>(null);

  const selected = models.find((model) => model.id === modelId);
  const voices = selected?.voices.length ? selected.voices : meta.voices;

  async function estimateCost() {
    if (!modelId || !text.trim()) {
      onError("متن و مدل را انتخاب کنید.");
      return;
    }
    onDone();
    try {
      const result = await clientFetch<SpeechEstimate>(
        `/audio/speech/estimate?model_id=${modelId}&text=${encodeURIComponent(text)}`,
      );
      setEstimate(result);
    } catch (exc) {
      onError(messageOf(exc));
    }
  }

  async function generate() {
    if (!modelId || !text.trim()) {
      onError("متن و مدل را انتخاب کنید.");
      return;
    }
    setBusy(true);
    onDone();
    try {
      const response = await fetch("/api/audio/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          model_id: modelId,
          text,
          voice,
          format,
          speed: Number(speed) || 1,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw toApiError(response.status, payload);
      }
      const blob = await response.blob();
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setAudioUrl(URL.createObjectURL(blob));
      setLastMeta(estimate);
    } catch (exc) {
      onError(messageOf(exc));
    } finally {
      setBusy(false);
    }
  }

  if (models.length === 0) {
    return (
      <Card>
        <CardHeader title="متن به گفتار" subtitle="هیچ مدل TTS فعالی ثبت نشده است" />
        <div className="card-body muted">ابتدا از پایین صفحه یک مدل صوتی اضافه کنید.</div>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader
        title="متن به گفتار (TTS)"
        subtitle={`حداکثر ${meta.max_tts_chars.toLocaleString("fa-IR")} نویسه · هزینه بر اساس هزار نویسه`}
      />
      <div className="card-body space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="مدل">
            <select
              className="input"
              value={modelId}
              onChange={(e) => {
                setModelId(e.target.value);
                const next = models.find((model) => model.id === e.target.value);
                setVoice(next?.voices[0] ?? "alloy");
              }}
            >
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.display_name_fa ?? model.external_id} — {model.provider_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="صدا (voice)">
            <select className="input" value={voice} onChange={(e) => setVoice(e.target.value)}>
              {voices.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field
          label="متن"
          hint={`${text.length.toLocaleString("fa-IR")} از ${meta.max_tts_chars.toLocaleString("fa-IR")} نویسه`}
        >
          <textarea
            className="input min-h-32"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setEstimate(null);
            }}
            placeholder="سلام! این یک نمونهٔ تبدیل متن به گفتار است."
          />
        </Field>

        <div className="grid gap-3 md:grid-cols-2">
          <Field label="قالب فایل">
            <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
              {meta.formats.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="سرعت" hint="۰.۲۵ تا ۴">
            <input className="input" value={speed} onChange={(e) => setSpeed(e.target.value)} />
          </Field>
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-primary" onClick={generate} disabled={busy}>
            {busy ? "در حال ساخت صدا…" : "تولید صدا"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={estimateCost} disabled={busy}>
            برآورد هزینه
          </button>
        </div>

        {busy ? <Spinner label="در حال تبدیل متن به گفتار…" /> : null}

        {estimate ? (
          <p className="text-sm text-ink-600">
            برآورد: {estimate.chars.toLocaleString("fa-IR")} نویسه ·{" "}
            {costLabel(estimate.cost_irr, estimate.cost_usd)}
          </p>
        ) : null}

        {audioUrl ? (
          <div className="space-y-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <audio controls src={audioUrl} className="w-full" />
            <a className="btn btn-ghost" href={audioUrl} download={`kaarvand-speech.${format}`}>
              دانلود فایل
            </a>
            {lastMeta ? (
              <p className="text-xs text-emerald-700">
                هزینهٔ ثبت‌شده در دفتر مصرف: {costLabel(lastMeta.cost_irr, lastMeta.cost_usd)}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}

export function AddModelCard({
  presets,
  providers,
  canEdit,
}: {
  presets: AudioPreset[];
  providers: Provider[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [providerId, setProviderId] = useState(providers[0]?.id ?? "");
  const [presetSlug, setPresetSlug] = useState(presets[0]?.slug ?? "");
  const [externalId, setExternalId] = useState("");
  const [kind, setKind] = useState<"stt" | "tts">("stt");
  const [minutePrice, setMinutePrice] = useState("");
  const [charPrice, setCharPrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selectedProvider = providers.find((provider) => provider.id === providerId);
  const audioCapable = !selectedProvider || AUDIO_CAPABLE_KINDS.includes(selectedProvider.kind);

  async function addFromPreset() {
    const preset = presets.find((item) => item.slug === presetSlug);
    if (!preset || !providerId) {
      setError("پروایدر و مدل آماده را انتخاب کنید.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await clientFetch("/models", {
        method: "POST",
        body: JSON.stringify({
          provider_id: providerId,
          external_id: preset.external_id,
          display_name_fa: preset.label_fa,
          audio_kind: preset.kind,
          audio_input_price: preset.audio_input_price,
          audio_output_price: preset.audio_output_price,
        }),
      });
      setMessage(`مدل «${preset.label_fa}» اضافه شد.`);
      router.refresh();
    } catch (exc) {
      setError(messageOf(exc));
    } finally {
      setBusy(false);
    }
  }

  async function addCustom() {
    if (!providerId || !externalId.trim()) {
      setError("پروایدر و شناسهٔ مدل لازم است.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await clientFetch("/models", {
        method: "POST",
        body: JSON.stringify({
          provider_id: providerId,
          external_id: externalId.trim(),
          audio_kind: kind,
          audio_input_price: kind === "stt" ? minutePrice || null : null,
          audio_output_price: kind === "tts" ? charPrice || null : null,
        }),
      });
      setMessage(`مدل «${externalId.trim()}» اضافه شد.`);
      setExternalId("");
      router.refresh();
    } catch (exc) {
      setError(messageOf(exc));
    } finally {
      setBusy(false);
    }
  }

  if (!canEdit) return null;

  return (
    <Card>
      <CardHeader
        title="افزودن مدل صوتی"
        subtitle="اگر پروایدر شما مدل گفتار/صدا را در فهرست نمی‌آورد، از اینجا اضافه کنید"
      />
      <div className="card-body space-y-4">
        {providers.length === 0 ? (
          <p className="muted">اول در صفحهٔ «پروایدرها» یک پروایدر اضافه کنید.</p>
        ) : (
          <Field label="پروایدر">
            <select
              className="input"
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
            >
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name} ({provider.kind})
                </option>
              ))}
            </select>
          </Field>
        )}

        {audioCapable ? null : (
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            این پروایدر ({selectedProvider?.kind}) نقطهٔ پایانی صوتی ندارد؛ مدل اضافه می‌شود ولی
            فراخوانی صوتی خطای «پروایدر پشتیبانی نمی‌کند» می‌دهد. برای صدا از پروایدری با نوع
            openai / openai_compatible / groq / together / azure_openai استفاده کنید.
          </p>
        )}

        <div className="rounded-lg border border-ink-100 p-3">
          <p className="mb-2 text-sm font-bold text-ink-800">مدل‌های آماده (قیمت رسمی)</p>
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex-1">
              <span className="label">مدل</span>
              <select
                className="input"
                value={presetSlug}
                onChange={(e) => setPresetSlug(e.target.value)}
              >
                {presets.map((preset) => (
                  <option key={preset.slug} value={preset.slug}>
                    {preset.label_fa} ({preset.kind === "stt" ? "گفتار→متن" : "متن→گفتار"})
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="btn btn-primary" onClick={addFromPreset} disabled={busy}>
              افزودن
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-ink-100 p-3">
          <p className="mb-2 text-sm font-bold text-ink-800">مدل دلخواه</p>
          <div className="grid gap-3 md:grid-cols-4">
            <Field label="شناسهٔ مدل">
              <input
                className="input"
                value={externalId}
                onChange={(e) => setExternalId(e.target.value)}
                placeholder="whisper-large-v3"
              />
            </Field>
            <Field label="نوع">
              <select
                className="input"
                value={kind}
                onChange={(e) => setKind(e.target.value as "stt" | "tts")}
              >
                <option value="stt">گفتار به متن</option>
                <option value="tts">متن به گفتار</option>
              </select>
            </Field>
            <Field label="قیمت (دلار/دقیقه)" hint="برای STT">
              <input
                className="input"
                value={minutePrice}
                onChange={(e) => setMinutePrice(e.target.value)}
                placeholder="0.006"
                disabled={kind !== "stt"}
              />
            </Field>
            <Field label="قیمت (دلار/۱۰۰۰ نویسه)" hint="برای TTS">
              <input
                className="input"
                value={charPrice}
                onChange={(e) => setCharPrice(e.target.value)}
                placeholder="0.015"
                disabled={kind !== "tts"}
              />
            </Field>
          </div>
          <button type="button" className="btn btn-ghost mt-3" onClick={addCustom} disabled={busy}>
            افزودن مدل دلخواه
          </button>
        </div>

        {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
        {error ? <ErrorBox message={error} /> : null}
      </div>
    </Card>
  );
}


