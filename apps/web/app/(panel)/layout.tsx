import Link from "next/link";
import { redirect } from "next/navigation";

import { Shell } from "@/components/shell";
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
  if (user.role !== "admin") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
        <Card className="w-full max-w-md">
          <EmptyState
            title="این پنل مخصوص مدیران است"
            description="حساب شما یک حساب کاربری (مشتری) است. برای استفاده از کاروند، اپلیکیشن دسکتاپ یا اندروید را باز کنید."
            action={
              <a className="btn-primary" href="/api/auth/logout">
                خروج از حساب
              </a>
            }
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

