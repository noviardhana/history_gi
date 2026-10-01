"""
03_dashboard.py
================
Interactive Streamlit dashboard for Genshin Impact gacha analytics.

Loads data_clean.csv from 01_preprocessing.py and renders a dashboard with
a Teyvat-night visual identity (deep navy + gold/purple wish accents):
    - Hero header with account context chips
    - Banner pity meters (Character Event / Weapon Event / Standard) with
      Lifetime Pulls, 5-star pity, and 4-star pity, plus a progress bar
      toward hard pity for each
    - 8 insights across tabs, on a shared chart design system
    - Account comparison mode (compare 2+ accounts side-by-side)
    - Data download (CSV export)

Usage:
    pip install streamlit pandas plotly
    streamlit run 03_dashboard.py

    Or with custom data:
    streamlit run 03_dashboard.py -- --data data/data_clean_887284572.csv

Note: the accompanying .streamlit/config.toml sets the dark navy theme.
Run this script from the project root so Streamlit picks up that config.
"""

import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# ----------------------------------------------------------------------------
# Design tokens
# ----------------------------------------------------------------------------
BG_MAIN = "#0f0f26"
BG_CARD = "#1b1b3a"
BG_CARD_ALT = "#22224a"
BG_ELEVATED = "#26264f"
TEXT_PRIMARY = "#f4f3fb"
TEXT_SECONDARY = "#9d9dc9"
TEXT_MUTED = "#6f6f9c"
DIVIDER = "rgba(255,255,255,0.08)"

ACCENT_GOLD = "#f2a641"
ACCENT_PURPLE = "#b57edc"
ACCENT_BLUE = "#5b8fd6"
ACCENT_TEAL = "#57c7b8"
SUCCESS = "#6bbf7b"
DANGER = "#e2707a"

FONT_DISPLAY = "'Manrope', sans-serif"
FONT_BODY = "'Inter', sans-serif"
FONT_MONO = "'JetBrains Mono', monospace"

RARITY_COLORS = {3: ACCENT_BLUE, 4: ACCENT_PURPLE, 5: ACCENT_GOLD}
BANNER_COLORS = {
    "Character Event": ACCENT_GOLD,
    "Weapon Event": ACCENT_BLUE,
    "Standard": "#6bbf7b",
    "Beginners": "#c9576a",
}
BANNER_ICONS = {
    "Character Event": "🎯",
    "Weapon Event": "⚔️",
    "Standard": "🌌",
    "Beginners": "🔰",
}
RESULT_COLORS = {"Win": SUCCESS, "Lose": DANGER, "Guaranteed": ACCENT_TEAL}
HARD_PITY_5STAR = {
    "Character Event": 90,
    "Standard": 90,
    "Weapon Event": 80,
    "Beginners": 20,
}
HARD_PITY_4STAR = {
    "Character Event": 10,
    "Standard": 10,
    "Weapon Event": 10,
    "Beginners": 10,
}

# Canonical banner ordering used across every chart/table in the dashboard
BANNER_ORDER = ["Character Event", "Weapon Event", "Standard", "Beginners"]
# Banners shown as pity meters, in the requested order
PITY_CARD_BANNERS = ["Character Event", "Weapon Event", "Standard"]

