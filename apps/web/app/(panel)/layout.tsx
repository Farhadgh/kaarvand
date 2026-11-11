import { redirect } from "next/navigation";

import { Shell } from "@/components/shell";
import { serverFetch } from "@/lib/api-server";
import type { Meta, User } from "@/lib/types";

async function load(): Promise<{ user: User | null; meta: Meta | null }> {
  try {
    const user = await serverFetch<User>("/auth/me");
    let meta: Meta | null = null;
    try {
      meta = await serverFetch<Meta>("/meta");
    } catch {
      meta = null;
    }
    return { user, meta };
  } catch {
    return { user: null, meta: null };
  }
}

export default async function PanelLayout({ children }: { children: React.ReactNode }) {
  const { user, meta } = await load();
  if (!user) redirect("/login");
  return (
    <Shell user={user} meta={meta}>
      {children}
    </Shell>
  );
}
