"""
Align two YOLOv8-pose per-second CSVs by horizontal head movement progress.

Input CSV format (from your exporter):
second, person_index, detection_confidence, keypoint_index, keypoint_name, x, y, keypoint_confidence

Output:
One row per (progress_step, keypoint_name) with keypoint coords from both files
at the seconds closest to that progress step.

Example:
python alignment.py a.csv b.csv --out aligned.csv --step 0.10 --tolerance 0.05
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

DEFAULT_HEAD_KPS = ["nose", "left_eye", "right_eye", "left_ear", "right_ear"]


def read_pose_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "second",
        "person_index",
        "detection_confidence",
        "keypoint_index",
        "keypoint_name",
        "x",
        "y",
        "keypoint_confidence",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")
    return df


def to_wide_per_second(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert long format (one row per second per keypoint) to wide format (one row per second),
    with columns like nose_x, nose_y, nose_conf, left_eye_x, ...
    """
    # Ensure keypoint_name is string
    df = df.copy()
    df["keypoint_name"] = df["keypoint_name"].astype(str)

    # Pivot x/y/conf separately then merge
    xw = df.pivot(index="second", columns="keypoint_name", values="x").add_suffix("_x")
    yw = df.pivot(index="second", columns="keypoint_name", values="y").add_suffix("_y")
    cw = df.pivot(index="second", columns="keypoint_name",
                  values="keypoint_confidence").add_suffix("_conf")

    # Bring along one detection confidence per second (should be same for all rows in that second)
    det = df.groupby("second",
                     as_index=True)["detection_confidence"].first().rename("detection_confidence")
    pidx = df.groupby("second", as_index=True)["person_index"].first().rename("person_index")

    wide = pd.concat([pidx, det, xw, yw, cw], axis=1).reset_index()
    wide = wide.sort_values("second").reset_index(drop=True)
    return wide


def head_x_series(
    wide: pd.DataFrame,
    head_kps: List[str],
    kp_conf_thres: float,
    method: str = "conf_weighted_avg",
) -> pd.Series:
    """
    Compute a single head X position per second.

    method:
      - "conf_weighted_avg": sum(x_i * conf_i) / sum(conf_i) over head keypoints
      with conf>=threshold
      - "simple_avg": average of x_i over head keypoints with conf>=threshold
      - "nose": use nose_x if available & conf>=threshold, else NaN
    """
    if method not in {"conf_weighted_avg", "simple_avg", "nose"}:
        raise ValueError(f"Unknown method: {method}")

    if method == "nose":
        if "nose_x" not in wide.columns or "nose_conf" not in wide.columns:
            return pd.Series([np.nan] * len(wide), index=wide.index)
        ok = wide["nose_conf"] >= kp_conf_thres
        out = pd.Series(np.nan, index=wide.index, dtype=float)
        out.loc[ok] = wide.loc[ok, "nose_x"].astype(float)
        return out

    xs = []
    cs = []
    for kp in head_kps:
        xcol = f"{kp}_x"
        ccol = f"{kp}_conf"
        if xcol in wide.columns and ccol in wide.columns:
            xs.append(wide[xcol].astype(float))
            cs.append(wide[ccol].astype(float))
    if not xs:
        return pd.Series([np.nan] * len(wide), index=wide.index)

    X = np.vstack([s.to_numpy() for s in xs])  # shape (K, T)
    C = np.vstack([s.to_numpy() for s in cs])  # shape (K, T)

    mask = C >= kp_conf_thres
    X_masked = np.where(mask, X, np.nan)

    if method == "simple_avg":
        return pd.Series(np.nanmean(X_masked, axis=0), index=wide.index)

    # conf_weighted_avg
    W = np.where(mask, C, 0.0)
    num = np.nansum(X * W, axis=0)
    den = np.sum(W, axis=0)
    out = np.where(den > 0, num / den, np.nan)
    return pd.Series(out, index=wide.index)


