import Link from "next/link";

import { PromptEditor } from "@/components/prompt-editor";
import { Card, EmptyState } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import { statusLabels } from "@/lib/copy";
import { formatNumber } from "@/lib/format";
import type { Prompt, PromptVersion, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function PromptsPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const params = await searchParams;
  const [prompts, me] = await Promise.all([
    serverFetch<Prompt[]>("/prompts"),
    serverFetch<User>("/auth/me"),
  ]);

  if (prompts.length === 0) {
    return (
      <Card>
        <EmptyState
          title="پرامپتی وجود ندارد"
          description="با اجرای seed پرامپت‌های فارسی ساخته می‌شوند."
        />
      </Card>
    );
  }

  const canEdit = me.role === "admin" || me.role === "user";
  const selectedId = params.id ?? prompts[0].id;
  const selected = prompts.find((item) => item.id === selectedId) ?? prompts[0];
  const versions = await serverFetch<PromptVersion[]>(`/prompts/${selected.id}/versions`).catch(
    () => [] as PromptVersion[],
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">پرامپت‌ها</h1>
        <p className="muted mt-1">
          هر ویرایش یک نسخه‌ی جدید می‌سازد؛ نسخه‌های قبلی قابل بازگردانی‌اند و پرامپت سازمانی بر
          سراسری اولویت دارد.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[18rem_1fr]">
        <Card className="h-fit">
          <ul className="divide-y divide-ink-100">
            {prompts.map((prompt) => (
              <li key={prompt.id}>
                <Link
                  href={`/prompts?id=${prompt.id}`}
                  className={`block px-4 py-3 text-sm transition hover:bg-ink-50 ${
                    prompt.id === selected.id ? "bg-brand-50" : ""
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-ink-900">{prompt.title_fa}</span>
                    <span className="text-[11px] text-ink-400">
                      {statusLabels[prompt.status] ?? prompt.status}
                    </span>
                  </div>
                  <div className="ltr mt-0.5 text-[11px] text-ink-400">{prompt.key}</div>
                  <div className="mt-0.5 text-[11px] text-ink-400">
                    نسخه {formatNumber(prompt.current_version)}
                    {prompt.org_id === null ? " · سراسری" : " · سازمانی"}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </Card>

        <PromptEditor prompt={selected} versions={versions} canEdit={canEdit} />
      </div>
    </div>
  );
}
