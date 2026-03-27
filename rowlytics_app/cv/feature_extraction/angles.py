"""Reusable geometry helpers for pose-angle calculations."""

from __future__ import annotations

import math


def validate_point(point: dict) -> None:
    if not isinstance(point, dict):
        raise ValueError("Point must be a dictionary")

    required_keys = {"x", "y"}
    if not required_keys.issubset(point.keys()):
        raise ValueError("Point must contain 'x' and 'y'")

    if not isinstance(point["x"], (int, float)) or not isinstance(point["y"], (int, float)):
        raise ValueError("'x' and 'y' must be numeric")


def vector(point_a: dict, point_b: dict) -> tuple[float, float]:
    validate_point(point_a)
    validate_point(point_b)
    return (point_b["x"] - point_a["x"], point_b["y"] - point_a["y"])


def magnitude(vector_xy: tuple[float, float]) -> float:
    return math.hypot(vector_xy[0], vector_xy[1])


def angle_between_vectors(vector_a: tuple[float, float], vector_b: tuple[float, float]) -> float:
    magnitude_a = magnitude(vector_a)
    magnitude_b = magnitude(vector_b)

    if magnitude_a == 0 or magnitude_b == 0:
        raise ValueError("Cannot calculate angle with a zero-length segment")

    dot_product = (vector_a[0] * vector_b[0]) + (vector_a[1] * vector_b[1])
    cosine = dot_product / (magnitude_a * magnitude_b)
    cosine = max(-1.0, min(1.0, cosine))

    return math.degrees(math.acos(cosine))


def joint_angle(point_a: dict, joint_point: dict, point_c: dict) -> float:
    validate_point(point_a)
    validate_point(joint_point)
    validate_point(point_c)

    first_segment = vector(joint_point, point_a)
    second_segment = vector(joint_point, point_c)
    return angle_between_vectors(first_segment, second_segment)


def normalized_joint_angle(point_a: dict, joint_point: dict, point_c: dict) -> float:
    """Return the joint angle as a 0..1 fraction of a 180-degree bend."""
    return joint_angle(point_a, joint_point, point_c) / 180.0


def segment_orientation(start_point: dict, end_point: dict) -> float:
    validate_point(start_point)
    validate_point(end_point)

    delta_x = end_point["x"] - start_point["x"]
    delta_y = end_point["y"] - start_point["y"]

    if delta_x == 0 and delta_y == 0:
        raise ValueError("Cannot calculate orientation of a zero-length segment")

    if delta_x == 0:
        return 90.0 if delta_y > 0 else -90.0

    if delta_y == 0:
        return 0.0 if delta_x > 0 else 180.0

    return math.degrees(math.atan2(delta_y, delta_x))


def angle_difference(angle_a: float, angle_b: float) -> float:
    if math.isclose(abs(angle_a), 90.0, abs_tol=1e-9):
        angle_a = 90.0
    if math.isclose(abs(angle_b), 90.0, abs_tol=1e-9):
        angle_b = 90.0

    difference = abs(angle_a - angle_b) % 360
    return min(difference, 360 - difference)


def midpoint(point_a: dict, point_b: dict, name: str = "midpoint") -> dict:
    validate_point(point_a)
    validate_point(point_b)

    return {
        "name": name,
        "x": (point_a["x"] + point_b["x"]) / 2.0,
        "y": (point_a["y"] + point_b["y"]) / 2.0,
    }
