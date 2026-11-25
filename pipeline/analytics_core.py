"""
analytics_core.py
=================
Analytics engine for Genshin Impact and Honkai: Star Rail (merged from the former
03_analytics_gi.py, 03_analytics_hsr.py and 03_radiance_check_gi.py).

Both games run through exactly the same code, so the chart style and the
Luck Score formula are identical. Only the GameConfig differs.

Insights (same order as the dashboard storytelling):
    1. Total Pull & Account Progress
    2. Timeline
    3. 5-Star Pity Distribution
    4. Win/Lose 50-50
    5. Top Character & Top Weapon / Light Cone
    6. Banner Performance
    7. Luck Score
    8. Radiance check (Genshin only)

Luck Score (identical for both games; implemented in luck.py, 50 = exactly as expected):
    pity_luck  = clip(50 + 50 * (E - pity) / (E - 1), 0, 100), averaged over 5* pulls,
                 E = 100 / consolidated 5* rate of the banner (expected_rate_5 in config.py);
                 banners without an expected rate (Beginners) are not scored
    win_luck   = 0 with no wins, 50 at the expected rate-up win rate, 100 with all wins;
                 the expected rate is the official rate-up chance of the banner of each pull
                 (e.g. Character 50%, Weapon/Light Cone 75%)
    luck_score = 0.6 * pity_luck + 0.4 * win_luck   (re-weighted if one is missing)
"""

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

if __package__:  # imported as part of the package (dashboard.py, python -m pipeline) ...
    from .config import GAMES, OUTPUT_DIR, GameConfig, default_clean_csv
    from .luck import compute_luck
else:  # ... or run as a script from pipeline/
    from config import GAMES, OUTPUT_DIR, GameConfig, default_clean_csv
    from luck import compute_luck

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
INK = "#1F2933"
MUTED = "#6B7280"
GRID = "#E5E7EB"
AXIS = "#9CA3AF"

RARITY_COLORS = {5: "#D9A441", 4: "#8E6BBF", 3: "#6C8EBF"}
OUTCOME_COLORS = {"Win": "#4C9F70", "Lose": "#C8553D", "Guaranteed": "#E0B04A"}
LUCK_COLORS = {"pity": "#5B8FD6", "win": "#4C9F70", "score": "#D9A441"}

LOW_SAMPLE = 5  # fewer decisive Win/Lose outcomes than this -> bar is faded


@dataclass
class Context:
    cfg: GameConfig
    subtitle: str
    footer: str


def apply_theme():
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": INK,
            "axes.labelsize": 9.5,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 10,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "font.size": 10,
            "legend.frameon": False,
            "legend.fontsize": 9,
        }
    )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def make_context(df: pd.DataFrame, cfg: GameConfig) -> Context:
    n_acc = df["account"].nunique()
    subtitle = (
        f"{cfg.title}   \u00b7   {len(df):,} {cfg.pull_word.lower()}s   \u00b7   "
        f"{n_acc} account{'s' if n_acc != 1 else ''}   \u00b7   "
        f"{df['datetime'].min():%b %Y} \u2013 {df['datetime'].max():%b %Y}"
    )
    footer = f"Source: {cfg.source_label}   \u00b7   Data through {df['datetime'].max():%d %b %Y}"
    return Context(cfg, subtitle, footer)


def save_csv(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False)
    print(f"  [csv] {path}")


def finish(fig, path: Path, ctx: Context, title: str, note: str = None):
    """Left-aligned title + subtitle (+ optional note) at the top, source footer at the bottom."""
    _, h = fig.get_size_inches()
    fig.text(0.004, 1 - 0.14 / h, title, ha="left", va="top", fontsize=15, fontweight="bold", color=INK)
    fig.text(0.004, 1 - 0.54 / h, ctx.subtitle, ha="left", va="top", fontsize=9.5, color=MUTED)
    top = 0.95
    if note:
        fig.text(0.004, 1 - 0.80 / h, note, ha="left", va="top", fontsize=8.5, color=MUTED, style="italic")
        top = 1.2
    fig.text(0.004, 0.14 / h, ctx.footer, ha="left", va="bottom", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.5 / h, 1, 1 - top / h))
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"  [png] {path}")


