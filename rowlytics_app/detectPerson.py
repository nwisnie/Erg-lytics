import math

import cv2
import matplotlib.pyplot as plt
import mediapipe as mp


def cameraTest():
    # Zero input accesses webcam
    cap = cv2.VideoCapture(0)

    try:
        while True:
            # Divides input video into frames
            ret, frame = cap.read()
            if not ret:
                break

            # Display the frame
            cv2.imshow("Webcam Stream :)", frame)

            # Exit with 'q' key
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def detectTest():
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    cap = cv2.VideoCapture(0)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.resize(frame, (640, 480))

            # Detect people in the image
            boxes, _weights = hog.detectMultiScale(frame, winStride=(8, 8))

            # Draw detection boxes
            for (x, y, w, h) in boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            cv2.imshow("Person Detection", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def kinematicTest():
    mp_drawing = mp.solutions.drawing_utils
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )  # Pose estimator

    cap = cv2.VideoCapture(0)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.resize(frame, (640, 480))

            results = pose.process(frame)
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
            )  # Landmarks of pose estimator

            # Show the final output
            cv2.imshow("Output", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def modelTest():
    mp_drawing = mp.solutions.drawing_utils
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )  # Pose estimator

    cap = cv2.VideoCapture(r"rowing_model_2.mp4")
    num_frames = 0
    nose_x = []
    nose_y = []
    chest_angle = []
    knee_angle = []
    thumb_pos = []
    arm_angle = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            num_frames += 1
            frame = cv2.resize(frame, (640, 480))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(frame_rgb)

            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                )  # Landmarks of pose estimator

                if (
                    results.pose_landmarks.landmark[
                        mp_pose.PoseLandmark.RIGHT_KNEE
                    ].x
                    > results.pose_landmarks.landmark[
                        mp_pose.PoseLandmark.RIGHT_HIP
                    ].x
                ):  # facing right

                    nose_x.append(
                        results.pose_landmarks.landmark[
                            mp_pose.PoseLandmark.RIGHT_THUMB
                        ].x
                    )
                    nose_y.append(
                        1
                        - results.pose_landmarks.landmark[
                            mp_pose.PoseLandmark.RIGHT_THUMB
                        ].y
                    )
                    thumb_pos.append(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_THUMB
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_THUMB
                            ].y,
                        )
                    )

                    angle = math.atan(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_HIP
                            ].y
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_SHOULDER
                            ].y
                        )
                        / (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_SHOULDER
                            ].x
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_HIP
                            ].x
                        )
                    )
                    if angle < 0:
                        angle += math.pi
                    chest_angle.append(angle)

                    knee_hip = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_HIP
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_HIP
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_KNEE
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_KNEE
                            ].y,
                        ),
                    )
                    knee_ankle = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_ANKLE
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_ANKLE
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_KNEE
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_KNEE
                            ].y,
                        ),
                    )
                    hip_ankle = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_HIP
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_HIP
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_ANKLE
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_ANKLE
                            ].y,
                        ),
                    )
                    knee_angle.append(
                        math.acos(
                            (knee_hip**2 + knee_ankle**2 - hip_ankle**2)
                            / (2 * knee_hip * knee_ankle)
                        )
                    )

                    thumb_elbow = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_THUMB
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_THUMB
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_ELBOW
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_ELBOW
                            ].y,
                        ),
                    )
                    elbow_shoulder = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_ELBOW
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_ELBOW
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_SHOULDER
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_SHOULDER
                            ].y,
                        ),
                    )
                    thumb_shoulder = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_THUMB
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_THUMB
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_SHOULDER
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.RIGHT_SHOULDER
                            ].y,
                        ),
                    )
                    arm_angle.append(
                        math.acos(
                            (
                                thumb_elbow**2
                                + elbow_shoulder**2
                                - thumb_shoulder**2
                            )
                            / (2 * thumb_elbow * elbow_shoulder)
                        )
                    )

                else:  # facing left
                    thumb_pos.append(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_THUMB
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_THUMB
                            ].y,
                        )
                    )

                    angle = math.atan(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_HIP
                            ].y
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_SHOULDER
                            ].y
                        )
                        / (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_SHOULDER
                            ].x
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_HIP
                            ].x
                        )
                    )
                    if angle < 0:
                        angle += math.pi
                    chest_angle.append(angle)

                    knee_hip = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_HIP
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_HIP
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_KNEE
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_KNEE
                            ].y,
                        ),
                    )
                    knee_ankle = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_ANKLE
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_ANKLE
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_KNEE
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_KNEE
                            ].y,
                        ),
                    )
                    hip_ankle = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_HIP
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_HIP
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_ANKLE
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_ANKLE
                            ].y,
                        ),
                    )
                    knee_angle.append(
                        math.acos(
                            (knee_hip**2 + knee_ankle**2 - hip_ankle**2)
                            / (2 * knee_hip * knee_ankle)
                        )
                    )

                    thumb_elbow = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_THUMB
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_THUMB
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_ELBOW
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_ELBOW
                            ].y,
                        ),
                    )
                    elbow_shoulder = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_ELBOW
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_ELBOW
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_SHOULDER
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_SHOULDER
                            ].y,
                        ),
                    )
                    thumb_shoulder = math.dist(
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_THUMB
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_THUMB
                            ].y,
                        ),
                        (
                            results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_SHOULDER
                            ].x,
                            1
                            - results.pose_landmarks.landmark[
                                mp_pose.PoseLandmark.LEFT_SHOULDER
                            ].y,
                        ),
                    )
                    arm_angle.append(
                        math.acos(
                            (
                                thumb_elbow**2
                                + elbow_shoulder**2
                                - thumb_shoulder**2
                            )
                            / (2 * thumb_elbow * elbow_shoulder)
                        )
                    )

            cv2.imshow("Output", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"Total frames processed: {num_frames}")
        print(arm_angle)
        plt.plot(nose_x, nose_y, "bo-")
        plt.xlim(0, 1)
        plt.ylim(0, 1)
        plt.show()


if __name__ == "__main__":
    # cameraTest()
    # detectTest()
    kinematicTest()
