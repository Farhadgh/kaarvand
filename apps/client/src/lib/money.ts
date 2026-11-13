/** Persian money helpers: the API always speaks IRR, the customer reads Toman. */

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

export const TOMAN = 10;

export function toToman(irr: number): number {
  return Math.round(irr / TOMAN);
}

export function faDigits(value: string | number): string {
  return String(value).replace(/\d/g, (d) => PERSIAN_DIGITS[Number(d)]);
}

export function formatToman(irr: number): string {
  const toman = toToman(irr);
  return `${faDigits(toman.toLocaleString("en-US"))} تومان`;
}

/** The catalog API already speaks Toman (it converted from USD once, server side). */
export function formatTomanValue(toman: number): string {
  return `${faDigits(Math.round(toman).toLocaleString("en-US"))} تومان`;
}

/** Accept ۰۹۱۲…, 0912…, +98912… and return the canonical 09xxxxxxxxx. */
export function normalizePhone(value: string): string {
  let digits = value.replace(/[۰-۹]/g, (d) => String(PERSIAN_DIGITS.indexOf(d)));
  digits = digits.replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
  digits = digits.replace(/[\s()-]/g, "");
  if (digits.startsWith("+98")) digits = `0${digits.slice(3)}`;
  else if (digits.startsWith("0098")) digits = `0${digits.slice(4)}`;
  else if (digits.startsWith("98") && digits.length === 12) digits = `0${digits.slice(2)}`;
  return digits;
}

export function isValidIranMobile(value: string): boolean {
  return /^09\d{9}$/.test(normalizePhone(value));
}
