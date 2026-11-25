"""Renders dashboard.py headlessly (both game sections) and exits 1 on any exception.

Run from the project root:  PYTHONPATH=. python tests/smoke_dashboard.py
(used by the 'Smoke-test dashboard' step in .github/workflows/cml.yml)
"""
import sys

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("dashboard.py", default_timeout=180).run()
errors = [str(e.value).replace("\n", " ")[:300] for e in at.exception]
if errors:
    print("::warning::Dashboard raised an exception: " + errors[0])
    sys.exit(1)
print("Dashboard rendered OK")
