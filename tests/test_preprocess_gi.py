import logging

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def gi(load_script):
    return load_script("02_preprocess_gi.py")


def pulls(items, ts="2025-01-01 10:00:00", account="main", banner="Character Event"):
    """items: list of (item_id, rarity, pity). All rows share one timestamp, like a 10-pull."""
    df = pd.DataFrame(
        [dict(account=account, banner_type=banner, datetime=pd.Timestamp(ts), item_id=i, item_category="weapon",
              rarity=r, pity=p, rate_raw=None) for i, r, p in items])
    df["pull_number"] = range(1, len(df) + 1)
    return df


def test_ten_identical_3star_pulls_are_kept(gi):
    df = pulls([("black_tassel", 3, 1)] * 10)   # real: same item 10x in one 10-pull, pity always 1
    assert len(gi.drop_duplicate_pulls(df)) == 10


def test_a_10_pull_that_appears_twice_is_cut_to_one(gi):
    ten = [(f"item{i}", 3, 1) for i in range(9)] + [("char", 5, 33)]
    out = gi.drop_duplicate_pulls(pulls(ten + ten))
    assert len(out) == 10
    assert list(out["pull_number"]) == list(range(1, 11))


def test_more_than_ten_rows_that_are_not_a_repeat_are_reported_not_dropped(gi, caplog, monkeypatch):
    monkeypatch.setattr(logging.getLogger("gacha"), "propagate", True)   # let caplog see the pipeline logger
    with caplog.at_level(logging.WARNING, logger="gacha"):
        out = gi.drop_duplicate_pulls(pulls([(f"item{i}", 3, 1) for i in range(11)]))
    assert len(out) == 11
    assert "nothing was dropped" in caplog.text


def test_banners_and_accounts_are_not_mixed(gi):
    a = pulls([("x", 3, 1)] * 10)
    b = pulls([("x", 3, 1)] * 10, banner="Standard")
    c = pulls([("x", 3, 1)] * 10, account="alt")
    assert len(gi.drop_duplicate_pulls(pd.concat([a, b, c], ignore_index=True))) == 30


def test_timezone_conversion(gi):
    s = pd.Series(["2025-01-01 00:00:00"])
    assert gi.to_target_tz(s, "UTC", "Asia/Jakarta").iloc[0] == pd.Timestamp("2025-01-01 07:00:00")
    assert gi.to_target_tz(s, "Asia/Jakarta", "Asia/Jakarta").iloc[0] == pd.Timestamp("2025-01-01 00:00:00")


def test_mask_uid(gi):
    assert gi.mask_uid("887284572") == "88xxxxx72"
    assert gi.mask_uid(1817478961) == "18xxxxxx61"


def test_mask_uids_extends_when_two_masks_would_collide(gi):
    df = pd.DataFrame({"uid": [887284572, 887999572, 887284572]})
    masked = gi.mask_uids(df)["uid"]
    assert masked.nunique() == 2
    assert masked.iloc[0] == masked.iloc[2]
    assert "887284572" not in masked.tolist()
