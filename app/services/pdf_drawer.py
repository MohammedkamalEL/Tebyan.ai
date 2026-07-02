"""
Drawing Layer — يأخذ ExtractedDocument + AnnotationPlan المُتحقَّق منهما،
ويرسم فوق PDF الأصلي: خطوط متعرجة تحت الجمل، دوائر حول الكلمات،
وملاحظات هامشية بخط عربي يدوي.

التبعيات الحرجة:
  - arabic_reshaper + python-bidi: لمعالجة النص العربي (reshaping + RTL).
    بدونهما الحروف العربية في PyMuPDF تظهر منفصلة ومقلوبة.
  - خط .ttf عربي في app/static/fonts/: يجب أن يكون موجوداً قبل تشغيل هذه الطبقة.
    موصى به: Amiri أو Scheherazade New (مفتوح المصدر، يدعم العربية الكاملة).

نظام الإحداثيات المستخدم: نظام PDF الأصلي (origin أعلى-يسار، وحدات: points).
هذا هو نفس ما يرجعه PyMuPDF في get_text("words") وما خزّنّاه في BoundingBox.
"""

import os
import random
from pathlib import Path

import arabic_reshaper
import fitz  # PyMuPDF
from bidi.algorithm import get_display

from app.models.schemas import (
    AnnotationPlan,
    BoundingBox,
    ExtractedDocument,
    ExtractedSentence,
)
from app.utils.geometry import (
    margin_note_position,
    oval_control_points,
    wavy_underline_segments,
)

# ───────────────────────────────────────────────
# الإعدادات البصرية — سهلة التعديل في مكان واحد
# ───────────────────────────────────────────────
INK_COLOR      = (0.82, 0.10, 0.10)  # أحمر داكن (RGB 0-1) — يحاكي قلم تصحيح
INK_WIDTH      = 1.1                  # سماكة الخط بالـ points
CIRCLE_WIDTH   = 1.3                  # دوائر أسمك قليلاً لتبرز بصرياً
NOTE_FONT_SIZE = 7.5                  # حجم خط الملاحظات الهامشية
NOTE_OPACITY   = 0.85                 # شفافية طفيفة تجعل الملاحظة تبدو "مكتوبة"
UNDERLINE_GAP  = 2.0                  # المسافة الرأسية بين النص والخط (points)


def _get_font_path() -> str | None:
    """
    يبحث عن أي خط .ttf داخل app/static/fonts/.
    يرجع المسار الكامل لأول خط عربي موجود، أو None إذا كان المجلد فارغاً.
    """
    fonts_dir = Path(__file__).parent.parent / "static" / "fonts"
    for f in fonts_dir.glob("*.ttf"):
        return str(f)
    return None


def _prepare_arabic_text(text: str) -> str:
    """
    خطوتان ضروريتان لعرض العربية صحيحاً في PDF عبر PyMuPDF:

    1. arabic_reshaper: يربط الحروف المنفصلة في شكلها الصحيح حسب موضعها
       في الكلمة (حرف بداية، وسط، نهاية). بدونه: "ك ت ب" بدل "كتب".

    2. get_display (bidi): يعكس ترتيب الأحرف لتوافق RTL في ملف PDF.
       بدونه: النص يظهر مقلوباً من اليسار لليمين.
    """
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def _draw_wavy_underline(page: fitz.Page, bbox: BoundingBox, seed: int) -> None:
    """
    يرسم خطاً متعرجاً تحت جملة كاملة (محاكاة خط تسطير باليد).
    الخط يُرسم على y = bbox.y1 + UNDERLINE_GAP (أسفل النص مباشرة).
    """
    y = bbox.y1 + UNDERLINE_GAP
    segments = wavy_underline_segments(
        bbox.x0, y, bbox.x1,
        amplitude=1.2,
        segments=max(4, int((bbox.x1 - bbox.x0) / 20)),  # كثافة التموج تتناسب مع طول الخط
        seed=seed,
    )
    for seg in segments:
        page.draw_bezier(
            fitz.Point(seg.p0.x, seg.p0.y),
            fitz.Point(seg.p1.x, seg.p1.y),
            fitz.Point(seg.p2.x, seg.p2.y),
            fitz.Point(seg.p3.x, seg.p3.y),
            color=INK_COLOR,
            width=INK_WIDTH,
        )


def _draw_circle_around_word(page: fitz.Page, bbox: BoundingBox, seed: int) -> None:
    """
    يرسم شكلاً بيضاوياً غير منتظم حول كلمة (محاكاة دائرة رُسمت باليد).
    يستخدم 4 منحنيات Bézier من geometry.py لتكوين الشكل الكامل.
    """
    segments = oval_control_points(
        bbox.x0, bbox.y0, bbox.x1, bbox.y1,
        padding=3.0,
        jitter=1.5,
        seed=seed,
    )
    for seg in segments:
        page.draw_bezier(
            fitz.Point(seg.p0.x, seg.p0.y),
            fitz.Point(seg.p1.x, seg.p1.y),
            fitz.Point(seg.p2.x, seg.p2.y),
            fitz.Point(seg.p3.x, seg.p3.y),
            color=INK_COLOR,
            width=CIRCLE_WIDTH,
        )


