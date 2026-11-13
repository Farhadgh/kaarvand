/** Single source of Persian copy: navigation, labels, statuses, messages. */

export const nav = [
  { href: "/", label: "داشبورد", icon: "home" },
  { href: "/playground", label: "آزمایشگاه", icon: "terminal" },
  { href: "/agents", label: "ایجنت‌ها", icon: "bot" },
  { href: "/providers", label: "پروایدرها", icon: "plug" },
  { href: "/models", label: "مدل‌ها", icon: "cpu" },
  { href: "/audio", label: "صدا و گفتار", icon: "mic" },
  { href: "/prompts", label: "پرامپت‌ها", icon: "fileText" },
  { href: "/tools", label: "ابزارها", icon: "wrench" },
  { href: "/apps", label: "برنامه‌ها", icon: "plug" },
  { href: "/channels", label: "کانال‌های ورودی", icon: "activity" },
  { href: "/devices", label: "دستگاه‌ها", icon: "monitor" },
  { href: "/runs", label: "اجراها", icon: "activity" },
  { href: "/usage", label: "مصرف و هزینه", icon: "chart" },
  { href: "/payments", label: "پرداخت‌ها", icon: "wallet" },
  { href: "/users", label: "کاربران", icon: "users" },
  { href: "/settings", label: "تنظیمات", icon: "settings" },
] as const;

export const roles: Record<string, string> = {
  admin: "مدیر",
  user: "کاربر",
};

export const statusLabels: Record<string, string> = {
  queued: "در صف",
  running: "در حال اجرا",
  waiting_approval: "در انتظار تأیید",
  completed: "تکمیل‌شده",
  failed: "ناموفق",
  cancelled: "لغو‌شده",
  canceled: "لغو‌شده",
  paid: "پرداخت‌شده",
  online: "آنلاین",
  offline: "آفلاین",
  paired: "جفت‌شده",
  pending: "در انتظار جفت‌سازی",
  draft: "پیش‌نویس",
  published: "منتشرشده",
  archived: "بایگانی",
  ok: "موفق",
  error: "خطا",
  unknown: "نامشخص",
};

export const riskLabels: Record<string, string> = {
  low: "کم",
  medium: "متوسط",
  high: "زیاد",
};

export const permissionLabels: Record<string, string> = {
  auto: "خودکار",
  confirm: "با تأیید",
  deny: "ممنوع",
};

export const toolKindLabels: Record<string, string> = {
  builtin: "داخلی",
  http: "HTTP",
  mcp: "MCP",
  connector: "کانکتور",
};

export const categoryLabels: Record<string, string> = {
  general: "عمومی",
  social: "شبکه اجتماعی",
  office: "آفیس",
  media: "رسانه",
  finance: "مالی",
  phone: "تلفن",
  web: "وب",
  dev: "توسعه",
  productivity: "بهره‌وری",
  devices: "برنامه‌ی دستگاه",
};

export const runtimeLabels: Record<string, string> = {
  cloud: "ابر",
  desktop: "روی دستگاه",
};

export const appCategoryLabels: Record<string, string> = {
  social: "شبکه‌های اجتماعی",
  office: "آفیس و ایمیل",
  productivity: "بهره‌وری",
  devices: "برنامه‌های ویندوز",
  other: "سایر",
};

export const triggerLabels: Record<string, string> = {
  manual: "دستی",
  schedule: "زمان‌بندی",
  webhook: "وبهوک",
  event: "رویداد",
  inbound_call: "تماس ورودی",
};

export const messages = {
  loginTitle: "ورود به پنل مدیریت",
  loginSubtitle: "برای ادامه، اطلاعات حساب خود را وارد کنید",
  email: "ایمیل",
  password: "رمز عبور",
  login: "ورود",
  logout: "خروج",
  loading: "در حال بارگذاری…",
  empty: "موردی برای نمایش نیست",
  save: "ذخیره",
  cancel: "انصراف",
  create: "افزودن",
  edit: "ویرایش",
  delete: "حذف",
  confirmDelete: "آیا از حذف مطمئن هستید؟",
  search: "جست‌وجو",
  actions: "عملیات",
  yes: "بله",
  no: "خیر",
  freeMode: "حالت آزمایشی — بدون درگاه پرداخت",
  cost: "هزینه",
  tokens: "توکن",
  agent: "ایجنت",
  model: "مدل",
  provider: "پروایدر",
  retry: "تلاش دوباره",
  copied: "کپی شد",
  refresh: "به‌روزرسانی",
  approve: "تأیید و ادامه",
  deny: "رد",
  stop: "توقف",
  send: "ارسال",
  notAllowed: "شما به این بخش دسترسی ندارید",
};

export { errorMessages, translateCode } from "./errors-fa";
