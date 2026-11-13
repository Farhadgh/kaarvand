import { ProviderForm } from "@/components/providers-form";
import { ProvidersTable } from "@/components/providers-table";
import { serverFetch } from "@/lib/api-server";
import type { Provider, ProviderAdapter, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ProvidersPage() {
  const [providerList, adapters, me] = await Promise.all([
    serverFetch<Provider[]>("/providers"),
    serverFetch<ProviderAdapter[]>("/provider-adapters"),
    serverFetch<User>("/auth/me"),
  ]);
  const canEdit = me.role === "admin" || me.role === "user";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">پروایدرها</h1>
        <p className="muted mt-1">
          هر سرویس سازگار با OpenAI فقط با آدرس و کلید اضافه می‌شود؛ برای پروتکل ناشناس از آداپتور
          «توصیفی» استفاده کنید.
        </p>
      </div>

      <ProviderForm adapters={adapters} canEdit={canEdit} />
      <ProvidersTable providers={providerList} canEdit={canEdit} />
    </div>
  );
}
