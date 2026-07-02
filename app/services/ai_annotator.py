"""
AI Decision Layer — يستخدم Gemini 1.5 Flash (مجاني) بدل Anthropic.

لماذا Gemini 1.5 Flash؟
  - مجاني ضمن حدود يومية معقولة (15 طلب/دقيقة، 1500 طلب/يوم)
  - يدعم JSON mode مدمجاً: response_mime_type="application/json"
  - جيد جداً في فهم العربية وتحليل النصوص

الفرق المعماري عن Anthropic:
  - Anthropic: Tool Use (الموديل يستدعي "أداة" بـ schema صارم على مستوى API)
  - Gemini: JSON Mode (نطلب JSON + schema في الـ prompt، الموديل يلتزم بالشكل)
  - النتيجة العملية متشابهة — كلاهما يضمن JSON منظم.
  - _validate_annotation_plan() لم تتغير لأنها مستقلة عن المزود.

مبدأ ثابت من النسخة السابقة: لا نثق بمخرجات الـ AI افتراضياً.
كل مرجع (sentence_id, word_index) يُتحقق منه مقابل ExtractedDocument الحقيقي.
"""

import json
import logging

import google.generativeai as genai

from app.config import settings
from app.models.schemas import (
    AnnotationPlan,
    CircleAnnotation,
    ExtractedDocument,
    MarginNoteAnnotation,
    UnderlineAnnotation,
)

logger = logging.getLogger(__name__)

# تهيئة العميل مرة واحدة عند تحميل الـ module (singleton)
genai.configure(api_key=settings.GEMINI_API_KEY)
_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",  # يفرض JSON output صارم
        temperature=0.3,   # منخفض: نريد قرارات متسقة لا إبداعاً
        max_output_tokens=4096,
    ),
)

_SYSTEM_PROMPT = """\
أنت مساعد متخصص في تحليل النصوص العربية الأكاديمية والمهنية.
مهمتك: قراءة الجمل المرقّمة وإنتاج خطة تعليق تحاكي مراجع يقرأ بقلم أحمر.

اختر بعناية وبشكل مقتصد:
1. underlines: الجمل الأهم فكرياً (تعريفات، نتائج، أفكار محورية)
2. circles: كلمات مفتاحية مفردة فقط (مصطلحات تقنية، أرقام مهمة)
3. margin_notes: تعليقات قصيرة بالعربية تلخص أو تتساءل

قواعد صارمة:
- استخدم sentence_id و word_index كما وردا بالضبط — لا تخترع أرقاماً
- word_index يبدأ من 0
- لا تُسطّر أكثر من 30% من الجمل
- كل margin_note يجب ألا يتجاوز 8 كلمات

أرجع JSON فقط بهذا الشكل بالضبط:
{
  "underlines": [
    {"sentence_id": <int>, "reason": "<سبب قصير>"}
  ],
  "circles": [
    {"sentence_id": <int>, "word_index": <int>, "reason": "<سبب>"}
  ],
  "margin_notes": [
    {"anchor_sentence_id": <int>, "note_text": "<نص عربي>", "side": "right"}
  ]
}
"""


def _build_document_summary(document: ExtractedDocument) -> str:
    """
    يحوّل ExtractedDocument إلى نص للـ prompt.
    نرسل: رقم الجملة + النص + فهرس كل كلمة.
    فهرس الكلمات ضروري هنا (بخلاف Anthropic) لأن Gemini لا يعرف
    word_index تلقائياً — يحتاج يراه صريحاً في الـ prompt ليُشير إليه بدقة.
    """
    lines = []
    for s in document.sentences:
        words_indexed = " ".join(f"[{i}]{w.text}" for i, w in enumerate(s.words))
        lines.append(f"جملة {s.sentence_id}: {s.text}")
        lines.append(f"  الكلمات: {words_indexed}")
    return "\n".join(lines)


def _validate_annotation_plan(
    raw: dict, document: ExtractedDocument
) -> AnnotationPlan:
    """
    يتحقق من كل مرجع في خطة الـ AI مقابل المستند الحقيقي.
    يتجاهل (silent drop) أي عنصر غير صالح بدل إسقاط الخطة كاملاً.
    هذا المنطق مستقل عن مزود الـ AI — لم يتغير عن نسخة Anthropic.
    """
    sentences_by_id = {s.sentence_id: s for s in document.sentences}

    valid_underlines: list[UnderlineAnnotation] = []
    for item in raw.get("underlines", []):
        sid = item.get("sentence_id")
        if sid in sentences_by_id:
            valid_underlines.append(UnderlineAnnotation(**item))
        else:
            logger.warning("underline مرفوض: sentence_id=%s غير موجود", sid)

    valid_circles: list[CircleAnnotation] = []
    for item in raw.get("circles", []):
        sid  = item.get("sentence_id")
        widx = item.get("word_index")
        sentence = sentences_by_id.get(sid)
        if sentence is not None and isinstance(widx, int) and 0 <= widx < len(sentence.words):
            valid_circles.append(CircleAnnotation(**item))
        else:
            logger.warning("circle مرفوض: sentence_id=%s word_index=%s", sid, widx)

    valid_margin_notes: list[MarginNoteAnnotation] = []
    for item in raw.get("margin_notes", []):
        sid = item.get("anchor_sentence_id")
        if sid in sentences_by_id and item.get("note_text", "").strip():
            # side افتراضي "right" لو الموديل نسيه
            item.setdefault("side", "right")
            valid_margin_notes.append(MarginNoteAnnotation(**item))
        else:
            logger.warning("margin_note مرفوض: anchor_sentence_id=%s", sid)

    logger.info(
        "التحقق اكتمل | تسطيرات: %d | دوائر: %d | هوامش: %d",
        len(valid_underlines), len(valid_circles), len(valid_margin_notes),
    )

    return AnnotationPlan(
        underlines=valid_underlines,
        circles=valid_circles,
        margin_notes=valid_margin_notes,
    )


def generate_annotation_plan(document: ExtractedDocument) -> AnnotationPlan:
    """
    نقطة الدخول الرئيسية.
    ترسل محتوى المستند لـ Gemini 1.5 Flash وترجع AnnotationPlan موثوقاً.
    """
    doc_summary = _build_document_summary(document)
    prompt = f"{_SYSTEM_PROMPT}\n\n---\n{doc_summary}"

    logger.info("إرسال %d جملة لـ Gemini", len(document.sentences))

    response = _model.generate_content(prompt)

    # Gemini مع JSON mode يرجع النص كـ JSON نظيف بدون markdown fences
    # لكن نضيف strip() دفاعاً لو جاء بمسافات زائدة
    raw_text = response.text.strip()

    try:
        raw_plan = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Gemini أرجع JSON غير صالح: %s\nالنص: %s", exc, raw_text[:200])
        raise RuntimeError(f"Gemini أرجع JSON غير صالح: {exc}") from exc

    return _validate_annotation_plan(raw_plan, document)
