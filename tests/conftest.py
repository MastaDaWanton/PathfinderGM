"""Test setup.

Django is configured here rather than through pytest-django, because the rules engine and
the world loader do not touch the ORM and the app has no models — one fewer dependency for
PyInstaller to be told about, which is a real cost in the frozen build.

Tests run from the repository root so that the fixture paths in them are the same paths a
person would type.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Campaign saves must never land in the real user data directory during a test run.
os.environ.setdefault("PATHFINDER_GM_DATA", str(ROOT / ".test-data"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()