def _draw_margin_note(
    page: fitz.Page,
    text: str,
    anchor_bbox: BoundingBox,
    side: str,
    font_name: str,
) -> None:
    """
    يكتب ملاحظة هامشية بالعربية في هامش الصفحة على نفس مستوى الجملة المرجعية.

    font_name هو الاسم المسجَّل في PyMuPDF (بعد font.register) لا مسار الملف.
    """
    page_rect = page.rect
    position = margin_note_position(
        anchor_y=anchor_bbox.y0,
        page_width=page_rect.width,
        page_height=page_rect.height,
        side=side,
    )

    prepared_text = _prepare_arabic_text(text)

    # fitz.Point هو موضع baseline النص (ليس top-left)
    page.insert_text(
        fitz.Point(position.x, position.y),
        prepared_text,
        fontname=font_name,
        fontsize=NOTE_FONT_SIZE,
        color=INK_COLOR,
    )


def _build_page_index(document: ExtractedDocument) -> dict[int, dict]:
    """
    يبني فهرساً سريعاً من page_number → {page_info, sentences}
    لتجنب المرور على كل الجمل في كل مرة نبحث عن جملة في صفحة معينة.
    O(n) مرة واحدة هنا بدل O(n²) داخل حلقات الرسم.
    """
    index: dict[int, dict] = {}
    for page_info in document.pages:
        index[page_info.page_number] = {
            "page_info": page_info,
            "sentences": {},
        }
    for sentence in document.sentences:
        pn = sentence.page_number
        if pn in index:
            index[pn]["sentences"][sentence.sentence_id] = sentence
    return index


def draw_annotations(
    input_pdf_path: str,
    output_pdf_path: str,
    document: ExtractedDocument,
    plan: AnnotationPlan,
) -> None:
    """
    نقطة الدخول الرئيسية لهذه الطبقة.
    تفتح PDF الأصلي، ترسم فوقه كل التعليقات من AnnotationPlan، وتحفظ النتيجة.

    لا تُعدّل input_pdf_path أبداً — الكتابة تذهب لـ output_pdf_path فقط.
    """
    font_path = _get_font_path()
    if font_path is None:
        raise FileNotFoundError(
            "لم يُعثر على خط .ttf في app/static/fonts/. "
            "حمّل خطاً عربياً مثل Amiri أو Scheherazade New وضعه في ذلك المجلد."
        )

    doc = fitz.open(input_pdf_path)

    # تسجيل الخط العربي مرة واحدة لكل المستند
    # fontbuffer يحمل bytes الخط في الذاكرة، ونسجله بـ set_font
    registered_font_name = "arabic_handwriting"
    font_bytes = Path(font_path).read_bytes()

    # نبني فهرس sentence_id → ExtractedSentence للبحث السريع
    sentences_by_id = {s.sentence_id: s for s in document.sentences}
    page_index = _build_page_index(document)

    # عداد seed يزيد بشكل رتيب لضمان أن كل خط/دائرة تبدو مختلفة بصرياً
    # لكنها ثابتة عند إعادة تشغيل نفس المستند (reproducible)
    seed_counter = 0

    try:
        # ─── رسم التسطيرات ───────────────────────────────────
        for ann in plan.underlines:
            sentence = sentences_by_id.get(ann.sentence_id)
            if sentence is None:
                continue  # تم التحقق في ai_annotator، لكن دفاعاً مضاعفاً
            page = doc[sentence.page_number - 1]
            _draw_wavy_underline(page, sentence.bbox, seed=seed_counter)
            seed_counter += 1

        # ─── رسم الدوائر ─────────────────────────────────────
        for ann in plan.circles:
            sentence = sentences_by_id.get(ann.sentence_id)
            if sentence is None:
                continue
            if ann.word_index >= len(sentence.words):
                continue  # حماية مضاعفة — تم التحقق سابقاً
            word = sentence.words[ann.word_index]
            page = doc[sentence.page_number - 1]
            _draw_circle_around_word(page, word.bbox, seed=seed_counter)
            seed_counter += 1

        # ─── رسم الملاحظات الهامشية ──────────────────────────
        for ann in plan.margin_notes:
            anchor_sentence = sentences_by_id.get(ann.anchor_sentence_id)
            if anchor_sentence is None:
                continue
            page = doc[anchor_sentence.page_number - 1]

            # تسجيل الخط في هذه الصفحة (PyMuPDF يحتاج تسجيل لكل صفحة)
            page.insert_font(
                fontname=registered_font_name,
                fontbuffer=font_bytes,
            )

            _draw_margin_note(
                page=page,
                text=ann.note_text,
                anchor_bbox=anchor_sentence.bbox,
                side=ann.side,
                font_name=registered_font_name,
            )
            seed_counter += 1

        doc.save(output_pdf_path, garbage=4, deflate=True)

    finally:
        doc.close()
