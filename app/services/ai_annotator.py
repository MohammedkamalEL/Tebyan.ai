"""
AI Decision Layer — OpenRouter مع Gemini 2.0 Flash (مجاني).

لماذا OpenRouter؟
  - يدير quota موديلات متعددة تلقائياً
  - يستخدم OpenAI SDK interface (بسيط ومستقر)
  - موديلات مجانية أقوى وأكثر استقراراً من Groq Free Tier
  - nvidia/nemotron-3-ultra-550b-a55b:free نفسه لكن بدون quota يومي صارم

مبدأ ثابت: chunking للملفات الكبيرة + validation لكل مرجع.
"""

import json
import logging
import time

from openai import OpenAI

from app.config import settings
from app.models.schemas import (
    AnnotationPlan,
    CircleAnnotation,
    ExtractedDocument,
    ExtractedSentence,
    MarginNoteAnnotation,
    UnderlineAnnotation,
)

logger = logging.getLogger(__name__)

# OpenRouter يستخدم نفس OpenAI interface — فقط نغيّر base_url والـ key
_client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
CHUNK_SIZE  = 20   # جمل لكل chunk — توازن بين السرعة وحدود الـ tokens
CHUNK_DELAY = 3.0  # ثواني بين الـ chunks

_SYSTEM_PROMPT = """\
You are an expert Arabic text analyst. Analyze the numbered sentences and return annotation decisions \
that mimic a human reviewer reading with a red pen.

Choose SPARINGLY and carefully:
1. underlines: Most important sentences only (definitions, conclusions, key ideas). Max 30% of sentences.
2. circles: Single critical keywords only (technical terms, important numbers). Use rarely.
3. margin_notes: Short Arabic comments max 8 words, insightful and relevant.

STRICT RULES:
- Use sentence_id and word_index EXACTLY as provided — never invent numbers
- word_index starts at 0
- Return ONLY valid JSON, no markdown fences, no explanation

Required JSON format:
{
  "underlines": [{"sentence_id": <int>, "reason": "<brief reason in English>"}],
  "circles": [{"sentence_id": <int>, "word_index": <int>, "reason": "<brief reason>"}],
  "margin_notes": [{"anchor_sentence_id": <int>, "note_text": "<Arabic text max 8 words>", "side": "right"}]
}
"""


def _build_chunk_summary(sentences: list[ExtractedSentence]) -> str:
    lines = []
    for s in sentences:
        words_indexed = " ".join(f"[{i}]{w.text}" for i, w in enumerate(s.words))
        lines.append(f"Sentence {s.sentence_id}: {s.text}")
        lines.append(f"  Words: {words_indexed}")
    return "\n".join(lines)


def _call_openrouter(chunk_text: str) -> dict:
    """يرسل chunk واحد لـ OpenRouter ويرجع dict خام."""
    response = _client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Analyze these sentences:\n\n{chunk_text}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=2048,
    )
    raw = response.choices[0].message.content.strip()

    # نظّف markdown fences لو الموديل أضافها رغم الـ json_object mode
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def _validate_and_merge(
    chunks_results: list[dict],
    document: ExtractedDocument,
) -> AnnotationPlan:
    """يدمج نتائج كل الـ chunks ويتحقق من صحة كل مرجع."""
    sentences_by_id = {s.sentence_id: s for s in document.sentences}

    valid_underlines:   list[UnderlineAnnotation]   = []
    valid_circles:      list[CircleAnnotation]       = []
    valid_margin_notes: list[MarginNoteAnnotation]   = []

    for raw in chunks_results:
        for item in raw.get("underlines", []):
            sid = item.get("sentence_id")
            if sid in sentences_by_id:
                valid_underlines.append(UnderlineAnnotation(**item))
            else:
                logger.warning("underline مرفوض: sentence_id=%s", sid)

        for item in raw.get("circles", []):
            sid  = item.get("sentence_id")
            widx = item.get("word_index")
            sentence = sentences_by_id.get(sid)
            if sentence and isinstance(widx, int) and 0 <= widx < len(sentence.words):
                valid_circles.append(CircleAnnotation(**item))
            else:
                logger.warning("circle مرفوض: sentence_id=%s word_index=%s", sid, widx)

        for item in raw.get("margin_notes", []):
            sid = item.get("anchor_sentence_id")
            if sid in sentences_by_id and item.get("note_text", "").strip():
                item.setdefault("side", "right")
                valid_margin_notes.append(MarginNoteAnnotation(**item))
            else:
                logger.warning("margin_note مرفوض: anchor_sentence_id=%s", sid)

    logger.info(
        "✅ الدمج اكتمل | تسطيرات: %d | دوائر: %d | هوامش: %d",
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
    تقسّم الجمل إلى chunks وترسل كل chunk لـ OpenRouter مع تأخير بينها.
    """
    sentences  = document.sentences
    total      = len(sentences)
    chunks     = [sentences[i:i + CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]
    num_chunks = len(chunks)

    logger.info(
        "📄 %d جملة → %d chunk (كل chunk = %d جملة) | موديل: %s",
        total, num_chunks, CHUNK_SIZE, _MODEL,
    )

    results: list[dict] = []

    for idx, chunk in enumerate(chunks, start=1):
        logger.info("🔄 chunk %d/%d (%d جملة)...", idx, num_chunks, len(chunk))

        chunk_text = _build_chunk_summary(chunk)

        try:
            raw = _call_openrouter(chunk_text)
            results.append(raw)
            logger.info(
                "✅ chunk %d: تسطيرات=%d دوائر=%d هوامش=%d",
                idx,
                len(raw.get("underlines", [])),
                len(raw.get("circles", [])),
                len(raw.get("margin_notes", [])),
            )
        except json.JSONDecodeError as exc:
            logger.error("chunk %d: JSON خاطئ — %s", idx, exc)
            results.append({"underlines": [], "circles": [], "margin_notes": []})
        except Exception as exc:
            logger.error("chunk %d: خطأ — %s", idx, exc)
            results.append({"underlines": [], "circles": [], "margin_notes": []})

        if idx < num_chunks:
            logger.info("⏳ انتظار %.1f ثانية...", CHUNK_DELAY)
            time.sleep(CHUNK_DELAY)

    return _validate_and_merge(results, document)
