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
import html
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
BG_MAIN = "#12122b"
BG_CARD = "#1e1e42"
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
# 5★ soft pity start (rates ramp up from this pull)
SOFT_PITY_5STAR = {
    "Character Event": 74,
    "Standard": 74,
    "Weapon Event": 63,
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
    /* ---- TL;DR, key parameters, executive summary ------------------------ */
    .tldr-card {{
        background: linear-gradient(135deg, {BG_CARD} 0%, {BG_ELEVATED} 100%);
        border: 1px solid {DIVIDER};
        border-left: 4px solid {ACCENT_GOLD};
        border-radius: 14px;
        padding: 16px 22px;
        margin-bottom: 16px;
    }}
    .tldr-title {{
        font-family: {FONT_MONO};
        font-size: 0.72em;
        letter-spacing: 0.14em;
        color: {ACCENT_GOLD};
        text-transform: uppercase;
        margin-bottom: 6px;
    }}
    .tldr-line {{
        color: {TEXT_SECONDARY};
        font-size: 0.95em;
        line-height: 1.9;
    }}
    .tldr-line b {{ color: {TEXT_PRIMARY}; }}
    .kpi-card {{
        background-color: {BG_CARD};
        border: 1px solid {DIVIDER};
        border-radius: 12px;
        padding: 14px 16px;
        min-height: 112px;
    }}
    .kpi-label {{
        color: {TEXT_SECONDARY};
        font-size: 0.74em;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }}
    .kpi-value {{
        font-family: {FONT_MONO};
        font-weight: 700;
        margin: 6px 0 4px 0;
        line-height: 1.2;
        overflow-wrap: anywhere;
    }}
    .kpi-sub {{
        color: {TEXT_MUTED};
        font-size: 0.78em;
    }}
    .summary-list {{
        color: {TEXT_SECONDARY};
        font-size: 0.93em;
        line-height: 1.85;
        padding-left: 18px;
        margin: 0;
    }}
    .summary-list b {{ color: {TEXT_PRIMARY}; }}
    .mona-footer {{
        text-align: center;
        color: {TEXT_MUTED};
        font-size: 0.78em;
        padding: 18px 0 6px 0;
        border-top: 1px solid {DIVIDER};
        margin-top: 28px;
    }}

    /* ---- Page frame: width, spacing, hidden Streamlit chrome ------------- */
    .block-container {{
        max-width: 1400px;
        padding-top: 2.2rem;
        padding-bottom: 2rem;
    }}
    #MainMenu, footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{ background: transparent; }}

    /* ---- Block labels (group headings between page areas) ---------------- */
    .block-label {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 26px 0 12px 0;
    }}
    .block-label-text {{
        font-family: {FONT_MONO};
        font-size: 0.74em;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: {TEXT_SECONDARY};
        white-space: nowrap;
    }}
    .block-label-line {{
        flex: 1;
        height: 1px;
        background: {DIVIDER};
    }}

    /* ---- Cards: consistent hover + equal heights ------------------------- */
    .paimon-card, .kpi-card {{
        transition: border-color .15s ease, transform .15s ease;
    }}
    .paimon-card:hover, .kpi-card:hover {{
        border-color: rgba(242,166,65,0.45);
        transform: translateY(-1px);
    }}
    .kpi-card {{ margin-bottom: 12px; }}

    /* ---- Tabs: scroll instead of wrapping, roomier hit area -------------- */
    [data-baseweb="tab-list"] {{ overflow-x: auto; }}
    [data-baseweb="tab"] {{ padding: 10px 14px; white-space: nowrap; }}
    [data-baseweb="tab-panel"] {{ padding-top: 18px; }}

    /* ---- Expanders, charts, sidebar -------------------------------------- */
    [data-testid="stExpander"] {{
        border: 1px solid {DIVIDER};
        border-radius: 12px;
        background-color: {BG_CARD};
    }}
    [data-testid="stPlotlyChart"] {{
        background-color: {BG_CARD};
        border: 1px solid {DIVIDER};
        border-radius: 14px;
        padding: 6px 8px 2px 8px;
    }}
    [data-testid="stSidebar"] {{
        background-color: {BG_CARD};
        border-right: 1px solid {DIVIDER};
    }}
    [data-testid="stSidebar"] hr {{ margin: 14px 0; }}
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


