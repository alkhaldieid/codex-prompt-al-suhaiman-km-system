import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "مكتبة الأنظمة والسوابق",
  description: "مكتبة الأنظمة والسوابق — السحيمان",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
