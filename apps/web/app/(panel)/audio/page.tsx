import { AudioClient } from "@/components/audio-client";
import { serverFetch } from "@/lib/api-server";
import type { AudioMeta, AudioModel, AudioPreset, Provider, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AudioPage() {
  const [models, meta, presets, providers, me] = await Promise.all([
    serverFetch<AudioModel[]>("/audio/models"),
    serverFetch<AudioMeta>("/audio/meta"),
    serverFetch<AudioPreset[]>("/audio/presets"),
    serverFetch<Provider[]>("/providers"),
    serverFetch<User>("/auth/me"),
  ]);
  const canEdit = me.role === "admin" || me.role === "user";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-ink-900">صدا و گفتار</h1>
        <p className="muted mt-1">
          تبدیل گفتار به متن و متن به گفتار با مدل‌های صوتی پروایدرهای شما؛ هزینه به‌صورت دقیقه
          (STT) و هزار نویسه (TTS) در دفتر مصرف ثبت می‌شود.
        </p>
      </div>
      <AudioClient
        models={models}
        meta={meta}
        presets={presets}
        providers={providers}
        canEdit={canEdit}
      />
    </div>
  );
}
