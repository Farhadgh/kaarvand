/** Persian formatting: digits, money, Jalali dates, numbers to words. */

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

export function toFaDigits(value: string | number): string {
  return String(value).replace(/\d/g, (digit) => PERSIAN_DIGITS[Number(digit)]);
}

export function toEnDigits(value: string): string {
  return value
    .replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
}

export function formatNumber(value: number | string, digits: "fa" | "en" = "fa"): string {
  const numeric = Number(value ?? 0);
  const text = new Intl.NumberFormat("en-US").format(Number.isFinite(numeric) ? numeric : 0);
  return digits === "fa" ? toFaDigits(text.replace(/,/g, "٬")) : text;
}

/** Amounts are stored in IRR (Rial); the panel shows Toman by default. */
export function formatMoney(
  rial: number | string,
  options: { unit?: "toman" | "rial"; digits?: "fa" | "en"; withUnit?: boolean } = {},
): string {
  const { unit = "toman", digits = "fa", withUnit = true } = options;
  const value = unit === "toman" ? Number(rial ?? 0) / 10 : Number(rial ?? 0);
  const rounded = unit === "toman" ? Math.round(value) : Math.round(value);
  const text = formatNumber(rounded, digits);
  if (!withUnit) return text;
  return `${text} ${unit === "toman" ? "تومان" : "ریال"}`;
}

/* --- Jalali calendar (same algorithm as the backend) ---------------------- */

const G_DAYS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

function div(a: number, b: number): number {
  return Math.floor(a / b);
}

export function gregorianToJalali(gy: number, gm: number, gd: number): [number, number, number] {
  const gy2 = gy - 1600;
  const gm2 = gm - 1;
  const gd2 = gd - 1;
  let gDayNo =
    365 * gy2 + div(gy2 + 3, 4) - div(gy2 + 99, 100) + div(gy2 + 399, 400);
  gDayNo += G_DAYS[gm2] + gd2;
  if (gm > 2 && ((gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0)) gDayNo += 1;

  let jDayNo = gDayNo - 79;
  const jNp = div(jDayNo, 12053);
  jDayNo %= 12053;

  let jy = 979 + 33 * jNp + 4 * div(jDayNo, 1461);
  jDayNo %= 1461;
  if (jDayNo >= 366) {
    jy += div(jDayNo - 1, 365);
    jDayNo = (jDayNo - 1) % 365;
  }

  let jm: number;
  let jd: number;
  if (jDayNo < 186) {
    jm = 1 + div(jDayNo, 31);
    jd = 1 + (jDayNo % 31);
  } else {
    jm = 7 + div(jDayNo - 186, 30);
    jd = 1 + ((jDayNo - 186) % 30);
  }
  return [jy, jm, jd];
}

export const JALALI_MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];

function pad(value: number): string {
  return value < 10 ? `0${value}` : String(value);
}

export function jalaliDate(input: string | Date): [number, number, number] {
  const date = typeof input === "string" ? new Date(input) : input;
  return gregorianToJalali(date.getFullYear(), date.getMonth() + 1, date.getDate());
}

/** 1405/08/18 */
export function formatJalali(input: string | Date | null | undefined, digits: "fa" | "en" = "fa"): string {
  if (!input) return "—";
  const [jy, jm, jd] = jalaliDate(input);
  const text = `${jy}/${pad(jm)}/${pad(jd)}`;
  return digits === "fa" ? toFaDigits(text) : text;
}

/** ۱۸ آبان ۱۴۰۵ */
export function formatJalaliLong(
  input: string | Date | null | undefined,
  digits: "fa" | "en" = "fa",
): string {
  if (!input) return "—";
  const [jy, jm, jd] = jalaliDate(input);
  const text = `${jd} ${JALALI_MONTHS[jm - 1]} ${jy}`;
  return digits === "fa" ? toFaDigits(text) : text;
}

/** ۱۴:۰۵ — local (Asia/Tehran) time */
export function formatTime(input: string | Date | null | undefined, digits: "fa" | "en" = "fa"): string {
  if (!input) return "—";
  const date = typeof input === "string" ? new Date(input) : input;
  const text = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Tehran",
  }).format(date);
  return digits === "fa" ? toFaDigits(text) : text;
}

export function formatDateTime(
  input: string | Date | null | undefined,
  digits: "fa" | "en" = "fa",
): string {
  if (!input) return "—";
  return `${formatJalali(input, digits)} — ${formatTime(input, digits)}`;
}

export function relativeFa(input: string | Date | null | undefined): string {
  if (!input) return "—";
  const date = typeof input === "string" ? new Date(input) : input;
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "همین حالا";
  if (seconds < 3600) return `${toFaDigits(Math.floor(seconds / 60))} دقیقه پیش`;
  if (seconds < 86400) return `${toFaDigits(Math.floor(seconds / 3600))} ساعت پیش`;
  return `${toFaDigits(Math.floor(seconds / 86400))} روز پیش`;
}