def banner_index(cfg: GameConfig, banner: str) -> int:
    return cfg.banner_order.index(banner) if banner in cfg.banner_order else len(cfg.banner_order)


def sort_banners(cfg: GameConfig, banners):
    return sorted(banners, key=lambda b: banner_index(cfg, b))


def vgrid(ax):
    """Horizontal-bar charts: light vertical grid instead of horizontal."""
    ax.grid(axis="x", visible=True)
    ax.grid(axis="y", visible=False)


def int_axis(axis):
    axis.set_major_locator(mticker.MaxNLocator(integer=True))


def label_h(ax, bars, values, fmt="{:,.0f}", pad=4):
    for b, v in zip(bars, values):
        if pd.isna(v):
            continue
        ax.annotate(fmt.format(v), (b.get_width(), b.get_y() + b.get_height() / 2),
                    xytext=(pad, 0), textcoords="offset points", va="center", ha="left",
                    fontsize=8.5, color=INK)


def label_v(ax, bars, values, fmt="{:,.0f}", pad=3):
    for b, v in zip(bars, values):
        if pd.isna(v):
            continue
        ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, pad), textcoords="offset points", va="bottom", ha="center",
                    fontsize=8.5, color=INK)


def row_label(banner: str, rarity) -> str:
    # int(): rarity is 5.0 (float) when the CSV has rows without a rarity mapping
    return f"{banner}  \u00b7  {int(rarity)}\u2605"


# ---------------------------------------------------------------------------
# 1. Total Pull & Account Progress
# ---------------------------------------------------------------------------
def insight_total_pull(df, outdir, ctx):
    print("\n[1] Total Pull & Account Progress")
    cfg = ctx.cfg

    agg = {}
    for col in ("uid", "adventure_rank", "world_level", "profile_key"):
        if col in df.columns:
            agg[col] = (col, "first")
    agg.update(
        total_pull=("item_id", "count"),
        pull_5star=("is_5star", "sum"),
        pull_4star=("is_4star", "sum"),
        pull_3star=("is_3star", "sum"),
        first_pull=("datetime", "min"),
        last_pull=("datetime", "max"),
    )
    summary = df.groupby("account").agg(**agg).reset_index()
    summary["pct_5star"] = (summary["pull_5star"] / summary["total_pull"] * 100).round(2)
    summary["pct_4star"] = (summary["pull_4star"] / summary["total_pull"] * 100).round(2)
    save_csv(summary, outdir / "01_total_pull_progress.csv")

    has_progress = (
        {"adventure_rank", "world_level"} <= set(summary.columns)
        and summary["adventure_rank"].notna().any()
    )

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5))
    x = np.arange(len(summary))

    # Left: total pulls per account, stacked by rarity
    ax = axes[0]
    bottom = np.zeros(len(summary))
    for r in (3, 4, 5):
        vals = summary[f"pull_{r}star"].to_numpy(float)
        ax.bar(x, vals, 0.55, bottom=bottom, color=RARITY_COLORS[r], label=f"{r}\u2605")
        bottom += vals
    for xi, total in zip(x, summary["total_pull"]):
        ax.annotate(f"{total:,}", (xi, total), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=10, fontweight="bold", color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(summary["account"])
    ax.set_ylabel(f"{cfg.pull_word}s")
    ax.set_ylim(0, summary["total_pull"].max() * 1.12)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_title(f"Total {cfg.pull_word}s by Rarity")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=3)

    # Right: AR & WL (if the export has them) otherwise 5*/4* rate
    ax2 = axes[1]
    w = 0.34
    if has_progress:
        b1 = ax2.bar(x - w / 2, summary["adventure_rank"], w, color="#D9A441", label="Adventure Rank")
        b2 = ax2.bar(x + w / 2, summary["world_level"], w, color="#5B8FD6", label="World Level")
        label_v(ax2, b1, summary["adventure_rank"])
        label_v(ax2, b2, summary["world_level"])
        ax2.set_title("Account Progress")
        ax2.set_ylabel("Level")
    else:
        b1 = ax2.bar(x - w / 2, summary["pct_5star"], w, color=RARITY_COLORS[5], label="5\u2605 rate")
        b2 = ax2.bar(x + w / 2, summary["pct_4star"], w, color=RARITY_COLORS[4], label="4\u2605 rate")
        for bars, pct, cnt in ((b1, summary["pct_5star"], summary["pull_5star"]), (b2, summary["pct_4star"], summary["pull_4star"])):
            for b, p, c in zip(bars, pct, cnt):
                ax2.annotate(f"{p:.2f}%\n({int(c)})", (b.get_x() + b.get_width() / 2, b.get_height()),
                             xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                             fontsize=8.5, color=INK)
        ax2.set_ylim(0, max(summary["pct_4star"].max(), summary["pct_5star"].max()) * 1.25)
        ax2.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
        ax2.set_title("5\u2605 & 4\u2605 Rate per Account")
        ax2.set_ylabel(f"Share of {cfg.pull_word.lower()}s")
    ax2.set_xticks(x)
    ax2.set_xticklabels(summary["account"])
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2)

    finish(fig, outdir / "01_total_pull_progress.png", ctx, "Total Pull & Account Progress")
    return summary


