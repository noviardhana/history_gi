"""
luck.py
=======
Luck Score formula, shared by the PNG reports (analytics_core.py) and the
dashboard (dashboard.py). Needs only pandas, so the dashboard does not have to
load matplotlib.

    pity_luck  = mean over 5* pulls of (1 - (pity - 1) / (hard_pity - 1)) * 100
    win_luck   = 50 * actual 5* rate-up win rate / expected win rate, where the
                 expected rate is the official rate-up chance of the banner of
                 each pull (e.g. Character 50%, Weapon/Light Cone 75%)
                 -> exactly as expected scores 50, always better than expected > 50
    luck_score = 0.6 * pity_luck + 0.4 * win_luck   (re-weighted if one is missing)
"""

import pandas as pd

if __package__:  # imported as part of the package (dashboard.py) ...
    from .config import GameConfig
else:  # ... or run as a script from pipeline/
    from config import GameConfig

PITY_WEIGHT = 0.6
WIN_WEIGHT = 0.4


def compute_luck(df: pd.DataFrame, cfg: GameConfig) -> pd.DataFrame:
    five = df[df["is_5star"]].copy()
    # to_numeric: on an empty selection map() can return a string column, which has no mean()/arithmetic
    hard = pd.to_numeric(five["banner_type"].map(cfg.hard_pity), errors="coerce").fillna(cfg.default_hard_pity)
    # 100 if obtained on pull #1, 0 if obtained exactly at hard pity; can go below 0 only if pity > hard pity
    five["pity_luck"] = (1 - (five["pity"] - 1) / (hard - 1)) * 100
    pity_by_acc = five.groupby("account")["pity_luck"].mean()

    dec = df[(df["rarity"] == 5) & df["win_50_50"].isin(["Win", "Lose"])].copy()
    dec["is_win"] = (dec["win_50_50"] == "Win").astype(float) * 100.0
    dec["expected"] = pd.to_numeric(dec["banner_type"].map(cfg.rateup_chance), errors="coerce").fillna(50.0)
    actual_by_acc = dec.groupby("account")["is_win"].mean()
    expected_by_acc = dec.groupby("account")["expected"].mean()

    rows = []
    for acc in df["account"].unique():
        pity_luck = pity_by_acc.get(acc, float("nan"))
        actual = actual_by_acc.get(acc, float("nan"))
        expected = expected_by_acc.get(acc, float("nan"))
        win_luck = 50 * actual / expected if pd.notna(actual) and pd.notna(expected) and expected > 0 else float("nan")

        parts = []
        if pd.notna(pity_luck):
            parts.append((pity_luck, PITY_WEIGHT))
        if pd.notna(win_luck):
            parts.append((win_luck, WIN_WEIGHT))
        score = sum(v * w for v, w in parts) / sum(w for _, w in parts) if parts else float("nan")

        rows.append({
            "account": acc,
            "avg_pity_luck": round(pity_luck, 1) if pd.notna(pity_luck) else None,
            "win_rate_5star_pct": round(actual, 1) if pd.notna(actual) else None,
            "expected_win_rate_pct": round(expected, 1) if pd.notna(expected) else None,
            "win_rate_luck": round(win_luck, 1) if pd.notna(win_luck) else None,
            "luck_score": round(score, 1) if pd.notna(score) else None,
        })
    return pd.DataFrame(rows).sort_values("luck_score", ascending=False).reset_index(drop=True)