def progress_between_extremes(head_x: pd.Series) -> Tuple[pd.Series, float, float]:
    """
    Compute progress p in [0,1] from min(head_x) to max(head_x).
    Returns (progress_series, x_min, x_max).
    """
    valid = head_x.dropna()
    if valid.empty:
        raise ValueError("No valid head_x values after filtering; cannot compute extremes.")

    x_min = float(valid.min())
    x_max = float(valid.max())
    if np.isclose(x_max, x_min):
        raise ValueError("Head movement range is ~0 (x_max == x_min); cannot compute progress.")

    p = (head_x - x_min) / (x_max - x_min)
    return p, x_min, x_max


def choose_seconds_for_steps(
    wide: pd.DataFrame,
    progress: pd.Series,
    steps: List[float],
    tolerance: float,
) -> Dict[float, Optional[int]]:
    """
    For each desired step s, pick the second whose progress is closest to s.
    If abs(diff) > tolerance, return None for that step.
    """
    sec = wide["second"].astype(int).to_numpy()
    p = progress.to_numpy()

    chosen: Dict[float, Optional[int]] = {}
    for s in steps:
        diffs = np.abs(p - s)
        # ignore NaNs
        diffs = np.where(np.isnan(diffs), np.inf, diffs)
        j = int(np.argmin(diffs))
        if diffs[j] <= tolerance:
            chosen[s] = int(sec[j])
        else:
            chosen[s] = None
    return chosen


