"""
luck.py
=======
Luck Score formula, shared by the PNG reports (analytics_core.py) and the
dashboard (dashboard.py). Needs only pandas/numpy, so the dashboard does not have to
load matplotlib.

Both components are on a 0-100 scale where 50 means "exactly as expected":

    pity_luck  per 5*, linear in pity and anchored per banner on the expected pity
               E = 100 / consolidated 5* rate (e.g. 62.5 at 1.6%):
                   pity_luck = clip(50 + 50 * (E - pity) / (E - 1), 0, 100)
                   -> pull 1 = 100, pity E = 50, later = lower (~28 at pity 90 on a 1.6% banner)
               averaged over all 5*. Being linear, its average over a player with
               exactly the expected pity is exactly 50 (verified by simulation).
               Banners without an `expected_rate_5` entry (e.g. Beginners) are left out.
    win_luck   per account, from the actual and the expected 5* rate-up win rate
               (expected = official rate-up chance of the banner of each pull,
               e.g. Character 50%, Weapon/Light Cone 75%):
                   0 wins -> 0,   expected rate -> 50,   all wins -> 100
    luck_score = 0.6 * pity_luck + 0.4 * win_luck   (re-weighted if one is missing)
"""

import numpy as np
import pandas as pd

if __package__:  # imported as part of the package (dashboard.py) ...
    from .config import GameConfig
else:  # ... or run as a script from pipeline/
    from config import GameConfig

PITY_WEIGHT = 0.6
WIN_WEIGHT = 0.4


def pity_luck_values(pity, expected) -> np.ndarray:
    """Pity luck per 5* on a 0-100 scale: 100 at pull 1, 50 at the `expected` pity, linear in between and beyond."""
    p = np.maximum(np.asarray(pity, dtype=float), 1.0)
    exp = np.maximum(np.asarray(expected, dtype=float), 1.0 + 1e-9)
    return np.clip(50 + 50 * (exp - p) / (exp - 1), 0, 100)


def win_luck_value(actual_pct: float, expected_pct: float) -> float:
    """Rate-up win luck on a 0-100 scale: 0 at no wins, 50 at the expected win rate, 100 at all wins."""
    if not (pd.notna(actual_pct) and pd.notna(expected_pct)) or expected_pct <= 0:
        return float("nan")
    if actual_pct <= expected_pct or expected_pct >= 100:
        return 50 * actual_pct / expected_pct
    return 50 + 50 * (actual_pct - expected_pct) / (100 - expected_pct)


def compute_luck(df: pd.DataFrame, cfg: GameConfig) -> pd.DataFrame:
    five = df[df["is_5star"]].copy()
    banner = five["banner_type"].astype(object)
    rate = pd.to_numeric(banner.map(getattr(cfg, "expected_rate_5", {}) or {}), errors="coerce")
    five = five[rate.notna() & five["pity"].notna()].copy()    # banners without an expected rate are not scored
    banner, rate = banner.loc[five.index], rate.loc[five.index]
    five["pity_luck"] = pity_luck_values(five["pity"], 100.0 / rate)
    pity_by_acc = five.groupby("account")["pity_luck"].mean()

    dec = df[(df["rarity"] == 5) & df["win_50_50"].isin(["Win", "Lose"])].copy()
    dec["is_win"] = (dec["win_50_50"] == "Win").astype(float) * 100.0
    # to_numeric: on an empty selection map() can return a string column, which has no mean()/arithmetic
    dec["expected"] = pd.to_numeric(dec["banner_type"].astype(object).map(cfg.rateup_chance), errors="coerce").fillna(50.0)
    actual_by_acc = dec.groupby("account")["is_win"].mean()
    expected_by_acc = dec.groupby("account")["expected"].mean()

    rows = []
    for acc in df["account"].unique():
        pity_luck = pity_by_acc.get(acc, float("nan"))
        actual = actual_by_acc.get(acc, float("nan"))
        expected = expected_by_acc.get(acc, float("nan"))
        win_luck = win_luck_value(actual, expected)

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
