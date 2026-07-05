"use client";

/**
 * PDFPreview — يعرض PDF المُعلَّق داخل المتصفح + زر تنزيل.
 *
 * نستخدم <iframe> بدل react-pdf لأسباب:
 * 1. لا يحتاج تبعية إضافية
 * 2. يستخدم PDF viewer المتصفح الأصلي (مألوف للمستخدم)
 * 3. كافٍ تماماً لعرض ثم تنزيل
 *
 * objectURL يُحرَّر من الذاكرة عند إغلاق الصفحة أو
 * عند بدء معالجة ملف جديد (نستدعي revokeObjectURL من page.tsx).
 */

import { Download, RotateCcw } from "lucide-react";

interface PDFPreviewProps {
  url: string;
  filename: string;
  onReset: () => void;
}

export default function PDFPreview({ url, filename, onReset }: PDFPreviewProps) {
  const handleDownload = () => {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
  };

  return (
    <div className="w-full flex flex-col gap-4">

      {/* شريط أعلى — اسم الملف + أزرار */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-xs text-stone-400 mb-0.5">الملف جاهز</p>
          <p className="text-stone-800 font-medium text-sm truncate max-w-xs">
            {filename}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* زر معالجة ملف جديد */}
          <button
            onClick={onReset}
            className="
              flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm
              text-stone-600 border border-stone-200
              hover:bg-stone-50 transition-colors duration-150
            "
          >
            <RotateCcw size={14} />
            ملف جديد
          </button>

          {/* زر التنزيل */}
          <button
            onClick={handleDownload}
            className="
              flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium
              bg-amber-500 text-white
              hover:bg-amber-600 active:bg-amber-700
              transition-colors duration-150
            "
          >
            <Download size={14} />
            تنزيل PDF
          </button>
        </div>
      </div>

      {/* PDF Viewer */}
      <div className="w-full rounded-xl overflow-hidden border border-stone-200 shadow-sm">
        <iframe
          src={url}
          className="w-full"
          style={{ height: "75vh", minHeight: "500px" }}
          title={filename}
        />
      </div>
    </div>
  );
}
