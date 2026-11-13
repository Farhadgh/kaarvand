import { useNavigate } from "react-router-dom";

export default function Soon() {
  const navigate = useNavigate();
  return (
    <div className="flex min-h-full items-center justify-center p-6 text-center">
      <div className="max-w-sm space-y-3">
        <p className="text-4xl">🚧</p>
        <h1 className="text-lg font-bold">این بخش در گام بعدی فعال می‌شود</h1>
        <p className="text-sm text-slate-500">
          زیرساخت آماده است؛ صفحهٔ کامل در فازهای ۲ تا ۵ اضافه می‌شود.
        </p>
        <button className="btn-ghost" onClick={() => navigate("/")}>
          بازگشت به خانه
        </button>
      </div>
    </div>
  );
}
