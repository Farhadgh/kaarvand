"use client";

import { TaskRowActions } from "@/components/task-row-actions";
import { Badge } from "@/components/ui";
import { triggerLabels } from "@/lib/copy";
import { formatDateTime, formatJalaliLong, formatTime } from "@/lib/format";
import type { AgentTask } from "@/lib/types";

export function TaskRow({
  agentId,
  task,
  canEdit,
}: {
  agentId: string;
  task: AgentTask;
  canEdit: boolean;
}) {
  return (
    <tr className="align-top hover:bg-ink-50/60">
      <td className="td">
        <div className="font-medium text-ink-900">{task.name}</div>
        <div className="ltr text-[11px] text-ink-400">{task.prompt_key ?? "—"}</div>
      </td>
      <td className="td text-xs">
        {task.trigger_type === "schedule" ? (
          <>
            <span className="ltr font-mono">{task.schedule_cron}</span>
            <div className="text-[11px] text-ink-400">
              {triggerLabels[task.trigger_type] ?? task.trigger_type}
            </div>
          </>
        ) : (
          <span className="text-ink-500">
            {triggerLabels[task.trigger_type] ?? task.trigger_type}
          </span>
        )}
      </td>
      <td className="td text-xs">
        {task.next_run_at ? (
          <>
            {formatJalaliLong(task.next_run_at)}
            <div className="text-[11px] text-ink-400">ساعت {formatTime(task.next_run_at)}</div>
          </>
        ) : (
          <span className="text-ink-400">—</span>
        )}
      </td>
      <td className="td text-xs">{task.last_run_at ? formatDateTime(task.last_run_at) : "—"}</td>
      <td className="td">
        <div className="flex flex-col gap-1">
          <Badge
            value={task.is_active ? "completed" : "cancelled"}
            label={task.is_active ? "فعال" : "غیرفعال"}
          />
          {task.requires_approval ? (
            <Badge value="waiting_approval" label="نیازمند تأیید" />
          ) : null}
        </div>
      </td>
      <td className="td">
        <TaskRowActions agentId={agentId} task={task} canEdit={canEdit} />
      </td>
    </tr>
  );
}
