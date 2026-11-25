"""
03_radiance_check_gi.py
=======================
Checks the Genshin Character Event 50/50 results against the "Capturing Radiance"
counter model, per account. Data: data/data_clean_gi.csv (from 02_preprocess_gi.py).

Model (from the community diagram, NOT verified against official sources):
    a counter k = 0..3 counts lost 50/50s; chance to get the featured character
    at the next non-guaranteed 5*:  k=0: 50%   k=1: 50%   k=2: 75%   k=3: 100%
    a guaranteed pull (rate=2) is not a roll and does not change the counter.
    "Win" in the data = featured character (Radiance can't be told apart from a normal win).

Two variants of what a win does to the counter are compared, because sources differ:
    reset      win -> counter 0          (diagram; long-run win rate 55.17%)
    decrement  win -> counter - 1

For every account (only Character Event 5* pulls on/after --start, in time order):
    expected_model_pct  sum of the per-roll chances / rolls
    z                   (wins - expected) / sqrt(variance); roughly within +-2 = normal luck
    impossible_losses   losses at k=3 (chance 0%): the model contradicts the data
A model with impossible_losses > 0 does not fit your data (or the counter started elsewhere).

Usage:
    python3 pipeline/03_radiance_check_gi.py
    python3 pipeline/03_radiance_check_gi.py --input data/data_clean_gi_887284572.csv --start 2024-08-28
"""

import argparse
import math

import pandas as pd

from config import OUTPUT_DIR, default_clean_csv

P_WIN = [0.50, 0.50, 0.75, 1.00]   # chance to get the featured character at counter 0..3
LAUNCH = "2024-08-28"              # Genshin 5.0 release (Capturing Radiance); check this date
MODES = ("reset", "decrement")


def next_counter(k: int, won: bool, mode: str) -> int:
    if won:
        return 0 if mode == "reset" else max(k - 1, 0)
    return min(k + 1, len(P_WIN) - 1)


def run_model(wins: list, mode: str) -> dict:
    k, expected, var, impossible = 0, 0.0, 0.0, 0
    states = [0] * len(P_WIN)
    for won in wins:
        p = P_WIN[k]
        states[k] += 1
        expected += p
        var += p * (1 - p)
        if not won and p == 1.0:
            impossible += 1
        k = next_counter(k, won, mode)
    n = len(wins)
    actual = sum(wins)
    return {
        "model": mode, "rolls": n, "wins": actual,
        "actual_pct": round(100 * actual / n, 1),
        "expected_model_pct": round(100 * expected / n, 1),
        "z": round((actual - expected) / math.sqrt(var), 2) if var > 0 else float("nan"),
        "impossible_losses": impossible,
        **{f"rolls_at_k{i}": c for i, c in enumerate(states)},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--input", default=str(default_clean_csv("GI")))
    ap.add_argument("--start", default=LAUNCH, help=f"first date to include (default {LAUNCH})")
    ap.add_argument("--outdir", default=str(OUTPUT_DIR / "gi"))
    args = ap.parse_args()

    df = pd.read_csv(args.input, parse_dates=["datetime"])
    df = df[(df["banner_type"] == "Character Event") & (df["rarity"] == 5) & (df["datetime"] >= args.start)]
    df = df[df["win_50_50"].isin(["Win", "Lose", "Guaranteed"])]
    if df.empty:
        raise SystemExit("No Character Event 5* rows with 50/50 data on/after the start date.")

    rows = []
    for acc, g in df.sort_values(["datetime", "pull_number"]).groupby("account", sort=False):
        labels = g["win_50_50"].tolist()
        rolls = [l == "Win" for l in labels if l != "Guaranteed"]
        if not rolls:
            continue
        broken = sum(1 for i, l in enumerate(labels[:-1]) if l == "Lose" and labels[i + 1] != "Guaranteed")
        flat50 = round(100 * sum(rolls) / len(rolls) - 50, 1)
        for mode in MODES:
            r = run_model(rolls, mode)
            rows.append({"account": acc, **r, "actual_minus_flat50_pp": flat50,
                         "lose_not_followed_by_guaranteed": broken})

    out = pd.DataFrame(rows)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(f"Character Event 5*, on/after {args.start}  (Win = featured character, Guaranteed rows skipped)\n")
    print(out.to_string(index=False))
    from pathlib import Path
    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    path = Path(args.outdir) / "08_radiance_check.csv"
    out.to_csv(path, index=False)
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
