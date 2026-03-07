class PracticeStrokeAssembler:
    def __init__(self):
        self.coordinates = []
        self.finished = False

    def assemble_practice_strokes(self, data):
        if data == "finished":
            self.finished = True
            return self.coordinates

        required_keys = {"name", "time", "x", "y"}
        if not isinstance(data, dict) or not required_keys.issubset(data.keys()):
            raise ValueError("Invalid coordinate format")

        self.coordinates.append({
            "name": data["name"],
            "time": data["time"],
            "x": data["x"],
            "y": data["y"]
        })

        return None

    def assemble_progression_steps(self, coordinates, progression_interval):
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError("coordinates must be a list with at least two entries")

        if not isinstance(progression_interval, (int, float)):
            raise ValueError("progression_interval must be a number")

        if not (0.01 <= progression_interval <= 0.5):
            raise ValueError("progression_interval must be between 0.01 and 0.5")

        min_coord = min(coordinates, key=lambda c: c["x"])
        max_coord = max(coordinates, key=lambda c: c["x"])

        min_x = min_coord["x"]
        max_x = max_coord["x"]
        x_distance = max_x - min_x

        if x_distance == 0:
            return [{
                "name": min_coord["name"],
                "time": min_coord["time"],
                "progression_step": 0.0,
                "x": min_coord["x"],
                "y": min_coord["y"]
            }]

        progression_list = []
        step_count = int(round(1.0 / progression_interval))

        for i in range(step_count + 1):
            progression_step = round(i * progression_interval, 10)
            if i == step_count:
                progression_step = 1.0

            expected_x = min_x + (progression_step * x_distance)

            closest_coord = min(
                coordinates,
                key=lambda c: abs(c["x"] - expected_x)
            )

            progression_list.append({
                "name": closest_coord["name"],
                "time": closest_coord["time"],
                "progression_step": progression_step,
                "x": closest_coord["x"],
                "y": closest_coord["y"]
            })

        return progression_list

    def match_progression_interval(self, progression_intervals, coordinate_list):
        if not isinstance(progression_intervals, list) or len(progression_intervals) == 0:
            raise ValueError("progression_intervals must be a non-empty list")

        if not isinstance(coordinate_list, list) or len(coordinate_list) == 0:
            raise ValueError("coordinate_list must be a non-empty list")

        target_name = progression_intervals[0]["name"]

        matching_coords = [c for c in coordinate_list if c.get("name") == target_name]

        if not matching_coords:
            raise ValueError(f"No matching body part '{target_name}' found in coordinate_list")

        target_coord = matching_coords[0]
        target_x = target_coord["x"]

        closest_progression = min(
            progression_intervals,
            key=lambda p: abs(p["x"] - target_x)
        )

        return {
            "name": target_name,
            "time": target_coord["time"],
            "progression_step": float(closest_progression["progression_step"])
        }

    def get_ideal_coordinate_set(self, current_progression_step, ideal_model):
        if not isinstance(current_progression_step, dict):
            raise ValueError("current_progression_step must be a dictionary")

        if "progression_step" not in current_progression_step:
            raise ValueError("current_progression_step must contain 'progression_step'")

        if "time" not in current_progression_step:
            raise ValueError("current_progression_step must contain 'time'")

        if not isinstance(ideal_model, list) or len(ideal_model) == 0:
            raise ValueError("ideal_model must be a non-empty list")

        target_step = current_progression_step["progression_step"]
        target_time = current_progression_step["time"]

        available_steps = {
            coord["progression_step"]
            for coord in ideal_model
            if "progression_step" in coord
        }

        if not available_steps:
            raise ValueError("ideal_model does not contain any progression_step values")

        closest_step = min(available_steps, key=lambda step: abs(step - target_step))

        result = []
        seen_bodyparts = set()

        for coord in ideal_model:
            if coord.get("progression_step") == closest_step:
                bodypart_name = coord.get("name")

                if bodypart_name not in seen_bodyparts:
                    result.append({
                        "name": bodypart_name,
                        "time": target_time,
                        "progression_step": closest_step,
                        "x": coord["x"],
                        "y": coord["y"]
                    })
                    seen_bodyparts.add(bodypart_name)

        return result
