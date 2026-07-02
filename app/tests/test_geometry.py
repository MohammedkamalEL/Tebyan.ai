"""
اختبارات طبقة الهندسة (geometry.py).
هذه الاختبارات لا تحتاج PyMuPDF أو أي ملف PDF — رياضيات بحتة فقط.
شغّلها بـ: uv run pytest app/tests/test_geometry.py -v
"""

import pytest

from app.utils.geometry import (
    margin_note_position,
    oval_control_points,
    wavy_underline_segments,
)


class TestWavyUnderlineSegments:
    def test_returns_correct_segment_count(self):
        segs = wavy_underline_segments(0, 100, 200, segments=6)
        assert len(segs) == 6

    def test_segments_are_continuous(self):
        """نهاية كل قطعة = بداية التالية (خط متواصل)."""
        segs = wavy_underline_segments(0, 100, 300, segments=5, seed=42)
        for i in range(len(segs) - 1):
            assert segs[i].p3.x == pytest.approx(segs[i + 1].p0.x, abs=1e-6)
            assert segs[i].p3.y == pytest.approx(segs[i + 1].p0.y, abs=1e-6)

    def test_starts_at_x0_ends_at_x1(self):
        segs = wavy_underline_segments(50, 200, 350, segments=4, seed=7)
        assert segs[0].p0.x == pytest.approx(50.0)
        assert segs[-1].p3.x == pytest.approx(350.0)

    def test_y_stays_on_baseline(self):
        """نقاط بداية/نهاية كل قطعة على نفس y."""
        segs = wavy_underline_segments(0, 150, 400, segments=6, seed=99)
        for seg in segs:
            assert seg.p0.y == pytest.approx(150.0, abs=1e-6)
            assert seg.p3.y == pytest.approx(150.0, abs=1e-6)

    def test_same_seed_reproducible(self):
        s1 = wavy_underline_segments(0, 100, 200, seed=123)
        s2 = wavy_underline_segments(0, 100, 200, seed=123)
        assert s1 == s2

    def test_different_seeds_differ(self):
        s1 = wavy_underline_segments(0, 100, 200, seed=1)
        s2 = wavy_underline_segments(0, 100, 200, seed=2)
        assert any(a.p1 != b.p1 for a, b in zip(s1, s2))

    def test_control_points_within_amplitude(self):
        amplitude = 1.5
        segs = wavy_underline_segments(0, 100, 500, amplitude=amplitude, segments=10, seed=0)
        for seg in segs:
            assert abs(seg.p1.y - 100) <= amplitude + 1e-6
            assert abs(seg.p2.y - 100) <= amplitude + 1e-6


class TestOvalControlPoints:
    def test_returns_four_segments(self):
        segs = oval_control_points(10, 20, 80, 40)
        assert len(segs) == 4

    def test_oval_is_closed(self):
        segs = oval_control_points(10, 20, 80, 40, jitter=0, seed=0)
        assert segs[0].p0.x == pytest.approx(segs[-1].p3.x, abs=1e-4)
        assert segs[0].p0.y == pytest.approx(segs[-1].p3.y, abs=1e-4)

    def test_segments_are_continuous(self):
        segs = oval_control_points(0, 0, 60, 30, seed=5)
        for i in range(len(segs) - 1):
            assert segs[i].p3.x == pytest.approx(segs[i + 1].p0.x, abs=1e-6)
            assert segs[i].p3.y == pytest.approx(segs[i + 1].p0.y, abs=1e-6)

    def test_padding_expands_oval(self):
        segs_no_pad = oval_control_points(10, 10, 50, 30, padding=0, jitter=0, seed=0)
        segs_padded = oval_control_points(10, 10, 50, 30, padding=10, jitter=0, seed=0)
        max_x_no_pad = max(max(s.p0.x, s.p1.x, s.p2.x, s.p3.x) for s in segs_no_pad)
        max_x_padded = max(max(s.p0.x, s.p1.x, s.p2.x, s.p3.x) for s in segs_padded)
        assert max_x_padded > max_x_no_pad

    def test_same_seed_reproducible(self):
        s1 = oval_control_points(0, 0, 100, 50, seed=77)
        s2 = oval_control_points(0, 0, 100, 50, seed=77)
        assert s1 == s2


class TestMarginNotePosition:
    PAGE_W = 595.0
    PAGE_H = 842.0

    def test_right_margin_x_is_small(self):
        pos = margin_note_position(200, self.PAGE_W, self.PAGE_H, side="right")
        assert pos.x < self.PAGE_W / 2

    def test_left_margin_x_is_large(self):
        pos = margin_note_position(200, self.PAGE_W, self.PAGE_H, side="left")
        assert pos.x > self.PAGE_W / 2

    def test_y_stays_within_page(self):
        pos_top    = margin_note_position(0, self.PAGE_W, self.PAGE_H)
        pos_bottom = margin_note_position(self.PAGE_H, self.PAGE_W, self.PAGE_H)
        assert 0 <= pos_top.y <= self.PAGE_H
        assert 0 <= pos_bottom.y <= self.PAGE_H

    def test_y_tracks_anchor(self):
        pos_high = margin_note_position(100, self.PAGE_W, self.PAGE_H)
        pos_low  = margin_note_position(600, self.PAGE_W, self.PAGE_H)
        assert pos_high.y < pos_low.y
