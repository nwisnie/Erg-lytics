import pytest

from rowlytics_app.cv.alignment import PracticeStrokeAssembler


@pytest.fixture
def assembler():
    return PracticeStrokeAssembler()


# __init__
def test_init_sets_default_values(assembler):
    assert assembler.coordinates == []
    assert assembler.finished is False


# assemble_practice_strokes
def test_assemble_practice_strokes_adds_valid_coordinate(assembler):
    data = {
        "name": "wrist",
        "time": 1.2,
        "x": 100,
        "y": 200,
    }

    result = assembler.assemble_practice_strokes(data)

    assert result is None
    assert len(assembler.coordinates) == 1
    assert assembler.coordinates[0] == {
        "name": "wrist",
        "time": 1.2,
        "x": 100,
        "y": 200,
    }
    assert assembler.finished is False


def test_assemble_practice_strokes_returns_coordinates_when_finished(assembler):
    assembler.assemble_practice_strokes({
        "name": "elbow",
        "time": 0.5,
        "x": 50,
        "y": 75,
    })

    result = assembler.assemble_practice_strokes("finished")

    assert assembler.finished is True
    assert result == [
        {"name": "elbow", "time": 0.5, "x": 50, "y": 75}
    ]


def test_assemble_practice_strokes_raises_error_for_non_dict_input(assembler):
    with pytest.raises(ValueError, match="Invalid coordinate format"):
        assembler.assemble_practice_strokes(["not", "a", "dict"])


def test_assemble_practice_strokes_raises_error_for_missing_keys(assembler):
    bad_data = {
        "name": "knee",
        "time": 1.0,
        "x": 10,
        # missing y
    }

    with pytest.raises(ValueError, match="Invalid coordinate format"):
        assembler.assemble_practice_strokes(bad_data)


# assemble_progression_steps
def test_assemble_progression_steps_raises_error_for_invalid_coordinates_type(assembler):
    with pytest.raises(ValueError, match="coordinates must be a list with at least two entries"):
        assembler.assemble_progression_steps("not a list", 0.25)


def test_assemble_progression_steps_raises_error_for_too_few_coordinates(assembler):
    coords = [{"name": "wrist", "time": 0.0, "x": 0, "y": 0}]

    with pytest.raises(ValueError, match="coordinates must be a list with at least two entries"):
        assembler.assemble_progression_steps(coords, 0.25)


def test_assemble_progression_steps_raises_error_for_non_numeric_interval(assembler):
    coords = [
        {"name": "wrist", "time": 0.0, "x": 0, "y": 0},
        {"name": "wrist", "time": 1.0, "x": 10, "y": 5},
    ]

    with pytest.raises(ValueError, match="progression_interval must be a number"):
        assembler.assemble_progression_steps(coords, "0.25")


def test_assemble_progression_steps_raises_error_for_interval_too_small(assembler):
    coords = [
        {"name": "wrist", "time": 0.0, "x": 0, "y": 0},
        {"name": "wrist", "time": 1.0, "x": 10, "y": 5},
    ]

    with pytest.raises(ValueError, match="progression_interval must be between 0.01 and 0.5"):
        assembler.assemble_progression_steps(coords, 0.001)


def test_assemble_progression_steps_raises_error_for_interval_too_large(assembler):
    coords = [
        {"name": "wrist", "time": 0.0, "x": 0, "y": 0},
        {"name": "wrist", "time": 1.0, "x": 10, "y": 5},
    ]

    with pytest.raises(ValueError, match="progression_interval must be between 0.01 and 0.5"):
        assembler.assemble_progression_steps(coords, 0.75)


def test_assemble_progression_steps_returns_single_step_when_all_x_are_same(assembler):
    coords = [
        {"name": "wrist", "time": 0.0, "x": 5, "y": 10},
        {"name": "wrist", "time": 1.0, "x": 5, "y": 20},
    ]

    result = assembler.assemble_progression_steps(coords, 0.25)

    assert len(result) == 1
    assert result[0]["progression_step"] == 0.0
    assert result[0]["x"] == 5
    assert result[0]["y"] == 10


def test_assemble_progression_steps_generates_expected_steps(assembler):
    coords = [
        {"name": "wrist", "time": 0.0, "x": 0, "y": 0},
        {"name": "wrist", "time": 1.0, "x": 10, "y": 5},
        {"name": "wrist", "time": 2.0, "x": 20, "y": 10},
        {"name": "wrist", "time": 3.0, "x": 30, "y": 15},
        {"name": "wrist", "time": 4.0, "x": 40, "y": 20},
    ]

    result = assembler.assemble_progression_steps(coords, 0.25)

    assert len(result) == 5
    assert [item["progression_step"] for item in result] == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert result[0]["x"] == 0
    assert result[-1]["x"] == 40


def test_assemble_progression_steps_forces_final_progression_step_to_one(assembler):
    coords = [
        {"name": "wrist", "time": 0.0, "x": 0, "y": 0},
        {"name": "wrist", "time": 1.0, "x": 10, "y": 10},
        {"name": "wrist", "time": 2.0, "x": 20, "y": 20},
        {"name": "wrist", "time": 3.0, "x": 30, "y": 30},
    ]

    result = assembler.assemble_progression_steps(coords, 0.3)

    assert result[-1]["progression_step"] == 1.0


