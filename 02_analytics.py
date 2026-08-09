"""
02_analytics.py
=================
Analytics / EDA pipeline: data_clean.csv -> summary CSV + chart PNG.

Generates 7 insights for the storytelling dashboard, in this order:
    1. Total Pull & Account Progress
    2. Wish Timeline
    3. 5-Star Pity Distribution
    4. Win/Lose 50-50
    5. Top Character & Top Weapon
    6. Banner Performance
    7. Luck Score

Each insight produces a matching pair of files in the outputs/ folder:
    <number>_<insight_name>.csv   -> summary table (reusable)
    <number>_<insight_name>.png   -> ready-to-use chart

Usage:
    python3 02_analytics.py                       # uses data/data_clean.csv
    python3 02_analytics.py --input data/data_clean_887284572.csv --outdir outputs_887284572
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Hard pity per banner (official Genshin Impact reference) -- used for the Luck Score.
# The Weapon Event pity ceiling varies between game versions (77-80); we use 77 as a general reference.
HARD_PITY = {
    "Character Event": 90,
    "Standard": 90,
    "Weapon Event": 77,
    "Beginners": 20,
}

RARITY_COLORS = {5: "#c98a3e", 4: "#a256c9", 3: "#5b8fd6"}
BANNER_ORDER = ["Character Event", "Weapon Event", "Standard", "Beginners"]
BANNER_COLORS = {
    "Character Event": "#c98a3e",
    "Weapon Event": "#5b8fd6",
    "Standard": "#6bbf7b",
    "Beginners": "#c9576a",
}

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#444444",
        "axes.labelcolor": "#222222",
        "text.color": "#222222",
        "xtick.color": "#444444",
        "ytick.color": "#444444",
        "font.size": 10,
        "axes.grid": True,
        "grid.color": "#e6e6e6",
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
    }
)


def savefig(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  [png] {path}")


def save_csv(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False)
    print(f"  [csv] {path}")


# ---------------------------------------------------------------------------
# 1. Total Pull & Account Progress
# ---------------------------------------------------------------------------
def insight_total_pull(df: pd.DataFrame, outdir: Path):
    print("\n[1] Total Pull & Account Progress")

    summary = (
        df.groupby("account")
        .agg(
            uid=("uid", "first"),
            adventure_rank=("adventure_rank", "first"),
            world_level=("world_level", "first"),
            total_pull=("item_id", "count"),
            pull_5star=("is_5star", "sum"),
            pull_4star=("is_4star", "sum"),
            pull_3star=("is_3star", "sum"),
            first_pull=("datetime", "min"),
            last_pull=("datetime", "max"),
        )
        .reset_index()
    )
    summary["pct_5star"] = (summary["pull_5star"] / summary["total_pull"] * 100).round(2)
    summary["pct_4star"] = (summary["pull_4star"] / summary["total_pull"] * 100).round(2)

    save_csv(summary, outdir / "01_total_pull_progress_akun.csv")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # Left: total pulls per account (stacked by rarity)
    ax = axes[0]
    x = range(len(summary))
    bottom = [0] * len(summary)
    for rarity, label, col in [(3, "3\u2605", RARITY_COLORS[3]), (4, "4\u2605", RARITY_COLORS[4]), (5, "5\u2605", RARITY_COLORS[5])]:
        vals = summary[f"pull_{rarity}star"].tolist()
        ax.bar(x, vals, bottom=bottom, label=label, color=col)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(list(x))
    ax.set_xticklabels(summary["account"])
    ax.set_ylabel("Pull Count")
    ax.set_title("Total Pulls per Account (rarity breakdown)")
    ax.legend()

    # Right: AR & WL per account
    ax2 = axes[1]
    width = 0.35
    ax2.bar([i - width / 2 for i in x], summary["adventure_rank"], width, label="Adventure Rank", color="#c98a3e")
    ax2.bar([i + width / 2 for i in x], summary["world_level"], width, label="World Level", color="#5b8fd6")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(summary["account"])
    ax2.set_title("Account Progress (AR & WL)")
    ax2.legend()

    fig.suptitle("Total Pull & Account Progress", fontsize=13, fontweight="bold")
    savefig(fig, outdir / "01_total_pull_progress_akun.png")

    return summary


# ---------------------------------------------------------------------------
# 2. Wish Timeline
# ---------------------------------------------------------------------------
def insight_timeline(df: pd.DataFrame, outdir: Path):
    print("\n[2] Wish Timeline")

    timeline = (
        df.groupby(["year_month", "banner_type"])
        .size()
        .reset_index(name="pull_count")
        .sort_values("year_month")
    )
    save_csv(timeline, outdir / "02_timeline_wish.csv")

    pivot = timeline.pivot(index="year_month", columns="banner_type", values="pull_count").fillna(0)
    pivot = pivot.reindex(columns=[b for b in BANNER_ORDER if b in pivot.columns])

    fig, ax = plt.subplots(figsize=(12, 5))
    bottom = [0] * len(pivot)
    x = range(len(pivot))
    for banner in pivot.columns:
        ax.bar(x, pivot[banner], bottom=bottom, label=banner, color=BANNER_COLORS.get(banner, "#999999"))
        bottom = [b + v for b, v in zip(bottom, pivot[banner])]

    ax.set_xticks(list(x))
    ax.set_xticklabels(pivot.index, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("Pull Count")
    ax.set_title("Monthly Wish Timeline (banner breakdown)", fontsize=13, fontweight="bold")
    ax.legend()

    savefig(fig, outdir / "02_timeline_wish.png")
    return timeline


# ---------------------------------------------------------------------------
# 3. 5-Star Pity Distribution
# ---------------------------------------------------------------------------
def insight_pity_distribution(df: pd.DataFrame, outdir: Path):
    print("\n[3] 5\u2605 Pity Distribution")

    five_star = df[df["is_5star"]].copy()
    detail = five_star[["account", "banner_type", "datetime", "item_name", "item_category", "pity", "win_50_50"]].sort_values(
        "datetime"
    )
    save_csv(detail, outdir / "03_pity_distribution_5star.csv")

    banners = [b for b in BANNER_ORDER if b in five_star["banner_type"].unique()]

    # BUG FIX: plt.subplots(1, 0, ...) raises ValueError when there are no
    # 5-star pulls at all (e.g. a fresh/small filtered account). Guard against it.
    if not banners:
        print("  [skip] No 5-star pulls found, skipping pity distribution chart.")
        summary = pd.DataFrame(columns=["banner_type", "count", "mean", "median", "min", "max", "std"])
        save_csv(summary, outdir / "03_pity_distribution_5star_summary.csv")
        return detail

    fig, axes = plt.subplots(1, len(banners), figsize=(4.2 * len(banners), 4.3), sharey=True)
    if len(banners) == 1:
        axes = [axes]

    for ax, banner in zip(axes, banners):
        vals = five_star.loc[five_star["banner_type"] == banner, "pity"]
        ax.hist(vals, bins=range(0, HARD_PITY.get(banner, 90) + 5, 5), color=BANNER_COLORS.get(banner, "#999999"), edgecolor="white")
        ax.axvline(vals.mean(), color="#222222", linestyle="--", linewidth=1.2, label=f"mean = {vals.mean():.1f}")
        ax.set_title(banner)
        ax.set_xlabel("Pity at 5\u2605")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("5\u2605 pull count")

    fig.suptitle("5\u2605 Pity Distribution per Banner", fontsize=13, fontweight="bold")
    savefig(fig, outdir / "03_pity_distribution_5star.png")

    summary = five_star.groupby("banner_type")["pity"].agg(["count", "mean", "median", "min", "max", "std"]).round(2)
    save_csv(summary.reset_index(), outdir / "03_pity_distribution_5star_summary.csv")
    return detail


# ---------------------------------------------------------------------------
# 4. Win/Lose 50-50
# ---------------------------------------------------------------------------
def insight_win_lose(df: pd.DataFrame, outdir: Path):
    print("\n[4] Win/Lose 50-50")

    rate_df = df[df["win_50_50"].notna()].copy()
    summary = (
        rate_df.groupby(["banner_type", "rarity", "win_50_50"])
        .size()
        .reset_index(name="count")
    )
    save_csv(summary, outdir / "04_win_lose_50_50.csv")

    # win rate = Win / (Win + Lose); Guaranteed is excluded from the rate calculation
    decisive = rate_df[rate_df["win_50_50"].isin(["Win", "Lose"])]
    win_rate = (
        decisive.groupby(["banner_type", "rarity"])["win_50_50"]
        .apply(lambda s: (s == "Win").mean() * 100)
        .reset_index(name="win_rate_pct")
    )
    save_csv(win_rate, outdir / "04_win_rate_summary.csv")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # Left: stacked bar of Win/Lose/Guaranteed per banner+rarity
    ax = axes[0]
    pivot = summary.pivot_table(index=["banner_type", "rarity"], columns="win_50_50", values="count", fill_value=0)
    pivot = pivot.reindex(columns=[c for c in ["Win", "Lose", "Guaranteed"] if c in pivot.columns])
    labels = [f"{b}\n{r}\u2605" for b, r in pivot.index]
    bottom = [0] * len(pivot)
    colors = {"Win": "#6bbf7b", "Lose": "#c9576a", "Guaranteed": "#c9a13e"}
    x = range(len(pivot))
    for col in pivot.columns:
        vals = pivot[col].tolist()
        ax.bar(x, vals, bottom=bottom, label=col, color=colors.get(col))
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Pull count")
    ax.set_title("Win / Lose / Guaranteed Composition")
    ax.legend()

    # Right: win rate %
    ax2 = axes[1]
    labels2 = [f"{b}\n{r}\u2605" for b, r in zip(win_rate["banner_type"], win_rate["rarity"])]
    bars = ax2.bar(labels2, win_rate["win_rate_pct"], color="#6bbf7b")
    ax2.axhline(50, color="#222222", linestyle="--", linewidth=1, label="50% baseline")
    ax2.set_ylabel("Win rate (%)")
    ax2.set_title("50/50 Win Rate (Win vs Lose only)")
    ax2.set_ylim(0, 100)
    ax2.legend()
    for b, v in zip(bars, win_rate["win_rate_pct"]):
        if pd.notna(v):
            ax2.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.0f}%", ha="center", fontsize=8)

    fig.suptitle("Win/Lose 50-50", fontsize=13, fontweight="bold")
    savefig(fig, outdir / "04_win_lose_50_50.png")

    return summary


# ---------------------------------------------------------------------------
# 5. Top Character & Top Weapon
# ---------------------------------------------------------------------------
def insight_top_items(df: pd.DataFrame, outdir: Path, top_n: int = 10):
    print("\n[5] Top Character & Top Weapon")

    def top_table(category, min_rarity):
        sub = df[(df["item_category"] == category) & (df["rarity"] >= min_rarity)]
        table = (
            sub.groupby(["item_name", "rarity"])
            .size()
            .reset_index(name="count_obtained")
            .sort_values("count_obtained", ascending=False)
        )
        return table

    top_char = top_table("character", 4)
    top_weapon = top_table("weapon", 4)

    save_csv(top_char, outdir / "05_top_character.csv")
    save_csv(top_weapon, outdir / "05_top_weapon.csv")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, table, title in [
        (axes[0], top_char.head(top_n), "Top Character (4\u2605 & 5\u2605)"),
        (axes[1], top_weapon.head(top_n), "Top Weapon (4\u2605 & 5\u2605)"),
    ]:
        table = table.iloc[::-1]  # reverse order so the horizontal bars read top-to-bottom by rank
        colors = [RARITY_COLORS.get(r, "#999999") for r in table["rarity"]]
        ax.barh(table["item_name"], table["count_obtained"], color=colors)
        ax.set_title(title)
        ax.set_xlabel("Count obtained")
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    fig.suptitle("Top Character & Top Weapon", fontsize=13, fontweight="bold")
    savefig(fig, outdir / "05_top_character_weapon.png")

    return top_char, top_weapon


# ---------------------------------------------------------------------------
# 6. Banner Performance
# ---------------------------------------------------------------------------
def insight_banner_performance(df: pd.DataFrame, outdir: Path):
    print("\n[6] Banner Performance")

    perf = (
        df.groupby("banner_type")
        .agg(
            total_pull=("item_id", "count"),
            pull_5star=("is_5star", "sum"),
            pull_4star=("is_4star", "sum"),
        )
        .reset_index()
    )
    perf["pull_per_5star"] = (perf["total_pull"] / perf["pull_5star"].replace(0, float("nan"))).round(1)
    perf["rate_5star_pct"] = (perf["pull_5star"] / perf["total_pull"] * 100).round(2)

    decisive = df[df["win_50_50"].isin(["Win", "Lose"]) & (df["rarity"] == 5)]
    winrate = (
        decisive.groupby("banner_type")["win_50_50"]
        .apply(lambda s: round((s == "Win").mean() * 100, 2))
        .rename("win_rate_5star_pct")
        .reset_index()
    )
    perf = perf.merge(winrate, on="banner_type", how="left")
    perf["banner_type"] = pd.Categorical(perf["banner_type"], categories=BANNER_ORDER, ordered=True)
    perf = perf.sort_values("banner_type")

    save_csv(perf, outdir / "06_banner_performance.csv")

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

    axes[0].bar(perf["banner_type"], perf["total_pull"], color=[BANNER_COLORS.get(b, "#999") for b in perf["banner_type"]])
    axes[0].set_title("Total Pulls per Banner")
    axes[0].set_ylabel("Pull count")
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].bar(perf["banner_type"], perf["pull_per_5star"], color=[BANNER_COLORS.get(b, "#999") for b in perf["banner_type"]])
    axes[1].set_title('Most "Expensive" Banner\n(pulls needed per 5\u2605)')
    axes[1].set_ylabel("Pulls per 5\u2605")
    axes[1].tick_params(axis="x", rotation=20)

    # BUG FIX: banners with no decisive Win/Lose rows (e.g. Standard) get
    # win_rate_5star_pct = NaN after the left-merge, which drew as an empty,
    # unexplained gap. Fill with 0 for plotting and label those bars "N/A".
    win_rate_plot = perf["win_rate_5star_pct"].fillna(0)
    bars = axes[2].bar(perf["banner_type"], win_rate_plot, color=[BANNER_COLORS.get(b, "#999") for b in perf["banner_type"]])
    for bar, original in zip(bars, perf["win_rate_5star_pct"]):
        if pd.isna(original):
            axes[2].text(bar.get_x() + bar.get_width() / 2, 2, "N/A", ha="center", fontsize=8, color="#666666")
    axes[2].axhline(50, color="#222222", linestyle="--", linewidth=1)
    axes[2].set_title("50/50 Win Rate (5\u2605) per Banner")
    axes[2].set_ylabel("Win rate (%)")
    axes[2].set_ylim(0, 100)
    axes[2].tick_params(axis="x", rotation=20)

    fig.suptitle("Banner Performance", fontsize=13, fontweight="bold")
    savefig(fig, outdir / "06_banner_performance.png")

    return perf


# ---------------------------------------------------------------------------
# 7. Luck Score
# ---------------------------------------------------------------------------
def insight_luck_score(df: pd.DataFrame, outdir: Path):
    print("\n[7] Luck Score")

    five_star = df[df["is_5star"]].copy()
    five_star["hard_pity"] = five_star["banner_type"].map(HARD_PITY).fillna(90)
    # pity_luck: 100 if obtained on pull #1, 0 if obtained exactly at hard pity. Can exceed 100 if better than expected.
    five_star["pity_luck"] = (1 - (five_star["pity"] - 1) / (five_star["hard_pity"] - 1)) * 100

    pity_luck_by_account = five_star.groupby("account")["pity_luck"].mean()

    decisive = df[df["win_50_50"].isin(["Win", "Lose"])]
    winrate_by_account = decisive.groupby("account")["win_50_50"].apply(lambda s: (s == "Win").mean() * 100)

    accounts = df["account"].unique()
    rows = []
    for acc in accounts:
        pity_luck = pity_luck_by_account.get(acc, float("nan"))
        winrate = winrate_by_account.get(acc, float("nan"))
        # Weights: 60% pity luck, 40% win-rate luck (normalized so a 50% baseline win rate scores 50)
        weights = []
        if pd.notna(pity_luck):
            weights.append((pity_luck, 0.6))
        if pd.notna(winrate):
            weights.append((winrate, 0.4))
        if weights:
            total_w = sum(w for _, w in weights)
            luck_score = sum(v * w for v, w in weights) / total_w
        else:
            luck_score = float("nan")

        rows.append(
            {
                "account": acc,
                "avg_pity_luck": round(pity_luck, 1) if pd.notna(pity_luck) else None,
                "win_rate_pct": round(winrate, 1) if pd.notna(winrate) else None,
                "luck_score": round(luck_score, 1) if pd.notna(luck_score) else None,
            }
        )

    luck_df = pd.DataFrame(rows).sort_values("luck_score", ascending=False)
    save_csv(luck_df, outdir / "07_luck_score.csv")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(luck_df["account"], luck_df["luck_score"], color="#c98a3e")
    ax.axhline(50, color="#222222", linestyle="--", linewidth=1, label="neutral baseline = 50")
    ax.set_ylabel("Luck Score (0-100+)")
    ax.set_title("Luck Score per Account\n(60% pity efficiency + 40% 50/50 win rate)", fontsize=12, fontweight="bold")
    ax.legend()
    for b, v in zip(bars, luck_df["luck_score"]):
        if pd.notna(v):
            ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}", ha="center", fontsize=9)

    savefig(fig, outdir / "07_luck_score.png")

    return luck_df


# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Analytics/EDA from data_clean.csv")
    parser.add_argument("--input", type=str, default=str(DATA_DIR / "data_clean.csv"), help="Path to the data_clean CSV file")
    parser.add_argument("--outdir", type=str, default=None, help="Output folder (default: outputs/ next to the project)")
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}. Run 01_preprocessing.py first.")

    outdir = Path(args.outdir) if args.outdir else BASE_DIR / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Reading: {input_path}")
    df = pd.read_csv(input_path)
    df["datetime"] = pd.to_datetime(df["datetime"])

    insight_total_pull(df, outdir)
    insight_timeline(df, outdir)
    insight_pity_distribution(df, outdir)
    insight_win_lose(df, outdir)
    insight_top_items(df, outdir)
    insight_banner_performance(df, outdir)
    insight_luck_score(df, outdir)

    print(f"\nAll insights saved to: {outdir}")


if __name__ == "__main__":
    main()