# ---------------------------------------------------------------------------
# 2. Timeline
# ---------------------------------------------------------------------------
def insight_timeline(df, outdir, ctx):
    print(f"\n[2] {ctx.cfg.pull_word} Timeline")
    cfg = ctx.cfg

    timeline = (
        df.groupby(["year_month", "banner_type"]).size().reset_index(name="pull_count").sort_values("year_month")
    )
    save_csv(timeline, outdir / "02_timeline.csv")

    pivot = timeline.pivot(index="year_month", columns="banner_type", values="pull_count").fillna(0)
    pivot = pivot.reindex(columns=[b for b in cfg.banner_order if b in pivot.columns])
    # continuous month axis: months with no pulls show as empty instead of being skipped
    months = pd.period_range(pivot.index.min(), pivot.index.max(), freq="M").astype(str)
    pivot = pivot.reindex(months, fill_value=0)

    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    x = np.arange(len(pivot))
    bottom = np.zeros(len(pivot))
    for banner in pivot.columns:
        vals = pivot[banner].to_numpy(float)
        ax.bar(x, vals, 0.75, bottom=bottom, label=banner, color=cfg.banner_colors.get(banner, "#999999"))
        bottom += vals
    if len(pivot) <= 30:
        for xi, total in zip(x, bottom):
            if total > 0:
                ax.annotate(f"{int(total):,}", (xi, total), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=7.5, color=MUTED)

    step = max(1, math.ceil(len(pivot) / 18))
    ticks = list(range(0, len(pivot), step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Period(pivot.index[i], "M").strftime("%b '%y") for i in ticks], rotation=45, ha="right")
    ax.set_ylabel(f"{cfg.pull_word}s per month")
    ax.set_ylim(0, bottom.max() * 1.12)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_title(f"Monthly {cfg.pull_word}s by Banner")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))

    finish(fig, outdir / "02_timeline.png", ctx, f"{cfg.pull_word} Timeline")
    return timeline


