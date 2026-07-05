"""
PDF Processing Router — نسخة محسّنة مع:
  - Async حقيقي عبر asyncio.to_thread() لعزل العمليات الثقيلة (PyMuPDF + AI)
  - Structured logging بـ Python logging standard module
  - قياس زمن كل طبقة (timing) لتشخيص bottlenecks
  - Correlation ID لكل طلب لتتبعه عبر السجلات

لماذا asyncio.to_thread() لا async/await مباشرة؟
PyMuPDF و Anthropic SDK (في استدعاءاتنا) كلاهما blocking بطبيعته.
لو استدعيناهما مباشرة في async def، سنحجب event loop الكامل طول فترة
المعالجة — أي طلبات أخرى تنتظر. to_thread() يشغّل الكود في thread pool
منفصل ويحرر event loop فوراً.
"""

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path

import fitz
from openai import APIConnectionError, APIStatusError, AuthenticationError
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.services.ai_annotator import generate_annotation_plan
from app.services.pdf_drawer import draw_annotations
from app.services.pdf_extractor import extract_pdf

router = APIRouter()

MAX_FILE_SIZE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024

# ─── Logger مخصص لهذا الـ module ─────────────────────────────────────────────
# نستخدم __name__ كاسم للـ logger — هذا يعطي مسار كامل في السجل:
# "app.routers.pdf_routes" بدل "root"، مما يسهل فلترة السجلات لاحقاً.
logger = logging.getLogger(__name__)


# ─── إعداد الـ logging (يُستدعى مرة واحدة من main.py عند الإقلاع) ───────────
def setup_logging() -> None:
    """
    يُعدّ نظام الـ logging للتطبيق كاملاً.
    Format يحتوي: الوقت، مستوى الخطورة، اسم الـ module، رقم السطر، الرسالة.
    هذا يكفي للـ development — في production استبدله بـ JSON formatter
    متوافق مع أي log aggregator (Datadog, CloudWatch, إلخ).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # تخفيف ضجيج مكتبات خارجية لا نحتاج تفاصيلها
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


def _cleanup_files(*paths: str) -> None:
    """يحذف ملفات مؤقتة — يُستدعى كـ BackgroundTask بعد إرسال الرد."""
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
            logger.debug("🗑  حُذف الملف المؤقت: %s", path)
        except Exception as exc:
            logger.warning("فشل حذف الملف المؤقت %s: %s", path, exc)


def _validate_upload(file: UploadFile, content: bytes) -> None:
    """تحقق مبكر قبل أي معالجة ثقيلة."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="يُقبل ملف PDF فقط")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"حجم الملف يتجاوز الحد المسموح ({settings.MAX_FILE_SIZE_MB}MB)",
        )

    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail="الملف ليس PDF صحيحاً (magic bytes خاطئة)",
        )


