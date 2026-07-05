/**
 * lib/api.ts — الطبقة الوحيدة المسؤولة عن التواصل مع البيكند.
 *
 * القاعدة: لا يوجد fetch() في أي component — كل HTTP هنا فقط.
 * لو غيّرت رابط البيكند أو أضفت auth header لاحقاً،
 * تغيّره في هذا الملف فقط.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type ProcessingStatus =
  | { stage: "idle" }
  | { stage: "uploading"; progress: number }
  | { stage: "processing" }
  | { stage: "done"; url: string; filename: string }
  | { stage: "error"; message: string };

/**
 * يرفع ملف PDF للبيكند ويرجع URL مؤقت للملف المُعلَّق.
 *
 * لماذا نرجع objectURL لا blob مباشرة؟
 * لأن objectURL يمكن استخدامه في <iframe src=...> و <a href=...>
 * بدون أي تحويل إضافي، ويُحرَّر من الذاكرة عند استدعاء revokeObjectURL.
 */
export async function processPDF(
  file: File,
  onProgress?: (progress: number) => void
): Promise<{ url: string; filename: string }> {
  // نبلّغ بـ 10% فور البدء — feedback فوري للمستخدم
  onProgress?.(10);

  const formData = new FormData();
  formData.append("file", file);

  // XMLHttpRequest بدل fetch لأنه يدعم progress events حقيقية
  // fetch لا يعطيك upload progress في المتصفح بدون workarounds معقدة
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        // رفع الملف = 10% إلى 40% من التقدم الكلي
        const uploadProgress = 10 + (e.loaded / e.total) * 30;
        onProgress?.(Math.round(uploadProgress));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status === 200) {
        // الـ processing (AI + drawing) = 40% إلى 95%
        // نضع 95% لأن الاستجابة وصلت — سنكمل لـ 100% في page.tsx
        onProgress?.(95);

        const blob = new Blob([xhr.response], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);

        // نستخرج اسم الملف من الـ header لو كان موجوداً
        const disposition = xhr.getResponseHeader("content-disposition") ?? "";
        const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
        const filename = match?.[1]
          ? decodeURIComponent(match[1])
          : `${file.name.replace(".pdf", "")}_annotated.pdf`;

        resolve({ url, filename });
      } else {
        // نحاول نقرأ رسالة الخطأ من JSON لو كانت موجودة
        try {
          const errorData = JSON.parse(xhr.responseText);
          reject(new Error(errorData.detail ?? `خطأ ${xhr.status}`));
        } catch {
          reject(new Error(`فشل الطلب: ${xhr.status}`));
        }
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("تعذّر الاتصال بالسيرفر — تأكد أن البيكند يعمل على المنفذ 8000"));
    });

    xhr.addEventListener("timeout", () => {
      reject(new Error("انتهت مهلة الطلب — الملف كبير جداً أو السيرفر بطيء"));
    });

    xhr.open("POST", `${API_BASE}/api/pdf/process`);
    xhr.responseType = "arraybuffer";
    xhr.timeout = 5 * 60 * 1000; // 5 دقائق — كافية لملف 50 صفحة
    xhr.send(formData);
  });
}
