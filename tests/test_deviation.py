import math

import pytest

from rowlytics_app.cv.deviation import SkeletalDeviationCalculator


def make_point(name, x, y, time=0.0):
    return {
        "name": name,
        "time": time,
        "x": x,
        "y": y
    }


@pytest.fixture
def calculator():
    return SkeletalDeviationCalculator()


def make_full_pose(include_centers=False):
    pose = [
        make_point("left_hand", -3, 2),
        make_point("left_elbow", -2, 1),
        make_point("left_shoulder", -1, 2),

        make_point("right_hand", 3, 2),
        make_point("right_elbow", 2, 1),
        make_point("right_shoulder", 1, 2),

        make_point("left_foot", -1, -2),
        make_point("left_knee", -1, -1),
        make_point("left_hip", -1, 0),

        make_point("right_foot", 1, -2),
        make_point("right_knee", 1, -1),
        make_point("right_hip", 1, 0),
    ]

    if include_centers:
        pose.extend([
            make_point("hip_center", 0, 0),
            make_point("shoulder_center", 0, 2),
        ])

    return pose


def test_validate_point_rejects_non_dict(calculator):
    with pytest.raises(ValueError, match="Point must be a dictionary"):
        calculator._validate_point("not a dict")


def test_validate_point_rejects_missing_keys(calculator):
    with pytest.raises(ValueError, match="Point must contain 'x' and 'y'"):
        calculator._validate_point({"x": 1})


def test_validate_point_rejects_non_numeric_coordinates(calculator):
    with pytest.raises(ValueError, match="'x' and 'y' must be numeric"):
        calculator._validate_point({"x": "a", "y": 2})


def test_vector_returns_expected_result(calculator):
    p1 = make_point("a", 1, 2)
    p2 = make_point("b", 4, 6)

    assert calculator._vector(p1, p2) == (3, 4)


def test_magnitude_returns_expected_value(calculator):
    assert calculator._magnitude((3, 4)) == 5


def test_angle_between_vectors_returns_90_degrees(calculator):
    angle = calculator._angle_between_vectors((1, 0), (0, 1))
    assert angle == pytest.approx(90.0)


def test_angle_between_vectors_raises_for_zero_length_vector(calculator):
    with pytest.raises(ValueError, match="Cannot calculate angle with a zero-length segment"):
        calculator._angle_between_vectors((0, 0), (1, 0))


def test_joint_angle_returns_90_degrees(calculator):
    point_a = make_point("hand", 2, 1)
    joint = make_point("elbow", 1, 1)
    point_c = make_point("shoulder", 1, 2)

    angle = calculator._joint_angle(point_a, joint, point_c)
    assert angle == pytest.approx(90.0)


def test_segment_orientation_returns_expected_angle(calculator):
    start = make_point("hip", 0, 0)
    end = make_point("shoulder", 0, 5)

    angle = calculator._segment_orientation(start, end)
    assert angle == pytest.approx(90.0)


def test_angle_difference_handles_wraparound(calculator):
    diff = calculator._angle_difference(350, 10)
    assert diff == pytest.approx(20.0)


def test_arm_angle_deviation_zero_for_identical_models(calculator):
    user_hand = make_point("left_hand", 2, 1)
    user_elbow = make_point("left_elbow", 1, 1)
    user_shoulder = make_point("left_shoulder", 1, 2)

    ideal_hand = make_point("left_hand", 2, 1)
    ideal_elbow = make_point("left_elbow", 1, 1)
    ideal_shoulder = make_point("left_shoulder", 1, 2)

    result = calculator.arm_angle_deviation(
        user_hand, user_elbow, user_shoulder,
        ideal_hand, ideal_elbow, ideal_shoulder
    )

    assert result["user_angle"] == pytest.approx(90.0)
    assert result["ideal_angle"] == pytest.approx(90.0)
    assert result["deviation"] == pytest.approx(0.0)


def test_arm_angle_deviation_detects_difference(calculator):
    # User arm is straight: 180 degrees
    user_hand = make_point("left_hand", 2, 0)
    user_elbow = make_point("left_elbow", 1, 0)
    user_shoulder = make_point("left_shoulder", 0, 0)

    # Ideal arm is bent: 90 degrees
    ideal_hand = make_point("left_hand", 2, 1)
    ideal_elbow = make_point("left_elbow", 1, 1)
    ideal_shoulder = make_point("left_shoulder", 1, 2)

    result = calculator.arm_angle_deviation(
        user_hand, user_elbow, user_shoulder,
        ideal_hand, ideal_elbow, ideal_shoulder
    )

    assert result["user_angle"] == pytest.approx(180.0)
    assert result["ideal_angle"] == pytest.approx(90.0)
    assert result["deviation"] == pytest.approx(90.0)


def test_leg_angle_deviation_zero_for_identical_models(calculator):
    user_foot = make_point("left_foot", 0, -2)
    user_knee = make_point("left_knee", 0, -1)
    user_hip = make_point("left_hip", 0, 0)

    ideal_foot = make_point("left_foot", 0, -2)
    ideal_knee = make_point("left_knee", 0, -1)
    ideal_hip = make_point("left_hip", 0, 0)

    result = calculator.leg_angle_deviation(
        user_foot, user_knee, user_hip,
        ideal_foot, ideal_knee, ideal_hip
    )

    assert result["user_angle"] == pytest.approx(180.0)
    assert result["ideal_angle"] == pytest.approx(180.0)
    assert result["deviation"] == pytest.approx(0.0)


