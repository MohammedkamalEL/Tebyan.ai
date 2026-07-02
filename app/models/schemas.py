"""
Pydantic Schemas — العقد (Contract) الرسمي بين طبقات النظام الثلاث:
  1) Extraction Layer  (pdf_extractor.py)   → ينتج PageContent / ExtractedDocument
  2) AI Decision Layer (ai_annotator.py)    → يستهلك ExtractedDocument، ينتج AnnotationPlan
  3) Drawing Layer     (pdf_drawer.py)      → يستهلك ExtractedDocument + AnnotationPlan

القرار المعماري الأساسي: الـ AI لا يتعامل مع إحداثيات أبداً. هو يقرر "ماذا" (أي جملة/كلمة)
عبر مرجع رقمي (sentence_id / word_index)، ونحن نحلّ (resolve) هذا المرجع إلى إحداثيات فعلية
محلياً باستخدام البيانات التي استخرجناها مسبقاً بـ PyMuPDF. هذا يفصل "القرار" عن "الموضع"
ويمنع اعتماد دقة الرسم على دقة نسخ الـ AI للنص الحرفي.
"""

from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# 1) طبقة الاستخراج (PyMuPDF) — ما يخرج من قراءة PDF الخام
# ============================================================

class BoundingBox(BaseModel):
    """
    صندوق محيط بعنصر نصي، بنظام إحداثيات PDF (الأصل أعلى-يسار، بالنقاط/points).
    هذا هو نفس النظام الذي يرجعه PyMuPDF عبر page.get_text("dict").
    """
    x0: float
    y0: float
    x1: float
    y1: float


class ExtractedWord(BaseModel):
    """
    كلمة واحدة بإحداثياتها الخاصة — ضرورية لأن 'circle' annotation
    يحيط بكلمة محددة، لا بالجملة كاملة. بدون هذا، لا يمكن رسم دائرة دقيقة.
    """
    word_index: int = Field(..., description="فهرس الكلمة داخل الجملة (يبدأ من 0)")
    text: str
    bbox: BoundingBox


class ExtractedSentence(BaseModel):
    """
    جملة واحدة مستخرجة، مع تفكيكها إلى كلمات.
    sentence_id فريد على مستوى المستند الكامل (لا الصفحة فقط) — هذا يبسّط
    على الـ AI الإشارة لأي جملة بمعرّف واحد دون الحاجة لمعرفة رقم الصفحة.
    """
    sentence_id: int = Field(..., description="معرف فريد للجملة على مستوى كل المستند")
    text: str
    bbox: BoundingBox
    page_number: int = Field(..., description="رقم الصفحة، يبدأ من 1")
    words: list[ExtractedWord] = Field(default_factory=list)


class PageInfo(BaseModel):
    """أبعاد الصفحة — ضرورية للرسم النسبي ولوضع الملاحظات الهامشية بشكل صحيح."""
    page_number: int
    width: float
    height: float


class ExtractedDocument(BaseModel):
    """
    الناتج الكامل لطبقة الاستخراج. هذا هو ما يُمرَّر لطبقة AI Decision
    (بعد تحويله لنص مبسّط) وما يُستخدم كاملاً في طبقة الرسم.
    """
    total_pages: int
    pages: list[PageInfo]
    sentences: list[ExtractedSentence]


# ============================================================
# 2) طبقة قرار الـ AI — ما يرجعه LLM كـ "خطة تعليق"
# ============================================================

class AnnotationType(str, Enum):
    """
    Enum بدل str خام: يمنع أخطاء كتابة (مثل 'underlne') من المرور بصمت،
    ويعطي IDE/linter قدرة فعلية على التحقق.
    """
    UNDERLINE = "underline"
    CIRCLE = "circle"
    MARGIN_NOTE = "margin_note"


class UnderlineAnnotation(BaseModel):
    """
    تسطير جملة كاملة. لا نحتاج إحداثيات هنا أبداً — فقط sentence_id،
    والرسم سيحل bbox الجملة من ExtractedDocument.
    """
    type: AnnotationType = AnnotationType.UNDERLINE
    sentence_id: int = Field(..., description="معرف الجملة المراد تسطيرها (من ExtractedDocument)")
    reason: str | None = Field(None, description="سبب اختصاري لماذا هذه الجملة مهمة (للتصحيح/المراجعة)")


class CircleAnnotation(BaseModel):
    """
    دائرة حول كلمة محددة داخل جملة. نحتاج sentence_id + word_index معاً
    لأن نفس الكلمة قد تتكرر في جمل مختلفة بنفس المستند.
    """
    type: AnnotationType = AnnotationType.CIRCLE
    sentence_id: int
    word_index: int = Field(..., description="فهرس الكلمة داخل ExtractedSentence.words")
    reason: str | None = None


class MarginNoteAnnotation(BaseModel):
    """
    ملاحظة هامشية بالعربية، مرتبطة بجملة مرجعية (لتحديد ارتفاعها على الصفحة)
    لكنها تُرسم في الهامش (يسار/يمين الصفحة) لا فوق النص مباشرة.
    """
    type: AnnotationType = AnnotationType.MARGIN_NOTE
    anchor_sentence_id: int = Field(..., description="الجملة التي تُحدد ارتفاع الملاحظة على الصفحة")
    note_text: str = Field(..., description="نص الملاحظة بالعربية")
    side: str = Field(default="right", description="'right' أو 'left' — أي هامش")


class AnnotationPlan(BaseModel):
    """
    الهيكل الكامل الذي نطلب من الـ AI إرجاعه كـ JSON صِرف.
    هذا هو الـ response_model الذي سنفرضه على استدعاء الـ LLM.
    """
    underlines: list[UnderlineAnnotation] = Field(default_factory=list)
    circles: list[CircleAnnotation] = Field(default_factory=list)
    margin_notes: list[MarginNoteAnnotation] = Field(default_factory=list)


# ============================================================
# 3) طبقة الرسم — مخرجات نهائية (للـ API response أو حفظ الملف)
# ============================================================

class ProcessPDFResponse(BaseModel):
    """رد الـ Endpoint النهائي بعد إتمام كل الخطوات الثلاث."""
    success: bool
    output_file_path: str | None = None
    total_pages: int
    annotation_summary: dict[str, int] = Field(
        default_factory=dict,
        description="مثال: {'underlines': 5, 'circles': 3, 'margin_notes': 2}",
    )
    error: str | None = None
