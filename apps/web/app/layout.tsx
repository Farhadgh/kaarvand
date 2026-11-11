import type { Metadata, Viewport } from "next";
import { Vazirmatn } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

const vazirmatn = Vazirmatn({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "700"],
  variable: "--font-vazirmatn",
  display: "swap",
});

export const metadata: Metadata = {
  title: "کاروند — پنل مدیریت",
  description:
    "پلتفرم ایجنت هوش مصنوعی فارسی کاروند: پروایدر، مدل، ابزار، اجرا و هزینه",
};

export const viewport: Viewport = {
  themeColor: "#1e63f0",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
