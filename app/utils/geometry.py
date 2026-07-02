"""
geometry.py — الدوال الرياضية المساعدة لطبقة الرسم.

مبدأ الفصل: كل ما يتعلق بحسابات الإحداثيات والعشوائية المحكومة يعيش هنا،
بعيداً عن كود PyMuPDF في pdf_drawer.py. هذا يسمح باختبار المنطق الرياضي
في test_geometry.py بدون أي اعتماد على PyMuPDF أو ملفات PDF فعلية.
"""

import math
import random
from typing import NamedTuple


class Point(NamedTuple):
    x: float
    y: float


class BezierSegment(NamedTuple):
    """نقطة بداية، نقطتا تحكم، نقطة نهاية — بنية curve مكعبة (cubic Bézier)."""
    p0: Point
    p1: Point  # نقطة تحكم 1
    p2: Point  # نقطة تحكم 2
    p3: Point


def wavy_underline_segments(
    x0: float,
    y: float,
    x1: float,
    *,
    amplitude: float = 1.2,
    segments: int = 6,
    seed: int | None = None,
) -> list[BezierSegment]:
    """
    يولّد قائمة من منحنيات Bézier تُشكّل مجتمعةً خطاً متعرجاً يحاكي خط اليد.

    المنطق:
    - نقسّم المسافة الأفقية [x0, x1] إلى N قطع متساوية.
    - لكل قطعة، نضع نقطتي تحكم Bézier بانحراف رأسي عشوائي محكوم بـ amplitude.
    - seed اختيارية: تجعل التعرج حتمياً (مفيد للاختبار)، بدونها كل رسم مختلف.

    الفرق عن draw_line بسيطة: draw_line يرسم مستقيماً تماماً (يبدو طابعة).
    Bézier متعدد القطع يعطي نفس التموج الطبيعي لخط يد بشرية مُرتجف قليلاً.
    """
    rng = random.Random(seed)
    step = (x1 - x0) / segments
    result: list[BezierSegment] = []

    for i in range(segments):
        seg_x0 = x0 + i * step
        seg_x1 = seg_x0 + step

        # نقطتا التحكم مزاحتان رأسياً بشكل عشوائي وبتوقيع متعاكس
        # لخلق تموج طبيعي (تارة فوق الخط، تارة تحته)
        dy1 = rng.uniform(-amplitude, amplitude)
        dy2 = rng.uniform(-amplitude, amplitude)

        p0 = Point(seg_x0, y)
        p1 = Point(seg_x0 + step * 0.33, y + dy1)
        p2 = Point(seg_x0 + step * 0.66, y + dy2)
        p3 = Point(seg_x1, y)

        result.append(BezierSegment(p0, p1, p2, p3))

    return result


def oval_control_points(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    padding: float = 3.0,
    jitter: float = 1.5,
    seed: int | None = None,
) -> list[BezierSegment]:
    """
    يولّد 4 منحنيات Bézier تُرسم معاً كشكل بيضاوي (oval) غير منتظم قليلاً
    يحاكي دائرة رُسمت باليد حول كلمة.

    المنطق:
    - المستطيل الأصلي (bbox الكلمة) + padding للتباعد عن النص.
    - 4 منحنيات: يمين، أسفل، يسار، أعلى (عكس عقارب الساعة).
    - نقاط التحكم مزاحة بـ jitter عشوائي لكسر الانتظام الهندسي الصارم.

    نستخدم تقريب κ = 0.5523 (ثابت رياضي لمحاكاة الدائرة بـ Bézier) كنقطة
    بداية، ثم نضيف jitter فوقه لإضفاء طابع يدوي.
    """
    rng = random.Random(seed)

    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    rx = (x1 - x0) / 2 + padding
    ry = (y1 - y0) / 2 + padding

    # κ: Magic number لتقريب دائرة بأربعة منحنيات Bézier مكعبة
    # (أفضل تقريب ممكن بدون بنى أكثر تعقيداً)
    k = 0.5523

    def j() -> float:
        return rng.uniform(-jitter, jitter)

    # 4 نقاط على محيط القطع (top, right, bottom, left)
    top    = Point(cx, cy - ry)
    right  = Point(cx + rx, cy)
    bottom = Point(cx, cy + ry)
    left   = Point(cx - rx, cy)

    segments = [
        # من top → right
        BezierSegment(
            top,
            Point(cx + rx * k + j(), cy - ry + j()),
            Point(cx + rx + j(), cy - ry * k + j()),
            right,
        ),
        # من right → bottom
        BezierSegment(
            right,
            Point(cx + rx + j(), cy + ry * k + j()),
            Point(cx + rx * k + j(), cy + ry + j()),
            bottom,
        ),
        # من bottom → left
        BezierSegment(
            bottom,
            Point(cx - rx * k + j(), cy + ry + j()),
            Point(cx - rx + j(), cy + ry * k + j()),
            left,
        ),
        # من left → top (إغلاق الشكل)
        BezierSegment(
            left,
            Point(cx - rx + j(), cy - ry * k + j()),
            Point(cx - rx * k + j(), cy - ry + j()),
            top,
        ),
    ]

    return segments


def margin_note_position(
    anchor_y: float,
    page_width: float,
    page_height: float,
    side: str = "right",
    *,
    margin_width: float = 60.0,
) -> Point:
    """
    يحسب إحداثيات موضع الملاحظة الهامشية.

    في نظام PDF (الأصل أعلى-يسار):
    - الهامش الأيمن: x بالقرب من 0 (لأن PDF العربي يضع النص الأساسي من اليمين)
    - الهامش الأيسر: x بالقرب من page_width

    anchor_y يُحدد مستوى الارتفاع (يتوافق مع y0 الجملة المرجعية).
    نضيف تعديلاً طفيفاً للتأكد من عدم تجاوز حدود الصفحة.
    """
    y = min(max(anchor_y, 10.0), page_height - 20.0)

    if side == "right":
        x = margin_width * 0.3  # قريب من الحافة اليمنى
    else:
        x = page_width - margin_width * 0.3  # قريب من الحافة اليسرى

    return Point(x, y)
