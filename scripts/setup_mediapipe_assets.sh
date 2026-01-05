#!/usr/bin/env bash

# use this if you want a fresh copy of the mediapipe wasm and model files
# you prob won't need to use this unless you mess something up lol
# still good to keep

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_DIR="$ROOT_DIR/node_modules/@mediapipe/tasks-vision"
WASM_SRC="$PKG_DIR/wasm"
DEST_DIR="$ROOT_DIR/rowlytics_app/static/mediapipe"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
TASK_DEST="$DEST_DIR/pose_landmarker_lite.task"

if [ ! -d "$WASM_SRC" ]; then
  echo "Missing $WASM_SRC"
  echo "Run: npm install @mediapipe/tasks-vision"
  exit 1
fi

mkdir -p "$DEST_DIR/wasm"
cp -R "$WASM_SRC/"* "$DEST_DIR/wasm/"

TASK_FILE="$(find "$PKG_DIR" -name 'pose_landmarker_lite.task' -print -quit)"
if [ -n "$TASK_FILE" ]; then
  cp "$TASK_FILE" "$TASK_DEST"
else
  echo "pose_landmarker_lite.task not found in $PKG_DIR"
  echo "Downloading from $MODEL_URL"
  if command -v curl >/dev/null 2>&1; then
    curl -fL "$MODEL_URL" -o "$TASK_DEST"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$TASK_DEST" "$MODEL_URL"
  else
    echo "Install curl or wget, or download manually to $TASK_DEST"
    exit 1
  fi
fi

echo "MediaPipe assets copied to $DEST_DIR"
