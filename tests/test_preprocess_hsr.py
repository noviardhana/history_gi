import pandas as pd
import pytest


@pytest.fixture(scope="module")
def hsr():
    from pipeline import preprocess
    return preprocess


def warps(pull_uids):
    """Minimal frame in the shape build_rows() produces, one row per pull_uid."""
    n = len(pull_uids)
    return pd.DataFrame({
        "game": "hsr", "account": "main", "profile_key": "1", "banner_type": "Standard", "banner_code": None,
        "pull_number": range(1, n + 1),
        "timestamp_ms": [1735700000000 + i * 1000 for i in range(n)],
        "item_id": 1003, "item_name": "Himeko", "item_category": "character", "rarity": 3,
        "pity": None, "pity4": None, "pity5": None, "rate_raw": None, "win_50_50": None,
        "manual_input": None, "pull_uid": pull_uids,
    })


def test_rows_without_pull_uid_are_never_dropped(hsr):
    """pandas treats missing values as equal: without a guard, rows with no pull_uid collapse into one."""
    assert len(hsr.postprocess_hsr(warps([None, None, None]), "Asia/Jakarta")) == 3


def test_repeated_pull_uid_is_dropped(hsr):
    out = hsr.postprocess_hsr(warps(["a", "b", "a"]), "Asia/Jakarta")
    assert sorted(out["pull_uid"]) == ["a", "b"]
