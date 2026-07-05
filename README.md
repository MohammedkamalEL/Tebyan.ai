# PDF-ScribbleAI — Backend

نظام معالجة PDF يستخرج النص، يحلله بالذكاء الاصطناعي، ويرسم تعليقات بأسلوب خط اليد.

## المكدس التقني

| المكون | التقنية |
|---|---|
| Framework | FastAPI + Uvicorn |
| استخراج PDF | PyMuPDF (fitz) |
| ذكاء اصطناعي | OpenRouter → Gemini / Llama (مجاني) |
| رسم التعليقات | PyMuPDF drawing API + Bézier curves |
| الخط العربي | arabic-reshaper + python-bidi |
| إدارة البيئة | UV + pyproject.toml |

## هيكلة المشروع

```
backend/
├── app/
│   ├── main.py              # نقطة الدخول — FastAPI + CORS + lifespan
│   ├── config.py            # إعدادات البيئة (pydantic-settings)
│   ├── models/
│   │   └── schemas.py       # عقد البيانات بين الطبقات (Pydantic)
│   ├── services/
│   │   ├── pdf_extractor.py # استخراج النص + إحداثيات الكلمات
│   │   ├── ai_annotator.py  # قرارات الـ AI + chunking + validation
│   │   └── pdf_drawer.py    # رسم خطوط Bézier + دوائر + هوامش
│   ├── routers/
│   │   └── pdf_routes.py    # API endpoint + async + logging
│   ├── utils/
│   │   └── geometry.py      # دوال رياضية (تموج الخط، شكل الدائرة)
│   ├── static/fonts/        # خط عربي .ttf (Amiri أو غيره)
│   └── tests/
│       ├── test_geometry.py # 11 اختبار للدوال الرياضية
│       └── test_routes.py   # 18 اختبار للـ API
├── storage/
│   ├── uploads/             # ملفات PDF المرفوعة (مؤقتة)
│   └── outputs/             # ملفات PDF المُعلَّقة (مؤقتة)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── .env
```

## Pipeline المعالجة

```
PDF مرفوع
  ↓
pdf_extractor.py   → استخراج النص + bbox لكل كلمة + sentence_id فريد
  ↓
ai_annotator.py    → تقسيم لـ chunks (20 جملة) → OpenRouter API → AnnotationPlan
  ↓
pdf_drawer.py      → رسم خطوط Bézier متعرجة + دوائر + ملاحظات هامشية عربية
  ↓
PDF مُعلَّق للتنزيل
```

## التشغيل المحلي

### 1. المتطلبات
- Python 3.11+
- UV: `pip install uv`
- مفتاح OpenRouter مجاني: https://openrouter.ai/

### 2. الإعداد

```bash
cd backend

# تثبيت التبعيات
uv sync

# إعداد متغيرات البيئة
cp .env.example .env
# ضع OPENROUTER_API_KEY في .env

# تحميل خط عربي (مرة واحدة)
curl -L "https://github.com/aliftype/amiri/releases/download/1.000/Amiri-1.000.zip" \
  -o amiri.zip && unzip amiri.zip "*.ttf" -d app/static/fonts/ && rm amiri.zip
```

### 3. التشغيل

```bash
uv run uvicorn app.main:app --reload --port 8000
```

### 4. الاختبار

```bash
# فحص صحة المكونات
curl http://localhost:8000/api/pdf/health/pipeline

# تشغيل الاختبارات
uv run pytest app/tests/ -v

# Swagger UI
http://localhost:8000/docs
```

## API Endpoints

| Method | Path | الوصف |
|---|---|---|
| GET | `/` | فحص السيرفر |
| GET | `/health` | health check |
| GET | `/api/pdf/health/pipeline` | فحص كل المكونات |
| POST | `/api/pdf/process` | معالجة PDF وإرجاع نسخة مُعلَّقة |

### POST /api/pdf/process

**المدخل:** ملف PDF عبر `multipart/form-data` (حقل `file`)

**المخرج:** ملف PDF مُعلَّق جاهز للتنزيل

**حدود:**
- الحجم الأقصى: 20MB
- عدد الصفحات: 50 صفحة

## إعدادات البيئة (.env)

```env
ENV=development
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
MAX_PDF_PAGES=50
MAX_FILE_SIZE_MB=20
```

## التشغيل بـ Docker

```bash
docker compose up --build
```

## الاختبارات

```bash
# كل الاختبارات
uv run pytest app/tests/ -v

# اختبارات الرياضيات فقط (لا تحتاج API key)
uv run pytest app/tests/test_geometry.py -v

# مع تقرير التغطية
uv run pytest app/tests/ --cov=app --cov-report=term-missing
```

## ملاحظات تقنية

- **Chunking:** الملفات الكبيرة تُقسَّم إلى 20 جملة لكل chunk مع تأخير 3 ثواني بين الـ chunks لحماية Free Tier limits.
- **Validation:** كل `sentence_id` و `word_index` يُتحقق منه محلياً قبل الرسم — الـ AI لا يُمرَّر للرسم مباشرة.
- **Async:** كل طبقة ثقيلة (استخراج، AI، رسم) تعمل في `asyncio.to_thread()` لتحرير event loop.
- **خط اليد:** الخطوط والدوائر مرسومة بمنحنيات Bézier مع انحراف عشوائي محكوم لمحاكاة الكتابة اليدوية.
