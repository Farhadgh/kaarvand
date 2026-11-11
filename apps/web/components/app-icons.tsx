"use client";

/**
 * Brand + generic icon resolver for the app catalog.
 *
 * The database stores an icon *key* (`si:whatsapp`, `lucide:file-text`,
 * `mono:in`) so adding a catalog row never needs a front-end change. Unknown
 * keys fall back to a coloured monogram — that is also what we do for brands
 * that simple-icons no longer ships (LinkedIn, Slack, ...).
 */

import {
  AppWindow,
  Chrome,
  FileSpreadsheet,
  FileText,
  Hash,
  Mail,
  MessageCircle,
  MessageSquare,
  Phone,
  Send,
  type LucideIcon,
} from "lucide-react";
import type { IconType } from "react-icons";
import {
  SiDiscord,
  SiFacebook,
  SiGithub,
  SiGmail,
  SiGooglecalendar,
  SiGooglechrome,
  SiGooglesheets,
  SiInstagram,
  SiNotion,
  SiTelegram,
  SiTrello,
  SiWhatsapp,
  SiX,
  SiZoom,
} from "react-icons/si";

const brand: Record<string, IconType> = {
  telegram: SiTelegram,
  whatsapp: SiWhatsapp,
  instagram: SiInstagram,
  x: SiX,
  facebook: SiFacebook,
  discord: SiDiscord,
  gmail: SiGmail,
  googlesheets: SiGooglesheets,
  googlecalendar: SiGooglecalendar,
  googlechrome: SiGooglechrome,
  notion: SiNotion,
  trello: SiTrello,
  github: SiGithub,
  zoom: SiZoom,
};

const generic: Record<string, LucideIcon> = {
  "message-circle": MessageCircle,
  "message-square": MessageSquare,
  send: Send,
  hash: Hash,
  mail: Mail,
  phone: Phone,
  "file-text": FileText,
  "file-spreadsheet": FileSpreadsheet,
  chrome: Chrome,
  "app-window": AppWindow,
};

export function AppIcon({
  icon,
  color,
  name,
  size = 22,
}: {
  icon: string | null | undefined;
  color?: string | null;
  name?: string;
  size?: number;
}) {
  const key = (icon ?? "").trim();
  const [set, rawName] = key.includes(":") ? key.split(":", 2) : ["", key];

  if (set === "si" && brand[rawName]) {
    const Brand = brand[rawName];
    return <Brand size={size} color={color ?? undefined} aria-hidden />;
  }
  if (set === "lucide" && generic[rawName]) {
    const Generic = generic[rawName];
    return <Generic size={size} color={color ?? undefined} aria-hidden />;
  }
  if (set === "mono" && rawName) {
    return <Monogram text={rawName} color={color} size={size} />;
  }
  return <Monogram text={(name ?? "?").slice(0, 2)} color={color} size={size} />;
}

function Monogram({
  text,
  color,
  size,
}: {
  text: string;
  color?: string | null;
  size: number;
}) {
  return (
    <span
      className="inline-flex items-center justify-center rounded-lg font-bold text-white"
      style={{
        width: size + 10,
        height: size + 10,
        backgroundColor: color ?? "#475569",
        fontSize: Math.max(10, size * 0.5),
      }}
      aria-hidden
    >
      {text.toUpperCase()}
    </span>
  );
}

/** Tile used on catalog cards: brand mark on a tinted background. */
export function AppTile({
  icon,
  color,
  name,
  size = 40,
}: {
  icon: string | null | undefined;
  color?: string | null;
  name?: string;
  size?: number;
}) {
  return (
    <span
      className="flex items-center justify-center rounded-xl2 border border-ink-100 bg-white shadow-sm"
      style={{ width: size, height: size }}
    >
      <AppIcon icon={icon} color={color} name={name} size={Math.round(size * 0.55)} />
    </span>
  );
}
