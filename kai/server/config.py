"""Server configuration from environment variables.

Set KAI_DATA_DIR to the directory containing items.json, recipes.json, etc.
"""
import os
from pathlib import Path

_raw = os.environ.get("KAI_DATA_DIR", "")
if not _raw:
    # Fall back to the repo-relative data/ directory so local dev works without env vars.
    _raw = str(Path(__file__).resolve().parents[2] / "data")

DATA_DIR = Path(_raw)
HOST = os.environ.get("KAI_HOST", "0.0.0.0")
PORT = int(os.environ.get("KAI_PORT", "8000"))
