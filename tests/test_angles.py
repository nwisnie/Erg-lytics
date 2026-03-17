from __future__ import annotations

import pytest

from rowlytics_app.cv.feature_extraction.angles import normalized_joint_angle


def make_point(x: float, y: float) -> dict[str, float]:
    return {"x": x, "y": y}


def test_normalized_joint_angle_returns_half_turn_for_right_angle() -> None:
    shoulder = make_point(1, 2)
    elbow = make_point(1, 1)
    wrist = make_point(2, 1)

    angle = normalized_joint_angle(shoulder, elbow, wrist)

    assert angle == pytest.approx(0.5)


def test_normalized_joint_angle_raises_for_zero_length_segment() -> None:
    shoulder = make_point(1, 1)
    elbow = make_point(1, 1)
    wrist = make_point(2, 1)

    with pytest.raises(ValueError, match="zero-length segment"):
        normalized_joint_angle(shoulder, elbow, wrist)