# ---------------------------------------------------------------------------
# 3. 5-Star Pity Distribution
# ---------------------------------------------------------------------------
def insight_pity_distribution(df, outdir, ctx):
    print("\n[3] 5\u2605 Pity Distribution")
    cfg = ctx.cfg

    five = df[df["is_5star"]].copy()
    detail = five[["account", "banner_type", "datetime", "item_name", "item_category", "pity", "win_50_50"]].sort_values("datetime")
    save_csv(detail, outdir / "03_pity_distribution_5star.csv")

    # only banners that have at least one 5* with a pity value (int(NaN) / hist of nothing would fail)
    with_pity = five.loc[five["pity"].notna(), "banner_type"].unique()
    banners = [b for b in cfg.banner_order if b in with_pity]
    if not banners:
        print("  [skip] No 5-star pulls found, skipping pity distribution chart.")
        save_csv(pd.DataFrame(columns=["banner_type", "count", "mean", "median", "min", "max", "std"]),
                 outdir / "03_pity_distribution_5star_summary.csv")
        return detail

    n = len(banners)
    ncols = min(3, n)
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.7 * nrows), sharey=True, squeeze=False)
    flat = axes.flatten()

    for ax, banner in zip(flat, banners):
        vals = five.loc[five["banner_type"] == banner, "pity"].dropna()
        hard = cfg.hard_pity.get(banner, cfg.default_hard_pity)
        limit = (getattr(cfg, "pull_limit", None) or {}).get(banner)
        reach = min(hard, limit) if limit else hard   # Beginners: the pull limit, not the 5* hard pity
        upper = max(reach, int(vals.max())) + 5
        color = cfg.banner_colors.get(banner, "#999999")
        ax.hist(vals, bins=range(0, upper, 5), color=color, edgecolor="white", linewidth=0.8)
        ax.axvline(vals.mean(), color=INK, linestyle="--", linewidth=1.3, label=f"mean {vals.mean():.1f}")
        if hard <= reach:
            ax.axvline(hard, color=MUTED, linestyle=":", linewidth=1.3, label=f"hard pity {hard}")
        ax.set_xlim(0, upper)
        ax.set_title(f"{banner}  (n={len(vals)})")
        ax.set_xlabel("Pity at 5\u2605")
        int_axis(ax.yaxis)
        ax.legend(loc="upper left", fontsize=8)
    for ax in flat[n:]:
        ax.set_visible(False)
    for r in range(nrows):
        axes[r][0].set_ylabel("5\u2605 count")

    finish(fig, outdir / "03_pity_distribution_5star.png", ctx, "5\u2605 Pity Distribution")

    summary = five.groupby("banner_type")["pity"].agg(["count", "mean", "median", "min", "max", "std"]).round(2)
    summary = summary.reindex(sort_banners(cfg, summary.index))
    save_csv(summary.reset_index(), outdir / "03_pity_distribution_5star_summary.csv")
    return detail


# ---------------------------------------------------------------------------
# 4. Win/Lose 50-50
# ---------------------------------------------------------------------------
def insight_win_lose(df, outdir, ctx):
    print("\n[4] Win/Lose 50-50")
    cfg = ctx.cfg

    rate_df = df[df["win_50_50"].notna()].copy()
    summary = rate_df.groupby(["banner_type", "rarity", "win_50_50"]).size().reset_index(name="count")
    save_csv(summary, outdir / "04_win_lose_50_50.csv")

    # win rate = Win / (Win + Lose); Guaranteed is excluded from the rate calculation
    decisive = rate_df[rate_df["win_50_50"].isin(["Win", "Lose"])].copy()
    decisive["is_win"] = (decisive["win_50_50"] == "Win").astype(float)
    win_rate = (
        decisive.groupby(["banner_type", "rarity"])
        .agg(n_decisive=("is_win", "size"), win_rate_pct=("is_win", lambda s: s.mean() * 100))
        .reset_index()
    )
    win_rate["baseline_pct"] = [cfg.rateup_chance.get(b) if r == 5 else None
                                for b, r in zip(win_rate["banner_type"], win_rate["rarity"])]
    save_csv(win_rate, outdir / "04_win_rate_summary.csv")

    if summary.empty:
        print("  [skip] No Win/Lose data found, skipping 50-50 chart.")
        return summary

    keys = sorted(set(zip(summary["banner_type"], summary["rarity"])), key=lambda k: (banner_index(cfg, k[0]), -k[1]))
    counts = summary.pivot_table(index=["banner_type", "rarity"], columns="win_50_50", values="count", fill_value=0)
    wr = {(r.banner_type, r.rarity): r for r in win_rate.itertuples()}

    fig, axes = plt.subplots(1, 2, figsize=(13, 0.62 * len(keys) + 2.6), sharey=True)
    y = np.arange(len(keys))

    # Left: composition (% of 4*/5* pulls) of Win / Lose / Guaranteed
    ax = axes[0]
    left = np.zeros(len(keys))
    totals = np.array([counts.loc[k].sum() for k in keys], dtype=float)
    for outcome in ("Win", "Lose", "Guaranteed"):
        if outcome not in counts.columns:
            continue
        pct = np.array([counts.loc[k, outcome] / counts.loc[k].sum() * 100 for k in keys])
        ax.barh(y, pct, 0.62, left=left, color=OUTCOME_COLORS[outcome], label=outcome)
        for yi, (p, l0) in enumerate(zip(pct, left)):
            if p >= 9:
                ax.text(l0 + p / 2, yi, f"{p:.0f}%", ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")
        left += pct
    for yi, t in enumerate(totals):
        ax.text(101.5, yi, f"n={int(t)}", va="center", ha="left", fontsize=8.5, color=MUTED, clip_on=False)
    ax.set_xlim(0, 100)
    ax.set_yticks(y)
    ax.set_yticklabels([row_label(b, r) for b, r in keys])
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    vgrid(ax)
    ax.set_title("Outcome Composition")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=3)

    # Right: win rate with the official rate-up chance marked on the 5* rows
    ax2 = axes[1]
    for yi, k in enumerate(keys):
        row = wr.get(k)
        if row is None:
            ax2.text(1, yi, "N/A", va="center", fontsize=8.5, color=MUTED)
            continue
        faded = row.n_decisive < LOW_SAMPLE
        ax2.barh(yi, row.win_rate_pct, 0.62, color=OUTCOME_COLORS["Win"], alpha=0.4 if faded else 1.0)
        ax2.annotate(f"{row.win_rate_pct:.0f}%  (n={row.n_decisive})", (row.win_rate_pct, yi),
                     xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5, color=INK)
        if pd.notna(row.baseline_pct):
            ax2.plot([row.baseline_pct] * 2, [yi - 0.42, yi + 0.42], color=INK, linewidth=2)
    ax2.set_xlim(0, 118)
    ax2.set_xticks([0, 25, 50, 75, 100])
    ax2.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    vgrid(ax2)
    ax2.set_title("Rate-up Win Rate  (Win vs Lose only)")
    ax2.legend(handles=[Line2D([0], [0], color=INK, linewidth=2, label="Official 5\u2605 rate-up chance"),
                        Patch(facecolor=OUTCOME_COLORS["Win"], alpha=0.4, label=f"Fewer than {LOW_SAMPLE} outcomes")],
               loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2)

    finish(fig, outdir / "04_win_lose_50_50.png", ctx, "Win / Lose 50-50")
    return summary


