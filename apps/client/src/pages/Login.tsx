import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../lib/api";
import { saveSession } from "../lib/auth";
import { faError } from "../lib/errors-fa";
import { faDigits, isValidIranMobile, normalizePhone } from "../lib/money";

/** Phone + OTP sign-in: the only way a customer enters the app. */
export default function Login() {
  const navigate = useNavigate();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (seconds <= 0) return;
    const timer = setTimeout(() => setSeconds((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [seconds]);

  async function sendCode() {
    setError(null);
    if (!isValidIranMobile(phone)) {
      setError(faError("auth.invalid_phone"));
      return;
    }
    setBusy(true);
    try {
      const result = await api.requestOtp(normalizePhone(phone));
      setDebugCode(result.debug_code);
      setSeconds(result.resend_in);
      setStep("code");
    } catch (err) {
      const apiError = err as ApiError;
      setError(faError(apiError.code));
      if (typeof apiError.params?.retry_after === "number") {
        setSeconds(apiError.params.retry_after as number);
      }
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setError(null);
    if (code.trim().length < 4) {
      setError("کد پیامک‌شده را وارد کنید.");
      return;
    }
    setBusy(true);
    try {
      const result = await api.verifyOtp(normalizePhone(phone), code.trim());
      saveSession({
        accessToken: result.access_token,
        refreshToken: result.refresh_token,
        user: result.user,
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(faError((err as ApiError).code));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500 text-2xl font-bold text-white">
            ک
          </div>
          <h1 className="text-xl font-bold">کاروند</h1>
          <p className="mt-1 text-sm text-slate-500">
            {step === "phone" ? "شماره موبایل خود را وارد کنید" : "کد پیامک‌شده را وارد کنید"}
          </p>
        </div>

        <div className="card space-y-4">
          {step === "phone" ? (
            <>
              <label className="block text-sm text-slate-600" htmlFor="phone">
                شماره موبایل
              </label>
              <input
                id="phone"
                className="input text-center tracking-widest"
                inputMode="numeric"
                autoComplete="tel"
                placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void sendCode();
                }}
              />
              <button className="btn-primary w-full" disabled={busy} onClick={() => void sendCode()}>
                {busy ? "در حال ارسال…" : "دریافت کد ورود"}
              </button>
            </>
          ) : (
            <>
              <label className="block text-sm text-slate-600" htmlFor="code">
                کد {faDigits(5)} رقمی
              </label>
              <input
                id="code"
                className="input text-center text-lg tracking-[0.5em]"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={8}
                value={code}
                onChange={(event) => setCode(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void verify();
                }}
              />
              {debugCode ? (
                <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  حالت آزمایشی (پیامک فعال نیست): کد شما {faDigits(debugCode)}
                </p>
              ) : null}
              <button className="btn-primary w-full" disabled={busy} onClick={() => void verify()}>
                {busy ? "در حال بررسی…" : "ورود به کاروند"}
              </button>
              <div className="flex items-center justify-between text-xs text-slate-500">
                <button
                  className="underline disabled:no-underline disabled:opacity-50"
                  disabled={seconds > 0 || busy}
                  onClick={() => void sendCode()}
                >
                  {seconds > 0 ? `ارسال دوباره تا ${faDigits(seconds)} ثانیه` : "ارسال دوبارهٔ کد"}
                </button>
                <button className="underline" onClick={() => setStep("phone")}>
                  تغییر شماره
                </button>
              </div>
            </>
          )}

          {error ? (
            <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>
          ) : null}
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          با ورود، شرایط استفاده و قوانین کاروند را می‌پذیرید.
        </p>
      </div>
    </div>
  );
}
