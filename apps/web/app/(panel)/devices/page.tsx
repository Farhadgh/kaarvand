import { DeviceAppsCard } from "@/components/device-apps-card";
import { DeviceCreateForm } from "@/components/devices-create-form";
import { DevicesTable } from "@/components/devices-table";
import { Card, CardHeader } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import type { Device, DeviceApp, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DevicesPage() {
  const [devices, me] = await Promise.all([
    serverFetch<Device[]>("/devices"),
    serverFetch<User>("/auth/me"),
  ]);
  const canEdit = me.role === "owner" || me.role === "admin";

  const appsByDevice = new Map<string, DeviceApp[]>();
  await Promise.all(
    devices.map(async (device) => {
      const apps = await serverFetch<DeviceApp[]>(`/devices/${device.id}/apps`).catch(
        () => [] as DeviceApp[],
      );
      appsByDevice.set(device.id, apps);
    }),
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">دستگاه‌ها</h1>
        <p className="muted mt-1">
          کانکتور روی ویندوز اجرا می‌شود و با WSS به سرور وصل می‌شود؛ فایل، فرمان و ورودی کاربر فقط
          داخل مسیرهای مجاز.
        </p>
      </div>

      <DeviceCreateForm canEdit={canEdit} />
      <DevicesTable devices={devices} canEdit={canEdit} />

      {devices.map((device) => (
        <DeviceAppsCard
          key={device.id}
          device={device}
          apps={appsByDevice.get(device.id) ?? []}
          canEdit={canEdit}
        />
      ))}

      <Card>
        <CardHeader title="اجرای کلاینت" subtitle="روی دستگاه ویندوزی" />
        <div className="card-body space-y-2 text-sm text-ink-600">
          <pre className="ltr overflow-auto rounded-lg bg-ink-900 p-3 text-xs text-ink-100">
{`python scripts/connector_client.py \\
  --server ws://127.0.0.1:8000/v1/ws/connector \\
  --device-id <شناسه دستگاه> \\
  --allow-path C:\\Users\\Public`}
          </pre>
          <p>
            کلاینت پس از اتصال، کد جفت‌سازی را دریافت و ثبت می‌کند؛ پس از آن توکن دستگاه ذخیره
            می‌شود.
          </p>
        </div>
      </Card>
    </div>
  );
}
