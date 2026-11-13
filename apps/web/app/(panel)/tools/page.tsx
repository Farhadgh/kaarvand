import { ToolsClient } from "@/components/tools-client";
import { serverFetch } from "@/lib/api-server";
import type { Tool, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ToolsPage() {
  const [tools, me] = await Promise.all([
    serverFetch<Tool[]>("/tools?enabled_only=false"),
    serverFetch<User>("/auth/me"),
  ]);
  const canEdit = me.role === "admin" || me.role === "user";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">ابزارها</h1>
        <p className="muted mt-1">
          ابزار HTTP، MCP، داخلی و کانکتور با JSON Schema و ماتریس ریسک؛ هر ابزار را همین‌جا تست
          کنید.
        </p>
      </div>
      <ToolsClient tools={tools} canEdit={canEdit} />
    </div>
  );
}
