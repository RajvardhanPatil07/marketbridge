"""Vercel entrypoint; local/Docker entrypoint remains marketbridge.api:app."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from marketbridge.api import app  # noqa: E402,F401

