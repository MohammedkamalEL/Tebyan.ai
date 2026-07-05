"use client";

/**
 * page.tsx — الصفحة الرئيسية الوحيدة.
 *
 * مسؤولة فقط عن:
 * 1. إدارة الـ state (idle → uploading → processing → done → error)
 * 2. استدعاء api.ts
 * 3. تمرير البيانات للـ components المناسبة
 *
 * لا منطق معالجة هنا — هذا في api.ts
 * لا UI هنا — هذا في components/
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { processPDF, ProcessingStatus } from "@/lib/api";
import UploadZone from "@/components/UploadZone";
import ProcessingState from "@/components/ProcessingState";
import PDFPreview from "@/components/PDFPreview";
import { AlertCircle } from "lucide-react";

export default function Home() {
  const [status, setStatus] = useState<ProcessingStatus>({ stage: "idle" });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  // تنظيف objectURL عند unmount أو عند إعادة التعيين
  // لمنع تسريب الذاكرة في جلسات استخدام طويلة
  useEffect(() => {
    return () => {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
      }
    };
  }, []);

  const handleFileSelect = useCallback(async (file: File) => {
    // تنظيف objectURL القديم لو كان موجوداً
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }

    setSelectedFile(file);
    setStatus({ stage: "uploading", progress: 0 });

    try {
      const result = await processPDF(file, (progress) => {
        setStatus({ stage: progress < 95 ? "uploading" : "processing", progress } as ProcessingStatus);
      });

      objectUrlRef.current = result.url;
      setStatus({ stage: "done", url: result.url, filename: result.filename });
    } catch (err) {
      const message = err instanceof Error ? err.message : "حدث خطأ غير متوقع";
      setStatus({ stage: "error", message });
    }
  }, []);

  const handleReset = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setSelectedFile(null);
    setStatus({ stage: "idle" });
  }, []);

  const isLoading = status.stage === "uploading" || status.stage === "processing";
  const progress = status.stage === "uploading" ? status.progress :
                   status.stage === "processing" ? 95 : 0;

  return (
    <main className="min-h-screen bg-stone-50" dir="rtl">

      {/* Header */}
      <header className="border-b border-stone-200 bg-white">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-stone-900 tracking-tight">
              تبيان
              <span className="text-amber-500"> / Tebyan</span>
            </h1>
            <p className="text-xs text-stone-400 mt-0.5">
              تعليقات يدوية ذكية على ملفات PDF
            </p>
          </div>
          <div className="text-xs text-stone-400 bg-stone-100 px-3 py-1.5 rounded-full">
            مجاني · بدون تسجيل
          </div>
        </div>
      </header>

      {/* المحتوى الرئيسي */}
      <div className="max-w-4xl mx-auto px-6 py-12">

        {/* Hero — يظهر فقط في حالة idle */}
        {status.stage === "idle" && (
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-stone-900 mb-3 leading-snug">
              حوّل ملفك الأكاديمي
              <br />
              <span className="text-amber-500">إلى ورقة مُراجَعة</span>
            </h2>
            <p className="text-stone-500 text-base max-w-md mx-auto leading-relaxed">
              يستخرج النص ويضع خطوطاً تحت الجمل المهمة،
              ودوائر حول المصطلحات، وملاحظات هامشية عربية — كلها بأسلوب خط اليد.
            </p>
          </div>
        )}

        {/* الحالات */}
        <div className="bg-white rounded-2xl border border-stone-200 shadow-sm p-8">
          {status.stage === "idle" && (
            <UploadZone onFileSelect={handleFileSelect} />
          )}

          {isLoading && (
            <ProcessingState
              progress={progress}
              filename={selectedFile?.name ?? ""}
            />
          )}

          {status.stage === "done" && (
            <PDFPreview
              url={status.url}
              filename={status.filename}
              onReset={handleReset}
            />
          )}

          {status.stage === "error" && (
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <div className="p-4 rounded-full bg-red-50">
                <AlertCircle size={36} className="text-red-500" />
              </div>
              <div>
                <p className="text-stone-800 font-medium mb-1">
                  فشلت المعالجة
                </p>
                <p className="text-stone-500 text-sm max-w-sm">
                  {status.message}
                </p>
              </div>
              <button
                onClick={handleReset}
                className="
                  mt-2 px-6 py-2.5 rounded-lg text-sm font-medium
                  bg-amber-500 text-white
                  hover:bg-amber-600 transition-colors duration-150
                "
              >
                حاول مرة أخرى
              </button>
            </div>
          )}
        </div>

        {/* كيف يعمل — يظهر فقط في حالة idle */}
        {status.stage === "idle" && (
          <div className="mt-12 grid grid-cols-3 gap-6">
            {[
              { step: "١", title: "ارفع الملف", desc: "اسحب ملف PDF أو اضغط للاختيار" },
              { step: "٢", title: "التحليل التلقائي", desc: "الذكاء الاصطناعي يقرأ ويحدد الأهم" },
              { step: "٣", title: "نزّل النتيجة", desc: "PDF مُعلَّق بأسلوب خط اليد" },
            ].map(({ step, title, desc }) => (
              <div key={step} className="text-center">
                <div className="w-10 h-10 rounded-full bg-amber-100 text-amber-600 font-bold text-lg flex items-center justify-center mx-auto mb-3">
                  {step}
                </div>
                <p className="text-stone-800 font-medium text-sm mb-1">{title}</p>
                <p className="text-stone-400 text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
