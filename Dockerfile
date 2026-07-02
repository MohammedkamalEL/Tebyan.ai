# ─── Stage 1: Builder ────────────────────────────────────────────────────────
# نثبّت التبعيات في image مستقل أولاً، ثم ننسخ فقط ما نحتاجه للـ runtime.
# هذا يقلّل حجم الـ image النهائي ويمنع وصول أدوات البناء للإنتاج.
FROM python:3.12-slim AS builder

# تثبيت UV مباشرة من صورته الرسمية (أسرع من pip install uv)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ننسخ ملفات التبعيات أولاً (قبل الكود) — Docker layer caching:
# لو لم تتغير pyproject.toml، لن يُعيد تثبيت التبعيات في كل build
COPY pyproject.toml .

# تثبيت التبعيات في مجلد مستقل (لا venv داخل المشروع)
RUN uv pip install --system --no-cache -r pyproject.toml 2>/dev/null || \
    uv pip install --system --no-cache \
    fastapi==0.115.6 \
    "uvicorn[standard]==0.34.0" \
    python-multipart==0.0.20 \
    pymupdf==1.25.1 \
    pydantic==2.10.4 \
    pydantic-settings==2.7.0 \
    google-generativeai==0.8.3 \
    python-dotenv==1.0.1 \
    aiofiles==24.1.0 \
    arabic-reshaper==3.0.0 \
    python-bidi==0.6.6


# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# مستخدم غير root — ممارسة أمنية أساسية
# لو شغّلنا كـ root وفيه ثغرة في الكود، المهاجم يحصل على root access كامل
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# ننسخ Python packages المثبتة من stage البناء
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin

# ننسخ كود التطبيق
COPY app/ ./app/

# ننسخ الخطوط العربية (يجب أن تكون موجودة قبل docker build)
# لو المجلد فارغ، pdf_drawer سيرفع FileNotFoundError عند أول طلب
COPY app/static/fonts/ ./app/static/fonts/

# مجلدات التخزين المؤقت
RUN mkdir -p storage/uploads storage/outputs && \
    chown -R appuser:appuser /app

USER appuser

# FastAPI port
EXPOSE 8000

# فحص صحة مدمج — Docker يعرف تلقائياً إذا السيرفر ميت
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

# --workers 1: مناسب للبداية — زده لاحقاً حسب الحمل
# --timeout-keep-alive 65: أطول من LB timeout الافتراضي (60s) لتجنب dropped connections
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--timeout-keep-alive", "65"]