def extract_keypoints_at_second(df_long: pd.DataFrame, second: int) -> pd.DataFrame:
    """
    Return rows for all keypoints at a given second.
    """
    out = df_long[df_long["second"].astype(int) == int(second)].copy()
    # Keep only the columns we care about
    return out[["keypoint_name", "x", "y", "keypoint_confidence"]].rename(
        columns={"keypoint_confidence": "conf"}
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv1", type=str, help="First per-second keypoints CSV")
    ap.add_argument("csv2", type=str, help="Second per-second keypoints CSV")
    ap.add_argument("--out", type=str, default="aligned_head_progress.csv", help="Output CSV path")

    ap.add_argument("--step", type=float, default=0.10,
                    help="Progress step size (e.g., 0.10 for 10%%)")
    ap.add_argument("--tolerance", type=float, default=0.05,
                    help="Max allowed |progress - step| to accept a match (e.g., 0.05)")

    ap.add_argument("--head-kps", type=str, default=",".join(DEFAULT_HEAD_KPS),
                    help="Comma-separated head keypoints to use")
    ap.add_argument("--kp-conf", type=float, default=0.25,
                    help="Keypoint confidence threshold for head tracking")

    ap.add_argument("--head-method", type=str, default="conf_weighted_avg",
                    choices=["conf_weighted_avg", "simple_avg", "nose"],
                    help="How to compute head x per second")

    args = ap.parse_args()

    csv1_path = Path(args.csv1)
    csv2_path = Path(args.csv2)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    head_kps = [s.strip() for s in args.head_kps.split(",") if s.strip()]
    if not head_kps:
        raise ValueError("No head keypoints provided via --head-kps")

    # steps: include 0 and 1
    if args.step <= 0 or args.step > 1:
        raise ValueError("--step must be in (0, 1]")
    n_steps = int(round(1.0 / args.step))
    steps = [round(i * args.step, 10) for i in range(n_steps + 1)]
    if steps[-1] != 1.0:
        steps.append(1.0)
    steps = sorted(set(steps))

    df1 = read_pose_csv(csv1_path)
    df2 = read_pose_csv(csv2_path)

    wide1 = to_wide_per_second(df1)
    wide2 = to_wide_per_second(df2)

    hx1 = head_x_series(wide1, head_kps=head_kps,
                        kp_conf_thres=args.kp_conf, method=args.head_method)
    hx2 = head_x_series(wide2, head_kps=head_kps,
                        kp_conf_thres=args.kp_conf, method=args.head_method)

    p1, x1_min, x1_max = progress_between_extremes(hx1)
    p2, x2_min, x2_max = progress_between_extremes(hx2)

    chosen1 = choose_seconds_for_steps(wide1, p1, steps, tolerance=args.tolerance)
    chosen2 = choose_seconds_for_steps(wide2, p2, steps, tolerance=args.tolerance)

    # Determine keypoint set (use intersection so output aligns cleanly)
    kp_set1 = set(df1["keypoint_name"].astype(str).unique())
    kp_set2 = set(df2["keypoint_name"].astype(str).unique())
    kp_names = sorted(kp_set1.intersection(kp_set2))
    if not kp_names:
        raise ValueError("The two CSVs share no keypoint_name values in common.")

    rows = []
    for s in steps:
        sec1 = chosen1[s]
        sec2 = chosen2[s]

        # Extract all keypoints at those seconds (or empty if None)
        kp1 = extract_keypoints_at_second(df1, sec1) if sec1 is not None else pd.DataFrame(
            {"keypoint_name": kp_names, "x": np.nan, "y": np.nan, "conf": np.nan}
        )
        kp2 = extract_keypoints_at_second(df2, sec2) if sec2 is not None else pd.DataFrame(
            {"keypoint_name": kp_names, "x": np.nan, "y": np.nan, "conf": np.nan}
        )

        # Ensure all keypoints exist; reindex
        kp1 = kp1.set_index("keypoint_name").reindex(kp_names).reset_index()
        kp2 = kp2.set_index("keypoint_name").reindex(kp_names).reset_index()

        # Progress + head_x at chosen seconds (for debugging/inspection)
        head_x1_at = float(wide1.loc[wide1["second"] == sec1, "second"].size and
                           hx1.loc[wide1.index[wide1["second"] == sec1][0]]
                           ) if sec1 is not None else np.nan
        head_x2_at = float(wide2.loc[wide2["second"] == sec2, "second"].size and
                           hx2.loc[wide2.index[wide2["second"] == sec2][0]]
                           ) if sec2 is not None else np.nan

        for i, kp in enumerate(kp_names):
            rows.append({
                "progress_step": s,

                "file1_second": sec1,
                "file1_head_x": head_x1_at,
                "file1_xmin": x1_min,
                "file1_xmax": x1_max,
                "file1_kp": kp,
                "file1_x": float(kp1.loc[i, "x"]) if pd.notna(kp1.loc[i, "x"]) else np.nan,
                "file1_y": float(kp1.loc[i, "y"]) if pd.notna(kp1.loc[i, "y"]) else np.nan,
                "file1_kp_conf": float(
                  kp1.loc[i, "conf"]) if pd.notna(kp1.loc[i, "conf"]) else np.nan,

                "file2_second": sec2,
                "file2_head_x": head_x2_at,
                "file2_xmin": x2_min,
                "file2_xmax": x2_max,
                "file2_kp": kp,
                "file2_x": float(kp2.loc[i, "x"]) if pd.notna(kp2.loc[i, "x"]) else np.nan,
                "file2_y": float(kp2.loc[i, "y"]) if pd.notna(kp2.loc[i, "y"]) else np.nan,
                "file2_kp_conf": float(
                  kp2.loc[i, "conf"]) if pd.notna(kp2.loc[i, "conf"]) else np.nan,
            })

    out_df = pd.DataFrame(rows)
    out_df.to_csv(out_path, index=False)

    print(f"Wrote aligned CSV: {out_path}")
    print("Notes:")
    print(f"  Steps: {steps}")
    print(f"  File1 head_x range: [{x1_min:.3f}, {x1_max:.3f}]")
    print(f"  File2 head_x range: [{x2_min:.3f}, {x2_max:.3f}]")
    print("Any step with no close match (>|tolerance|) will have NaNs for that file at that step.")


if __name__ == "__main__":
    main()
