"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, CardHeader, ErrorBox, Field } from "@/components/ui";
import { clientFetch, messageOf } from "@/lib/api";
import { messages, roles } from "@/lib/copy";
import type { User } from "@/lib/types";

export function UsersCreateForm({ canEdit }: { canEdit: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    password: "",
    role: "operator",
  });

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await clientFetch<User>("/users", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setNotice("کاربر ساخته شد.");
      setForm({ email: "", full_name: "", password: "", role: "operator" });
      router.refresh();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  if (!canEdit) return null;

  return (
    <div className="space-y-3">
      {error ? <ErrorBox message={error} /> : null}
      {notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}
      <Card>
        <CardHeader title="کاربر جدید" subtitle="رمز عبور حداقل ۸ کاراکتر" />
        <form className="card-body grid grid-cols-1 gap-4 md:grid-cols-4" onSubmit={submit}>
          <Field label="ایمیل">
            <input
              className="input ltr"
              dir="ltr"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              required
            />
          </Field>
          <Field label="نام و نام خانوادگی">
            <input
              className="input"
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
              required
            />
          </Field>
          <Field label="نقش">
            <select
              className="input"
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value })}
            >
              <option value="operator">{roles.operator}</option>
              <option value="viewer">{roles.viewer}</option>
              <option value="admin">{roles.admin}</option>
            </select>
          </Field>
          <Field label="رمز عبور">
            <input
              className="input ltr"
              dir="ltr"
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              minLength={8}
              required
            />
          </Field>
          <div className="flex justify-end md:col-span-4">
            <button className="btn-primary" disabled={busy}>
              {busy ? "…" : messages.create}
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}
