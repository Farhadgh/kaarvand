import Link from "next/link";
import { redirect } from "next/navigation";

import { Shell } from "@/components/shell";
import { LogoutButton } from "@/components/logout-button";
import { Card, EmptyState } from "@/components/ui";
import { ApiError, serverFetch } from "@/lib/api-server";
import type { Meta, User } from "@/lib/types";

async function load(): Promise<{
  user: User | null;
  meta: Meta | null;
  unauthorized: boolean;
}> {
  try {
    const user = await serverFetch<User>("/auth/me");
    let meta: Meta | null = null;
    try {
      meta = await serverFetch<Meta>("/meta");
    } catch {
      meta = null;
    }
    return { user, meta, unauthorized: false };
  } catch (error) {
    return {
      user: null,
      meta: null,
      unauthorized: error instanceof ApiError && error.status === 401,
    };
  }
}

export default async function PanelLayout({ children }: { children: React.ReactNode }) {
  const { user, meta, unauthorized } = await load();

  // A cookie the API rejects has to be dropped, otherwise the middleware keeps
  // bouncing /login back to / and the browser loops forever with a blank page.
  if (unauthorized) redirect("/api/auth/expired");

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
        <Card className="w-full max-w-md">
          <EmptyState
            title="ارتباط با سرور برقرار نشد"
            description="سرویس API پاسخ نداد. چند لحظه بعد دوباره تلاش کنید."
            action={
              <Link className="btn-primary" href="/">
                تلاش دوباره
              </Link>
            }
          />
        </Card>
      </div>
    );
  }

  // This panel is the admin console: customers live in the client app (OTP).
  // A customer account that somehow has a password must not see provider data.
  // The account is named so a locked-out admin can see *which* login is wrong,
  // and the exit is a real POST logout (a GET link used to 405 and trap them).
  if (user.role !== "admin") {
    const account = user.email || user.phone || user.full_name;
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
        <Card className="w-full max-w-md">
          <EmptyState
            title="این پنل مخصوص مدیران است"
            description={`حساب «${account}» یک حساب کاربری (مشتری) است. برای استفاده از کاروند، اپلیکیشن دسکتاپ یا اندروید را باز کنید. اگر این حساب باید به پنل دسترسی داشته باشد، نقش آن در سرور باید admin باشد.`}
            action={<LogoutButton>ورود با حساب دیگر</LogoutButton>}
          />
        </Card>
      </div>
    );
  }

  return (
    <Shell user={user} meta={meta}>
      {children}
    </Shell>
  );
}