# ---------------------------------------------------------------------------
# 5. Top Character & Top Weapon / Light Cone
# ---------------------------------------------------------------------------
def insight_top_items(df, outdir, ctx, top_n: int = 10):
    cfg = ctx.cfg
    print(f"\n[5] Top Character & Top {cfg.gear_label}")

    def top_table(category, min_rarity):
        sub = df[(df["item_category"] == category) & (df["rarity"] >= min_rarity)]
        return (
            sub.groupby(["item_name", "rarity"]).size().reset_index(name="count_obtained")
            .sort_values(["count_obtained", "rarity", "item_name"], ascending=[False, False, True])
            .reset_index(drop=True)
        )

    top_char = top_table("character", 4)
    top_gear = top_table(cfg.gear_category, 4)
    save_csv(top_char, outdir / "05_top_character.csv")
    save_csv(top_gear, outdir / f"05_top_{cfg.gear_category}.csv")

    fig, axes = plt.subplots(1, 2, figsize=(13, 0.5 * top_n + 2.6))
    for ax, table, title in ((axes[0], top_char.head(top_n), "Top Characters"),
                             (axes[1], top_gear.head(top_n), f"Top {cfg.gear_label}s")):
        ax.set_title(title)
        if table.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes, color=MUTED)
            ax.set_axis_off()
            continue
        t = table.iloc[::-1]
        bars = ax.barh(t["item_name"], t["count_obtained"], 0.66, color=[RARITY_COLORS.get(r, "#999999") for r in t["rarity"]])
        label_h(ax, bars, t["count_obtained"])
        ax.set_xlim(0, t["count_obtained"].max() * 1.12)
        int_axis(ax.xaxis)
        vgrid(ax)
        ax.set_xlabel("Times obtained")
    shown = set(top_char.head(top_n)["rarity"]) | set(top_gear.head(top_n)["rarity"])
    handles = [Patch(facecolor=RARITY_COLORS[r], label=f"{r}\u2605") for r in (5, 4) if r in shown]
    if handles:
        fig.legend(handles=handles, loc="lower center", ncol=len(handles), bbox_to_anchor=(0.5, 0.0))

    finish(fig, outdir / f"05_top_character_{cfg.gear_category}.png", ctx, f"Top Character & Top {cfg.gear_label}")
    return top_char, top_gear


