import cv2
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


if __name__ == "__main__":
    # cameraTest()
    # detectTest()
    kinematicTest()
