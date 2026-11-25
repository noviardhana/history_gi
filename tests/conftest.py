"""Shared test helpers: put pipeline/ on sys.path and load digit-prefixed scripts by file path."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE))


def load_script(filename: str):
    """Import pipeline/<filename> (names like 02_preprocess_hsr.py cannot be imported normally)."""
    spec = importlib.util.spec_from_file_location(Path(filename).stem.replace("-", "_") + "_under_test", PIPELINE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def hsr():
    return load_script("02_preprocess_hsr.py")


@pytest.fixture(scope="session")
def gi_pre():
    return load_script("02_preprocess_gi.py")


@pytest.fixture(scope="session")
def gi_fetch():
    return load_script("01_fetch_gi_lookup.py")

sys.path.insert(0, str(ROOT))  # so `import pipeline.luck` works like in dashboard.py
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sync_mod():
    return load_script("04_sync_gsheet.py")


def make_gi_export(path, uid="800000001"):
    """Small FAKE Paimon.moe export: main account + one extra account, with a duplicated pull."""
    import json

    def pulls(n, start_id, hits):
        out = []
        for i in range(1, n + 1):
            item = hits.get(i)
            rec = {"type": "character", "id": item[0] if item else "amber", "time": f"2026-02-0{1 + i % 5} 10:{i % 60:02d}:00",
                   "code": "301", "pity": item[1] if item else 1}
            if item and len(item) > 2:
                rec["rate"] = item[2]
            out.append(rec)
        return out

    char = pulls(40, 0, {10: ("hutao", 10, 1), 25: ("diluc", 15, 0), 40: ("hutao", 15, 2), 5: ("xiangling", 5, 1)})
    char.append(dict(char[9]))  # exact duplicate of the 5* pull at position 10
    raw = {
        "wish-uid": uid, "ar": 60, "wl": 8, "accounts": "alt",
        "wish-counter-character-event": {"pulls": char},
        "wish-counter-standard": {"pulls": [{"type": "weapon", "id": "sword", "time": "2026-02-01 10:00:00", "code": "200", "pity": 1}]},
        "alt-wish-uid": "800000002", "alt-ar": 30, "alt-wl": 5,
        "alt-wish-counter-weapon-event": {"pulls": [{"type": "weapon", "id": "staff", "time": "2026-03-01 10:00:00",
                                                       "code": "302", "pity": 40, "rate": 1}]},
    }
    path.write_text(json.dumps(raw), encoding="utf-8")


GI_CHAR_LOOKUP = {"hutao": {"name": "Hu Tao", "rarity": 5}, "diluc": {"name": "Diluc", "rarity": 5},
                  "xiangling": {"name": "Xiangling", "rarity": 4}, "amber": {"name": "Amber", "rarity": 4}}
GI_WEAPON_LOOKUP = {"sword": {"name": "Dull Blade", "rarity": 3}, "staff": {"name": "Staff of Homa", "rarity": 5}}


@pytest.fixture
def gi_csv(tmp_path, gi_pre, monkeypatch):
    """Runs 02_preprocess_gi.main() on the fake export -> returns the CSV path."""
    import json

    export = tmp_path / "paimon-moe-local-data.json"
    make_gi_export(export)
    (tmp_path / "char_full.json").write_text(json.dumps(GI_CHAR_LOOKUP))
    (tmp_path / "weapon_full.json").write_text(json.dumps(GI_WEAPON_LOOKUP))
    for name, value in (("RAW_PATH", export), ("CHAR_LOOKUP_PATH", tmp_path / "char_full.json"),
                        ("WEAPON_LOOKUP_PATH", tmp_path / "weapon_full.json"), ("DATA_DIR", tmp_path),
                        ("CLEAN_CSV", {"GI": tmp_path / "data_clean_gi.csv"})):
        monkeypatch.setattr(gi_pre, name, value)
    monkeypatch.setattr(gi_pre, "clean_csv_variant", lambda k, s: tmp_path / f"data_clean_gi_{s}.csv")
    monkeypatch.setattr(sys, "argv", ["02_preprocess_gi.py"])
    gi_pre.main()
    return tmp_path / "data_clean_gi.csv"


@pytest.fixture
def hsr_csv(tmp_path, hsr, monkeypatch):
    """Runs 02_preprocess_hsr.main() on the fake backup -> returns the CSV path."""
    import shutil

    for name in ("hsr_char_full.json", "hsr_lc_full.json"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    monkeypatch.setattr(hsr, "DATA_DIR", tmp_path)
    monkeypatch.setattr(hsr, "CHAR_LOOKUP_PATH", tmp_path / "hsr_char_full.json")
    monkeypatch.setattr(hsr, "LC_LOOKUP_PATH", tmp_path / "hsr_lc_full.json")
    monkeypatch.setattr(hsr, "CLEAN_CSV", {"HSR": tmp_path / "data_clean_hsr.csv"})
    monkeypatch.setattr(hsr, "clean_csv_variant", lambda k, s: tmp_path / f"data_clean_hsr_{s}.csv")
    monkeypatch.setattr(sys, "argv", ["02_preprocess_hsr.py", "--input", str(FIXTURES / "hsr_backup.dat")])
    hsr.main()
    return tmp_path / "data_clean_hsr.csv"
