"""Renders dashboard.py headlessly (both game sections) and exits 1 on any exception.

Run from the project root:  PYTHONPATH=. python tests/smoke_dashboard.py
(used by the 'Smoke-test dashboard' step in .github/workflows/cml.yml)
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
GAME_KEYS = ["GI", "HSR"]  # sama dengan key di pipeline.config.GAMES

failed = False
for game in GAME_KEYS:
    at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=180)
    at.session_state["game"] = game  # radio "Select game" di sidebar
    at.run()
    errors = [str(e.value).replace("\n", " ")[:300] for e in at.exception]
    if errors:
        print(f"::warning::Dashboard [{game}] raised an exception: {errors[0]}")
        failed = True
    else:
        print(f"Dashboard [{game}] rendered OK")

sys.exit(1 if failed else 0)