# ---------------------------------------------------------------------------
# 6. Banner Performance
# ---------------------------------------------------------------------------
def insight_banner_performance(df, outdir, ctx):
    print("\n[6] Banner Performance")
    cfg = ctx.cfg

    perf = (
        df.groupby("banner_type")
        .agg(total_pull=("item_id", "count"), pull_5star=("is_5star", "sum"), pull_4star=("is_4star", "sum"))
        .reset_index()
    )
    perf["raw_pulls_per_5star"] = (perf["total_pull"] / perf["pull_5star"].replace(0, float("nan"))).round(1)
    # Efficiency = mean pity of the 5* obtained: unlike total pulls / 5* it leaves out the unfinished streak
    # after the last 5*, so it is not biased upward.
    pity5 = df[df["is_5star"]].groupby("banner_type")["pity"].mean().round(1).rename("pull_per_5star")
    perf = perf.merge(pity5, on="banner_type", how="left")
    rates = getattr(cfg, "expected_rate_5", None) or {}
    perf["expected_pull_per_5star"] = [round(100 / rates[b], 1) if rates.get(b) else float("nan") for b in perf["banner_type"]]
    perf["rate_5star_pct"] = (perf["pull_5star"] / perf["total_pull"] * 100).round(2)

    dec = df[df["win_50_50"].isin(["Win", "Lose"]) & (df["rarity"] == 5)]
    winrate = (
        dec.groupby("banner_type")["win_50_50"].apply(lambda s: round((s == "Win").mean() * 100, 2))
        .rename("win_rate_5star_pct").reset_index()
    )
    perf = perf.merge(winrate, on="banner_type", how="left")
    perf["baseline_5star_pct"] = pd.to_numeric(perf["banner_type"].map(cfg.rateup_chance), errors="coerce")
    perf["_o"] = perf["banner_type"].map(lambda b: banner_index(cfg, b))
    perf = perf.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    save_csv(perf, outdir / "06_banner_performance.csv")

    banners = perf["banner_type"].tolist()
    colors = [cfg.banner_colors.get(b, "#999999") for b in banners]
    y = np.arange(len(perf))

    fig, axes = plt.subplots(1, 3, figsize=(15, 0.62 * len(perf) + 2.8), sharey=True)

    ax = axes[0]
    bars = ax.barh(y, perf["total_pull"], 0.62, color=colors)
    label_h(ax, bars, perf["total_pull"])
    ax.set_xlim(0, perf["total_pull"].max() * 1.18)
    ax.set_yticks(y)
    ax.set_yticklabels(banners)
    ax.invert_yaxis()
    ax.set_title(f"Total {cfg.pull_word}s")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    vgrid(ax)

    ax = axes[1]
    vals = perf["pull_per_5star"]
    bars = ax.barh(y, vals.fillna(0), 0.62, color=colors)
    for yi, v, n5, exp in zip(y, vals, perf["pull_5star"], perf["expected_pull_per_5star"]):
        if pd.isna(v):
            ax.text(1, yi, "N/A", va="center", fontsize=8.5, color=MUTED)
        else:
            ax.annotate(f"{v:.1f} (n={int(n5)})", (v, yi), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5)
        if pd.notna(exp):
            ax.plot([exp, exp], [yi - 0.42, yi + 0.42], color=INK, linewidth=2)
    vmax = np.nanmax([vals.max(), perf["expected_pull_per_5star"].max()])  # NaN when no banner has a 5* or a rate
    ax.set_xlim(0, 1 if pd.isna(vmax) else max(vmax * 1.3, 1))
    ax.set_title("Avg pity per 5\u2605  (lower = better)")
    ax.legend(handles=[Line2D([0], [0], color=INK, linewidth=2, label="Expected (1 \u00f7 consolidated rate)")],
              loc="lower right", fontsize=8, frameon=False)
    vgrid(ax)

    ax = axes[2]
    vals = perf["win_rate_5star_pct"]
    ax.barh(y, vals.fillna(0), 0.62, color=colors)
    for yi, v, base in zip(y, vals, perf["baseline_5star_pct"]):
        if pd.isna(v):
            ax.text(1, yi, "N/A", va="center", fontsize=8.5, color=MUTED)
        else:
            ax.annotate(f"{v:.0f}%", (v, yi), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5)
        if pd.notna(base):
            ax.plot([base, base], [yi - 0.42, yi + 0.42], color=INK, linewidth=2)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_title("5\u2605 Rate-up Win Rate")
    vgrid(ax)
    ax.legend(handles=[Line2D([0], [0], color=INK, linewidth=2, label="Official 5\u2605 rate-up chance")],
              loc="upper center", bbox_to_anchor=(0.5, -0.09))

    finish(fig, outdir / "06_banner_performance.png", ctx, "Banner Performance")
    return perf


