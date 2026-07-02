"""
Extraction Layer — يستخدم PyMuPDF لتحويل PDF خام إلى ExtractedDocument منظم.

المسؤولية الوحيدة لهذا الملف: "القراءة الدقيقة". لا قرارات AI هنا، لا رسم.
المخرج (ExtractedDocument) هو العقد الذي تعتمد عليه طبقتا AI والرسم.

قرار تقني أساسي: نستخدم page.get_text("words") بدل page.get_text("dict").
"words" يرجع قائمة مسطّحة: (x0, y0, x1, y1, word, block_no, line_no, word_no)
وهذا يكفي تماماً لمهمتنا (نص + bbox لكل كلمة) دون تعقيد التنقل في dict متداخل.
"""

import re

import fitz  # PyMuPDF

from app.models.schemas import (
    BoundingBox,
    ExtractedDocument,
    ExtractedSentence,
    ExtractedWord,
    PageInfo,
)

# علامات نهاية الجملة — عربية ولاتينية معاً.
# لاحظ: '،' (الفاصلة العربية) و '،' ليست نهاية جملة، فقط علامات الوقف الكاملة.
SENTENCE_END_CHARS = {".", "!", "?", "؟", "۔"}


def _word_ends_sentence(word: str) -> bool:
    """
    يتحقق إن كانت الكلمة (كما استخرجها PyMuPDF) تنتهي بعلامة ترقيم تُغلق جملة.
    نتعامل مع حالات مثل 'كلمة.' أو 'كلمة؟' أو حتى 'كلمة."' (علامة اقتباس بعد النقطة).
    """
    stripped = word.rstrip("\"'»”’")
    return bool(stripped) and stripped[-1] in SENTENCE_END_CHARS


def _merge_bboxes(boxes: list[BoundingBox]) -> BoundingBox:
    """
    يدمج (union) عدة bounding boxes في صندوق واحد يحيط بها جميعاً.
    ضروري لأن الجملة قد تمتد على أكثر من سطر، فلا يكفي bbox كلمة واحدة.
    """
    return BoundingBox(
        x0=min(b.x0 for b in boxes),
        y0=min(b.y0 for b in boxes),
        x1=max(b.x1 for b in boxes),
        y1=max(b.y1 for b in boxes),
    )


def _extract_words_from_page(page: fitz.Page) -> list[tuple[str, BoundingBox]]:
    """
    يستخرج كل الكلمات من صفحة واحدة بترتيب القراءة الصحيح.
    PyMuPDF يرتب الكلمات حسب (block_no, line_no, word_no) تلقائياً عبر
    sort=True، وهذا يعطي ترتيب قراءة بصري صحيح حتى للنص العربي RTL
    (لأن الترتيب مبني على الموضع الفعلي في الصفحة المُرندرة، لا على
    منطق Unicode bidi).
    """
    raw_words = page.get_text("words", sort=True)
    # raw_words: list of (x0, y0, x1, y1, word, block_no, line_no, word_no)
    result = []
    for x0, y0, x1, y1, word, *_ in raw_words:
        if word.strip():  # تجاهل أي كلمة فارغة (نادر، لكن يحدث مع مسافات شاذة)
            result.append((word, BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)))
    return result


def _segment_into_sentences(
    words_with_bbox: list[tuple[str, BoundingBox]],
    page_number: int,
    sentence_id_start: int,
) -> tuple[list[ExtractedSentence], int]:
    """
    يحوّل قائمة (كلمة, bbox) مسطّحة إلى جمل كاملة.

    المنطق: نتجمّع الكلمات تباعاً، وعند مصادفة كلمة تنتهي بعلامة وقف،
    نقفل الجملة الحالية ونبدأ جملة جديدة. أي كلمات متبقية في نهاية
    الصفحة بدون علامة وقف (مثل عنوان أو سطر منقطع) تُعتبر جملة كاملة أيضاً
    — لا نريد فقدان أي نص فقط لأنه لا ينتهي بنقطة.

    يرجع: (قائمة الجمل، sentence_id التالي المتاح) — حتى نحافظ على عداد
    فريد عبر كل صفحات المستند، لا فقط داخل الصفحة الواحدة.
    """
    sentences: list[ExtractedSentence] = []
    current_words: list[tuple[str, BoundingBox]] = []
    next_id = sentence_id_start

    def flush_current():
        nonlocal current_words, next_id
        if not current_words:
            return
        text = " ".join(w for w, _ in current_words)
        bbox = _merge_bboxes([b for _, b in current_words])
        extracted_words = [
            ExtractedWord(word_index=i, text=w, bbox=b)
            for i, (w, b) in enumerate(current_words)
        ]
        sentences.append(
            ExtractedSentence(
                sentence_id=next_id,
                text=text,
                bbox=bbox,
                page_number=page_number,
                words=extracted_words,
            )
        )
        next_id += 1
        current_words = []

    for word, bbox in words_with_bbox:
        current_words.append((word, bbox))
        if _word_ends_sentence(word):
            flush_current()

    flush_current()  # أي كلمات متبقية بدون علامة وقف ختامية

    return sentences, next_id


def extract_pdf(file_path: str) -> ExtractedDocument:
    """
    نقطة الدخول الرئيسية لهذه الطبقة.
    تفتح ملف PDF، تمر صفحة بصفحة، وترجع ExtractedDocument كامل وجاهز
    للتمرير إلى طبقة AI Decision.
    """
    doc = fitz.open(file_path)
    total_pages = doc.page_count  # نحفظه قبل الإغلاق، لأن doc.close() يجعل أي خاصية لاحقة غير موثوقة

    all_sentences: list[ExtractedSentence] = []
    pages_info: list[PageInfo] = []
    next_sentence_id = 0

    try:
        for page_index in range(total_pages):
            page = doc[page_index]
            page_number = page_index + 1  # نرقم من 1 لا من 0 (أوضح للمستخدم النهائي)

            pages_info.append(
                PageInfo(
                    page_number=page_number,
                    width=page.rect.width,
                    height=page.rect.height,
                )
            )

            words_with_bbox = _extract_words_from_page(page)
            page_sentences, next_sentence_id = _segment_into_sentences(
                words_with_bbox, page_number, next_sentence_id
            )
            all_sentences.extend(page_sentences)
    finally:
        doc.close()  # دائماً نغلق المستند حتى لو حدث خطأ، لتجنب تسريب file handles

    return ExtractedDocument(
        total_pages=total_pages,
        pages=pages_info,
        sentences=all_sentences,
    )
