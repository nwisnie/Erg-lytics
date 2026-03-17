from rowlytics_app.cv.feature_extraction.angles import (
    angle_between_vectors,
    angle_difference,
    joint_angle,
    magnitude,
    midpoint,
    segment_orientation,
    validate_point,
    vector,
)


class SkeletalDeviationCalculator:

    def _validate_point(self, point):
        validate_point(point)

    def _vector(self, p1, p2):
        return vector(p1, p2)

    def _magnitude(self, vector):
        return magnitude(vector)

    def _angle_between_vectors(self, v1, v2):
        return angle_between_vectors(v1, v2)

    def _joint_angle(self, point_a, joint_point, point_c):
        return joint_angle(point_a, joint_point, point_c)

    def _segment_orientation(self, start_point, end_point):
        return segment_orientation(start_point, end_point)

    def _angle_difference(self, angle1, angle2):
        return angle_difference(angle1, angle2)

    def _joint_deviation(
        self,
        user_point_a,
        user_joint,
        user_point_c,
        ideal_point_a,
        ideal_joint,
        ideal_point_c,
    ):
        user_angle = self._joint_angle(user_point_a, user_joint, user_point_c)
        ideal_angle = self._joint_angle(ideal_point_a, ideal_joint, ideal_point_c)

        return {
            "user_angle": user_angle,
            "ideal_angle": ideal_angle,
            "deviation": abs(user_angle - ideal_angle)
        }

    def arm_angle_deviation(
        self,
        user_hand,
        user_elbow,
        user_shoulder,
        ideal_hand,
        ideal_elbow,
        ideal_shoulder
    ):
        return self._joint_deviation(
            user_hand,
            user_elbow,
            user_shoulder,
            ideal_hand,
            ideal_elbow,
            ideal_shoulder,
        )

    def leg_angle_deviation(
        self,
        user_foot,
        user_knee,
        user_hip,
        ideal_foot,
        ideal_knee,
        ideal_hip
    ):
        return self._joint_deviation(
            user_foot,
            user_knee,
            user_hip,
            ideal_foot,
            ideal_knee,
            ideal_hip,
        )

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
        return midpoint(p1, p2, name=name)

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
