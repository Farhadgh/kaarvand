import { PlaygroundClient } from "@/components/playground-client";
import { Card, EmptyState } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import Link from "next/link";
import type { Agent, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function PlaygroundPage() {
  const [agents, me] = await Promise.all([
    serverFetch<Agent[]>("/agents?is_active=true"),
    serverFetch<User>("/auth/me"),
  ]);

  if (agents.length === 0) {
    return (
      <Card>
        <EmptyState
          title="ایجنت فعالی وجود ندارد"
          description="برای آزمایش، ابتدا یک ایجنت بسازید و مدل آن را انتخاب کنید."
          action={
            <Link className="btn-primary" href="/agents">
              ساخت ایجنت
            </Link>
          }
        />
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">آزمایشگاه</h1>
        <p className="muted mt-1">
          پاسخ زنده‌ی ایجنت، فراخوانی ابزارها و هزینه‌ی هر اجرا؛ درخواست‌های پرخطر اینجا برای تأیید
          متوقف می‌شوند.
        </p>
      </div>

      <PlaygroundClient
        agents={agents.map((agent) => ({
          id: agent.id,
          name: agent.name,
          model: agent.model_external_id,
        }))}
        canRun={me.role !== "viewer"}
      />
    </div>
  );
}