# Page config
st.set_page_config(
    page_title="Genshin Gacha Analytics",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark plotly template so every chart matches the app background
_dark_template = pio.templates["plotly_dark"]
_dark_template.layout.paper_bgcolor = "rgba(0,0,0,0)"
_dark_template.layout.plot_bgcolor = "rgba(0,0,0,0)"
_dark_template.layout.font.color = TEXT_PRIMARY
pio.templates["paimon_dark"] = _dark_template
pio.templates.default = "paimon_dark"

# ----------------------------------------------------------------------------
# Global styling
# ----------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap');

    html, body, [class*="css"] {{
        font-family: {FONT_BODY};
    }}
    h1, h2, h3, h4, h5,
    .mona-hero-title, .mona-section-title, .mona-side-title {{
        font-family: {FONT_DISPLAY} !important;
        letter-spacing: -0.01em;
    }}

    /* ---- Hero masthead -------------------------------------------------- */
    .mona-hero {{
        background: linear-gradient(135deg, {BG_CARD} 0%, {BG_ELEVATED} 100%);
        border-left: 4px solid {ACCENT_GOLD};
        border-radius: 16px;
        padding: 22px 26px;
        margin-bottom: 18px;
    }}
    .mona-hero-eyebrow {{
        font-family: {FONT_MONO};
        font-size: 0.72em;
        letter-spacing: 0.14em;
        color: {ACCENT_GOLD};
        text-transform: uppercase;
        margin-bottom: 6px;
    }}
    .mona-hero-title {{
        font-size: 1.9em;
        font-weight: 800;
        color: {TEXT_PRIMARY};
        line-height: 1.15;
    }}
    .mona-hero-subtitle {{
        color: {TEXT_SECONDARY};
        font-size: 0.92em;
        margin-top: 4px;
    }}
    .mona-hero-chips {{
        margin-top: 14px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }}
    .mona-chip {{
        display: inline-block;
        background: rgba(255,255,255,0.05);
        border: 1px solid {DIVIDER};
        color: {TEXT_SECONDARY};
        font-family: {FONT_MONO};
        font-size: 0.76em;
        padding: 4px 12px;
        border-radius: 999px;
    }}

    /* ---- Section headers ------------------------------------------------ */
    .mona-section {{
        display: flex;
        align-items: baseline;
        gap: 10px;
        border-bottom: 1px solid {DIVIDER};
        padding-bottom: 10px;
        margin: 6px 0 18px 0;
    }}
    .mona-section-icon {{ font-size: 1.25em; }}
    .mona-section-title {{
        font-size: 1.2em;
        font-weight: 800;
        color: {TEXT_PRIMARY};
    }}
    .mona-section-subtitle {{
        color: {TEXT_MUTED};
        font-size: 0.82em;
        margin-left: 2px;
    }}

    /* ---- Pity meter cards ------------------------------------------------ */
    .paimon-card {{
        background-color: {BG_CARD};
        border: 1px solid {DIVIDER};
        border-radius: 14px;
        padding: 20px 22px;
        margin-bottom: 12px;
    }}
    .paimon-card-title {{
        font-family: {FONT_DISPLAY};
        font-size: 1.05em;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        margin-bottom: 14px;
    }}
    .paimon-card-row {{
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        padding: 8px 0 2px 0;
    }}
    .paimon-card-divider {{
        border-top: 1px solid {DIVIDER};
        margin-top: 12px;
    }}
    .paimon-card-label {{
        color: {TEXT_SECONDARY};
        font-size: 0.83em;
        line-height: 1.4;
    }}
    .paimon-card-sublabel {{
        color: {TEXT_MUTED};
        font-size: 0.85em;
    }}
    .paimon-card-value {{
        font-family: {FONT_MONO};
        font-size: 1.5em;
        font-weight: 700;
        color: {TEXT_PRIMARY};
    }}
    .paimon-gold {{ color: {ACCENT_GOLD}; }}
    .paimon-purple {{ color: {ACCENT_PURPLE}; }}

    .pity-bar-track {{
        height: 7px;
        border-radius: 999px;
        background: rgba(255,255,255,0.06);
        overflow: hidden;
        margin-top: 8px;
    }}
    .pity-bar-fill {{
        height: 100%;
        border-radius: 999px;
    }}

    /* ---- Result badges ---------------------------------------------------- */
    .mona-badge {{
        display: inline-flex;
        align-items: center;
        font-family: {FONT_MONO};
        font-size: 0.76em;
        font-weight: 700;
        padding: 3px 11px;
        border-radius: 999px;
        margin-right: 6px;
    }}

    /* ---- Metric cards ------------------------------------------------------ */
    [data-testid="stMetric"] {{
        background-color: {BG_CARD_ALT};
        border: 1px solid {DIVIDER};
        border-radius: 12px;
        padding: 14px 16px;
    }}
    [data-testid="stMetricValue"] {{
        font-family: {FONT_MONO};
        color: {ACCENT_GOLD};
    }}
    [data-testid="stMetricLabel"] {{
        color: {TEXT_SECONDARY};
    }}

    /* ---- Tabs ---------------------------------------------------------- */
    [data-baseweb="tab-list"] {{
        gap: 4px;
        border-bottom: 1px solid {DIVIDER};
    }}
    [data-baseweb="tab"] {{
        font-family: {FONT_DISPLAY};
        font-weight: 700;
        font-size: 0.92em;
        color: {TEXT_SECONDARY};
    }}
    [data-baseweb="tab"][aria-selected="true"] {{
        color: {ACCENT_GOLD};
    }}
    [data-baseweb="tab-highlight"] {{
        background-color: {ACCENT_GOLD} !important;
    }}

    /* ---- Dataframes & sidebar -------------------------------------------- */
    [data-testid="stDataFrame"] {{
        border: 1px solid {DIVIDER};
        border-radius: 10px;
        overflow: hidden;
    }}
    .mona-side-title {{
        font-size: 1.15em;
        font-weight: 800;
        color: {TEXT_PRIMARY};
    }}
    .mona-side-caption {{
        color: {TEXT_MUTED};
        font-size: 0.78em;
        margin-bottom: 6px;
    }}
    .mona-side-section {{
        font-family: {FONT_DISPLAY};
        font-weight: 700;
        font-size: 0.82em;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: {TEXT_SECONDARY};
        margin: 4px 0 6px 0;
    }}
    .mona-footer {{
        text-align: center;
        color: {TEXT_MUTED};
        font-size: 0.78em;
        padding: 18px 0 6px 0;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# Small presentation helpers
# ============================================================================
def section_header(icon: str, title: str, subtitle: str = ""):
    """Render a consistent section header used at the top of every insight."""
    sub_html = f'<span class="mona-section-subtitle">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f"""
        <div class="mona-section">
            <span class="mona-section-icon">{icon}</span>
            <span class="mona-section-title">{title}</span>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, color: str) -> str:
    """Return an inline HTML pill badge in the given accent color."""
    return (
        f'<span class="mona-badge" style="background:{color}26; color:{color}; '
        f'border:1px solid {color}55;">{text}</span>'
    )


def apply_layout(fig, title, xaxis_title=None, yaxis_title=None, height=380, legend=False, yaxis_range=None, **extra):
    """Apply the shared chart design system to a Plotly figure: consistent
    typography, margins, gridlines, and hover styling across every insight."""
    yaxis_cfg = dict(title=yaxis_title, gridcolor=DIVIDER, zerolinecolor=DIVIDER)
    if yaxis_range is not None:
        yaxis_cfg["range"] = yaxis_range
    fig.update_layout(
        title=dict(text=title, font=dict(family=FONT_DISPLAY, size=15, color=TEXT_PRIMARY), x=0.01, xanchor="left"),
        font=dict(family=FONT_BODY, color=TEXT_SECONDARY, size=12),
        xaxis=dict(title=xaxis_title, gridcolor=DIVIDER, zerolinecolor=DIVIDER),
        yaxis=yaxis_cfg,
        height=height,
        margin=dict(l=8, r=8, t=54, b=8),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=BG_CARD_ALT, bordercolor=DIVIDER, font=dict(family=FONT_BODY, color=TEXT_PRIMARY)),
        **extra,
    )
    return fig


def style_result_column(df: pd.DataFrame, column: str = "Result") -> "pd.io.formats.style.Styler":
    """Color-code a Win/Lose/Guaranteed column in a dataframe for display."""

    def _style(val):
        color = RESULT_COLORS.get(val)
        if color:
            return f"background-color:{color}22; color:{color}; font-weight:700;"
        return f"color:{TEXT_MUTED};"

    styler = df.style
    style_fn = getattr(styler, "map", None) or styler.applymap
    return style_fn(_style, subset=[column])


def render_hero(title: str, subtitle: str, chips: list):
    chips_html = "".join(f'<span class="mona-chip">{c}</span>' for c in chips)
    st.markdown(
        f"""
        <div class="mona-hero">
            <div class="mona-hero-eyebrow">Genshin Impact · Wish Analytics</div>
            <div class="mona-hero-title">{title}</div>
            <div class="mona-hero-subtitle">{subtitle}</div>
            <div class="mona-hero-chips">{chips_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def order_banners(items) -> list:
    """Return banner names ordered as Character Event, Weapon Event, Standard,
    Beginners, followed by any unexpected banner names."""
    items = list(items)
    ordered = [b for b in BANNER_ORDER if b in items]
    extra = [b for b in items if b not in BANNER_ORDER]
    return ordered + extra


@st.cache_data
def load_data(filepath: str) -> pd.DataFrame:
    """Load and clean the CSV data."""
    df = pd.read_csv(filepath)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["date"] = df["datetime"].dt.date
    df["year_month"] = df["datetime"].dt.to_period("M").astype(str)
    df["is_5star"] = df["rarity"] == 5
    df["is_4star"] = df["rarity"] == 4
    df["is_3star"] = df["rarity"] == 3

    # Make banner_type an ordered categorical so every groupby/pivot in the
    # dashboard naturally sorts as Character Event -> Weapon Event -> Standard
    # -> Beginners, instead of the default alphabetical order.
    banner_categories = order_banners(df["banner_type"].dropna().unique())
    df["banner_type"] = pd.Categorical(
        df["banner_type"], categories=banner_categories, ordered=True
    )
    return df


def get_main_account(df: pd.DataFrame) -> str:
    """Pick the 'main' account: an account whose name contains 'main'
    (case-insensitive), otherwise the account with the most pulls."""
    counts = df["account"].value_counts()
    main_candidates = [a for a in counts.index if "main" in str(a).lower()]
    if main_candidates:
        return main_candidates[0]
    return counts.idxmax()


def get_account_order(df: pd.DataFrame) -> list:
    """Return account names with the main account first, others alphabetical."""
    main_account = get_main_account(df)
    others = sorted(a for a in df["account"].unique() if a != main_account)
    return [main_account] + others


def compute_current_pity(df: pd.DataFrame, banner_type: str, star: int = 5):
    """Number of pulls since the last reset for the given star tier's pity
    counter. 5-star pity resets on a 5-star pull; 4-star pity resets on
    either a 4-star or a 5-star pull (matching in-game mechanics). Returns
    None if the banner has no pulls at all."""
    banner_df = df[df["banner_type"] == banner_type].sort_values("datetime")
    if banner_df.empty:
        return None
    banner_df = banner_df.reset_index(drop=True)
    if star == 5:
        reset_mask = banner_df["is_5star"]
    else:
        reset_mask = banner_df["is_4star"] | banner_df["is_5star"]
    reset_positions = banner_df.index[reset_mask]
    if len(reset_positions) == 0:
        return len(banner_df)
    last_reset_pos = reset_positions[-1]
    return len(banner_df) - last_reset_pos - 1


def calculate_win_rate(df: pd.DataFrame) -> float:
    """Calculate the 50-50 win rate."""
    decisive = df[(df["win_50_50"].isin(["Win", "Lose"])) & (df["is_5star"] | df["is_4star"])]
    if len(decisive) == 0:
        return 0
    win_count = (decisive["win_50_50"] == "Win").sum()
    return (win_count / len(decisive) * 100) if len(decisive) > 0 else 0


def render_pity_cards(df: pd.DataFrame):
    """Render banner pity meters: Lifetime Pulls, 5-star pity, 4-star pity,
    each with a progress bar toward hard pity, for Character Event /
    Weapon Event / Standard."""
    cols = st.columns(len(PITY_CARD_BANNERS))
    for col, banner in zip(cols, PITY_CARD_BANNERS):
        banner_df = df[df["banner_type"] == banner]
        lifetime_pulls = len(banner_df)
        pity_5 = compute_current_pity(df, banner, star=5)
        pity_4 = compute_current_pity(df, banner, star=4)
        hard_5 = HARD_PITY_5STAR.get(banner, 90)
        hard_4 = HARD_PITY_4STAR.get(banner, 10)
        pity_5_display = pity_5 if pity_5 is not None else "-"
        pity_4_display = pity_4 if pity_4 is not None else "-"
        pct_5 = min(100, round((pity_5 or 0) / hard_5 * 100)) if pity_5 is not None else 0
        pct_4 = min(100, round((pity_4 or 0) / hard_4 * 100)) if pity_4 is not None else 0
        icon = BANNER_ICONS.get(banner, "🔮")
        top_color = BANNER_COLORS.get(banner, ACCENT_GOLD)

        with col:
            st.markdown(
                f"""
                <div class="paimon-card" style="border-top:3px solid {top_color};">
                    <div class="paimon-card-title">{icon} {banner}</div>
                    <div class="paimon-card-row">
                        <div class="paimon-card-label">Lifetime Pulls</div>
                        <div class="paimon-card-value">{lifetime_pulls:,}</div>
                    </div>
                    <div class="paimon-card-divider"></div>
                    <div class="paimon-card-row">
                        <div class="paimon-card-label">5★ Pity<br>
                            <span class="paimon-card-sublabel">Guaranteed at {hard_5}</span>
                        </div>
                        <div class="paimon-card-value paimon-gold">{pity_5_display}</div>
                    </div>
                    <div class="pity-bar-track">
                        <div class="pity-bar-fill" style="width:{pct_5}%; background:{ACCENT_GOLD};"></div>
                    </div>
                    <div class="paimon-card-divider"></div>
                    <div class="paimon-card-row">
                        <div class="paimon-card-label">4★ Pity<br>
                            <span class="paimon-card-sublabel">Guaranteed at {hard_4}</span>
                        </div>
                        <div class="paimon-card-value paimon-purple">{pity_4_display}</div>
                    </div>
                    <div class="pity-bar-track">
                        <div class="pity-bar-fill" style="width:{pct_4}%; background:{ACCENT_PURPLE};"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def display_metrics_row(df: pd.DataFrame):
    """Display the account-level KPI overview row."""
    col1, col2, col3, col4, col5 = st.columns(5)

    total_pulls = len(df)
    five_star_pct = (df["is_5star"].sum() / total_pulls * 100) if total_pulls > 0 else 0
    avg_pity_5 = df[df["is_5star"]]["pity"].mean() if df["is_5star"].sum() > 0 else 0
    five_star_count = df["is_5star"].sum()
    active_days = (df["datetime"].max() - df["datetime"].min()).days if len(df) > 0 else 0

    with col1:
        st.metric("📊 Total Pulls", f"{total_pulls:,}", delta=None)

    with col2:
        st.metric("⭐ 5★ Count", f"{five_star_count:,}", delta=f"{five_star_pct:.1f}%")

    with col3:
        st.metric("🍀 Avg Pity 5★", f"{avg_pity_5:.0f}", delta=None)

    with col4:
        win_rate = calculate_win_rate(df)
        st.metric("🏆 50-50 Win Rate", f"{win_rate:.0f}%", delta=None)

    with col5:
        st.metric("📅 Active Days", f"{active_days:,}", delta=None)


# ============================================================================
# INSIGHT 1: Total Pulls & Progress
# ============================================================================
def insight_1_total_pull(df: pd.DataFrame):
    section_header("📊", "Total Pulls & Account Progress", "Rarity breakdown and AR/WL progress per account")

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
        )
        .reset_index()
    )
    summary["pct_5star"] = (summary["pull_5star"] / summary["total_pull"] * 100).round(2)

    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=summary["account"], y=summary["pull_3star"], name="3★", marker_color=RARITY_COLORS[3]))
        fig.add_trace(go.Bar(x=summary["account"], y=summary["pull_4star"], name="4★", marker_color=RARITY_COLORS[4]))
        fig.add_trace(go.Bar(x=summary["account"], y=summary["pull_5star"], name="5★", marker_color=RARITY_COLORS[5]))
        apply_layout(
            fig,
            title="Total Pulls per Account (rarity breakdown)",
            xaxis_title="Account",
            yaxis_title="Number of Pulls",
            barmode="stack",
            hovermode="x unified",
            legend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=summary["account"], y=summary["adventure_rank"], name="Adventure Rank", marker_color=ACCENT_GOLD))
        fig.add_trace(go.Bar(x=summary["account"], y=summary["world_level"], name="World Level", marker_color=ACCENT_BLUE))
        apply_layout(
            fig,
            title="Account Progress (AR & WL)",
            xaxis_title="Account",
            yaxis_title="Level",
            barmode="group",
            legend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Data Details"):
        st.dataframe(summary, use_container_width=True, hide_index=True)


# ============================================================================
# INSIGHT 2: Wish Timeline
# ============================================================================
def insight_2_timeline(df: pd.DataFrame):
    section_header("📈", "Wish Timeline", "Monthly pull volume, broken down by banner")

    timeline = (
        df.groupby(["year_month", "banner_type"], observed=True)
        .size()
        .reset_index(name="pull_count")
        .sort_values("year_month")
    )

    pivot = timeline.pivot(index="year_month", columns="banner_type", values="pull_count").fillna(0)
    pivot = pivot.reindex(columns=order_banners(pivot.columns))

    fig = go.Figure()
    for banner in pivot.columns:
        fig.add_trace(
            go.Bar(x=pivot.index, y=pivot[banner], name=banner, marker_color=BANNER_COLORS.get(banner, "#999999"))
        )
    # Total pulls per month (all banners) shown above each stacked bar
    monthly_total = pivot.sum(axis=1)
    fig.add_trace(
        go.Scatter(
            x=monthly_total.index,
            y=monthly_total.values,
            mode="text",
            text=[f"{int(v):,}" for v in monthly_total.values],
            textposition="top center",
            textfont=dict(color=TEXT_PRIMARY, size=12),
            showlegend=False,
            hoverinfo="skip",
            cliponaxis=False,
        )
    )
    apply_layout(
        fig,
        title="Monthly Wish Timeline (banner breakdown)",
        xaxis_title="Month",
        yaxis_title="Number of Pulls",
        height=460,
        barmode="stack",
        hovermode="x unified",
        legend=True,
    )
    fig.update_yaxes(range=[0, monthly_total.max() * 1.15])
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Data Details"):
        st.dataframe(timeline, use_container_width=True, hide_index=True)


# ============================================================================
# INSIGHT 3: 5★ Pity Distribution
# ============================================================================
def insight_3_pity_distribution(df: pd.DataFrame):
    section_header("🍀", "5★ Pity Distribution", "How many pulls each 5★ took to land, per banner")

    five_star = df[df["is_5star"]].copy()
    if len(five_star) == 0:
        st.warning("No 5★ pulls found for this account.")
        return

    five_star["hard_pity"] = five_star["banner_type"].map(HARD_PITY_5STAR).fillna(90)

    banners = order_banners(five_star["banner_type"].unique())
    cols = st.columns(len(banners)) if banners else []

    for col, banner in zip(cols, banners):
        with col:
            vals = five_star.loc[five_star["banner_type"] == banner, "pity"]
            if len(vals) > 0:
                fig = go.Figure()
                fig.add_trace(
                    go.Histogram(x=vals, nbinsx=20, marker_color=BANNER_COLORS.get(banner, "#999999"), name=banner)
                )
                fig.add_vline(
                    x=vals.mean(),
                    line_dash="dash",
                    line_color=TEXT_PRIMARY,
                    annotation_text=f"Average: {vals.mean():.1f}",
                    annotation_font_color=TEXT_SECONDARY,
                )
                apply_layout(fig, title=banner, xaxis_title="Pity", yaxis_title="Frequency")
                st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Data Details"):
        detail = five_star[
            ["banner_type", "datetime", "item_name", "item_category", "pity", "win_50_50"]
        ].sort_values(["banner_type", "datetime"])
        st.dataframe(detail, use_container_width=True, hide_index=True)


# ============================================================================
# INSIGHT 4: 50-50 Win/Lose
# ============================================================================
def insight_4_win_lose(df: pd.DataFrame):
    section_header("🏆", "50-50 Win/Lose", "Featured-rate outcomes by banner and rarity")

    rate_df = df[df["win_50_50"].notna()].copy()
    if len(rate_df) == 0:
        st.warning("No 50-50 data available for this account.")
        return

    col1, col2 = st.columns(2)

    with col1:
        summary = (
            rate_df.groupby(["banner_type", "rarity", "win_50_50"], observed=True)
            .size()
            .reset_index(name="count")
        )
        pivot = summary.pivot_table(
            index=["banner_type", "rarity"], columns="win_50_50", values="count", fill_value=0, observed=True
        )
        pivot = pivot.reindex(columns=[c for c in ["Win", "Lose", "Guaranteed"] if c in pivot.columns])

        labels = [f"{b}<br>{r}★" for b, r in pivot.index]
        fig = go.Figure()
        for col_name in pivot.columns:
            fig.add_trace(go.Bar(x=labels, y=pivot[col_name], name=col_name, marker_color=RESULT_COLORS.get(col_name)))
        apply_layout(
            fig,
            title="Win / Lose / Guaranteed Breakdown",
            xaxis_title="Banner & Rarity",
            yaxis_title="Number of Pulls",
            barmode="stack",
            legend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        decisive = rate_df[rate_df["win_50_50"].isin(["Win", "Lose"])]
        win_rate = (
            decisive.groupby(["banner_type", "rarity"], observed=True)["win_50_50"]
            .apply(lambda s: (s == "Win").mean() * 100)
            .reset_index(name="win_rate_pct")
        )
        labels_wr = [f"{b}<br>{r}★" for b, r in zip(win_rate["banner_type"], win_rate["rarity"])]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=labels_wr, y=win_rate["win_rate_pct"], marker_color=SUCCESS))
        fig.add_hline(
            y=50, line_dash="dash", line_color=TEXT_PRIMARY, annotation_text="50% (Baseline)",
            annotation_font_color=TEXT_SECONDARY,
        )
        apply_layout(
            fig,
            title="50-50 Win Rate (Win vs Lose)",
            xaxis_title="Banner & Rarity",
            yaxis_title="Win Rate (%)",
            yaxis_range=[0, 100],
        )
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Data Details"):
        st.dataframe(summary, use_container_width=True, hide_index=True)


