import pandas as pd
import pytest

from pipeline.config import GI
from pipeline.luck import compute_luck


def frame(rows):
    df = pd.DataFrame(rows, columns=["account", "banner_type", "rarity", "pity", "win_50_50"])
    df["is_5star"] = df["rarity"] == 5
    return df


def test_average_luck_is_50_and_win_rate_as_expected():
    df = frame([
        ("a", "Character Event", 5, 1, "Win"),      # pity 1  -> 100
        ("a", "Character Event", 5, 90, "Lose"),    # hard pity -> 0
    ])
    row = compute_luck(df, GI).iloc[0]
    assert row["avg_pity_luck"] == 50.0
    assert row["win_rate_5star_pct"] == 50.0 and row["expected_win_rate_pct"] == 50.0
    assert row["win_rate_luck"] == 50.0
    assert row["luck_score"] == 50.0


def test_weapon_event_expects_75_percent():
    df = frame([("a", "Weapon Event", 5, 40, "Win")])
    row = compute_luck(df, GI).iloc[0]
    assert row["expected_win_rate_pct"] == 75.0
    assert row["win_rate_luck"] == pytest.approx(66.7, abs=0.05)


def test_guaranteed_pulls_do_not_count_as_a_50_50():
    df = frame([
        ("a", "Character Event", 5, 10, "Lose"),
        ("a", "Character Event", 5, 10, "Guaranteed"),
    ])
    row = compute_luck(df, GI).iloc[0]
    assert row["win_rate_5star_pct"] == 0.0


def test_missing_50_50_data_uses_pity_only():
    df = frame([("a", "Standard", 5, 1, None)])
    row = compute_luck(df, GI).iloc[0]
    assert row["luck_score"] == 100.0
    assert row["win_rate_luck"] is None


def test_accounts_are_scored_separately_and_sorted():
    df = frame([
        ("lucky", "Character Event", 5, 1, "Win"),
        ("unlucky", "Character Event", 5, 90, "Lose"),
    ])
    out = compute_luck(df, GI)
    assert list(out["account"]) == ["lucky", "unlucky"]
    assert out["luck_score"].iloc[0] > out["luck_score"].iloc[1]
