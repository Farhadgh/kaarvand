"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, ErrorBox } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { formatDateTime, toFaDigits } from "@/lib/format";
import type { Device, DeviceWithCode } from "@/lib/types";

export function DevicesTable({
  devices,
  canEdit,
}: {
  devices: Device[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState<{ name: string; code: string; expires: string } | null>(null);
  const [ops, setOps] = useState<Record<string, string[]>>({});
  const [openId, setOpenId] = useState<string | null>(null);

  async function act(key: string, task: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await task();
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      {error ? <ErrorBox message={error} /> : null}
      {code ? (
        <div className="rounded-lg border border-brand-200 bg-brand-50 px-4 py-3">
          <p className="text-sm text-brand-900">کد جفت‌سازی «{code.name}»:</p>
          <p className="font-mono text-2xl tracking-[0.3em] text-brand-800" dir="ltr">
            {toFaDigits(code.code)}
          </p>
          <p className="text-xs text-brand-700">اعتبار تا {formatDateTime(code.expires)}</p>
        </div>
      ) : null}

      <div className="table-wrapper">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">دستگاه</th>
              <th className="th">سیستم</th>
              <th className="th">وضعیت</th>
              <th className="th">مسیرهای مجاز</th>
              <th className="th">آخرین اتصال</th>
              <th className="th">عملیات</th>
            </tr>
          </thead>
          <tbody>
            {devices.length === 0 ? (
              <tr>
                <td className="td text-center text-ink-500" colSpan={6}>
                  هنوز دستگاهی ثبت نشده است.
                </td>
              </tr>
            ) : (
              devices.map((device) => (
                <tr key={device.id} className="hover:bg-ink-50/60">
                  <td className="td font-medium text-ink-900">{device.name}</td>
                  <td className="td text-xs">{device.os ?? "—"}</td>
                  <td className="td">
                    <Badge value={device.status} />
                  </td>
                  <td className="td ltr text-[11px]">{device.allowed_paths.join(", ") || "—"}</td>
                  <td className="td text-xs">{formatDateTime(device.last_seen_at)}</td>
                  <td className="td">
                    <div className="flex flex-wrap gap-1">
                      <button
                        className="btn-ghost !px-2 !py-1 text-xs"
                        disabled={!canEdit || busy !== null}
                        onClick={() =>
                          void act(`rotate-${device.id}`, async () => {
                            const rotated = await clientFetch<DeviceWithCode>(
                              `/devices/${device.id}/rotate-code`,
                              { method: "POST" },
                            );
                            setCode({
                              name: rotated.name,
                              code: rotated.pairing_code,
                              expires: rotated.pairing_expires_at,
                            });
                          })
                        }
                      >
                        کد جدید
                      </button>
                      <button
                        className="btn-ghost !px-2 !py-1 text-xs"
                        onClick={() => {
                          setOpenId(openId === device.id ? null : device.id);
                          if (!ops[device.id]) {
                            void act(`ops-${device.id}`, async () => {
                              const payload = await clientFetch<{ ops: string[] }>(
                                `/devices/${device.id}/ops`,
                              );
                              setOps((current) => ({ ...current, [device.id]: payload.ops }));
                            });
                          }
                        }}
                      >
                        اقدام‌ها
                      </button>
                      {canEdit ? (
                        <button
                          className="btn-ghost !px-2 !py-1 text-xs text-rose-600"
                          onClick={() => {
                            if (!window.confirm("این دستگاه حذف شود؟")) return;
                            void act(`del-${device.id}`, () =>
                              clientFetch(`/devices/${device.id}`, { method: "DELETE" }),
                            );
                          }}
                        >
                          حذف
                        </button>
                      ) : null}
                    </div>
                    {openId === device.id ? (
                      <div className="ltr mt-2 max-w-xs text-[11px] text-ink-500">
                        {(ops[device.id] ?? []).join(" · ") || "—"}
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