# ============================================================================
# INSIGHT 5: Top Character & Weapon
# ============================================================================
def insight_5_top_items(df: pd.DataFrame, top_n: int = 10):
    section_header("👑", "Top Character & Weapon", "Most frequently obtained 4★ and 5★ items")

    col1, col2 = st.columns(2)

    with col1:
        char_df = df[(df["item_category"] == "character") & (df["rarity"] >= 4)]
        if len(char_df) > 0:
            top_char = (
                char_df.groupby(["item_name", "rarity"])
                .size()
                .reset_index(name="times_obtained")
                .sort_values("times_obtained", ascending=False)
                .head(top_n)
            )
            colors = [RARITY_COLORS.get(r, "#999999") for r in top_char["rarity"]]
            fig = go.Figure()
            fig.add_trace(go.Bar(y=top_char["item_name"], x=top_char["times_obtained"], orientation="h", marker_color=colors))
            apply_layout(fig, title="Top Characters (4★ & 5★)", xaxis_title="Times Obtained", yaxis_title="Character", height=480)
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No 4★ or 5★ characters found.")

    with col2:
        weapon_df = df[(df["item_category"] == "weapon") & (df["rarity"] >= 4)]
        if len(weapon_df) > 0:
            top_weapon = (
                weapon_df.groupby(["item_name", "rarity"])
                .size()
                .reset_index(name="times_obtained")
                .sort_values("times_obtained", ascending=False)
                .head(top_n)
            )
            colors = [RARITY_COLORS.get(r, "#999999") for r in top_weapon["rarity"]]
            fig = go.Figure()
            fig.add_trace(go.Bar(y=top_weapon["item_name"], x=top_weapon["times_obtained"], orientation="h", marker_color=colors))
            apply_layout(fig, title="Top Weapons (4★ & 5★)", xaxis_title="Times Obtained", yaxis_title="Weapon", height=480)
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No 4★ or 5★ weapons found.")