# match_progression_interval
def test_match_progression_interval_raises_error_for_empty_progression_intervals(assembler):
    coordinate_list = [{"name": "wrist", "time": 1.0, "x": 9, "y": 20}]

    with pytest.raises(ValueError, match="progression_intervals must be a non-empty list"):
        assembler.match_progression_interval([], coordinate_list)


def test_match_progression_interval_raises_error_for_empty_coordinate_list(assembler):
    progression_intervals = [{"name": "wrist", "progression_step": 0.5, "x": 10, "y": 20}]

    with pytest.raises(ValueError, match="coordinate_list must be a non-empty list"):
        assembler.match_progression_interval(progression_intervals, [])


def test_match_progression_interval_raises_error_when_name_not_found(assembler):
    progression_intervals = [
        {"name": "wrist", "progression_step": 0.0, "x": 0, "y": 0},
        {"name": "wrist", "progression_step": 1.0, "x": 10, "y": 10},
    ]
    coordinate_list = [
        {"name": "elbow", "time": 2.0, "x": 9, "y": 5}
    ]

    with pytest.raises(ValueError, match="No matching body part 'wrist' found in coordinate_list"):
        assembler.match_progression_interval(progression_intervals, coordinate_list)


def test_match_progression_interval_returns_closest_progression_step(assembler):
    progression_intervals = [
        {"name": "wrist", "time": 0.0, "progression_step": 0.0, "x": 0, "y": 0},
        {"name": "wrist", "time": 1.0, "progression_step": 0.5, "x": 10, "y": 10},
        {"name": "wrist", "time": 2.0, "progression_step": 1.0, "x": 20, "y": 20},
    ]
    coordinate_list = [
        {"name": "wrist", "time": 7.5, "x": 11, "y": 13},
        {"name": "elbow", "time": 7.5, "x": 30, "y": 40},
    ]

    result = assembler.match_progression_interval(progression_intervals, coordinate_list)

    assert result["name"] == "wrist"
    assert result["time"] == 7.5
    assert result["progression_step"] == 0.5


# get_ideal_coordinate_set
def test_get_ideal_coordinate_set_raises_error_for_non_dict_progression_step(assembler):
    with pytest.raises(ValueError, match="current_progression_step must be a dictionary"):
        assembler.get_ideal_coordinate_set("not a dict", [])


def test_get_ideal_coordinate_set_raises_error_when_progression_step_missing(assembler):
    current_progression_step = {"time": 1.0}

    with pytest.raises(ValueError,
                       match="current_progression_step must contain 'progression_step'"):
        assembler.get_ideal_coordinate_set(
            current_progression_step,
            [{"name": "wrist", "progression_step": 0.0, "x": 0, "y": 0}],
        )


def test_get_ideal_coordinate_set_raises_error_when_time_missing(assembler):
    current_progression_step = {"progression_step": 0.5}

    with pytest.raises(ValueError, match="current_progression_step must contain 'time'"):
        assembler.get_ideal_coordinate_set(
            current_progression_step,
            [{"name": "wrist", "progression_step": 0.0, "x": 0, "y": 0}],
        )


def test_get_ideal_coordinate_set_raises_error_for_empty_ideal_model(assembler):
    current_progression_step = {"progression_step": 0.5, "time": 3.0}

    with pytest.raises(ValueError, match="ideal_model must be a non-empty list"):
        assembler.get_ideal_coordinate_set(current_progression_step, [])


def test_get_ideal_coordinate_set_raises_error_when_no_progression_steps_exist(assembler):
    current_progression_step = {"progression_step": 0.5, "time": 3.0}
    ideal_model = [
        {"name": "wrist", "x": 10, "y": 20},
        {"name": "elbow", "x": 30, "y": 40},
    ]

    with pytest.raises(ValueError,
                       match="ideal_model does not contain any progression_step values"):
        assembler.get_ideal_coordinate_set(current_progression_step, ideal_model)


def test_get_ideal_coordinate_set_returns_unique_bodyparts_for_closest_step(assembler):
    current_progression_step = {"progression_step": 0.52, "time": 9.9}
    ideal_model = [
        {"name": "wrist", "progression_step": 0.5, "x": 10, "y": 20},
        {"name": "elbow", "progression_step": 0.5, "x": 30, "y": 40},
        {"name": "wrist", "progression_step": 0.5, "x": 999, "y": 999},  # duplicate name, ignored
        {"name": "knee", "progression_step": 1.0, "x": 50, "y": 60},
    ]

    result = assembler.get_ideal_coordinate_set(current_progression_step, ideal_model)

    assert len(result) == 2
    assert result[0]["name"] == "wrist"
    assert result[1]["name"] == "elbow"
    assert all(item["time"] == 9.9 for item in result)
    assert all(item["progression_step"] == 0.5 for item in result)
    assert result[0]["x"] == 10
    assert result[1]["x"] == 30
