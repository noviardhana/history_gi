"""Renders dashboard.py headlessly for every game that has data and exits 1 on any exception.

Run from anywhere:  python tests/smoke_dashboard.py
(used by the 'Smoke-test dashboard' step in .github/workflows/cml.yml)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # `import pipeline` works without PYTHONPATH

from streamlit.testing.v1 import AppTest  # noqa: E402

from pipeline.config import GAMES, default_clean_csv  # noqa: E402

failed = False
tested = 0

for key, cfg in GAMES.items():
    csv = default_clean_csv(key)
    if not csv.exists():
        # without the CSV the dashboard only shows a warning, so there is nothing to test
        print(f"[skip] {cfg.title}: {csv.name} not found")
        continue

    at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=180)
    at.session_state["game"] = key  # the "Select game" radio in the sidebar
    at.run()
    tested += 1

    errors = [str(e.value).replace("\n", " ")[:300] for e in at.exception]
    errors += [str(e.value).replace("\n", " ")[:300] for e in at.error]
    if errors:
        print(f"::warning::Dashboard [{key}] raised an exception: {errors[0]}")
        failed = True
    else:
        print(f"Dashboard [{key}] rendered OK")

if tested == 0:
    print("::warning::Smoke test did not render any game: no data_clean CSV found")
    failed = True

sys.exit(1 if failed else 0)