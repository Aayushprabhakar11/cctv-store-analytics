# PROMPT: Unit tests for bbox zone classification per camera role.
# CHANGES MADE: Added billing and staff heuristic smoke test.

import numpy as np
import pytest

from pipeline.zone_rules import ZoneClassifier


@pytest.mark.parametrize(
    "camera, cx_norm, cy_norm, expected",
    [
        ("CAM_ENTRY_01", 0.5, 0.70, "ENTRY_THRESHOLD"),
        ("CAM_BILLING_01", 0.40, 0.50, "BILLING"),
        ("CAM_MAIN_01", 0.20, 0.25, "SKINCARE"),
        ("CAM_MAIN_01", 0.70, 0.75, "MAKEUP"),
    ],
)
def test_classify_bbox(camera, cx_norm, cy_norm, expected):
    clf = ZoneClassifier(camera)
    w, h = 640, 480
    x1 = cx_norm * w - 10
    x2 = cx_norm * w + 10
    y1 = cy_norm * h - 10
    y2 = cy_norm * h + 10
    zone = clf.classify_bbox(x1, y1, x2, y2, (h, w, 3))
    assert zone == expected


def test_staff_heuristic_on_blank_frame():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert ZoneClassifier.staff_heuristic(frame, (10, 10, 50, 50)) is False
