/** Session storage shared by the web build, Electron and the Android WebView. */

export type User = {
  id: string;
  org_id: string;
  email: string | null;
  phone: string | null;
  full_name: string;
  role: "admin" | "user";
  locale: string;
  digits_pref: "fa" | "en";
  is_phone_verified: boolean;
  has_password: boolean;
};

export type Session = {
  accessToken: string;
  refreshToken: string;
  user: User;
};

const KEY = "kaarvand.session";

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    if (!parsed.accessToken || !parsed.refreshToken) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(session: Session): void {
  localStorage.setItem(KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(KEY);
}