def block_label(text: str):
    """Thin labelled divider that groups page areas (Overview, Pity, Analysis)."""
    st.markdown(
        f'<div class="block-label"><span class="block-label-text">{text}</span>'
        f'<span class="block-label-line"></span></div>',
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


def win_stats(df: pd.DataFrame):
    """(wins, losses) over decisive 4★/5★ 50-50s, same filter as calculate_win_rate."""
    decisive = df[(df["win_50_50"].isin(["Win", "Lose"])) & (df["is_5star"] | df["is_4star"])]
    wins = int((decisive["win_50_50"] == "Win").sum())
    return wins, len(decisive) - wins


def calc_luck_score(df: pd.DataFrame):
    """Same formula as the Luck Score tab (60% pity efficiency, 40% 50-50 win
    rate), computed over the whole selection. Returns None if no data."""
    parts = []
    five_star = df[df["is_5star"]]
    if len(five_star) > 0:
        hard = five_star["banner_type"].astype(object).map(HARD_PITY_5STAR).fillna(90).astype(float)
        pity_luck = ((1 - (five_star["pity"] - 1) / (hard - 1)) * 100).mean()
        if pd.notna(pity_luck):
            parts.append((pity_luck, 0.6))
    wins, losses = win_stats(df)
    if wins + losses > 0:
        parts.append((wins / (wins + losses) * 100, 0.4))
    if not parts:
        return None
    return sum(v * w for v, w in parts) / sum(w for _, w in parts)


def luck_verdict(score: float):
    """(label, color) using the thresholds shown in the Luck Score tab."""
    if score > 70:
        return "Very lucky 🍀", SUCCESS
    if score >= 50:
        return "Above average", ACCENT_TEAL
    return "Below average", DANGER


def build_summary_stats(df: pd.DataFrame) -> dict:
    """Headline numbers shared by the TL;DR, key parameters and summary."""
    total = len(df)
    five = df[df["is_5star"]].sort_values("datetime")
    n5 = len(five)
    wins, losses = win_stats(df)
    return {
        "total": total,
        "n5": n5,
        "n4": int(df["is_4star"].sum()),
        "rate_5": (n5 / total * 100) if total else 0,
        "per_5": (total / n5) if n5 else None,
        "avg_pity_5": five["pity"].mean() if n5 else None,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / (wins + losses) * 100) if wins + losses else None,
        "luck": calc_luck_score(df),
        "last5": five.iloc[-1] if n5 else None,
    }