# ============================================================================
# INSIGHT 6: Banner Performance
# ============================================================================
def insight_6_banner_performance(df: pd.DataFrame):
    section_header("📍", "Banner Performance", "Volume, efficiency, and win rate compared across banners")

    perf = (
        df.groupby("banner_type", observed=True)
        .agg(total_pull=("item_id", "count"), pull_5star=("is_5star", "sum"), pull_4star=("is_4star", "sum"))
        .reset_index()
    )
    perf["pull_per_5star"] = (perf["total_pull"] / perf["pull_5star"].replace(0, float("nan"))).round(1)
    perf["rate_5star_pct"] = (perf["pull_5star"] / perf["total_pull"] * 100).round(2)

    col1, col2, col3 = st.columns(3)

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=perf["banner_type"], y=perf["total_pull"], marker_color=[BANNER_COLORS.get(b, "#999") for b in perf["banner_type"]]))
        apply_layout(fig, title="Total Pulls per Banner", xaxis_title="Banner", yaxis_title="Number of Pulls")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=perf["banner_type"], y=perf["pull_per_5star"], marker_color=[BANNER_COLORS.get(b, "#999") for b in perf["banner_type"]]))
        apply_layout(fig, title="Pulls per 5★ (lower = more efficient)", xaxis_title="Banner", yaxis_title="Pulls per 5★")
        st.plotly_chart(fig, use_container_width=True)

    with col3:
        decisive = df[(df["win_50_50"].isin(["Win", "Lose"])) & (df["is_5star"] | df["is_4star"])]
        if len(decisive) > 0:
            win_rate = (
                decisive.groupby("banner_type", observed=True)["win_50_50"]
                .apply(lambda s: (s == "Win").mean() * 100)
                .reset_index(name="win_rate_pct")
            )
            fig = go.Figure()
            fig.add_trace(go.Bar(x=win_rate["banner_type"], y=win_rate["win_rate_pct"], marker_color=SUCCESS))
            fig.add_hline(
                y=50, line_dash="dash", line_color=TEXT_PRIMARY, annotation_text="Baseline 50%",
                annotation_font_color=TEXT_SECONDARY,
            )
            apply_layout(fig, title="50-50 Win Rate per Banner", xaxis_title="Banner", yaxis_title="Win Rate (%)", yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Data Details"):
        st.dataframe(perf, use_container_width=True, hide_index=True)


# ============================================================================
# INSIGHT 7: Luck Score
# ============================================================================
def insight_7_luck_score(df: pd.DataFrame):
    section_header("✨", "Luck Score", "A composite score blending pity efficiency and 50-50 win rate")

    five_star = df[df["is_5star"]].copy()
    if len(five_star) == 0:
        st.warning("No 5★ pulls found for this account. Luck Score cannot be calculated.")
        return

    five_star["hard_pity"] = five_star["banner_type"].map(HARD_PITY_5STAR).fillna(90)
    five_star["pity_luck"] = (1 - (five_star["pity"] - 1) / (five_star["hard_pity"] - 1)) * 100

    pity_luck_by_account = five_star.groupby("account")["pity_luck"].mean()

    decisive = df[df["win_50_50"].isin(["Win", "Lose"])]
    winrate_by_account = (
        decisive.groupby("account")["win_50_50"].apply(lambda s: (s == "Win").mean() * 100)
        if len(decisive) > 0
        else pd.Series(dtype=float)
    )

    accounts = df["account"].unique()
    rows = []
    for acc in accounts:
        pity_luck = pity_luck_by_account.get(acc, float("nan"))
        winrate = winrate_by_account.get(acc, float("nan"))
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

    luck_df = pd.DataFrame(rows).sort_values("luck_score", ascending=False, na_position="last")

    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=luck_df["account"], y=luck_df["luck_score"], marker_color=ACCENT_GOLD))
        fig.add_hline(
            y=50, line_dash="dash", line_color=TEXT_PRIMARY, annotation_text="Baseline 50 (Neutral)",
            annotation_font_color=TEXT_SECONDARY,
        )
        apply_layout(fig, title="Luck Score per Account", xaxis_title="Account", yaxis_title="Luck Score (0-100+)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown(
            f"""
            <div class="paimon-card">
                <div class="paimon-card-title">📊 Luck Score Formula</div>
                <p style="color:{TEXT_SECONDARY}; font-size:0.88em; line-height:1.7; margin:0;">
                    <b style="color:{TEXT_PRIMARY}">60%</b> Pity Efficiency (lower pity = higher score)<br>
                    <b style="color:{TEXT_PRIMARY}">40%</b> 50-50 Win Rate (higher win rate = higher score)<br>
                    <b style="color:{TEXT_PRIMARY}">Baseline 50</b> = neutral, statistical average result
                </p>
                <div class="paimon-card-divider"></div>
                <div class="paimon-card-title" style="margin-top:12px;">🎯 Interpretation</div>
                <p style="color:{TEXT_SECONDARY}; font-size:0.88em; line-height:1.7; margin:0;">
                    {badge("&gt; 70 Very lucky 🍀", SUCCESS)}<br><br>
                    {badge("50–70 Above average", ACCENT_TEAL)}<br><br>
                    {badge("&lt; 50 Below average", DANGER)}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("📋 Data Details"):
            st.dataframe(luck_df, use_container_width=True, hide_index=True)


# ============================================================================
# INSIGHT 8: Latest 5★ Obtained per Banner
# ============================================================================
def insight_8_latest_5star(df: pd.DataFrame, top_n: int = 10):
    section_header("🆕", "Latest 5★ Characters & Weapons", "The 10 most recent 5★ pulls per banner, newest first")

    five_star = df[df["is_5star"]].copy()
    if len(five_star) == 0:
        st.warning("No 5★ pulls found for this account.")
        return

    banners = order_banners(five_star["banner_type"].unique())

    for banner in banners:
        banner_df = five_star[five_star["banner_type"] == banner].sort_values("datetime", ascending=False)
        if banner_df.empty:
            continue

        win_count = int((banner_df["win_50_50"] == "Win").sum())
        lose_count = int((banner_df["win_50_50"] == "Lose").sum())
        guaranteed_count = int((banner_df["win_50_50"] == "Guaranteed").sum())
        decisive_count = win_count + lose_count
        win_rate = (win_count / decisive_count * 100) if decisive_count > 0 else None
        win_rate_text = f"{win_rate:.0f}% win rate" if win_rate is not None else "no decisive 50-50s"

        icon = BANNER_ICONS.get(banner, "🔮")
        top_color = BANNER_COLORS.get(banner, ACCENT_GOLD)

        st.markdown(
            f"""
            <div class="mona-section" style="border-bottom:1px solid {DIVIDER}; margin-top:22px;">
                <span class="mona-section-icon">{icon}</span>
                <span class="mona-section-title">{banner}</span>
                <span class="mona-section-subtitle">
                    {badge(f"{win_count} Win", SUCCESS)}
                    {badge(f"{lose_count} Lose", DANGER)}
                    {badge(f"{guaranteed_count} Guaranteed", ACCENT_TEAL)}
                    · {win_rate_text}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        latest = banner_df.head(top_n)[["datetime", "item_name", "item_category", "pity", "win_50_50"]].rename(
            columns={
                "datetime": "Date",
                "item_name": "Name",
                "item_category": "Type",
                "pity": "Pity",
                "win_50_50": "Result",
            }
        )
        latest["Date"] = latest["Date"].dt.strftime("%Y-%m-%d %H:%M")
        latest["Type"] = latest["Type"].str.capitalize()
        latest["Result"] = latest["Result"].fillna("N/A")

        st.dataframe(
            style_result_column(latest, "Result"),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Pity": st.column_config.NumberColumn("Pity", format="%d"),
            },
        )