def test_torso_angle_deviation_zero_for_identical_models(calculator):
    user_hip = make_point("hip", 0, 0)
    user_shoulder = make_point("shoulder", 0, 3)

    ideal_hip = make_point("hip", 0, 0)
    ideal_shoulder = make_point("shoulder", 0, 3)

    result = calculator.torso_angle_deviation(
        user_hip, user_shoulder,
        ideal_hip, ideal_shoulder
    )

    assert result["user_angle"] == pytest.approx(90.0)
    assert result["ideal_angle"] == pytest.approx(90.0)
    assert result["deviation"] == pytest.approx(0.0)


def test_torso_angle_deviation_handles_wraparound(calculator):
    theta1 = math.radians(10)
    theta2 = math.radians(-10)

    ideal_hip = make_point("hip", 0, 0)
    ideal_shoulder = make_point("shoulder", math.cos(theta1), math.sin(theta1))

    user_hip = make_point("hip", 0, 0)
    user_shoulder = make_point("shoulder", math.cos(theta2), math.sin(theta2))

    result = calculator.torso_angle_deviation(
        user_hip, user_shoulder,
        ideal_hip, ideal_shoulder
    )

    assert result["deviation"] == pytest.approx(20.0)


def test_build_name_map_rejects_empty_list(calculator):
    with pytest.raises(ValueError, match="coordinates must be a non-empty list"):
        calculator._build_name_map([])


def test_build_name_map_rejects_missing_name(calculator):
    with pytest.raises(ValueError, match="Each coordinate must contain 'name'"):
        calculator._build_name_map([{"x": 1, "y": 2}])


def test_midpoint_returns_expected_point(calculator):
    p1 = make_point("p1", 0, 0)
    p2 = make_point("p2", 4, 6)

    midpoint = calculator._midpoint(p1, p2, name="center")

    assert midpoint["name"] == "center"
    assert midpoint["x"] == pytest.approx(2.0)
    assert midpoint["y"] == pytest.approx(3.0)


def test_compare_pose_returns_all_regions(calculator):
    user_model = make_full_pose()
    ideal_model = make_full_pose()

    result = calculator.compare_pose(user_model, ideal_model)

    assert set(result.keys()) == {
        "left_arm",
        "right_arm",
        "left_leg",
        "right_leg",
        "torso"
    }

    for body_region in result.values():
        assert "user_angle" in body_region
        assert "ideal_angle" in body_region
        assert "deviation" in body_region


def test_compare_pose_identical_models_have_zero_deviation(calculator):
    user_model = make_full_pose()
    ideal_model = make_full_pose()

    result = calculator.compare_pose(user_model, ideal_model)

    assert result["left_arm"]["deviation"] == pytest.approx(0.0)
    assert result["right_arm"]["deviation"] == pytest.approx(0.0)
    assert result["left_leg"]["deviation"] == pytest.approx(0.0)
    assert result["right_leg"]["deviation"] == pytest.approx(0.0)
    assert result["torso"]["deviation"] == pytest.approx(0.0)


def test_compare_pose_uses_midpoints_when_centers_are_missing(calculator):
    user_model = make_full_pose(include_centers=False)
    ideal_model = make_full_pose(include_centers=False)

    result = calculator.compare_pose(user_model, ideal_model)

    # Midpoint between hips is (0,0), midpoint between shoulders is (0,2)
    # So torso should be vertical for both models.
    assert result["torso"]["user_angle"] == pytest.approx(90.0)
    assert result["torso"]["ideal_angle"] == pytest.approx(90.0)
    assert result["torso"]["deviation"] == pytest.approx(0.0)


def test_compare_pose_uses_explicit_centers_when_present(calculator):
    user_model = make_full_pose(include_centers=True)
    ideal_model = make_full_pose(include_centers=True)

    # Change only explicit center points to force a torso difference
    # while leaving left/right shoulders and hips unchanged.
    for point in user_model:
        if point["name"] == "hip_center":
            point["x"] = 0
            point["y"] = 0
        elif point["name"] == "shoulder_center":
            point["x"] = 1
            point["y"] = 0  # horizontal torso => 0 degrees

    for point in ideal_model:
        if point["name"] == "hip_center":
            point["x"] = 0
            point["y"] = 0
        elif point["name"] == "shoulder_center":
            point["x"] = 0
            point["y"] = 1  # vertical torso => 90 degrees

    result = calculator.compare_pose(user_model, ideal_model)

    assert result["torso"]["user_angle"] == pytest.approx(0.0)
    assert result["torso"]["ideal_angle"] == pytest.approx(90.0)
    assert result["torso"]["deviation"] == pytest.approx(90.0)


def test_compare_pose_raises_keyerror_when_required_body_part_is_missing(calculator):
    user_model = make_full_pose()
    ideal_model = make_full_pose()

    user_model = [p for p in user_model if p["name"] != "left_hand"]

    with pytest.raises(KeyError):
        calculator.compare_pose(user_model, ideal_model)


def test_arm_angle_deviation_raises_for_zero_length_segment(calculator):
    # hand and elbow are the same point
    user_hand = make_point("left_hand", 1, 1)
    user_elbow = make_point("left_elbow", 1, 1)
    user_shoulder = make_point("left_shoulder", 1, 2)

    ideal_hand = make_point("left_hand", 2, 1)
    ideal_elbow = make_point("left_elbow", 1, 1)
    ideal_shoulder = make_point("left_shoulder", 1, 2)

    with pytest.raises(ValueError, match="Cannot calculate angle with a zero-length segment"):
        calculator.arm_angle_deviation(
            user_hand, user_elbow, user_shoulder,
            ideal_hand, ideal_elbow, ideal_shoulder
        )