def render_tldr(df: pd.DataFrame, stats: dict, single_account: bool):
    """Three-line TL;DR: where you are, what's next, how the 50-50s went."""
    lines = []

    if stats["n5"]:
        luck_txt = ""
        if stats["luck"] is not None:
            label, _ = luck_verdict(stats["luck"])
            luck_txt = f" · luck score <b>{stats['luck']:.0f}</b> ({label})"
        lines.append(
            f"🔮 <b>{stats['total']:,}</b> pulls → <b>{stats['n5']}</b> five-star, "
            f"1 per <b>{stats['per_5']:.1f}</b> pulls{luck_txt}"
        )
    else:
        lines.append(f"🔮 <b>{stats['total']:,}</b> pulls, no 5★ yet")

    if single_account:
        parts = []
        for banner, short in [("Character Event", "Character"), ("Weapon Event", "Weapon")]:
            pity = compute_current_pity(df, banner, star=5)
            if pity is None:
                continue
            hard = HARD_PITY_5STAR[banner]
            parts.append(f"{short} <b>{pity}/{hard}</b> ({max(hard - pity, 0)} to guaranteed)")
        if parts:
            lines.append("⏳ Current 5★ pity: " + " · ".join(parts))

    third = []
    if stats["win_rate"] is not None:
        third.append(f"🏆 50-50: <b>{stats['win_rate']:.0f}%</b> won ({stats['wins']}W–{stats['losses']}L)")
    last5 = stats["last5"]
    if last5 is not None:
        pity_txt = f", pity {int(last5['pity'])}" if pd.notna(last5["pity"]) else ""
        third.append(f"last 5★: <b>{html.escape(str(last5['item_name']))}</b>{pity_txt}")
    if third:
        lines.append(" · ".join(third))

    body = "".join(f'<div class="tldr-line">{line}</div>' for line in lines)
    st.markdown(
        f'<div class="tldr-card"><div class="tldr-title">⚡ TL;DR</div>{body}</div>',
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, sub: str = "", color: str = ACCENT_GOLD, value_size: str = "1.6em") -> str:
    return (
        f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value" style="color:{color}; font-size:{value_size};">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )


def render_key_parameters(stats: dict):
    """The handful of numbers worth looking at first."""
    cards = []

    cards.append(kpi_card("🔮 Total Pulls", f"{stats['total']:,}", f"≈ {stats['total'] * 160:,} primogems"))

    per5 = f"1 per {stats['per_5']:.1f} pulls" if stats["per_5"] else "no 5★ yet"
    cards.append(kpi_card("⭐ 5★ Obtained", f"{stats['n5']:,}", f"{per5} · 4★: {stats['n4']:,}"))

    avg = f"{stats['avg_pity_5']:.1f}" if stats["avg_pity_5"] is not None else "-"
    cards.append(kpi_card("🍀 Avg Pity 5★", avg, "lower = better"))

    if stats["win_rate"] is not None:
        color = SUCCESS if stats["win_rate"] >= 50 else DANGER
        cards.append(
            kpi_card("🏆 50-50 Win Rate", f"{stats['win_rate']:.0f}%", f"{stats['wins']}W–{stats['losses']}L", color)
        )
    else:
        cards.append(kpi_card("🏆 50-50 Win Rate", "-", "no decisive 50-50s", TEXT_MUTED))

    if stats["luck"] is not None:
        label, color = luck_verdict(stats["luck"])
        cards.append(kpi_card("✨ Luck Score", f"{stats['luck']:.0f}", label, color))
    else:
        cards.append(kpi_card("✨ Luck Score", "-", "needs 5★ or 50-50 data", TEXT_MUTED))

    last5 = stats["last5"]
    if last5 is not None:
        pity_txt = f" · pity {int(last5['pity'])}" if pd.notna(last5["pity"]) else ""
        cards.append(
            kpi_card(
                "🆕 Latest 5★",
                html.escape(str(last5["item_name"])),
                f"{last5['datetime']:%Y-%m-%d}{pity_txt}",
                ACCENT_GOLD,
                value_size="1.05em",
            )
        )
    else:
        cards.append(kpi_card("🆕 Latest 5★", "-", "none yet", TEXT_MUTED, value_size="1.05em"))

    # 3 x 2 grid: wider cards so values and sub-labels never get cramped
    for row_cards in (cards[:3], cards[3:]):
        for col, card in zip(st.columns(3), row_cards):
            with col:
                st.markdown(card, unsafe_allow_html=True)


def render_executive_summary(df: pd.DataFrame, stats: dict, single_account: bool):
    """Short, auto-generated written summary of the selected account(s)."""
    items = []
    start = df["datetime"].min().strftime("%b %Y")
    end = df["datetime"].max().strftime("%b %Y")

    overall = f"<b>Overall:</b> {stats['total']:,} pulls ({start} – {end}) gave {stats['n5']} five-star ({stats['rate_5']:.2f}%) and {stats['n4']} four-star."
    if stats["avg_pity_5"] is not None:
        overall += f" Average 5★ pity is {stats['avg_pity_5']:.1f}."
    items.append(overall)

    five = df[df["is_5star"]]
    decisive5 = five[five["win_50_50"].isin(["Win", "Lose"])]
    if len(decisive5) > 0:
        w5 = int((decisive5["win_50_50"] == "Win").sum())
        l5 = len(decisive5) - w5
        g5 = int((five["win_50_50"] == "Guaranteed").sum())
        items.append(
            f"<b>50-50 (5★ only):</b> won {w5}, lost {l5} ({w5 / (w5 + l5) * 100:.0f}% win rate); {g5} more came from guarantees."
        )

    perf = df.groupby("banner_type", observed=True).agg(pulls=("item_id", "count"), five=("is_5star", "sum"))
    perf = perf[perf["five"] > 0]
    if len(perf) >= 2:
        ppf = perf["pulls"] / perf["five"]
        best, worst = ppf.idxmin(), ppf.idxmax()
        if best != worst:
            items.append(
                f"<b>Banner efficiency:</b> {best} is the most efficient ({ppf[best]:.1f} pulls per 5★), "
                f"{worst} the least ({ppf[worst]:.1f})."
            )

    monthly = df.groupby("year_month").size()
    items.append(
        f"<b>Activity:</b> busiest month was {monthly.idxmax()} ({monthly.max():,} pulls); "
        f"latest pull on {df['datetime'].max():%Y-%m-%d}."
    )

    if single_account:
        for banner in ["Character Event", "Weapon Event"]:
            pity = compute_current_pity(df, banner, star=5)
            if pity is None:
                continue
            hard, soft = HARD_PITY_5STAR[banner], SOFT_PITY_5STAR[banner]
            if pity >= soft:
                status = f"in soft pity (starts at {soft}), {max(hard - pity, 0)} pulls to guaranteed"
            else:
                status = f"{soft - pity} pulls until soft pity ({soft}), {hard - pity} to guaranteed"
            items.append(f"<b>{banner} now:</b> pity {pity}/{hard} — {status}.")
    else:
        items.append("<b>Current pity:</b> select a single account to see it.")

    body = "".join(f"<li>{item}</li>" for item in items)
    with st.expander("📝 Executive Summary", expanded=True):
        st.markdown(f'<ul class="summary-list">{body}</ul>', unsafe_allow_html=True)


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
# INSIGHT 9: Pull History (5★ and 4★)
# ============================================================================
def _render_history_table(df: pd.DataFrame, rarity: int):
    rarity_df = df[df["rarity"] == rarity].copy()
    if rarity_df.empty:
        st.info(f"No {rarity}★ pulls found for the current filters.")
        return

    # Running number of each pull within its account (1 = oldest)
    rarity_df = rarity_df.sort_values("datetime")
    rarity_df["No."] = rarity_df.groupby("account").cumcount() + 1

    banner_choices = ["All"] + order_banners(rarity_df["banner_type"].dropna().astype(str).unique())
    f1, f2 = st.columns([3, 2])
    with f1:
        banner_choice = st.radio("Banner", banner_choices, horizontal=True, key=f"history_banner_{rarity}")
    with f2:
        type_choice = st.radio(
            "Type", ["All", "Character", "Weapon"], horizontal=True, key=f"history_type_{rarity}"
        )
    if banner_choice != "All":
        rarity_df = rarity_df[rarity_df["banner_type"].astype(str) == banner_choice]
    if type_choice != "All":
        rarity_df = rarity_df[rarity_df["item_category"].str.lower() == type_choice.lower()]
    if rarity_df.empty:
        st.info(f"No {rarity}★ pulls found for Banner: {banner_choice} · Type: {type_choice}.")
        return

    pity = rarity_df["pity"].dropna()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{rarity}★ Total", f"{len(rarity_df):,}")
    c2.metric("Avg Pity", f"{pity.mean():.1f}" if len(pity) else "-")
    c3.metric("Lowest Pity", f"{int(pity.min())}" if len(pity) else "-")
    c4.metric("Highest Pity", f"{int(pity.max())}" if len(pity) else "-")

    multi_account = df["account"].nunique() > 1
    columns = ["No.", "datetime"] + (["account"] if multi_account else []) + [
        "item_name", "item_category", "banner_type", "pity", "win_50_50",
    ]
    view = (
        rarity_df.sort_values("datetime", ascending=False)[columns]
        .rename(
            columns={
                "datetime": "Date",
                "account": "Account",
                "item_name": "Name",
                "item_category": "Type",
                "banner_type": "Banner",
                "pity": "Pity",
                "win_50_50": "Result",
            }
        )
    )
    view["Date"] = view["Date"].dt.strftime("%Y-%m-%d %H:%M")
    view["Banner"] = view["Banner"].astype(str)
    view["Type"] = view["Type"].str.capitalize()
    view["Result"] = view["Result"].fillna("N/A")

    st.dataframe(
        style_result_column(view, "Result"),
        use_container_width=True,
        hide_index=True,
        height=480,
        column_config={
            "No.": st.column_config.NumberColumn("No.", format="%d", width="small"),
            "Pity": st.column_config.ProgressColumn(
                "Pity", format="%d", min_value=0, max_value=90 if rarity == 5 else 10
            ),
        },
    )
    st.caption("No. = order of the pull within its account, counted inside the current date/banner filters. Newest first.")


def insight_9_pull_history(df: pd.DataFrame):
    section_header("📜", "Pull History", "Every 5★ and 4★ pull, newest first")
    tab_5, tab_4 = st.tabs(["⭐ 5★ History", "💜 4★ History"])
    with tab_5:
        _render_history_table(df, 5)
    with tab_4:
        _render_history_table(df, 4)


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

    # ---- Sidebar: date & banner filters (applied to the whole page) ----
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

    if display_df.empty:
        st.warning("No pulls match the current filters. Adjust the date range or banner filter in the sidebar.")
        return

    # ---- Hero ----
    hero_chips = [
        f"📅 {date_range[0]} → {date_range[1]}",
        f"⭐ {int(display_df['is_5star'].sum()):,} five-star",
        f"🔮 {len(display_df):,} pulls",
        f"🏆 {calculate_win_rate(display_df):.0f}% 50-50 win rate",
    ]
    render_hero(title, subtitle, hero_chips)

    # Overview -> pity meters -> written summary -> detailed analysis
    single_account = display_df["account"].nunique() == 1
    stats = build_summary_stats(display_df)

    block_label("Overview")
    render_tldr(display_df, stats, single_account)
    render_key_parameters(stats)

    block_label("Banner Pity Meters")
    render_pity_cards(display_df)
    st.caption("Pity counters are computed from the pulls inside the active date and banner filters.")

    block_label("Summary")
    render_executive_summary(display_df, stats, single_account)

    block_label("Detailed Analysis")

    # Tabs ordered for presentation: big picture -> patterns -> outcomes -> items -> raw history
    (
        tab_total, tab_banner, tab_timeline, tab_pity, tab_5050,
        tab_luck, tab_items, tab_latest, tab_history,
    ) = st.tabs(
        [
            "📊 Total Pulls",
            "📍 Banner",
            "📈 Timeline",
            "🍀 Pity 5★",
            "🏆 50-50",
            "✨ Luck Score",
            "👑 Top Items",
            "🆕 Latest 5★",
            "📜 History",
        ]
    )

    with tab_total:
        insight_1_total_pull(display_df)

    with tab_banner:
        insight_6_banner_performance(display_df)

    with tab_timeline:
        insight_2_timeline(display_df)

    with tab_pity:
        insight_3_pity_distribution(display_df)

    with tab_5050:
        insight_4_win_lose(display_df)

    with tab_luck:
        insight_7_luck_score(display_df)

    with tab_items:
        insight_5_top_items(display_df)

    with tab_latest:
        insight_8_latest_5star(display_df)

    with tab_history:
        insight_9_pull_history(display_df)

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