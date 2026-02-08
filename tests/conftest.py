"""Pytest configuration for Rowlytics tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable when running tests directly (e.g., `pytest -q`).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
