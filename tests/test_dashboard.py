"""Renders dashboard.py headlessly with Streamlit's AppTest on the fake data (same idea as the CI smoke test)."""
import sys

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")
from streamlit.testing.v1 import AppTest  # noqa: E402

from conftest import ROOT  # noqa: E402


@pytest.mark.parametrize("game", ["GI", "HSR"])
def test_dashboard_renders_without_exception(gi_csv, hsr_csv, monkeypatch, game):
    monkeypatch.setattr(sys, "argv", ["dashboard.py", "--gi-data", str(gi_csv), "--hsr-data", str(hsr_csv)])
    at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=120)
    at.run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    if game == "HSR":
        at.sidebar.radio(key="game").set_value("HSR").run()
        assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert not at.warning or all("No data file" not in str(w.value) for w in at.warning)
