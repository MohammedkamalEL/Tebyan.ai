"""
PDF-ScribbleAI — Backend Entry Point
=====================================
نقطة الدخول الرئيسية لتطبيق FastAPI.
مسؤول فقط عن: إنشاء التطبيق، تسجيل الـ routers، إعداد CORS، وإدارة دورة حياة التطبيق.
لا منطق معالجة PDF هنا — هذا يعيش في app/services/.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

from app.routers import pdf_routes
from app.routers.pdf_routes import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    دورة حياة التطبيق: كود يعمل عند بدء التشغيل وعند الإغلاق.
    مفيد لاحقاً لتحميل أي موديل/عميل AI مرة واحدة فقط (singleton)
    بدل تحميله في كل طلب.
    """
    # --- Startup ---
    print(f"🚀 PDF-ScribbleAI Backend started | env={settings.ENV}")
    yield
    # --- Shutdown ---
    print("🛑 PDF-ScribbleAI Backend shutting down")


app = FastAPI(
    title="PDF-ScribbleAI API",
    description="Backend service for extracting, AI-annotating, and drawing handwritten-style notes on PDFs",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — مهم لأن واجهة Next.js (على بورت مختلف) ستستهلك هذا الـ API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """فحص سريع: هل السيرفر حي؟"""
    return {"status": "ok", "service": "pdf-scribble-ai-backend"}


@app.get("/health")
async def health_check():
    """Endpoint مخصص لفحوصات الصحة (health checks) من أدوات المراقبة أو Docker."""
    return {"status": "healthy"}


app.include_router(pdf_routes.router, prefix="/api/pdf", tags=["PDF Processing"])
