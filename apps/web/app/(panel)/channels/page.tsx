import { ChannelsClient } from "@/components/channels-client";
import { API_BASE } from "@/lib/api-config";
import { serverFetch } from "@/lib/api-server";
import type { Agent, InboundChannel, Tool, User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ChannelsPage() {
  const [channels, agents, tools, me] = await Promise.all([
    serverFetch<InboundChannel[]>("/channels").catch(() => [] as InboundChannel[]),
    serverFetch<Agent[]>("/agents").catch(() => [] as Agent[]),
    serverFetch<Tool[]>("/tools?enabled_only=false").catch(() => [] as Tool[]),
    serverFetch<User>("/auth/me"),
  ]);

  const canEdit = me.role === "owner" || me.role === "admin";
  const replyTools = tools
    .filter((tool) => tool.kind === "http" && Boolean(tool.config?.app_slug))
    .map((tool) => ({
      id: tool.id,
      label: tool.name_fa,
      appSlug: String(tool.config?.app_slug ?? ""),
    }));

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">کانال‌های ورودی</h1>
        <p className="muted mt-1">
          پیام‌های واتساپ و تلگرام را به ایجنت وصل کنید؛ هر پیام یک «اجرا» با تریگر{" "}
          <span className="ltr">webhook</span> می‌سازد و در صورت فعال‌بودن، پاسخ خودکار از همان
          ابزار برنامه ارسال می‌شود.
        </p>
      </div>

      <ChannelsClient
        channels={channels}
        agents={agents.map((agent) => ({ id: agent.id, name: agent.name }))}
        replyTools={replyTools}
        canEdit={canEdit}
        apiBase={API_BASE}
      />
    </div>
  );
}
