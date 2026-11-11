import Link from "next/link";

import { ModelsTable } from "@/components/models-table";
import { Card, EmptyState } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import type { AudioPreset, Model, Provider, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  const [models, providers, presets, me] = await Promise.all([
    serverFetch<Model[]>("/models?enabled_only=false&limit=500"),
    serverFetch<Provider[]>("/providers"),
    serverFetch<AudioPreset[]>("/audio/presets").catch(() => [] as AudioPreset[]),
    serverFetch<User>("/auth/me"),
  ]);

  if (providers.length === 0) {
    return (
      <Card>
        <EmptyState
          title="هنوز پروایدری ندارید"
          description="برای دیدن مدل‌ها ابتدا یک پروایدر اضافه و سینک کنید."
          action={
            <Link className="btn-primary" href="/providers">
              افزودن پروایدر
            </Link>
          }
        />
      </Card>
    );
  }

  const providerNames: Record<string, string> = {};
  for (const provider of providers) providerNames[provider.id] = provider.name;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">مدل‌ها</h1>
        <p className="muted mt-1">
          مدل‌ها از پروایدر کشف می‌شوند؛ فعال/غیرفعال کردن و قیمت دستی روی همین صفحه است.
        </p>
      </div>
      <ModelsTable
        models={models}
        providerNames={providerNames}
        presets={presets}
        providers={providers}
        canEdit={me.role === "owner" || me.role === "admin"}
      />
    </div>
  );
}