# ============================================================================
# MAIN APP
# ============================================================================
def main():
    # Parse arguments (parse_known_args avoids crashing on Streamlit's own flags)
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default=None, help="Path to data_clean.csv")
    args, _ = parser.parse_known_args()

    data_path = args.data if args.data else str(DATA_DIR / "data_clean.csv")
    if not Path(data_path).exists():
        st.error(f"❌ File not found: {data_path}")
        st.info("Run 01_preprocessing.py to generate data_clean.csv")
        return

    # Load data
    df = load_data(data_path)

    # ---- Sidebar: branding + account selector ----
    st.sidebar.markdown(
        '<div class="mona-side-title">✨ Gacha Analytics</div>'
        '<div class="mona-side-caption">Paimon.moe wish history explorer</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"📦 {len(df):,} pulls across {df['account'].nunique()} account(s) loaded")
    st.sidebar.divider()

    st.sidebar.markdown('<div class="mona-side-section">👤 Account</div>', unsafe_allow_html=True)
    all_accounts = get_account_order(df)

    mode = st.sidebar.radio(
        "Display Mode",
        options=["Single Account", "Compare Accounts", "All Accounts"],
        index=0,
        label_visibility="collapsed",
    )

    if mode == "Single Account":
        selected_account = st.sidebar.selectbox("Select Account", all_accounts, index=0)
        display_df = df[df["account"] == selected_account].copy()
        title = f"{selected_account}"
        subtitle = "Single-account wish history and pity tracking"
    elif mode == "Compare Accounts":
        selected_accounts = st.sidebar.multiselect(
            "Select Accounts to Compare",
            all_accounts,
            default=all_accounts[: min(2, len(all_accounts))],
        )
        if not selected_accounts:
            st.warning("Please select at least 1 account to compare.")
            return
        display_df = df[df["account"].isin(selected_accounts)].copy()
        title = "Comparing Accounts"
        subtitle = ", ".join(selected_accounts)
    else:  # All Accounts
        display_df = df.copy()
        title = "All Accounts"
        subtitle = f"Combined view across all {df['account'].nunique()} accounts"

    # ---- Hero ----
    hero_chips = [
        f"⭐ {int(display_df['is_5star'].sum()):,} five-star",
        f"🔮 {len(display_df):,} pulls",
        f"🏆 {calculate_win_rate(display_df):.0f}% 50-50 win rate",
    ]
    render_hero(title, subtitle, hero_chips)

    # Banner pity meters, then account overview KPIs
    render_pity_cards(display_df)
    st.markdown("")
    display_metrics_row(display_df)
    st.divider()

    # ---- Sidebar: date & banner filters ----
    st.sidebar.divider()
    st.sidebar.markdown('<div class="mona-side-section">🔎 Filters</div>', unsafe_allow_html=True)

    min_date = display_df["datetime"].min().date()
    max_date = display_df["datetime"].max().date()
    if min_date == max_date:
        st.sidebar.info(f"📅 All data is from {min_date}")
        date_range = (min_date, max_date)
    else:
        date_range = st.sidebar.slider(
            "Date Filter",
            min_value=min_date,
            max_value=max_date,
            value=(min_date, max_date),
        )
    display_df = display_df[
        (display_df["datetime"].dt.date >= date_range[0]) & (display_df["datetime"].dt.date <= date_range[1])
    ]

    banner_options = order_banners(display_df["banner_type"].dropna().unique())
    banner_filter = st.sidebar.multiselect(
        "Banner Filter",
        options=banner_options,
        default=banner_options,
    )
    display_df = display_df[display_df["banner_type"].isin(banner_filter)]

    # Tabs for insights
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        [
            "📊 Total Pulls",
            "📈 Timeline",
            "🍀 Pity 5★",
            "🏆 50-50",
            "👑 Top Items",
            "📍 Banner",
            "✨ Luck Score",
            "🆕 Latest 5★",
        ]
    )

    with tab1:
        insight_1_total_pull(display_df)

    with tab2:
        insight_2_timeline(display_df)

    with tab3:
        insight_3_pity_distribution(display_df)

    with tab4:
        insight_4_win_lose(display_df)

    with tab5:
        insight_5_top_items(display_df)

    with tab6:
        insight_6_banner_performance(display_df)

    with tab7:
        insight_7_luck_score(display_df)

    with tab8:
        insight_8_latest_5star(display_df)

    # ---- Sidebar: export ----
    st.sidebar.divider()
    st.sidebar.markdown('<div class="mona-side-section">📥 Export</div>', unsafe_allow_html=True)
    csv = display_df.to_csv(index=False)
    st.sidebar.download_button(
        label="📥 Download Filtered Data (CSV)",
        data=csv,
        file_name=f"gacha_data_{date_range[0]}_{date_range[1]}.csv",
        mime="text/csv",
    )

    st.markdown(
        '<div class="mona-footer">Genshin Impact Gacha Analytics · data sourced from your Paimon.moe export · '
        'independent, unaffiliated with HoYoverse</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
