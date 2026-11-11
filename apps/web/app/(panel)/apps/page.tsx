import { AppsCatalog } from "@/components/apps-catalog";
import { serverFetch } from "@/lib/api-server";
import type { Agent, CatalogApp, Device, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AppsPage() {
  const [apps, agents, devices, me] = await Promise.all([
    serverFetch<CatalogApp[]>("/apps"),
    serverFetch<Agent[]>("/agents").catch(() => [] as Agent[]),
    serverFetch<Device[]>("/devices").catch(() => [] as Device[]),
    serverFetch<User>("/auth/me"),
  ]);

  const canEdit = me.role === "owner" || me.role === "admin" || me.role === "operator";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">برنامه‌ها</h1>
        <p className="muted mt-1">
          شبکه‌های اجتماعی، آفیس و برنامه‌های نصب‌شده روی دستگاه مشتری را با یک کلیک به ایجنت وصل
          کنید؛ اگر ابزارتان اینجا نیست، خودتان اضافه کنید.
        </p>
      </div>

      <AppsCatalog
        apps={apps}
        agents={agents.map((agent) => ({ id: agent.id, name: agent.name }))}
        devices={devices}
        canEdit={canEdit}
      />
    </div>
  );
}
