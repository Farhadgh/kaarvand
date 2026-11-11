import { ProviderActions } from "@/components/providers-actions";
import { Badge } from "@/components/ui";
import { messages } from "@/lib/copy";
import { formatDateTime } from "@/lib/format";
import type { Provider } from "@/lib/types";

export function ProvidersTable({
  providers,
  canEdit,
}: {
  providers: Provider[];
  canEdit: boolean;
}) {
  return (
    <div className="table-wrapper">
      <table className="w-full">
        <thead>
          <tr>
            <th className="th">نام</th>
            <th className="th">نوع</th>
            <th className="th">سلامت</th>
            <th className="th">کلید</th>
            <th className="th">آخرین سینک</th>
            <th className="th">وضعیت</th>
            <th className="th">{messages.actions}</th>
          </tr>
        </thead>
        <tbody>
          {providers.length === 0 ? (
            <tr>
              <td className="td text-center text-ink-500" colSpan={7}>
                هنوز پروایدری اضافه نشده است.
              </td>
            </tr>
          ) : (
            providers.map((provider) => (
              <tr key={provider.id} className="hover:bg-ink-50/60">
                <td className="td">
                  <div className="font-medium text-ink-900">{provider.name}</div>
                  <div className="ltr text-xs text-ink-400">{provider.base_url ?? provider.slug}</div>
                </td>
                <td className="td">{provider.kind}</td>
                <td className="td">
                  <Badge value={provider.health} />
                  {provider.health_message ? (
                    <div className="mt-1 max-w-[16rem] truncate text-xs text-rose-600">
                      {provider.health_message}
                    </div>
                  ) : null}
                </td>
                <td className="td ltr text-xs">{provider.api_key_masked ?? "—"}</td>
                <td className="td text-xs">{formatDateTime(provider.last_synced_at)}</td>
                <td className="td">
                  <Badge
                    value={provider.is_enabled ? "completed" : "cancelled"}
                    label={provider.is_enabled ? "فعال" : "غیرفعال"}
                  />
                </td>
                <td className="td">
                  <ProviderActions provider={provider} canEdit={canEdit} />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
