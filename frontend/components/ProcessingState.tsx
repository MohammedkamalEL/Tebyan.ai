"use client";

/**
 * ProcessingState — شاشة الانتظار أثناء المعالجة.
 *
 * تعرض: progress bar + الخطوة الحالية بناءً على نسبة التقدم.
 *
 * لماذا نعرض خطوات وليس spinner فقط؟
 * لأن المعالجة تأخذ 30-120 ثانية — spinner بدون معلومات
 * يجعل المستخدم يظن أن الصفحة تعطلت.
 */

interface ProcessingStateProps {
  progress: number; // 0–100
  filename: string;
}

// نحدد الخطوة الحالية بناءً على نسبة التقدم
function getCurrentStep(progress: number): { label: string; detail: string } {
  if (progress < 15) return {
    label: "جاري رفع الملف",
    detail: "يتم إرسال الملف للسيرفر...",
  };
  if (progress < 45) return {
    label: "استخراج النص",
    detail: "يقرأ النظام محتوى PDF صفحة بصفحة",
  };
  if (progress < 90) return {
    label: "التحليل بالذكاء الاصطناعي",
    detail: "يحدد الجمل المهمة والكلمات المفتاحية",
  };
  return {
    label: "رسم التعليقات",
    detail: "يضيف الخطوط والدوائر والملاحظات الهامشية",
  };
}

export default function ProcessingState({ progress, filename }: ProcessingStateProps) {
  const { label, detail } = getCurrentStep(progress);

  return (
    <div className="w-full flex flex-col items-center gap-8 py-8">

      {/* أيقونة متحركة */}
      <div className="relative">
        <div className="w-20 h-20 rounded-full border-4 border-stone-100 border-t-amber-500 animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-semibold text-amber-600">
            {progress}%
          </span>
        </div>
      </div>

      {/* اسم الملف */}
      <div className="text-center">
        <p className="text-stone-500 text-sm mb-1">جاري معالجة</p>
        <p className="text-stone-800 font-medium text-base max-w-xs truncate">
          {filename}
        </p>
      </div>

      {/* Progress bar */}
      <div className="w-full max-w-sm space-y-2">
        <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-amber-500 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* الخطوة الحالية */}
        <div className="text-center space-y-0.5">
          <p className="text-stone-700 font-medium text-sm">{label}</p>
          <p className="text-stone-400 text-xs">{detail}</p>
        </div>
      </div>

      {/* تحذير وقت الانتظار */}
      <p className="text-stone-400 text-xs text-center max-w-xs leading-relaxed">
        قد تستغرق المعالجة من 30 ثانية إلى دقيقتين
        <br />
        حسب حجم الملف — لا تغلق الصفحة
      </p>
    </div>
  );
}
