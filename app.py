"""Vercel entrypoint; local/Docker entrypoint is marketbridge.app:app."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from marketbridge.app import app  # noqa: E402,F401
