import math


class SkeletalDeviationCalculator:

    def _validate_point(self, point):
        if not isinstance(point, dict):
            raise ValueError("Point must be a dictionary")

        required_keys = {"x", "y"}
        if not required_keys.issubset(point.keys()):
            raise ValueError("Point must contain 'x' and 'y'")

        if not isinstance(point["x"], (int, float)) or not isinstance(point["y"], (int, float)):
            raise ValueError("'x' and 'y' must be numeric")

    def _vector(self, p1, p2):
        self._validate_point(p1)
        self._validate_point(p2)
        return (p2["x"] - p1["x"], p2["y"] - p1["y"])

    def _magnitude(self, vector):
        return math.sqrt(vector[0] ** 2 + vector[1] ** 2)

    def _angle_between_vectors(self, v1, v2):
        mag1 = self._magnitude(v1)
        mag2 = self._magnitude(v2)

        if mag1 == 0 or mag2 == 0:
            raise ValueError("Cannot calculate angle with a zero-length segment")

        dot = v1[0] * v2[0] + v1[1] * v2[1]
        cos_theta = dot / (mag1 * mag2)

        cos_theta = max(-1.0, min(1.0, cos_theta))

        return math.degrees(math.acos(cos_theta))

    def _joint_angle(self, point_a, joint_point, point_c):
        self._validate_point(point_a)
        self._validate_point(joint_point)
        self._validate_point(point_c)

        v1 = self._vector(joint_point, point_a)
        v2 = self._vector(joint_point, point_c)

        return self._angle_between_vectors(v1, v2)

    def _segment_orientation(self, start_point, end_point):
        self._validate_point(start_point)
        self._validate_point(end_point)

        dx = end_point["x"] - start_point["x"]
        dy = end_point["y"] - start_point["y"]

        if dx == 0 and dy == 0:
            raise ValueError("Cannot calculate orientation of a zero-length segment")

        return math.degrees(math.atan2(dy, dx))

    def _angle_difference(self, angle1, angle2):
        diff = abs(angle1 - angle2) % 360
        return min(diff, 360 - diff)

    def arm_angle_deviation(
        self,
        user_hand,
        user_elbow,
        user_shoulder,
        ideal_hand,
        ideal_elbow,
        ideal_shoulder
    ):
        user_angle = self._joint_angle(user_hand, user_elbow, user_shoulder)
        ideal_angle = self._joint_angle(ideal_hand, ideal_elbow, ideal_shoulder)

        return {
            "user_angle": user_angle,
            "ideal_angle": ideal_angle,
            "deviation": abs(user_angle - ideal_angle)
        }

    def leg_angle_deviation(
        self,
        user_foot,
        user_knee,
        user_hip,
        ideal_foot,
        ideal_knee,
        ideal_hip
    ):
        user_angle = self._joint_angle(user_foot, user_knee, user_hip)
        ideal_angle = self._joint_angle(ideal_foot, ideal_knee, ideal_hip)

        return {
            "user_angle": user_angle,
            "ideal_angle": ideal_angle,
            "deviation": abs(user_angle - ideal_angle)
        }

    def torso_angle_deviation(
        self,
        user_hip,
        user_shoulder,
        ideal_hip,
        ideal_shoulder
    ):
        user_angle = self._segment_orientation(user_hip, user_shoulder)
        ideal_angle = self._segment_orientation(ideal_hip, ideal_shoulder)

        return {
            "user_angle": user_angle,
            "ideal_angle": ideal_angle,
            "deviation": self._angle_difference(user_angle, ideal_angle)
        }

    def _build_name_map(self, coordinates):
        if not isinstance(coordinates, list) or len(coordinates) == 0:
            raise ValueError("coordinates must be a non-empty list")

        name_map = {}
        for point in coordinates:
            if not isinstance(point, dict):
                raise ValueError("Each coordinate must be a dictionary")
            if "name" not in point:
                raise ValueError("Each coordinate must contain 'name'")
            name_map[point["name"]] = point

        return name_map

    def _midpoint(self, p1, p2, name="midpoint"):
        self._validate_point(p1)
        self._validate_point(p2)

        return {
            "name": name,
            "x": (p1["x"] + p2["x"]) / 2.0,
            "y": (p1["y"] + p2["y"]) / 2.0
        }

    def compare_pose(self, user_model, ideal_model):
        user_points = self._build_name_map(user_model)
        ideal_points = self._build_name_map(ideal_model)

        results = {
            "left_arm": self.arm_angle_deviation(
                user_points["left_hand"],
                user_points["left_elbow"],
                user_points["left_shoulder"],
                ideal_points["left_hand"],
                ideal_points["left_elbow"],
                ideal_points["left_shoulder"]
            ),
            "right_arm": self.arm_angle_deviation(
                user_points["right_hand"],
                user_points["right_elbow"],
                user_points["right_shoulder"],
                ideal_points["right_hand"],
                ideal_points["right_elbow"],
                ideal_points["right_shoulder"]
            ),
            "left_leg": self.leg_angle_deviation(
                user_points["left_foot"],
                user_points["left_knee"],
                user_points["left_hip"],
                ideal_points["left_foot"],
                ideal_points["left_knee"],
                ideal_points["left_hip"]
            ),
            "right_leg": self.leg_angle_deviation(
                user_points["right_foot"],
                user_points["right_knee"],
                user_points["right_hip"],
                ideal_points["right_foot"],
                ideal_points["right_knee"],
                ideal_points["right_hip"]
            )
        }

        if (
            "hip_center" in user_points and
            "shoulder_center" in user_points and
            "hip_center" in ideal_points and
            "shoulder_center" in ideal_points
        ):
            user_hip = user_points["hip_center"]
            user_shoulder = user_points["shoulder_center"]
            ideal_hip = ideal_points["hip_center"]
            ideal_shoulder = ideal_points["shoulder_center"]
        else:
            user_hip = self._midpoint(user_points["left_hip"],
                                      user_points["right_hip"], "user_hip_center")
            user_shoulder = self._midpoint(user_points["left_shoulder"],
                                           user_points["right_shoulder"], "user_shoulder_center")
            ideal_hip = self._midpoint(ideal_points["left_hip"],
                                       ideal_points["right_hip"], "ideal_hip_center")
            ideal_shoulder = self._midpoint(ideal_points["left_shoulder"],
                                            ideal_points["right_shoulder"], "ideal_shoulder_center")

        results["torso"] = self.torso_angle_deviation(
            user_hip,
            user_shoulder,
            ideal_hip,
            ideal_shoulder
        )

        return results
