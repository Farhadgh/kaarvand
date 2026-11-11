import { Suspense } from "react";

import { LoginForm } from "@/components/login-form";
import { messages } from "@/lib/copy";

export const metadata = { title: "ورود — کاروند" };

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-lg font-bold text-white">
            ک
          </div>
          <h1 className="text-xl font-bold text-ink-900">{messages.loginTitle}</h1>
          <p className="muted mt-1">{messages.loginSubtitle}</p>
        </div>

        <div className="card card-body">
          <Suspense fallback={<p className="muted">…</p>}>
            <LoginForm />
          </Suspense>
        </div>

        <p className="mt-4 text-center text-xs text-ink-400">
          نسخه‌ی آزمایشی — داده‌ها روی سرور خودتان ذخیره می‌شود.
        </p>
      </div>
    </div>
  );
}
