import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

"""python3 skeletal.py videoplayback.mp4 \
  --out output_with_skeleton.mp4 \
  --csv-per-second keypoints_per_second.csv \
  --person-only"""

# COCO-17 keypoint skeleton edges (index pairs)
COCO_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),        # nose->eyes->ears
    (5, 6),                                 # shoulders
    (5, 7), (7, 9),                         # left arm
    (6, 8), (8, 10),                        # right arm
    (5, 11), (6, 12),                       # torso
    (11, 12),                               # hips
    (11, 13), (13, 15),                     # left leg
    (12, 14), (14, 16),                     # right leg
]

# COCO keypoint names (optional, useful for debugging / exports)
COCO_KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]


def draw_skeleton(frame, kpts_xy, kpts_conf, conf_thres=0.25):
    """Draw keypoints + skeleton on frame in-place."""
    h, w = frame.shape[:2]

    # Draw edges
    for a, b in COCO_SKELETON:
        if kpts_conf[a] >= conf_thres and kpts_conf[b] >= conf_thres:
            ax, ay = kpts_xy[a]
            bx, by = kpts_xy[b]
            # clamp just in case
            ax, ay = int(np.clip(ax, 0, w - 1)), int(np.clip(ay, 0, h - 1))
            bx, by = int(np.clip(bx, 0, w - 1)), int(np.clip(by, 0, h - 1))
            cv2.line(frame, (ax, ay), (bx, by), (0, 255, 0), 2)

    # Draw keypoints
    for i, ((x, y), c) in enumerate(zip(kpts_xy, kpts_conf)):
        if c >= conf_thres:
            x, y = int(np.clip(x, 0, w - 1)), int(np.clip(y, 0, h - 1))
            cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)


def export_keypoints_per_second_csv(per_second_data, csv_path):
    """
    per_second_data:
      dict[int sec] -> dict with:
        - "person_index": int
        - "detection_confidence": float
        - "kpts_xy": (17,2) array-like
        - "kpts_conf": (17,) array-like
    Writes a single CSV with one row per second per keypoint.
    """
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "second",
        "person_index",
        "detection_confidence",
        "keypoint_index",
        "keypoint_name",
        "x",
        "y",
        "keypoint_confidence",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for sec in sorted(per_second_data.keys()):
            entry = per_second_data[sec]
            kpts_xy = entry["kpts_xy"]
            kpts_conf = entry["kpts_conf"]

            for ki, name in enumerate(COCO_KP_NAMES):
                w.writerow({
                    "second": sec,
                    "person_index": entry["person_index"],
                    "detection_confidence": float(entry["detection_confidence"]),
                    "keypoint_index": ki,
                    "keypoint_name": name,
                    "x": float(kpts_xy[ki][0]),
                    "y": float(kpts_xy[ki][1]),
                    "keypoint_confidence": float(kpts_conf[ki]),
                })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="Path to input video file")
    ap.add_argument("--out", default="pose_overlay.mp4", help="Output video path")
    ap.add_argument("--model", default="yolov8n-pose.pt", help="Pose model weights")
    ap.add_argument("--conf", type=float, default=0.25, help="Keypoint confidence threshold")
    ap.add_argument("--person-only",
                    action="store_true", help="Keep only detections of class 'person'")
    ap.add_argument("--save-json",
                    default=None, help="Optional path to save per-frame keypoints JSON")
    ap.add_argument("--device", default=None, help="Device override, e.g. 'cpu', '0' for GPU0")
    ap.add_argument("--csv-per-second", default=None,
                    help="Optional path to write keypoints sampled once per second (CSV)")
    args = ap.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Load model (downloads weights automatically if needed)
    model = YOLO(args.model)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))

    all_frames_data = []  # for optional JSON export
    per_second = {}  # sec -> representative pose

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # Run inference on the frame
        # results is a list with one element for one image/frame
        results = model.predict(
            source=frame,
            verbose=False,
            device=args.device,
        )
        r = results[0]

        frame_data = {"frame_index": frame_idx, "people": []}

        # r.boxes and r.keypoints align by detection index
        if r.keypoints is not None and r.boxes is not None and len(r.boxes) > 0:
            boxes = r.boxes
            kpts = r.keypoints  # Ultralytics Keypoints object

            # Classes: 0 is "person" for COCO models
            classes = boxes.cls.cpu().numpy().astype(int)
            det_confs = boxes.conf.cpu().numpy()

            # kpts.xy: (N, 17, 2), kpts.conf: (N, 17)
            kpts_xy = kpts.xy.cpu().numpy()
            if kpts.conf is not None:
                kpts_conf = kpts.conf.cpu().numpy()
            else:
                np.ones((kpts_xy.shape[0], kpts_xy.shape[1]))

            sec = int(frame_idx / fps)

            # If we're exporting CSV and haven't captured this second yet,
            # store a representative person.
            if args.csv_per_second is not None and sec not in per_second:
                # Choose the "best" person in this frame (highest detection confidence),
                # optionally restricted to class 'person' (0).
                best_di = None
                best_score = -1.0
                for di in range(kpts_xy.shape[0]):
                    if args.person_only and classes[di] != 0:
                        continue
                    score = float(det_confs[di])
                    if score > best_score:
                        best_score = score
                        best_di = di

                if best_di is not None:
                    per_second[sec] = {
                        "person_index": int(best_di),
                        "detection_confidence": float(det_confs[best_di]),
                        "kpts_xy": kpts_xy[best_di].tolist(),
                        # store as lists for easy serialization
                        "kpts_conf": kpts_conf[best_di].tolist(),
                    }
            for di in range(kpts_xy.shape[0]):
                if args.person_only and classes[di] != 0:
                    continue

                # Draw skeleton for each detected person
                draw_skeleton(frame, kpts_xy[di], kpts_conf[di], conf_thres=args.conf)

                # Collect data for JSON
                person_entry = {
                    "detection_confidence": float(det_confs[di]),
                    "class_id": int(classes[di]),
                    "keypoints": [
                        {
                            "name": COCO_KP_NAMES[ki],
                            "x": float(kpts_xy[di, ki, 0]),
                            "y": float(kpts_xy[di, ki, 1]),
                            "confidence": float(kpts_conf[di, ki]),
                        }
                        for ki in range(len(COCO_KP_NAMES))
                    ],
                }
                frame_data["people"].append(person_entry)

        if args.save_json is not None:
            all_frames_data.append(frame_data)

        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()

    if args.save_json is not None:
        json_path = Path(args.save_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "video": str(video_path),
                    "fps": float(fps),
                    "frame_size": {"width": width, "height": height},
                    "frames": all_frames_data,
                },
                f,
                indent=2,
            )

    if args.csv_per_second is not None:
        export_keypoints_per_second_csv(per_second, args.csv_per_second)
        print(f"Wrote per-second keypoints CSV to: {args.csv_per_second}")

    print(f"Done. Wrote overlay video to: {out_path}")
    if args.save_json is not None:
        print(f"Wrote keypoints JSON to: {args.save_json}")


if __name__ == "__main__":
    main()
