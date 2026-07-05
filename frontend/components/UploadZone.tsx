"use client";

/**
 * UploadZone — منطقة رفع الملف.
 *
 * يدعم:
 * - Click to upload
 * - Drag & Drop
 * - التحقق من نوع الملف (PDF فقط) وحجمه (20MB)
 *
 * لماذا نتحقق في الواجهة رغم أن البيكند يتحقق أيضاً؟
 * لأن التحقق المبكر يوفّر على المستخدم وقت الرفع كاملاً
 * قبل أن يعرف أن الملف خاطئ.
 */

import { useCallback, useRef, useState } from "react";
import { Upload, FileText, AlertCircle } from "lucide-react";

const MAX_SIZE_MB = 20;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

interface UploadZoneProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export default function UploadZone({ onFileSelect, disabled }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = (file: File): string | null => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      return "يُقبل ملف PDF فقط";
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `حجم الملف يتجاوز ${MAX_SIZE_MB}MB`;
    }
    return null;
  };

  const handleFile = useCallback(
    (file: File) => {
      setValidationError(null);
      const error = validate(file);
      if (error) {
        setValidationError(error);
        return;
      }
      onFileSelect(file);
    },
    [onFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [disabled, handleFile]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    // إعادة تصفير الـ input حتى لو اختار نفس الملف مرة ثانية
    e.target.value = "";
  };

  return (
    <div className="w-full">
      <div
        onClick={() => !disabled && inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          relative flex flex-col items-center justify-center gap-4
          w-full min-h-[280px] rounded-2xl border-2 border-dashed
          transition-all duration-200 cursor-pointer select-none
          ${isDragging
            ? "border-amber-500 bg-amber-50 scale-[1.01]"
            : "border-stone-300 bg-stone-50 hover:border-amber-400 hover:bg-amber-50/40"
          }
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}
        `}
      >
        {/* أيقونة */}
        <div className={`
          p-4 rounded-full transition-colors duration-200
          ${isDragging ? "bg-amber-100" : "bg-stone-100"}
        `}>
          {isDragging
            ? <FileText size={36} className="text-amber-600" />
            : <Upload size={36} className="text-stone-400" />
          }
        </div>

        {/* النص */}
        <div className="text-center space-y-1">
          <p className="text-stone-700 font-medium text-lg">
            {isDragging ? "أفلت الملف هنا" : "ارفع ملف PDF للتحليل"}
          </p>
          <p className="text-stone-400 text-sm">
            اسحب وأفلت، أو اضغط للاختيار
          </p>
          <p className="text-stone-400 text-xs">
            PDF فقط · الحجم الأقصى {MAX_SIZE_MB}MB
          </p>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled}
        />
      </div>

      {/* رسالة الخطأ */}
      {validationError && (
        <div className="mt-3 flex items-center gap-2 text-red-600 text-sm">
          <AlertCircle size={16} className="shrink-0" />
          <span>{validationError}</span>
        </div>
      )}
    </div>
  );
}