# ---------------------------------------------------------------------------
# 7. Luck Score  (formula lives in luck.py, shared with the dashboard)
# ---------------------------------------------------------------------------
def insight_luck_score(df, outdir, ctx):
    print("\n[7] Luck Score")
    luck = compute_luck(df, ctx.cfg)
    save_csv(luck, outdir / "07_luck_score.csv")

    metrics = [("Pity efficiency", "avg_pity_luck", LUCK_COLORS["pity"]),
               ("Rate-up win luck", "win_rate_luck", LUCK_COLORS["win"]),
               ("Luck Score", "luck_score", LUCK_COLORS["score"])]
    fig, ax = plt.subplots(figsize=(max(7.5, 2.6 * len(luck) + 3.5), 5))
    x = np.arange(len(luck))
    w = 0.26
    top = 100.0
    for i, (name, col, color) in enumerate(metrics):
        vals = pd.to_numeric(luck[col], errors="coerce")
        bars = ax.bar(x + (i - 1) * w, vals.fillna(0), w * 0.92, color=color, label=name)
        for b, v in zip(bars, vals):
            if pd.isna(v):
                ax.annotate("N/A", (b.get_x() + b.get_width() / 2, 0), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=8.5, color=MUTED)
            else:
                ax.annotate(f"{v:.0f}", (b.get_x() + b.get_width() / 2, v), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=9, fontweight="bold" if col == "luck_score" else "normal", color=INK,
                            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.9))
                top = max(top, v)
    ax.axhline(50, color=INK, linestyle="--", linewidth=1, label="Neutral = 50")
    ax.set_xticks(x)
    ax.set_xticklabels(luck["account"])
    ax.set_ylim(0, top * 1.12)
    ax.set_ylabel("Score  (50 = as expected)")
    ax.set_title("Luck Score per Account")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))

    finish(fig, outdir / "07_luck_score.png", ctx, "Luck Score",
           note="60% pity efficiency + 40% rate-up win luck  \u00b7  5\u2605 only  \u00b7  win rate compared with each banner's official rate-up chance")
    return luck


# ---------------------------------------------------------------------------
# 8. Radiance check (Genshin only; formerly 03_radiance_check_gi.py)
# ---------------------------------------------------------------------------
# "Capturing Radiance" counter model (community diagram, NOT verified against official sources):
#   a counter k = 0..3 counts lost 50/50s; chance to get the featured character at the next
#   non-guaranteed 5*:  k=0: 50%  k=1: 50%  k=2: 75%  k=3: 100%.
#   A guaranteed pull (rate=2) is not a roll and does not change the counter.
#   "Win" in the data = featured character (Radiance can't be told apart from a normal win).
# Two variants of what a win does to the counter are compared, because sources differ:
#   reset (win -> 0, long-run win rate 55.17%)  /  decrement (win -> k - 1)
# Columns: expected_model_pct = sum of per-roll chances / rolls; z = (wins - expected) / sqrt(variance),
# roughly within +-2 = normal luck; impossible_losses = losses at k=3 (chance 0%): the model
# contradicts the data (or the counter started elsewhere).
RADIANCE_P_WIN = [0.50, 0.50, 0.75, 1.00]
RADIANCE_LAUNCH = "2024-08-28"  # Genshin 5.0 release (Capturing Radiance); check this date
RADIANCE_MODES = ("reset", "decrement")


