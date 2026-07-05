import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "تبيان — تعليقات يدوية ذكية على PDF",
  description: "حوّل ملفك الأكاديمي إلى ورقة مُراجَعة بخط اليد باستخدام الذكاء الاصطناعي",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ar" dir="rtl">
      <body className="antialiased">{children}</body>
    </html>
  );
}
