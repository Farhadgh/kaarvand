/** Persian copy for every error code the client may receive. */

const MESSAGES: Record<string, string> = {
  "auth.invalid_phone": "شماره موبایل معتبر نیست. مثال: ۰۹۱۲۳۴۵۶۷۸۹",
  "auth.invalid_credentials": "ایمیل یا گذرواژه نادرست است.",
  "auth.user_inactive": "حساب شما غیرفعال شده است. با پشتیبانی تماس بگیرید.",
  "auth.missing_token": "برای ادامه باید وارد شوید.",
  "auth.session_expired": "نشست شما منقضی شده است؛ دوباره وارد شوید.",
  "auth.insufficient_role": "این بخش فقط برای مدیران سامانه است.",
  "otp.code_invalid": "کد واردشده درست نیست.",
  "otp.code_expired": "کد منقضی شده است؛ کد تازه بگیرید.",
  "otp.code_not_found": "کد فعالی برای این شماره نیست؛ دوباره درخواست دهید.",
  "otp.too_many_requests": "کمی صبر کنید و دوباره تلاش کنید.",
  "otp.too_many_attempts": "تعداد تلاش‌ها زیاد شد؛ کد تازه بگیرید.",
  "otp.daily_limit": "سهمیهٔ پیامک امروز این شماره تمام شده است.",
  "wallet.insufficient_balance": "موجودی کیف پول کافی نیست.",
  "wallet.amount_below_min": "مبلغ شارژ کمتر از حداقل مجاز است.",
  "wallet.disabled": "کیف پول شما غیرفعال است؛ با پشتیبانی تماس بگیرید.",
  "billing.disabled": "درگاه پرداخت فعلاً غیرفعال است.",
  "billing.gateway_not_configured": "درگاه پرداخت تنظیم نشده است؛ بعداً تلاش کنید.",
  "billing.gateway_unreachable": "ارتباط با درگاه پرداخت برقرار نشد؛ دوباره تلاش کنید.",
  "billing.gateway_error": "درگاه پرداخت درخواست را نپذیرفت؛ بعداً تلاش کنید.",
  "billing.gateway_bad_response": "پاسخ درگاه پرداخت قابل خواندن نبود.",
  "payment.not_found": "این پرداخت پیدا نشد.",
  "payment.amount_mismatch": "مبلغ پرداخت با سفارش هم‌خوانی ندارد؛ با پشتیبانی تماس بگیرید.",
  "common.validation_error": "اطلاعات واردشده کامل یا درست نیست.",
  "common.network": "ارتباط با سرور برقرار نشد. اینترنت خود را بررسی کنید.",
  "agent.not_found": "این ایجنت پیدا نشد یا حذف شده است.",
  "run.not_found": "این اجرا پیدا نشد.",
  "model.not_found": "مدل انتخاب‌شده در دسترس نیست.",
  "model.disabled": "این مدل موقتاً غیرفعال شده است.",
  "budget.agent_exceeded": "سقف بودجهٔ ماهانهٔ این ایجنت پر شده است.",
  "budget.org_exceeded": "سقف بودجهٔ ماهانه پر شده است؛ با پشتیبانی تماس بگیرید.",
  "budget.token_limit": "طول درخواست از حد مجاز بیشتر است.",
  "inbound.channel_not_found": "این اتصال پیدا نشد.",
  "inbound.reply_tool_required": "برای پاسخ خودکار، ابتدا ابزار پیام‌رسان را در پنل تنظیم کنید.",
  "link.not_found": "این حساب پیدا نشد یا حذف شده است.",
  "link.already_exists": "این حساب قبلاً وصل شده است؛ همان کارت را ببینید.",
  "link.unknown_provider": "این برنامه در فهرست پشتیبانی نیست.",
  "link.provider_soon": "این برنامه به‌زودی اضافه می‌شود.",
  "link.device_offline":
    "دستگاهی که این حساب روی آن ذخیره می‌شود آنلاین نیست. اپ کاروند را روی لپ‌تاپ خود باز کنید.",
  "link.device_error": "اجرای عملیات در مرورگر دستگاه انجام نشد؛ یک‌بار دیگر تلاش کنید.",
  "link.not_active": "این حساب هنوز فعال نیست؛ ابتدا «بررسی اتصال» را بزنید.",
  "link.login_required": "در پنجرهٔ بازشده وارد حساب خودتان شوید، سپس «بررسی اتصال» را بزنید.",
  "tool.rate_limited": "سقف مجاز این ابزار در یک ساعت گذشته پر شده است؛ کمی بعد دوباره تلاش کنید.",
};

export function faError(code: string | undefined, fallback = "خطای نامشخص رخ داد."): string {
  if (!code) return fallback;
  return MESSAGES[code] ?? fallback;
}
