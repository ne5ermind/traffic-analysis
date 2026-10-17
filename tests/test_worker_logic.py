import math

import pytest

from app.worker import clean_detection


def test_clean_detection_clips_boxes_and_accepts_bicycles():
    assert clean_detection(7, 1, [-5, 3, 120, 90], 1.2, 100, 80) == (
        7, 1, (0.0, 3.0, 100.0, 80.0), 1.0,
    )


@pytest.mark.parametrize("values", [
    (-1, 2, [0, 0, 10, 10], 0.8),
    (1.5, 2, [0, 0, 10, 10], 0.8),
    (1, 2.5, [0, 0, 10, 10], 0.8),
    (1, 4, [0, 0, 10, 10], 0.8),
    (1, 2, [5, 0, 5, 10], 0.8),
    (1, 2, [0, 0, math.inf, 10], 0.8),
    (1, 2, [0, 0, 10, 10], math.nan),
])
def test_clean_detection_rejects_invalid_tracker_rows(values):
    assert clean_detection(*values, width=100, height=80) is None