def _radiance_next(k: int, won: bool, mode: str) -> int:
    if won:
        return 0 if mode == "reset" else max(k - 1, 0)
    return min(k + 1, len(RADIANCE_P_WIN) - 1)


def run_radiance_model(wins: list, mode: str) -> dict:
    k, expected, var, impossible = 0, 0.0, 0.0, 0
    states = [0] * len(RADIANCE_P_WIN)
    for won in wins:
        p = RADIANCE_P_WIN[k]
        states[k] += 1
        expected += p
        var += p * (1 - p)
        if not won and p == 1.0:
            impossible += 1
        k = _radiance_next(k, won, mode)
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


def insight_radiance(df, outdir, ctx, start: str = RADIANCE_LAUNCH):
    print("\n[8] Radiance check")
    sub = df[(df["banner_type"] == "Character Event") & (df["rarity"] == 5) & (df["datetime"] >= start)]
    sub = sub[sub["win_50_50"].isin(["Win", "Lose", "Guaranteed"])]
    if sub.empty:
        print(f"  [skip] No Character Event 5* rows with 50/50 data on/after {start}.")
        return None

    rows = []
    for acc, g in sub.sort_values(["datetime", "pull_number"]).groupby("account", sort=False):
        labels = g["win_50_50"].tolist()
        rolls = [lab == "Win" for lab in labels if lab != "Guaranteed"]
        if not rolls:
            continue
        broken = sum(1 for i, lab in enumerate(labels[:-1]) if lab == "Lose" and labels[i + 1] != "Guaranteed")
        flat50 = round(100 * sum(rolls) / len(rolls) - 50, 1)
        for mode in RADIANCE_MODES:
            rows.append({"account": acc, **run_radiance_model(rolls, mode),
                         "actual_minus_flat50_pp": flat50, "lose_not_followed_by_guaranteed": broken})
    out = pd.DataFrame(rows)
    if out.empty:
        print("  [skip] Only guaranteed rows, nothing to check.")
        return None
    save_csv(out, outdir / "08_radiance_check.csv")
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(out.to_string(index=False))
    return out


# ---------------------------------------------------------------------------
# Entry point (python -m pipeline analytics  /  python pipeline/analytics_core.py --game gi)
# ---------------------------------------------------------------------------
def run_all(df: pd.DataFrame, outdir: Path, cfg: GameConfig, radiance_start: str = RADIANCE_LAUNCH):
    if df.empty:
        raise ValueError("The clean CSV has no rows.")
    apply_theme()
    ctx = make_context(df, cfg)
    insight_total_pull(df, outdir, ctx)
    insight_timeline(df, outdir, ctx)
    insight_pity_distribution(df, outdir, ctx)
    insight_win_lose(df, outdir, ctx)
    insight_top_items(df, outdir, ctx)
    insight_banner_performance(df, outdir, ctx)
    insight_luck_score(df, outdir, ctx)
    if cfg.key == "GI":  # the Radiance counter only exists in Genshin
        insight_radiance(df, outdir, ctx, radiance_start)
    print(f"\nAll insights saved to: {outdir}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analytics/EDA for Genshin Impact / Honkai: Star Rail")
    parser.add_argument("--game", required=True, choices=["gi", "hsr"], help="gi or hsr")
    parser.add_argument("--input", default=None, help="Path to the data_clean CSV (default: the game's data_clean CSV)")
    parser.add_argument("--outdir", default=None, help="Output folder (default: outputs/<game>)")
    parser.add_argument("--start", default=RADIANCE_LAUNCH, help=f"[gi] first date of the Radiance check (default {RADIANCE_LAUNCH})")
    args = parser.parse_args(argv)

    cfg = GAMES[args.game.upper()]
    input_path = Path(args.input) if args.input else default_clean_csv(cfg.key)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}. Run first: python -m pipeline preprocess --games {args.game}")
    outdir = Path(args.outdir) if args.outdir else OUTPUT_DIR / args.game
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Reading: {input_path}")
    df = pd.read_csv(input_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    run_all(df, outdir, cfg, args.start)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())