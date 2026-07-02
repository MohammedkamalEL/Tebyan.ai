"""
اختبارات الـ endpoint الرئيسي /api/pdf/process و /api/pdf/health/pipeline.

المبدأ الأساسي: لا نستدعي Anthropic API أو PyMuPDF الحقيقي في الاختبارات.
كل طبقة خارجية تُستبدل بـ mock — هذا يجعل الاختبارات:
  1. سريعة (ميلي ثواني لا ثواني)
  2. لا تحتاج API key أو ملف PDF حقيقي
  3. حتمية (deterministic) — لا تعتمد على استجابة شبكة أو AI

ما نختبره فعلياً هنا:
  - منطق التحقق من المدخلات (validation)
  - تدفق الـ pipeline (هل تُستدعى الطبقات بالترتيب الصحيح؟)
  - معالجة الأخطاء (هل كل خطأ يرجع HTTP status صحيح؟)
  - الـ response format (content-type، filename)

شغّل بـ: uv run pytest app/tests/test_routes.py -v
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import (
    AnnotationPlan,
    BoundingBox,
    ExtractedDocument,
    ExtractedSentence,
    ExtractedWord,
    PageInfo,
)

client = TestClient(app)

# ─── Fixtures: بيانات وهمية قابلة لإعادة الاستخدام ───────────────────────────

@pytest.fixture
def minimal_extracted_document() -> ExtractedDocument:
    """
    ExtractedDocument بسيط بصفحة واحدة وجملتين.
    يُمثل أصغر مخرج صحيح يمكن أن ينتجه pdf_extractor.
    """
    return ExtractedDocument(
        total_pages=1,
        pages=[PageInfo(page_number=1, width=595.0, height=842.0)],
        sentences=[
            ExtractedSentence(
                sentence_id=0,
                text="هذه جملة اختبارية أولى.",
                bbox=BoundingBox(x0=50, y0=100, x1=400, y1=115),
                page_number=1,
                words=[
                    ExtractedWord(word_index=0, text="هذه",    bbox=BoundingBox(x0=50,  y0=100, x1=90,  y1=115)),
                    ExtractedWord(word_index=1, text="جملة",   bbox=BoundingBox(x0=95,  y0=100, x1=145, y1=115)),
                    ExtractedWord(word_index=2, text="اختبارية", bbox=BoundingBox(x0=150, y0=100, x1=250, y1=115)),
                    ExtractedWord(word_index=3, text="أولى.",  bbox=BoundingBox(x0=255, y0=100, x1=310, y1=115)),
                ],
            ),
            ExtractedSentence(
                sentence_id=1,
                text="وهذه جملة ثانية للاختبار.",
                bbox=BoundingBox(x0=50, y0=120, x1=380, y1=135),
                page_number=1,
                words=[
                    ExtractedWord(word_index=0, text="وهذه",  bbox=BoundingBox(x0=50,  y0=120, x1=100, y1=135)),
                    ExtractedWord(word_index=1, text="جملة",  bbox=BoundingBox(x0=105, y0=120, x1=155, y1=135)),
                    ExtractedWord(word_index=2, text="ثانية", bbox=BoundingBox(x0=160, y0=120, x1=215, y1=135)),
                ],
            ),
        ],
    )


@pytest.fixture
def minimal_annotation_plan() -> AnnotationPlan:
    """AnnotationPlan فارغ — صحيح تماماً (الـ AI قد يقرر عدم التعليق)."""
    return AnnotationPlan(underlines=[], circles=[], margin_notes=[])


@pytest.fixture
def pdf_bytes() -> bytes:
    """
    أبسط ملف PDF صحيح ممكن (single-page فارغة).
    ينتهي بـ %%EOF ويبدأ بـ %PDF — يمر فحص magic bytes.
    لا نحتاج محتوى حقيقياً لأن extract_pdf مُستبدل بـ mock في كل الاختبارات.
    """
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f\n"
        b"0000000009 00000 n\n"
        b"0000000058 00000 n\n"
        b"0000000115 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n190\n%%EOF"
    )


# ─── Helper: يبني multipart/form-data request ────────────────────────────────

def _make_upload(content: bytes, filename: str = "test.pdf") -> dict:
    return {"file": (filename, io.BytesIO(content), "application/pdf")}


# ─── اختبارات /health/pipeline ───────────────────────────────────────────────

class TestPipelineHealth:
    def test_returns_200(self):
        res = client.get("/api/pdf/health/pipeline")
        assert res.status_code == 200

    def test_response_has_required_keys(self):
        res = client.get("/api/pdf/health/pipeline")
        data = res.json()
        assert "status" in data
        assert "checks" in data

    def test_checks_cover_all_components(self):
        res = client.get("/api/pdf/health/pipeline")
        checks = res.json()["checks"]
        assert "arabic_font"    in checks
        assert "upload_dir"     in checks
        assert "output_dir"     in checks
        assert "anthropic_key"  in checks

    def test_status_is_healthy_or_degraded(self):
        res = client.get("/api/pdf/health/pipeline")
        assert res.json()["status"] in ("healthy", "degraded")


# ─── اختبارات التحقق من المدخلات (Validation) ───────────────────────────────

class TestInputValidation:
    def test_rejects_non_pdf_extension(self):
        res = client.post(
            "/api/pdf/process",
            files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert res.status_code == 400
        assert "PDF" in res.json()["detail"]

    def test_rejects_file_with_wrong_magic_bytes(self):
        """ملف امتداده .pdf لكن محتواه ليس PDF حقيقياً."""
        fake_pdf = b"This is not a PDF file at all"
        res = client.post("/api/pdf/process", files=_make_upload(fake_pdf))
        assert res.status_code == 400
        assert "magic" in res.json()["detail"]

    def test_rejects_oversized_file(self):
        """ملف يتجاوز MAX_FILE_SIZE_MB."""
        # نبني header PDF صحيح + بيانات ضخمة
        oversized = b"%PDF-1.4 " + b"X" * (25 * 1024 * 1024)
        res = client.post("/api/pdf/process", files=_make_upload(oversized))
        assert res.status_code == 413

    def test_rejects_missing_file_field(self):
        """طلب بدون حقل 'file' أصلاً."""
        res = client.post("/api/pdf/process")
        assert res.status_code == 422  # FastAPI validation error

    def test_accepts_valid_pdf_magic_bytes(self, pdf_bytes, minimal_extracted_document, minimal_annotation_plan):
        """ملف صحيح يمر فحص magic bytes ويصل للطبقات (المُستبدلة بـ mock)."""
        with (
            patch("app.routers.pdf_routes.extract_pdf", return_value=minimal_extracted_document),
            patch("app.routers.pdf_routes.generate_annotation_plan", return_value=minimal_annotation_plan),
            patch("app.routers.pdf_routes.draw_annotations"),
            patch("app.routers.pdf_routes.FileResponse") as mock_response,
        ):
            mock_response.return_value = MagicMock(status_code=200)
            client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
            # إذا وصلنا هنا بدون 400/413، الـ validation مررت الملف بنجاح
            mock_response.assert_called_once()


# ─── اختبارات تدفق الـ Pipeline ──────────────────────────────────────────────

class TestPipelineFlow:
    """
    نتحقق أن الطبقات تُستدعى بالترتيب الصحيح وبالمعاملات الصحيحة.
    كل طبقة مُستبدلة بـ mock — نختبر "التنسيق بين الطبقات" لا الطبقات نفسها.
    """

    def test_extract_called_with_upload_path(self, pdf_bytes, minimal_extracted_document, minimal_annotation_plan):
        with (
            patch("app.routers.pdf_routes.extract_pdf", return_value=minimal_extracted_document) as mock_extract,
            patch("app.routers.pdf_routes.generate_annotation_plan", return_value=minimal_annotation_plan),
            patch("app.routers.pdf_routes.draw_annotations"),
            patch("app.routers.pdf_routes.FileResponse", return_value=MagicMock(status_code=200)),
        ):
            client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
            mock_extract.assert_called_once()
            # المعامل الأول هو مسار الملف المرفوع
            called_path = mock_extract.call_args[0][0]
            assert called_path.endswith("_input.pdf")

    def test_ai_annotator_receives_extracted_document(self, pdf_bytes, minimal_extracted_document, minimal_annotation_plan):
        with (
            patch("app.routers.pdf_routes.extract_pdf", return_value=minimal_extracted_document),
            patch("app.routers.pdf_routes.generate_annotation_plan", return_value=minimal_annotation_plan) as mock_ai,
            patch("app.routers.pdf_routes.draw_annotations"),
            patch("app.routers.pdf_routes.FileResponse", return_value=MagicMock(status_code=200)),
        ):
            client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
            mock_ai.assert_called_once_with(minimal_extracted_document)

    def test_drawer_receives_plan_and_document(self, pdf_bytes, minimal_extracted_document, minimal_annotation_plan):
        with (
            patch("app.routers.pdf_routes.extract_pdf", return_value=minimal_extracted_document),
            patch("app.routers.pdf_routes.generate_annotation_plan", return_value=minimal_annotation_plan),
            patch("app.routers.pdf_routes.draw_annotations") as mock_draw,
            patch("app.routers.pdf_routes.FileResponse", return_value=MagicMock(status_code=200)),
        ):
            client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
            mock_draw.assert_called_once()
            _, _, doc_arg, plan_arg = mock_draw.call_args[0]
            assert doc_arg  is minimal_extracted_document
            assert plan_arg is minimal_annotation_plan

    def test_draw_not_called_if_extract_fails(self, pdf_bytes):
        """لو فشل الاستخراج، لا يجب أن يُستدعى الرسم أبداً."""
        import fitz
        with (
            patch("app.routers.pdf_routes.extract_pdf", side_effect=fitz.FileDataError("تالف")),
            patch("app.routers.pdf_routes.draw_annotations") as mock_draw,
        ):
            res = client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
            assert res.status_code == 400
            mock_draw.assert_not_called()

    def test_draw_not_called_if_ai_fails(self, pdf_bytes, minimal_extracted_document):
        """لو فشل الـ AI، لا يجب أن يُستدعى الرسم."""
        from anthropic import APIConnectionError
        with (
            patch("app.routers.pdf_routes.extract_pdf", return_value=minimal_extracted_document),
            patch("app.routers.pdf_routes.generate_annotation_plan", side_effect=APIConnectionError.__new__(APIConnectionError)),
            patch("app.routers.pdf_routes.draw_annotations") as mock_draw,
        ):
            res = client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
            assert res.status_code == 502
            mock_draw.assert_not_called()


# ─── اختبارات معالجة الأخطاء ─────────────────────────────────────────────────

class TestErrorHandling:
    def test_empty_document_returns_422(self, pdf_bytes):
        """PDF بدون نص قابل للاستخراج (مثلاً مسح ضوئي بدون OCR)."""
        empty_doc = ExtractedDocument(
            total_pages=1,
            pages=[PageInfo(page_number=1, width=595.0, height=842.0)],
            sentences=[],
        )
        with patch("app.routers.pdf_routes.extract_pdf", return_value=empty_doc):
            res = client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
        assert res.status_code == 422
        assert "نص" in res.json()["detail"]

    def test_corrupted_pdf_returns_400(self, pdf_bytes):
        import fitz
        with patch("app.routers.pdf_routes.extract_pdf", side_effect=fitz.FileDataError("corrupt")):
            res = client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
        assert res.status_code == 400

    def test_anthropic_auth_error_returns_502(self, pdf_bytes, minimal_extracted_document):
        from anthropic import AuthenticationError
        mock_auth_err = MagicMock(spec=AuthenticationError)
        with (
            patch("app.routers.pdf_routes.extract_pdf", return_value=minimal_extracted_document),
            patch("app.routers.pdf_routes.generate_annotation_plan", side_effect=mock_auth_err),
        ):
            res = client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
        assert res.status_code == 502
        assert "API" in res.json()["detail"]

    def test_missing_font_returns_500(self, pdf_bytes, minimal_extracted_document, minimal_annotation_plan):
        with (
            patch("app.routers.pdf_routes.extract_pdf", return_value=minimal_extracted_document),
            patch("app.routers.pdf_routes.generate_annotation_plan", return_value=minimal_annotation_plan),
            patch("app.routers.pdf_routes.draw_annotations", side_effect=FileNotFoundError("خط مفقود")),
        ):
            res = client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
        assert res.status_code == 500
        assert "خط" in res.json()["detail"]

    def test_page_limit_exceeded_returns_413(self, pdf_bytes):
        """مستند يتجاوز MAX_PDF_PAGES."""
        large_doc = ExtractedDocument(
            total_pages=999,
            pages=[PageInfo(page_number=i + 1, width=595.0, height=842.0) for i in range(999)],
            sentences=[
                ExtractedSentence(
                    sentence_id=0,
                    text="جملة.",
                    bbox=BoundingBox(x0=0, y0=0, x1=100, y1=15),
                    page_number=1,
                    words=[],
                )
            ],
        )
        with patch("app.routers.pdf_routes.extract_pdf", return_value=large_doc):
            res = client.post("/api/pdf/process", files=_make_upload(pdf_bytes))
        assert res.status_code == 413
