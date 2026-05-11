"""Streamlit Cloud entrypoint.

The real app lives in app/streamlit_app.py. This wrapper keeps Streamlit Cloud's
default "streamlit_app.py" main-file path working and exposes src/ imports.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import app.streamlit_app  # noqa: E402,F401
