import Link from "next/link";

import { SettingsClient } from "@/components/settings-client";
import { Card, KeyValue } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import type { SettingsPayload } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const settings = await serverFetch<SettingsPayload>("/settings");
  const canEdit = settings.me.role === "owner" || settings.me.role === "admin";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">تنظیمات</h1>
        <p className="muted mt-1">سازمان، نرخ ارز و پروفایل شخصی</p>
      </div>

      <SettingsClient settings={settings} canEdit={canEdit} />

      <Card>
        <div className="card-body">
          <h2 className="mb-2 text-sm font-bold text-ink-800">وضعیت نسخه</h2>
          <KeyValue label="نسخه">{settings.version}</KeyValue>
          <KeyValue label="حالت آزمایشی">{settings.free_mode ? "فعال" : "غیرفعال"}</KeyValue>
          <KeyValue label="درگاه پرداخت">{settings.payment_gateway}</KeyValue>
          <KeyValue label="تقویم">{settings.calendar === "jalali" ? "جلالی" : "میلادی"}</KeyValue>
          <KeyValue label="کلید سازمان">
            <span className="ltr text-xs">{settings.org.slug}</span>
          </KeyValue>
          <p className="mt-3 text-xs text-ink-500">
            مصرف و هزینه را در{" "}
            <Link href="/usage" className="text-brand-700 underline">
              صفحه‌ی مصرف
            </Link>{" "}
            ببینید.
          </p>
        </div>
      </Card>
    </div>
  );
}
