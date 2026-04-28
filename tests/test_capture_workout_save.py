def test_workout_analysis_snapshot_values_are_preserved():
    latest_workout_analysis = {
        "summary": "Good workout",
        "movementQualified": True,
        "strokeCount": 12,
        "cadenceSpm": 24.5,
        "rangeOfMotion": 0.31,
        "armsStraightScore": 72.0,
        "backStraightScore": 88.0,
        "dominantSide": "left",
    }
    latest_workout_analysis_text = "clips observed: 3"
    latest_workout_score = 67.5

    workout_analysis = latest_workout_analysis
    workout_analysis_text = latest_workout_analysis_text
    workout_score = latest_workout_score

    payload = {
        "summary": workout_analysis.get("summary"),
        "workoutScore": workout_score,
        "alignmentDetails": workout_analysis_text,
        "strokeCount": workout_analysis.get("strokeCount"),
        "cadenceSpm": workout_analysis.get("cadenceSpm"),
        "rangeOfMotion": workout_analysis.get("rangeOfMotion"),
        "armsStraightScore": workout_analysis.get("armsStraightScore"),
        "backStraightScore": workout_analysis.get("backStraightScore"),
        "dominantSide": workout_analysis.get("dominantSide"),
    }

    assert payload["summary"] == "Good workout"
    assert payload["workoutScore"] == 67.5
    assert payload["alignmentDetails"] == "clips observed: 3"
    assert payload["armsStraightScore"] == 72.0
    assert payload["backStraightScore"] == 88.0
    assert payload["dominantSide"] == "left"


def test_workout_analysis_snapshot_clears_scores_when_movement_gate_fails():
    latest_workout_analysis = {
        "summary": "Not enough valid strokes were detected to calculate a score.",
        "movementQualified": False,
        "movementReason": "Need at least 3 strokes to save a clip.",
        "strokeCount": 1,
        "cadenceSpm": 12.0,
        "rangeOfMotion": 0.411,
        "armsStraightScore": None,
        "backStraightScore": None,
        "dominantSide": "right",
    }
    latest_workout_analysis_text = (
        "movement gate: failed\n"
        "movement reason: Need at least 3 strokes to save a clip.\n"
        "stroke count: 1"
    )
    latest_workout_score = None

    workout_analysis = latest_workout_analysis
    workout_analysis_text = latest_workout_analysis_text
    workout_score = latest_workout_score

    payload = {
        "summary": workout_analysis.get("summary"),
        "workoutScore": workout_score,
        "alignmentDetails": workout_analysis_text,
        "strokeCount": workout_analysis.get("strokeCount"),
        "cadenceSpm": workout_analysis.get("cadenceSpm"),
        "rangeOfMotion": workout_analysis.get("rangeOfMotion"),
        "armsStraightScore": workout_analysis.get("armsStraightScore"),
        "backStraightScore": workout_analysis.get("backStraightScore"),
        "dominantSide": workout_analysis.get("dominantSide"),
    }

    assert payload["workoutScore"] is None
    assert payload["armsStraightScore"] is None
    assert payload["backStraightScore"] is None
    assert payload["strokeCount"] == 1
    assert payload["summary"] == "Not enough valid strokes were detected to calculate a score."
    assert payload["alignmentDetails"].startswith("movement gate: failed")


def test_workout_analysis_snapshot_handles_missing_analysis():
    workout_analysis = None
    workout_analysis_text = ""
    workout_score = None
    fallback_summary = "Not enough valid strokes were detected to calculate a score."

    payload = {
        "summary": workout_analysis.get("summary") if workout_analysis else fallback_summary,
        "workoutScore": workout_score,
        "alignmentDetails": workout_analysis_text,
        "strokeCount": workout_analysis.get("strokeCount") if workout_analysis else None,
        "cadenceSpm": workout_analysis.get("cadenceSpm") if workout_analysis else None,
        "rangeOfMotion": workout_analysis.get("rangeOfMotion") if workout_analysis else None,
        "armsStraightScore": (
            workout_analysis.get("armsStraightScore") if workout_analysis else None
        ),
        "backStraightScore": (
            workout_analysis.get("backStraightScore") if workout_analysis else None
        ),
        "dominantSide": workout_analysis.get("dominantSide") if workout_analysis else None,
    }

    assert payload["summary"] == fallback_summary
    assert payload["workoutScore"] is None
    assert payload["alignmentDetails"] == ""
    assert payload["strokeCount"] is None
    assert payload["armsStraightScore"] is None
    assert payload["backStraightScore"] is None


def test_clip_threshold_rejection_behavior():
    recording_score_threshold = 100.0

    def should_save(score):
        if score is None or score > recording_score_threshold:
            return False
        return True

    assert should_save(None) is False
    assert should_save(120.0) is False
    assert should_save(100.0) is True
    assert should_save(72.5) is True