@router.post("/process", summary="معالجة PDF وإضافة تعليقات بخط اليد")
async def process_pdf(
    file: UploadFile,
    background_tasks: BackgroundTasks,
) -> FileResponse:
    # ─── Correlation ID: معرّف فريد لكل طلب يظهر في كل سطر logging ─────────
    # يسمح بتتبع طلب واحد كاملاً عبر السجلات حتى لو جاءت طلبات متزامنة
    job_id = uuid.uuid4().hex
    log = logging.LoggerAdapter(logger, {"job_id": job_id})
    request_start = time.perf_counter()

    log.info("📥 طلب جديد | ملف: %s | حجم تقريبي: سيُحسب بعد القراءة", file.filename)

    # ─── 1. استقبال الملف والتحقق ────────────────────────────────────────────
    content = await file.read()
    log.info("📄 حجم الملف: %.1f KB", len(content) / 1024)
    _validate_upload(file, content)

    upload_path = os.path.join(settings.UPLOAD_DIR, f"{job_id}_input.pdf")
    output_path = os.path.join(settings.OUTPUT_DIR, f"{job_id}_annotated.pdf")

    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(upload_path).write_bytes(content)

    background_tasks.add_task(_cleanup_files, upload_path, output_path)

    # ─── 2. طبقة الاستخراج (blocking → thread) ───────────────────────────────
    t0 = time.perf_counter()
    try:
        document = await asyncio.to_thread(extract_pdf, upload_path)
    except fitz.FileDataError as exc:
        log.error("❌ فشل استخراج PDF: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=f"تعذّر قراءة ملف PDF — قد يكون تالفاً أو مشفراً: {exc}",
        )

    extraction_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "✅ الاستخراج اكتمل | صفحات: %d | جمل: %d | زمن: %.0fms",
        document.total_pages,
        len(document.sentences),
        extraction_ms,
    )

    if not document.sentences:
        raise HTTPException(
            status_code=422,
            detail="لم يُعثر على نص قابل للاستخراج (ملف مسح ضوئي؟)",
        )

    if len(document.pages) > settings.MAX_PDF_PAGES:
        raise HTTPException(
            status_code=413,
            detail=f"عدد الصفحات ({len(document.pages)}) يتجاوز الحد ({settings.MAX_PDF_PAGES})",
        )

    # ─── 3. طبقة الـ AI (blocking → thread) ──────────────────────────────────
    t0 = time.perf_counter()
    try:
        annotation_plan = await asyncio.to_thread(generate_annotation_plan, document)
    except AuthenticationError:
        log.error("❌ OpenRouter API: مفتاح غير صحيح")
        raise HTTPException(status_code=502, detail="مفتاح OpenRouter API غير صحيح")
    except APIConnectionError as exc:
        log.error("❌ OpenRouter API: فشل الاتصال: %s", exc)
        raise HTTPException(status_code=502, detail="تعذّر الاتصال بـ OpenRouter API")
    except APIStatusError as exc:
        log.error("❌ OpenRouter API: status=%d", exc.status_code)
        raise HTTPException(status_code=502, detail=f"خطأ من OpenRouter API: {exc.status_code}")
    except RuntimeError as exc:
        log.error("❌ JSON parse error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    ai_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "✅ AI اكتمل | تسطيرات: %d | دوائر: %d | هوامش: %d | زمن: %.0fms",
        len(annotation_plan.underlines),
        len(annotation_plan.circles),
        len(annotation_plan.margin_notes),
        ai_ms,
    )

    # ─── 4. طبقة الرسم (blocking → thread) ───────────────────────────────────
    t0 = time.perf_counter()
    try:
        await asyncio.to_thread(
            draw_annotations, upload_path, output_path, document, annotation_plan
        )
    except FileNotFoundError as exc:
        log.error("❌ خط عربي مفقود: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        log.exception("❌ خطأ في الرسم: %s", exc)
        raise HTTPException(status_code=500, detail=f"خطأ في رسم التعليقات: {type(exc).__name__}")

    drawing_ms = (time.perf_counter() - t0) * 1000
    total_ms = (time.perf_counter() - request_start) * 1000

    log.info(
        "✅ الرسم اكتمل | زمن: %.0fms | إجمالي الطلب: %.0fms",
        drawing_ms,
        total_ms,
    )

    # ─── 5. إرجاع الملف ──────────────────────────────────────────────────────
    download_name = f"{Path(file.filename).stem}_annotated.pdf"
    log.info("📤 إرسال الملف: %s", download_name)

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=download_name,
    )


@router.get("/health/pipeline", summary="فحص صحة كل مكونات الـ pipeline")
async def pipeline_health() -> dict:
    """
    Endpoint مخصص لفحص جاهزية كل مكون قبل قبول أي طلب حقيقي.
    مفيد لـ Docker health checks ولـ CI/CD قبل النشر.
    """
    checks: dict[str, str] = {}

    # فحص وجود خط عربي
    fonts_dir = Path(__file__).parent.parent / "static" / "fonts"
    fonts = list(fonts_dir.glob("*.ttf"))
    checks["arabic_font"] = f"✅ {fonts[0].name}" if fonts else "❌ لا يوجد خط .ttf"

    # فحص مجلدات التخزين
    checks["upload_dir"]  = "✅" if Path(settings.UPLOAD_DIR).exists()  else "❌ مجلد uploads مفقود"
    checks["output_dir"]  = "✅" if Path(settings.OUTPUT_DIR).exists()  else "❌ مجلد outputs مفقود"

    # فحص مفتاح الـ API
    checks["openrouter_key"] = "✅ موجود" if settings.OPENROUTER_API_KEY else "❌ OPENROUTER_API_KEY فارغ"

    all_ok = all(v.startswith("✅") for v in checks.values())

    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
    }
