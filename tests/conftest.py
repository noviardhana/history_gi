import importlib.util
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"


@pytest.fixture(scope="session")
def load_script():
    """Import a pipeline script by file name (names start with a digit, so a normal import is impossible)."""
    cache = {}

    def _load(filename: str):
        if filename not in cache:
            spec = importlib.util.spec_from_file_location(filename.replace(".py", "").replace("-", "_") + "_under_test",
                                                          PIPELINE / filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cache[filename] = module
        return cache[filename]

    return _load
