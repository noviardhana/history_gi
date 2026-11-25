"""compute_luck(): pity luck, win luck and the 60/40 weighting."""
import math

import pandas as pd
import pytest

from config import GI
from luck import compute_luck


def make_df(rows):
    df = pd.DataFrame(rows, columns=["account", "banner_type", "rarity", "pity", "win_50_50"])
    df["is_5star"] = df["rarity"] == 5
    return df


def only(df):
    return compute_luck(df, GI).iloc[0]


def test_pity_one_scores_100_and_hard_pity_scores_0():
    assert only(make_df([("a", "Character Event", 5, 1, None)]))["avg_pity_luck"] == 100.0
    assert only(make_df([("a", "Character Event", 5, 90, None)]))["avg_pity_luck"] == 0.0


def test_hard_pity_depends_on_banner():
    # Weapon Event hard pity is 80, so pity 80 is also 0
    assert only(make_df([("a", "Weapon Event", 5, 80, None)]))["avg_pity_luck"] == 0.0


def test_win_rate_exactly_as_expected_scores_50():
    rows = [("a", "Character Event", 5, 50, "Win"), ("a", "Character Event", 5, 50, "Lose")]
    r = only(make_df(rows))
    assert r["win_rate_luck"] == 50.0
    assert r["win_rate_5star_pct"] == 50.0 and r["expected_win_rate_pct"] == 50.0


def test_all_wins_on_50_50_scores_100_and_75_banner_is_harder():
    assert only(make_df([("a", "Character Event", 5, 50, "Win")]))["win_rate_luck"] == 100.0
    # winning every time on a 75% banner is worth less than on a 50% banner
    assert round(only(make_df([("a", "Weapon Event", 5, 50, "Win")]))["win_rate_luck"], 1) == 66.7


def test_guaranteed_is_ignored_for_win_luck():
    rows = [("a", "Character Event", 5, 50, "Guaranteed")]
    assert only(make_df(rows))["win_rate_luck"] is None


def test_score_is_60_40_weighted():
    rows = [("a", "Character Event", 5, 1, "Lose")]  # pity luck 100, win luck 0
    assert only(make_df(rows))["luck_score"] == 60.0


def test_reweights_when_win_data_is_missing():
    rows = [("a", "Standard", 5, 1, None)]  # no rate-up info -> score is just the pity part
    assert only(make_df(rows))["luck_score"] == 100.0


def test_no_five_star_gives_no_score():
    r = only(make_df([("a", "Character Event", 4, 5, "Win")]))
    assert r["luck_score"] is None or (isinstance(r["luck_score"], float) and math.isnan(r["luck_score"]))


def test_sorted_by_score_descending():
    rows = [("low", "Character Event", 5, 89, "Lose"), ("high", "Character Event", 5, 2, "Win")]
    out = compute_luck(make_df(rows), GI)
    assert list(out["account"]) == ["high", "low"]


def test_unknown_banner_uses_default_hard_pity():
    assert only(make_df([("a", "Mystery", 5, 90, None)]))["avg_pity_luck"] == 0.0
    assert pytest.approx(only(make_df([("a", "Mystery", 5, 46, None)]))["avg_pity_luck"], abs=0.1) == 49.4
