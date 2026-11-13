import { UserRowActions } from "@/components/user-row-actions";
import { UsersCreateForm } from "@/components/users-create-form";
import { Badge, Card, EmptyState } from "@/components/ui";
import { serverFetch } from "@/lib/api-server";
import { roles } from "@/lib/copy";
import { formatDateTime } from "@/lib/format";
import type { User } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function UsersPage() {
  const me = await serverFetch<User>("/auth/me");
  const canManage = me.role === "admin" || me.role === "user";

  if (!canManage) {
    return (
      <Card>
        <EmptyState
          title="دسترسی ندارید"
          description="مدیریت کاربران فقط برای مالک و مدیر سازمان فعال است."
        />
      </Card>
    );
  }

  const users = await serverFetch<User[]>("/users");

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">کاربران</h1>
        <p className="muted mt-1">
          نقش‌ها: مالک، مدیر، کارشناس و ناظر؛ کاربران حذف نمی‌شوند بلکه غیرفعال می‌مانند تا سابقه
          حفظ شود.
        </p>
      </div>

      <UsersCreateForm canEdit={me.role === "admin" || me.role === "user"} />

      <div className="table-wrapper">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">نام</th>
              <th className="th">ایمیل</th>
              <th className="th">نقش</th>
              <th className="th">وضعیت</th>
              <th className="th">آخرین ورود</th>
              <th className="th">عملیات</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-ink-50/60">
                <td className="td font-medium text-ink-900">{user.full_name}</td>
                <td className="td ltr text-xs">{user.email}</td>
                <td className="td">{roles[user.role] ?? user.role}</td>
                <td className="td">
                  <Badge
                    value={user.is_active ? "completed" : "cancelled"}
                    label={user.is_active ? "فعال" : "غیرفعال"}
                  />
                </td>
                <td className="td text-xs">{formatDateTime(user.last_login_at)}</td>
                <td className="td">
                  {user.id === me.id ? (
                    <span className="text-xs text-ink-400">خودتان</span>
                  ) : (
                    <UserRowActions user={user} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
