"""
dashboard.py
============
Interactive Streamlit dashboard for gacha analytics, one section per game:

    Genshin Impact  |  Honkai: Star Rail

Each game section is self-contained and has the same structure:
    1. Account selector (every account found in the game's data) + date / banner filters
    2. Overview        - the game's own KPIs (never mixed with the other game)
    3. Banner pity meters
    4. Executive summary
    5. Detailed analysis tabs (Total Pulls, Banner, Timeline, Pity, 50-50, Luck Score,
       Top Items, Latest 5*, History)

Per-game rules (pity, soft pity, rate-up chance, banners, colours) come from
pipeline/config.py, and the Luck Score is computed by compute_luck() from
pipeline/luck.py, so the dashboard, the PNG reports and the Google Sheet agree.

Usage:
    pip install streamlit pandas plotly
    streamlit run dashboard.py

    Custom data files:
    streamlit run dashboard.py -- --gi-data data/data_clean_gi_887284572.csv --hsr-data data/data_clean_hsr.csv

Run from the project root; CSV files beside this script are detected automatically.
"""

import argparse
import copy
import html
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from pipeline.luck import compute_luck
from pipeline.config import GAMES, HSR_CLEAN, GameConfig, default_clean_csv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
def _first_existing(*paths: Path) -> Path:
    """First CSV that exists; otherwise the last candidate (the standard data/ location)."""
    return next((p for p in paths if p.exists()), paths[-1])


# Prefer the supplied CSVs beside this script; fall back to data/ (GI also accepts the old name data_clean.csv).
DEFAULT_DATA = {
    "GI": _first_existing(BASE_DIR / "data_clean_gi.csv", BASE_DIR / "data_clean.csv", default_clean_csv("GI")),
    "HSR": _first_existing(BASE_DIR / "data_clean_hsr.csv", HSR_CLEAN),
}
PREPROCESS_HINT = {"GI": "pipeline/02_preprocess_gi.py", "HSR": "pipeline/02_preprocess_hsr.py"}

# ----------------------------------------------------------------------------
# Design tokens — dark navy theme matching .streamlit/config.toml
# ----------------------------------------------------------------------------
BG_APP = "#0b1220"
BG_SIDEBAR = "#0b1220"
BG_CARD = "#121e2f"
BG_CARD_ALT = "#17263a"
BG_ELEVATED = "#1b2b40"
TEXT_PRIMARY = "#eef3f9"
TEXT_SECONDARY = "#c1cddd"
TEXT_MUTED = "#91a3b9"
DIVIDER = "rgba(238, 243, 249, 0.12)"

ACCENT_GOLD = "#f2a641"
ACCENT_PURPLE = "#ad91e8"
ACCENT_BLUE = "#79b8f2"
ACCENT_TEAL = "#55c2b2"
SUCCESS = "#54c78b"
DANGER = "#ff7777"

FONT_DISPLAY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FONT_BODY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FONT_MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

RARITY_COLORS = {3: ACCENT_BLUE, 4: ACCENT_PURPLE, 5: ACCENT_GOLD}
RESULT_COLORS = {"Win": SUCCESS, "Lose": DANGER, "Guaranteed": ACCENT_TEAL}
LUCK_SERIES = [("Pity efficiency", "avg_pity_luck", ACCENT_BLUE),
               ("Rate-up win luck", "win_rate_luck", SUCCESS),
               ("Luck Score", "luck_score", ACCENT_GOLD)]
LOW_SAMPLE = 5  # fewer decisive outcomes than this -> flagged as a small sample


def _version() -> tuple:
    out = []
    for part in st.__version__.split(".")[:2]:
        digits = re.sub(r"\D", "", part)
        out.append(int(digits) if digits else 0)
    return tuple(out)


# `use_container_width` was replaced by `width="stretch"` in newer Streamlit releases.
STRETCH = {"width": "stretch"} if _version() >= (1, 50) else {"use_container_width": True}

st.set_page_config(
    page_title="Gacha Analytics",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark Plotly template aligned with the application palette.
_clean_template = copy.deepcopy(pio.templates["plotly_dark"])
_clean_template.layout.paper_bgcolor = "rgba(0,0,0,0)"
_clean_template.layout.plot_bgcolor = "rgba(0,0,0,0)"
_clean_template.layout.font.color = TEXT_SECONDARY
_clean_template.layout.font.family = FONT_BODY
_clean_template.layout.xaxis.gridcolor = DIVIDER
_clean_template.layout.yaxis.gridcolor = DIVIDER
_clean_template.layout.xaxis.zerolinecolor = DIVIDER
_clean_template.layout.yaxis.zerolinecolor = DIVIDER
pio.templates["gacha_clean"] = _clean_template
pio.templates.default = "gacha_clean"

# ----------------------------------------------------------------------------
# Global styling
# ----------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    :root {{ color-scheme: dark; }}
    html, body, [class*="css"] {{ font-family: {FONT_BODY}; color: {TEXT_PRIMARY}; }}
    h1, h2, h3, h4, h5, .gx-hero-title, .gx-section-title {{
        font-family: {FONT_DISPLAY} !important;
        letter-spacing: -0.025em;
    }}

    .stApp {{ background: {BG_APP}; }}
    .block-container {{ max-width: 1440px; padding: 1.25rem 1.75rem 2.25rem; }}
    #MainMenu, footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stSidebar"] {{ background: {BG_SIDEBAR}; border-right: 1px solid {DIVIDER}; }}
    [data-testid="stSidebar"] > div:first-child {{ padding-top: 1rem; }}

    .gx-sidebar-brand {{ padding: 0.35rem 0.35rem 1rem; }}
    .gx-sidebar-mark {{ color: {ACCENT_TEAL}; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }}
    .gx-sidebar-name {{ color: {TEXT_PRIMARY}; font-size: 1.28rem; font-weight: 750; line-height: 1.2; margin-top: 0.25rem; }}
    .gx-sidebar-caption {{ color: {TEXT_MUTED}; font-size: 0.76rem; margin-top: 0.35rem; line-height: 1.5; }}
    .gx-side-section {{ color: {TEXT_MUTED}; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; margin: 0.3rem 0 0.55rem; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label p {{ color: {TEXT_SECONDARY}; font-weight: 600; }}

    .gx-appbar {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; padding: 0.2rem 0 0.9rem; margin-bottom: 0.25rem; border-bottom: 1px solid {DIVIDER}; }}
    .gx-app-kicker {{ color: {ACCENT_TEAL}; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }}
    .gx-app-title {{ color: {TEXT_PRIMARY}; font-family: {FONT_DISPLAY}; font-size: 1.5rem; font-weight: 750; letter-spacing: -0.03em; line-height: 1.2; margin-top: 0.2rem; }}
    .gx-app-subtitle {{ color: {TEXT_MUTED}; font-size: 0.82rem; margin-top: 0.25rem; }}
    .gx-app-status {{ color: {TEXT_SECONDARY}; font-size: 0.66rem; font-weight: 650; border: 1px solid {DIVIDER}; background: #121e2f; border-radius: 6px; padding: 0.32rem 0.55rem; white-space: nowrap; }}

    .gx-hero {{ background: {BG_CARD}; border: 1px solid {DIVIDER}; border-left: 3px solid {ACCENT_TEAL}; border-radius: 10px; padding: 1.05rem 1.25rem; margin: 0.55rem 0 1.15rem; }}
    .gx-hero-eyebrow {{ font-size: 0.65rem; font-weight: 700; letter-spacing: 0.11em; color: {ACCENT_TEAL}; text-transform: uppercase; margin-bottom: 0.4rem; }}
    .gx-hero-title {{ font-size: 1.65rem; font-weight: 750; color: {TEXT_PRIMARY}; line-height: 1.15; }}
    .gx-hero-subtitle {{ color: {TEXT_SECONDARY}; font-size: 0.84rem; margin-top: 0.35rem; }}
    .gx-hero-chips {{ margin-top: 0.8rem; display: flex; flex-wrap: wrap; gap: 0.4rem; }}
    .gx-chip {{ display: inline-block; background: {BG_CARD_ALT}; border: 1px solid {DIVIDER}; color: {TEXT_SECONDARY}; font-size: 0.68rem; padding: 0.3rem 0.55rem; border-radius: 6px; }}

    .st-key-gi_filter_panel, .st-key-hsr_filter_panel {{ background: {BG_CARD}; border: 1px solid {DIVIDER}; border-radius: 10px; padding: 0.55rem 0.85rem 0.25rem; margin: 0.55rem 0 1.15rem; }}
    [data-testid="stWidgetLabel"] p {{ color: {TEXT_SECONDARY}; font-size: 0.76rem; font-weight: 600; }}
    [data-baseweb="select"] > div {{ background: #121e2f; border-color: {DIVIDER}; border-radius: 7px; }}
    [data-baseweb="tag"] {{ background: #1d3a43; border: 1px solid #315765; color: #bce8df; }}
    [data-testid="stSlider"] [data-baseweb="slider"] {{ padding-top: 0.2rem; }}

    .gx-section {{ display: flex; align-items: baseline; flex-wrap: wrap; gap: 0.5rem; border-bottom: 1px solid {DIVIDER}; padding-bottom: 0.55rem; margin: 0.35rem 0 0.8rem; }}
    .gx-section-title {{ font-size: 1.02rem; font-weight: 750; color: {TEXT_PRIMARY}; }}
    .gx-section-subtitle {{ color: {TEXT_MUTED}; font-size: 0.75rem; margin-left: 0.1rem; }}
    .block-label {{ display: flex; align-items: center; gap: 0.6rem; margin: 1.35rem 0 0.65rem; }}
    .block-label-text {{ font-size: 0.66rem; font-weight: 700; letter-spacing: 0.11em; text-transform: uppercase; color: {TEXT_MUTED}; white-space: nowrap; }}
    .block-label-line {{ flex: 1; height: 1px; background: {DIVIDER}; }}

    .gx-card {{ background: {BG_CARD}; border: 1px solid {DIVIDER}; border-radius: 9px; padding: 0.9rem 1rem; margin-bottom: 0.65rem; }}
    .gx-card-title {{ font-family: {FONT_DISPLAY}; font-size: 0.88rem; font-weight: 700; color: {TEXT_PRIMARY}; margin-bottom: 0.65rem; }}
    .gx-card-row {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 0.75rem; padding: 0.42rem 0 0.12rem; }}
    .gx-card-divider {{ border-top: 1px solid {DIVIDER}; margin-top: 0.65rem; }}
    .gx-card-label {{ color: {TEXT_SECONDARY}; font-size: 0.75rem; line-height: 1.4; }}
    .gx-card-sublabel {{ color: {TEXT_MUTED}; font-size: 0.68rem; }}
    .gx-card-value {{ font-family: {FONT_MONO}; font-size: 1.22rem; font-weight: 700; color: {TEXT_PRIMARY}; }}
    .gx-gold {{ color: {ACCENT_GOLD}; }}
    .gx-purple {{ color: {ACCENT_PURPLE}; }}
    .pity-bar-track {{ height: 5px; border-radius: 999px; background: #26374c; overflow: hidden; margin-top: 0.45rem; }}
    .pity-bar-fill {{ height: 100%; border-radius: 999px; }}

    .kpi-card {{ background: {BG_CARD}; border: 1px solid {DIVIDER}; border-radius: 9px; padding: 0.85rem 0.95rem; min-height: 100px; margin-bottom: 0.6rem; }}
    .kpi-label {{ color: {TEXT_MUTED}; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; }}
    .kpi-value {{ font-family: {FONT_MONO}; font-weight: 700; margin: 0.5rem 0 0.25rem; line-height: 1.2; overflow-wrap: anywhere; }}
    .kpi-sub {{ color: {TEXT_SECONDARY}; font-size: 0.69rem; line-height: 1.4; }}
    .gx-badge {{ display: inline-flex; align-items: center; font-size: 0.65rem; font-weight: 700; padding: 0.18rem 0.42rem; border-radius: 5px; margin-right: 0.22rem; }}
    .summary-list {{ color: {TEXT_SECONDARY}; font-size: 0.82rem; line-height: 1.7; padding-left: 1.05rem; margin: 0; }}
    .summary-list li {{ padding: 0.1rem 0; }}
    .summary-list b {{ color: {TEXT_PRIMARY}; }}
    .chart-note {{ color: {TEXT_SECONDARY}; font-size: 0.74rem; line-height: 1.55; background: #17263a; border-left: 2px solid {ACCENT_TEAL}; border-radius: 0 6px 6px 0; padding: 0.5rem 0.7rem; margin: 0.45rem 0 0.85rem; }}
    .chart-note b {{ color: {TEXT_PRIMARY}; }}
    .gx-chart-guide {{ color: {TEXT_MUTED}; font-size: 0.72rem; line-height: 1.45; margin: 0.25rem 0 0.8rem; padding-left: 0.6rem; border-left: 2px solid #40536a; }}
    .gx-chart-guide b {{ color: {TEXT_SECONDARY}; font-weight: 700; }}

    [data-testid="stMetric"] {{ background: {BG_CARD}; border: 1px solid {DIVIDER}; border-radius: 8px; padding: 0.65rem 0.8rem; }}
    [data-testid="stMetricValue"] {{ font-family: {FONT_MONO}; color: {ACCENT_BLUE}; font-size: 1.25rem; }}
    [data-testid="stMetricLabel"] {{ color: {TEXT_SECONDARY}; font-size: 0.72rem; }}
    [data-baseweb="tab-list"] {{ gap: 0.2rem; border-bottom: 1px solid {DIVIDER}; overflow-x: auto; }}
    [data-baseweb="tab"] {{ font-family: {FONT_DISPLAY}; font-weight: 650; font-size: 0.78rem; color: {TEXT_MUTED}; padding: 0.55rem 0.75rem; white-space: nowrap; }}
    [data-baseweb="tab"][aria-selected="true"] {{ color: {TEXT_PRIMARY}; }}
    [data-baseweb="tab-highlight"] {{ background: {ACCENT_TEAL} !important; height: 2px; }}
    [data-baseweb="tab-panel"] {{ padding-top: 0.8rem; }}
    [data-baseweb="tab-panel"] [data-baseweb="tab-list"] {{ border-bottom: none; gap: 0.3rem; padding-bottom: 0.1rem; }}
    [data-baseweb="tab-panel"] [data-baseweb="tab"] {{ background: #121e2f; border: 1px solid {DIVIDER}; border-radius: 6px; padding: 0.3rem 0.65rem; font-size: 0.72rem; }}
    [data-baseweb="tab-panel"] [data-baseweb="tab"][aria-selected="true"] {{ background: #22364d; border-color: #405b76; color: {TEXT_PRIMARY}; }}
    [data-baseweb="tab-panel"] [data-baseweb="tab-highlight"], [data-baseweb="tab-panel"] [data-baseweb="tab-border"] {{ display: none; }}
    [data-testid="stDataFrame"] {{ border: 1px solid {DIVIDER}; border-radius: 8px; overflow: hidden; }}
    [data-testid="stExpander"] {{ border: 1px solid {DIVIDER}; border-radius: 8px; background: {BG_CARD}; }}
    [data-testid="stPlotlyChart"] {{ background: {BG_CARD}; border: 1px solid {DIVIDER}; border-radius: 9px; padding: 0.2rem 0.25rem 0; }}
    .stDownloadButton > button {{ background: #22364d; color: {TEXT_PRIMARY}; border: 1px solid #405b76; border-radius: 7px; font-weight: 650; min-height: 2.45rem; }}
    .stDownloadButton > button:hover {{ background: #2a4059; border-color: {ACCENT_BLUE}; color: {TEXT_PRIMARY}; }}
    [data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED}; }}
    .gx-footer {{ text-align: center; color: {TEXT_MUTED}; font-size: 0.68rem; padding: 1rem 0 0.3rem; border-top: 1px solid {DIVIDER}; margin-top: 1.8rem; }}

    @media (max-width: 900px) {{ .block-container {{ padding: 1rem 1rem 1.8rem; }} .gx-hero {{ padding: 0.95rem 1rem; }} .gx-appbar {{ align-items: flex-start; flex-direction: column; }} }}
    @media (max-width: 600px) {{ .block-container {{ padding: 0.75rem 0.6rem 1.35rem; }} .gx-chip {{ font-size: 0.63rem; }} .gx-section {{ gap: 0.3rem; }} .gx-section-subtitle {{ width: 100%; margin-left: 0; }} }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# Presentation helpers
# ============================================================================
SECTION_MEANINGS = {
    "Total Pulls & Account Progress": "Summarizes pull volume and rarity composition to compare account activity.",
    "5★ Pity Distribution": "Shows how many pulls were needed to obtain each 5★ item.",
    "Hazard Rate": "Estimates the chance of obtaining a 5★ at each pity level, provided one has not appeared yet.",
    "4★ Pity Distribution": "Shows the number of pulls required to obtain each 4★ item.",
    "5★ Pity Timeline": "Tracks the pity count for each 5★ result over time; colors distinguish rate-up outcomes.",
    "5★ Actual vs Expected": "Compares the actual number of 5★ results with the estimate based on the banner consolidated rate.",
    "Rolling Pulls per 5★": "Tracks the moving average pity across recent 5★ results to show changes in efficiency.",
    "50-50 Win/Lose": "Compares wins, losses, guarantees, and the rate-up win rate.",
    "Banner Performance": "Compares pull volume, 5★ acquisition efficiency, and rate-up success across banners.",
    "Luck Score": "Combines pity efficiency (60%) and rate-up success (40%); a score of 50 is neutral.",
    "Pull History": "Lists obtained 5★ and 4★ items, with banner and item-type filters.",
}


def section_meaning(title: str, fallback: str = "") -> str:
    if title in SECTION_MEANINGS:
        return SECTION_MEANINGS[title]
    if title.endswith(" Timeline") and title.split(" ", 1)[0] in {"Wish", "Warp"}:
        return "Shows monthly pull activity and each banner’s contribution."
    if title.startswith("Top Character &"):
        return "Summarizes the most frequently obtained 4★–5★ characters and weapons / Light Cones."
    if title.startswith("Latest 5★"):
        return "Shows the latest 5★ results for each banner, sorted newest first."
    return fallback


def section_header(title: str, subtitle: str = ""):
    meaning = section_meaning(title, subtitle)
    sub = f'<span class="gx-section-subtitle">What it shows: {html.escape(meaning)}</span>' if meaning else ""
    st.markdown(
        f'<div class="gx-section"><span class="gx-section-title">{html.escape(title)}</span>{sub}</div>',
        unsafe_allow_html=True,
    )


def block_label(text: str):
    st.markdown(
        f'<div class="block-label"><span class="block-label-text">{text}</span>'
        f'<span class="block-label-line"></span></div>',
        unsafe_allow_html=True,
    )


def chart_note(text: str):
    st.markdown(f'<div class="chart-note">{text}</div>', unsafe_allow_html=True)


def badge(text: str, color: str) -> str:
    return (
        f'<span class="gx-badge" style="background:{color}26; color:{color}; '
        f'border:1px solid {color}55;">{text}</span>'
    )


CHART_MEANINGS = {
    "total_pull": "The share of 3★, 4★, and 5★ results in each account’s pulls; compares rarity mix rather than raw volume.",
    "timeline": "Monthly pulls by banner; stacked bars show each banner’s contribution.",
    "timeline_5star": "The number of 5★ items obtained each month, broken down by banner.",
    "timeline_4star": "The number of 4★ items obtained each month, broken down by banner.",
    "pity_cdf": "The cumulative share of 5★ results obtained by each pity level; a faster-rising curve means results tend to arrive sooner.",
    "pity_timeline": "Each point represents one 5★ result; the X-axis shows the date and the Y-axis shows the pity count when it was obtained.",
    "exp_cum": "Compares cumulative actual 5★ results with the estimate based on the configured official rates.",
    "exp_gap": "Actual minus expected; a positive value means more 5★ results than expected by that date.",
    "rolling": "Dots show the pity count for each 5★; the line shows the moving average across the latest N results.",
    "wl_stack": "Rate-up outcome breakdown: Win, Lose, and Guaranteed for each banner and rarity.",
    "wl_rate": "Win rate is calculated from Win/Lose outcomes only; the marker shows the official 5★ rate-up chance.",
    "luck": "Compares pity efficiency, rate-up success, and Luck Score by account; 50 is the neutral point.",
    "banner_total": "Total pulls recorded for each banner; shows how activity is distributed.",
    "banner_eff": "Average pulls required to obtain one 5★; lower values indicate greater efficiency.",
    "banner_wr": "The 5★ rate-up win percentage among Win/Lose outcomes; the marker is the banner’s official baseline.",
}


def chart_meaning(name: str) -> str:
    if name in CHART_MEANINGS:
        return CHART_MEANINGS[name]
    if name.startswith("pity4_"):
        return "Distribution of pulls required to obtain a 4★ on this banner; the dashed line marks the average."
    if name.startswith("pity_"):
        return "Distribution of pulls required to obtain a 5★ on this banner; the dashed line marks the average and hard pity."
    if name.startswith("hazard_"):
        return "Observed chance of obtaining a 5★ in each pity bucket; faded bars indicate smaller at-risk samples."
    if name.startswith("top_"):
        return "Most frequently obtained items; bar length shows the number obtained and color indicates rarity."
    return "This chart summarizes data matching the account, banner, and date filters above."


def show(fig, k: str, name: str):
    """Render a Plotly figure and a short English guide, with a unique chart key."""
    st.plotly_chart(fig, key=f"{k}_{name}", **STRETCH)
    st.markdown(
        f'<div class="gx-chart-guide"><b>What it shows:</b> {html.escape(chart_meaning(name))}</div>',
        unsafe_allow_html=True,
    )


def show_df(data, **kwargs):
    st.dataframe(data, hide_index=True, **STRETCH, **kwargs)


def apply_layout(fig, title, xaxis_title=None, yaxis_title=None, height=380, legend=False, yaxis_range=None, **extra):
    """Shared chart design: typography, margins, gridlines and hover styling."""
    axis_base = dict(
        gridcolor=DIVIDER, zerolinecolor=DIVIDER, linecolor=DIVIDER,
        tickfont=dict(family=FONT_BODY, size=10, color=TEXT_SECONDARY),
        title_font=dict(family=FONT_BODY, size=10, color=TEXT_MUTED),
    )
    xaxis_cfg = {**axis_base, "title": xaxis_title}
    yaxis_cfg = {**axis_base, "title": yaxis_title}
    if yaxis_range is not None:
        yaxis_cfg["range"] = yaxis_range
    fig.update_layout(
        title=dict(text=title, font=dict(family=FONT_DISPLAY, size=14, color=TEXT_PRIMARY), x=0.015, xanchor="left"),
        font=dict(family=FONT_BODY, color=TEXT_SECONDARY, size=11),
        xaxis=xaxis_cfg,
        yaxis=yaxis_cfg,
        height=height,
        margin=dict(l=12, r=14, t=58, b=12),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=TEXT_SECONDARY)),
        hoverlabel=dict(bgcolor=BG_CARD_ALT, bordercolor=DIVIDER,
                        font=dict(family=FONT_BODY, color=TEXT_PRIMARY, size=11)),
        **extra,
    )
    return fig


def style_result_column(df: pd.DataFrame, column: str = "Result"):
    def _style(val):
        color = RESULT_COLORS.get(val)
        if color:
            return f"background-color:{color}22; color:{color}; font-weight:700;"
        return f"color:{TEXT_MUTED};"

    styler = df.style
    style_fn = getattr(styler, "map", None) or styler.applymap
    return style_fn(_style, subset=[column])


def kpi_card(label: str, value: str, sub: str = "", color: str = ACCENT_GOLD, value_size: str = "1.6em") -> str:
    return (
        f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value" style="color:{color}; font-size:{value_size};">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
    )


# ============================================================================
# Data + domain helpers (all driven by GameConfig)
# ============================================================================


def pull_plural(word: str) -> str:
    """Return a readable plural for the game's pull noun (Wish -> Wishes, Warp -> Warps)."""
    return "Wishes" if word.lower() == "wish" else (word + "es" if word.lower().endswith(("s", "sh", "ch", "x", "z")) else word + "s")


def order_banners(cfg: GameConfig, items) -> list:
    """Banner names in the game's canonical order, unexpected names last."""
    items = list(items)
    return [b for b in cfg.banner_order if b in items] + [b for b in items if b not in cfg.banner_order]


@st.cache_data
def load_data(filepath: str, mtime: float, game_key: str) -> pd.DataFrame:
    """Load a data_clean CSV. `mtime` only exists to refresh the cache when the file changes."""
    cfg = GAMES[game_key]
    df = pd.read_csv(filepath)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df[df["datetime"].notna()].reset_index(drop=True)
    df["date"] = df["datetime"].dt.date
    df["year_month"] = df["datetime"].dt.to_period("M").astype(str)
    df["is_5star"] = df["rarity"] == 5
    df["is_4star"] = df["rarity"] == 4
    df["is_3star"] = df["rarity"] == 3
    for col in ("uid", "adventure_rank", "world_level"):
        if col not in df.columns:
            df[col] = float("nan")

    # Pulls of one multi-pull share a timestamp, so `seq` gives the true order (0 = oldest).
    if "pull_number" in df.columns and df["pull_number"].notna().all():
        df["seq"] = df["pull_number"].astype(int)
    else:
        df["_row"] = range(len(df))

        def _chrono_seq(g):
            newest_first = g["datetime"].iloc[0] > g["datetime"].iloc[-1]
            return g["_row"].max() - g["_row"] if newest_first else g["_row"]

        df["seq"] = pd.concat([_chrono_seq(g) for _, g in df.groupby("account", sort=False)]).reindex(df.index)
        df = df.drop(columns="_row")

    df["banner_type"] = pd.Categorical(
        df["banner_type"], categories=order_banners(cfg, df["banner_type"].dropna().unique()), ordered=True
    )
    return df


def account_order(df: pd.DataFrame) -> list:
    """Main account first (name contains 'main', otherwise the most pulls), rest A-Z."""
    counts = df["account"].value_counts()
    mains = [a for a in counts.index if "main" in str(a).lower()]
    main = mains[0] if mains else counts.idxmax()
    return [main] + sorted(a for a in df["account"].unique() if a != main)


def current_pity(df: pd.DataFrame, banner: str, star: int = 5):
    """Pulls since the last pull of this rarity within one banner (None if no pulls).
    The 5* and 4* counters are independent."""
    b = df[df["banner_type"] == banner].sort_values(["datetime", "seq"]).reset_index(drop=True)
    if b.empty:
        return None
    pos = b.index[b["is_5star"] if star == 5 else b["is_4star"]]
    return len(b) if len(pos) == 0 else len(b) - pos[-1] - 1


def luck_table(df: pd.DataFrame, cfg: GameConfig) -> pd.DataFrame:
    """Luck Score per account using the shared formula from pipeline/luck.py."""
    d = df.copy()
    d["banner_type"] = d["banner_type"].astype(object)
    return compute_luck(d, cfg)


def overall_luck(df: pd.DataFrame, cfg: GameConfig):
    """One Luck Score for the whole selection (all accounts pooled)."""
    d = df.copy()
    d["banner_type"] = d["banner_type"].astype(object)
    d["account"] = "All"
    row = compute_luck(d, cfg).iloc[0]
    return None if pd.isna(row["luck_score"]) else float(row["luck_score"])


def luck_verdict(score: float):
    if score > 70:
        return "Very lucky", SUCCESS
    if score >= 50:
        return "Above average", ACCENT_TEAL
    return "Below average", DANGER


def rateup_stats(df: pd.DataFrame, cfg: GameConfig):
    """5* rate-up outcomes (Win vs Lose; Guaranteed excluded): wins, losses, expected win rate (%)."""
    d = df[(df["rarity"] == 5) & df["win_50_50"].isin(["Win", "Lose"])]
    wins = int((d["win_50_50"] == "Win").sum())
    losses = len(d) - wins
    expected = d["banner_type"].astype(object).map(cfg.rateup_chance).fillna(50.0).mean() if len(d) else None
    return wins, losses, expected


def build_summary_stats(df: pd.DataFrame, cfg: GameConfig) -> dict:
    total = len(df)
    five = df[df["is_5star"]].sort_values(["datetime", "seq"])
    n5 = len(five)
    wins, losses, expected = rateup_stats(df, cfg)
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
        "expected": expected,
        "luck": overall_luck(df, cfg),
        "last5": five.iloc[-1] if n5 else None,
    }


# ============================================================================
# Overview blocks
# ============================================================================
def render_hero(cfg: GameConfig, title: str, subtitle: str, chips: list):
    chips_html = "".join(f'<span class="gx-chip">{html.escape(str(c))}</span>' for c in chips)
    st.markdown(
        f"""
        <div class="gx-hero">
            <div class="gx-hero-eyebrow">{cfg.title} · {cfg.pull_word} Analytics</div>
            <div class="gx-hero-title">{html.escape(title)}</div>
            <div class="gx-hero-subtitle">{html.escape(subtitle)}</div>
            <div class="gx-hero-chips">{chips_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_key_parameters(cfg: GameConfig, stats: dict):
    w = cfg.pull_word
    cards = [kpi_card(f"Total {pull_plural(w)}", f"{stats['total']:,}", f"≈ {stats['total'] * cfg.pull_cost:,} {cfg.currency}")]

    per5 = f"1 per {stats['per_5']:.1f} {pull_plural(w).lower()}" if stats["per_5"] else "no 5★ yet"
    cards.append(kpi_card("5★ Obtained", f"{stats['n5']:,}", f"{per5} · 4★: {stats['n4']:,}"))

    avg = f"{stats['avg_pity_5']:.1f}" if stats["avg_pity_5"] is not None else "-"
    cards.append(kpi_card("Avg Pity 5★", avg, "lower = better"))

    if stats["win_rate"] is not None:
        exp = f" · expected {stats['expected']:.0f}%" if stats["expected"] is not None else ""
        color = SUCCESS if stats["expected"] is None or stats["win_rate"] >= stats["expected"] else DANGER
        cards.append(
            kpi_card("5★ Rate-up Win Rate", f"{stats['win_rate']:.0f}%", f"{stats['wins']}W–{stats['losses']}L{exp}", color)
        )
    else:
        cards.append(kpi_card("5★ Rate-up Win Rate", "-", "no decisive rate-up outcomes", TEXT_MUTED))

    if stats["luck"] is not None:
        label, color = luck_verdict(stats["luck"])
        cards.append(kpi_card("Luck Score", f"{stats['luck']:.0f}", label, color))
    else:
        cards.append(kpi_card("Luck Score", "-", "needs 5★ data", TEXT_MUTED))

    last5 = stats["last5"]
    if last5 is not None:
        pity_txt = f" · pity {int(last5['pity'])}" if pd.notna(last5["pity"]) else ""
        cards.append(
            kpi_card("Latest 5★", html.escape(str(last5["item_name"])), f"{last5['datetime']:%Y-%m-%d}{pity_txt}",
                     ACCENT_GOLD, value_size="1.05em")
        )
    else:
        cards.append(kpi_card("Latest 5★", "-", "none yet", TEXT_MUTED, value_size="1.05em"))

    for row_cards in (cards[:3], cards[3:]):
        for col, card in zip(st.columns(3), row_cards):
            with col:
                st.markdown(card, unsafe_allow_html=True)


def render_pity_cards(df: pd.DataFrame, cfg: GameConfig):
    banners = [b for b in cfg.pity_card_banners if b in set(df["banner_type"].dropna().astype(str))] or cfg.pity_card_banners
    per_row = 2 if len(banners) == 4 else 3   # 4 banners -> 2x2 grid instead of 3+1
    for i in range(0, len(banners), per_row):
        cols = st.columns(per_row)
        for col, banner in zip(cols, banners[i:i + per_row]):
            lifetime = int((df["banner_type"] == banner).sum())
            p5, p4 = current_pity(df, banner, 5), current_pity(df, banner, 4)
            hard5 = cfg.hard_pity.get(banner, cfg.default_hard_pity)
            hard4 = cfg.hard_pity_4
            soft5 = cfg.soft_pity.get(banner)
            pct5 = min(100, round((p5 or 0) / hard5 * 100)) if p5 is not None else 0
            pct4 = min(100, round((p4 or 0) / hard4 * 100)) if p4 is not None else 0
            in_soft = soft5 is not None and p5 is not None and p5 >= soft5
            bar5 = DANGER if in_soft else ACCENT_GOLD
            soft_txt = f" · soft pity from {soft5}" if soft5 else ""
            top = cfg.banner_colors.get(banner, ACCENT_GOLD)
            with col:
                st.markdown(
                    f"""
                    <div class="gx-card" style="border-top:3px solid {top};">
                        <div class="gx-card-title">{banner}</div>
                        <div class="gx-card-row">
                            <div class="gx-card-label">Lifetime {pull_plural(cfg.pull_word)}</div>
                            <div class="gx-card-value">{lifetime:,}</div>
                        </div>
                        <div class="gx-card-divider"></div>
                        <div class="gx-card-row">
                            <div class="gx-card-label">5★ Pity<br>
                                <span class="gx-card-sublabel">Hard pity {hard5}{soft_txt}</span></div>
                            <div class="gx-card-value gx-gold">{p5 if p5 is not None else '-'}</div>
                        </div>
                        <div class="pity-bar-track"><div class="pity-bar-fill" style="width:{pct5}%; background:{bar5};"></div></div>
                        <div class="gx-card-divider"></div>
                        <div class="gx-card-row">
                            <div class="gx-card-label">4★ Pity<br>
                                <span class="gx-card-sublabel">Guaranteed at {hard4}</span></div>
                            <div class="gx-card-value gx-purple">{p4 if p4 is not None else '-'}</div>
                        </div>
                        <div class="pity-bar-track"><div class="pity-bar-fill" style="width:{pct4}%; background:{ACCENT_PURPLE};"></div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_pity_section(df: pd.DataFrame, cfg: GameConfig):
    """Pity only makes sense per account: one tab per account when several are selected."""
    accounts = account_order(df)
    if len(accounts) <= 1:
        render_pity_cards(df, cfg)
        return
    tabs = st.tabs(accounts)
    for tab, acc in zip(tabs, accounts):
        with tab:
            render_pity_cards(df[df["account"] == acc], cfg)


def render_executive_summary(df: pd.DataFrame, cfg: GameConfig, stats: dict, single_account: bool):
    items = []
    start, end = df["datetime"].min().strftime("%b %Y"), df["datetime"].max().strftime("%b %Y")
    overall = f"<b>Period:</b> {start} – {end} · 5★ rate {stats['rate_5']:.2f}% ({stats['n5']} of {stats['total']:,} {pull_plural(cfg.pull_word).lower()})"
    if stats["avg_pity_5"] is not None:
        overall += f" · avg 5★ pity {stats['avg_pity_5']:.1f}"
    items.append(overall + ".")

    five = df[df["is_5star"]]
    if stats["wins"] + stats["losses"] > 0:
        g5 = int((five["win_50_50"] == "Guaranteed").sum())
        exp = f" vs {stats['expected']:.0f}% expected" if stats["expected"] is not None else ""
        items.append(
            f"<b>5★ rate-up:</b> won {stats['wins']}, lost {stats['losses']} "
            f"({stats['win_rate']:.0f}% win rate{exp}); {g5} more came from guarantees."
        )

    perf = df.groupby("banner_type", observed=True).agg(pulls=("item_id", "count"), five=("is_5star", "sum"))
    perf = perf[perf["five"] > 0]
    if len(perf) >= 2:
        ppf = perf["pulls"] / perf["five"]
        best, worst = ppf.idxmin(), ppf.idxmax()
        if best != worst:
            items.append(
                f"<b>Banner efficiency:</b> {best} is the most efficient ({ppf[best]:.1f} {pull_plural(cfg.pull_word).lower()} per 5★), "
                f"{worst} the least ({ppf[worst]:.1f})."
            )

    monthly = df.groupby("year_month").size()
    items.append(
        f"<b>Activity:</b> busiest month was {monthly.idxmax()} ({monthly.max():,} {pull_plural(cfg.pull_word).lower()}); "
        f"latest {cfg.pull_word.lower()} on {df['datetime'].max():%Y-%m-%d}."
    )

    for acc in account_order(df):
        acc_df = df[df["account"] == acc]
        parts = []
        for banner, short in cfg.summary_banners:
            pity = current_pity(acc_df, banner, 5)
            if pity is None:
                continue
            hard, soft = cfg.hard_pity[banner], cfg.soft_pity.get(banner)
            state = ""
            if soft:
                state = " (in soft pity)" if pity >= soft else f" ({soft - pity} to soft pity)"
            parts.append(f"{short} <b>{pity}/{hard}</b>{state}")
        if parts:
            label = "Current 5★ pity" if single_account else f"Current 5★ pity · {html.escape(str(acc))}"
            items.append(f"<b>{label}:</b> " + " · ".join(parts) + ".")

    body = "".join(f"<li>{item}</li>" for item in items)
    with st.expander("Executive Summary", expanded=True):
        st.markdown(f'<ul class="summary-list">{body}</ul>', unsafe_allow_html=True)


# ============================================================================
# Analysis tabs
# ============================================================================
def account_filter(df: pd.DataFrame, k: str, key: str, all_label: str = "All") -> pd.DataFrame:
    """Per-tab account selector, shown only when several accounts are in the selection."""
    accounts = account_order(df)
    if len(accounts) <= 1:
        return df
    choice = st.radio("Account", [all_label] + accounts, horizontal=True, key=f"{k}_accfilter_{key}")
    return df if choice == all_label else df[df["account"] == choice]


def banner_filter_radio(df: pd.DataFrame, cfg: GameConfig, k: str, key: str, all_label: str = "All"):
    """Single-banner selector for a tab. Returns (filtered df, chosen banner or None for all)."""
    banners = order_banners(cfg, df["banner_type"].dropna().astype(str).unique())
    if len(banners) <= 1:
        return df, (banners[0] if banners else None)
    choice = st.radio("Banner", [all_label] + banners, horizontal=True, key=f"{k}_bannerfilter_{key}")
    if choice == all_label:
        return df, None
    return df[df["banner_type"].astype(str) == choice], choice


def insight_total_pull(df, cfg, k):
    w = cfg.pull_word
    section_header("Total Pulls & Account Progress", f"Rarity breakdown per account")
    summary = (
        df.groupby("account")
        .agg(
            uid=("uid", "first"), adventure_rank=("adventure_rank", "first"), world_level=("world_level", "first"),
            total_pull=("item_id", "count"), pull_5star=("is_5star", "sum"),
            pull_4star=("is_4star", "sum"), pull_3star=("is_3star", "sum"),
        )
        .reset_index()
    )
    summary["pct_5star"] = (summary["pull_5star"] / summary["total_pull"] * 100).round(2)
    summary["pct_4star"] = (summary["pull_4star"] / summary["total_pull"] * 100).round(2)

    col1, col2 = st.columns(2)
    with col1:
        # 100% stacked: compares rarity mix without the largest account flattening the others.
        ranked = summary.sort_values("total_pull", ascending=False)
        labels = [f"{a}<br>{int(t):,} {pull_plural(w).lower()}" for a, t in zip(ranked["account"], ranked["total_pull"])]
        fig = go.Figure()
        for r in (3, 4, 5):
            share = ranked[f"pull_{r}star"] / ranked["total_pull"] * 100
            fig.add_trace(go.Bar(
                y=labels, x=share, orientation="h", name=f"{r}★", marker_color=RARITY_COLORS[r],
                customdata=ranked[f"pull_{r}star"],
                hovertemplate=f"{r}★: %{{x:.2f}}% (%{{customdata:,}} {pull_plural(w).lower()})<extra></extra>",
            ))
        apply_layout(fig, f"{w} Rarity Mix per Account (100%)", "Share of total (%)", None,
                     barmode="stack", legend=True, height=380)
        fig.update_xaxes(range=[0, 100])
        fig.update_yaxes(autorange="reversed")
        show(fig, k, "total_pull")
        top = summary.sort_values("total_pull", ascending=False).iloc[0]
        if len(summary) > 1:
            chart_note(f"<b>{html.escape(str(top['account']))}</b> has the most {pull_plural(w).lower()} ({int(top['total_pull']):,}). "
                       f"5★ share ranges from {summary['pct_5star'].min():.2f}% to {summary['pct_5star'].max():.2f}%.")
        else:
            chart_note(f"{int(top['total_pull']):,} {pull_plural(w).lower()}: {int(top['pull_5star'])} five-star ({top['pct_5star']:.2f}%), "
                       f"{int(top['pull_4star'])} four-star, {int(top['pull_3star'])} three-star.")

    with col2:
        has_progress = summary["adventure_rank"].notna().any()
        fig = go.Figure()
        if has_progress:
            def _lvl(v):
                return f"{int(v)}" if pd.notna(v) else "-"

            prog_rows = [
                '<div class="gx-card-row">'
                f'<div class="gx-card-label"><b style="color:{TEXT_PRIMARY}; font-size:0.95rem;">{html.escape(str(r["account"]))}</b></div>'
                '<div style="display:flex; gap:1.8rem; text-align:right;">'
                f'<div><div class="gx-card-sublabel">Adventure Rank</div><div class="gx-card-value gx-gold">{_lvl(r["adventure_rank"])}</div></div>'
                f'<div><div class="gx-card-sublabel">World Level</div><div class="gx-card-value" style="color:{ACCENT_BLUE};">{_lvl(r["world_level"])}</div></div>'
                '</div></div>'
                for _, r in summary.sort_values("adventure_rank", ascending=False).iterrows()
            ]
            st.markdown(
                '<div class="gx-card"><div class="gx-card-title">Account Progress</div>'
                + '<div class="gx-card-divider"></div>'.join(prog_rows) + '</div>',
                unsafe_allow_html=True,
            )
            ar = summary.dropna(subset=["adventure_rank"]).sort_values("adventure_rank", ascending=False).iloc[0]
            wl = f" (World Level {int(ar['world_level'])})" if pd.notna(ar["world_level"]) else ""
            chart_note(f"Progression context only: highest Adventure Rank is {int(ar['adventure_rank'])}{wl} on "
                       f"<b>{html.escape(str(ar['account']))}</b>. It shows how far an account has advanced, not how lucky it was.")
        else:
            # No account level data in this export: same text-only card, showing observed rates instead.
            def _per5(r):
                return f"{r['total_pull'] / r['pull_5star']:.1f}" if r["pull_5star"] else "-"

            sum_rows = [
                '<div class="gx-card-row">'
                f'<div class="gx-card-label"><b style="color:{TEXT_PRIMARY}; font-size:0.95rem;">{html.escape(str(r["account"]))}</b></div>'
                '<div style="display:flex; gap:1.8rem; text-align:right;">'
                f'<div><div class="gx-card-sublabel">5★ rate</div><div class="gx-card-value gx-gold">{r["pct_5star"]:.2f}%</div></div>'
                f'<div><div class="gx-card-sublabel">4★ rate</div><div class="gx-card-value gx-purple">{r["pct_4star"]:.2f}%</div></div>'
                f'<div><div class="gx-card-sublabel">{pull_plural(w)} per 5★</div><div class="gx-card-value">{_per5(r)}</div></div>'
                '</div></div>'
                for _, r in summary.sort_values("total_pull", ascending=False).iterrows()
            ]
            st.markdown(
                '<div class="gx-card"><div class="gx-card-title">Account Summary</div>'
                + '<div class="gx-card-divider"></div>'.join(sum_rows) + '</div>',
                unsafe_allow_html=True,
            )
            chart_note(f"{cfg.title} exports contain no account level data (no rank or level), so this shows the observed 5★ and 4★ "
                       f"rate per account instead (base rates are about 0.6% for 5★ and 5.1% for 4★).")

    with st.expander("Data Details"):
        show_df(summary)


def _monthly_star_counts(df, cfg, star: int) -> pd.DataFrame:
    """Months x banners table with the number of `star`★ obtained (every month in range, zeros filled)."""
    months = pd.period_range(df["datetime"].min(), df["datetime"].max(), freq="M").astype(str)
    banners = order_banners(cfg, df["banner_type"].dropna().astype(str).unique())
    d = df[df["rarity"] == star]
    if d.empty:
        return pd.DataFrame(0, index=months, columns=banners)
    pv = d.assign(banner_type=d["banner_type"].astype(str)).groupby(["year_month", "banner_type"]).size().unstack(fill_value=0)
    return pv.reindex(index=months, columns=banners, fill_value=0)


def _monthly_star_chart(pv: pd.DataFrame, cfg, star: int):
    fig = go.Figure()
    for banner in pv.columns:
        fig.add_trace(go.Bar(x=pv.index, y=pv[banner], name=banner, marker_color=cfg.banner_colors.get(banner, "#999999")))
    total = pv.sum(axis=1)
    fig.add_trace(go.Scatter(x=total.index, y=total.values, mode="text", text=[f"{int(v)}" if v else "" for v in total.values],
                             textposition="top center", textfont=dict(color=TEXT_PRIMARY, size=11),
                             showlegend=False, hoverinfo="skip", cliponaxis=False))
    apply_layout(fig, f"{star}★ Obtained per Month", "Month", f"{star}★ obtained", height=340,
                 barmode="stack", hovermode="x unified", legend=True)
    fig.update_yaxes(range=[0, max(int(total.max()), 1) * 1.25])
    fig.update_layout(legend_itemclick=False, legend_itemdoubleclick=False)
    return fig


def insight_timeline(df, cfg, k):
    w = cfg.pull_word
    section_header(f"{w} Timeline", f"Monthly {w.lower()} volume and 5★ / 4★ obtained, by banner and account")
    df = account_filter(df, k, "timeline", all_label="Total")
    # The totals are recomputed from the banners picked here.
    all_banners = order_banners(cfg, df["banner_type"].dropna().astype(str).unique())
    shown = st.multiselect("Banners shown", all_banners, default=all_banners)
    if not shown:
        st.warning("Select at least one banner.")
        return
    df = df[df["banner_type"].astype(str).isin(shown)]
    timeline = (df.groupby(["year_month", "banner_type"], observed=True).size().reset_index(name="pull_count").sort_values("year_month"))
    pivot = timeline.pivot(index="year_month", columns="banner_type", values="pull_count").fillna(0)
    pivot = pivot.reindex(columns=order_banners(cfg, pivot.columns))
    months = pd.period_range(pivot.index.min(), pivot.index.max(), freq="M").astype(str)
    pivot = pivot.reindex(months, fill_value=0)

    fig = go.Figure()
    for banner in pivot.columns:
        fig.add_trace(go.Bar(x=pivot.index, y=pivot[banner], name=banner, marker_color=cfg.banner_colors.get(banner, "#999999")))
    total = pivot.sum(axis=1)
    fig.add_trace(go.Scatter(x=total.index, y=total.values, mode="text", text=[f"{int(v):,}" if v else "" for v in total.values],
                             textposition="top center", textfont=dict(color=TEXT_PRIMARY, size=11),
                             showlegend=False, hoverinfo="skip", cliponaxis=False))
    apply_layout(fig, f"Monthly {pull_plural(w)} by Banner", "Month", f"{pull_plural(w)}", height=460, barmode="stack", hovermode="x unified", legend=True)
    fig.update_yaxes(range=[0, total.max() * 1.15])
    # Legend clicks would hide bars without updating the totals, so selection is done with the selector above.
    fig.update_layout(legend_itemclick=False, legend_itemdoubleclick=False)
    show(fig, k, "timeline")
    top_banner = pivot.sum().idxmax()
    share = pivot[top_banner].sum() / pivot.values.sum() * 100
    active = total[total > 0]
    chart_note(f"Busiest month: <b>{total.idxmax()}</b> ({int(total.max()):,} {pull_plural(w).lower()}); average {active.mean():.0f} per active month. "
               f"{top_banner} makes up {share:.0f}% of all {pull_plural(w).lower()}.")

    # ---- 5★ and 4★ obtained per month: per banner and total ----------------------
    block_label("5★ and 4★ obtained per month")
    pv5, pv4 = _monthly_star_counts(df, cfg, 5), _monthly_star_counts(df, cfg, 4)
    show(_monthly_star_chart(pv5, cfg, 5), k, "timeline_5star")
    show(_monthly_star_chart(pv4, cfg, 4), k, "timeline_4star")
    chart_note(f"Total in the selection: <b>{int(pv5.values.sum())}</b> five-star and <b>{int(pv4.values.sum())}</b> four-star. "
               "The number above each bar is the sum of the banners and account chosen above; hover a bar for the per-banner split.")

    table = pd.DataFrame(index=pv5.index)
    table["Total 5★"], table["Total 4★"] = pv5.sum(axis=1), pv4.sum(axis=1)
    for banner in pv5.columns:
        table[f"{banner} 5★"], table[f"{banner} 4★"] = pv5[banner], pv4[banner]
    table.loc["Total"] = table.sum()
    table = table.astype(int).rename_axis("Month").reset_index()
    with st.expander("Monthly table: total and per banner", expanded=True):
        show_df(table, height=min(38 * (len(table) + 1), 520))
    with st.expander("Data Details"):
        show_df(timeline)


def _kde(vals, grid):
    """Gaussian KDE (Silverman-style bandwidth) on `grid`; None when it cannot be estimated."""
    x = np.asarray(vals, dtype=float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return None
    sd = x.std(ddof=1)
    iqr = np.subtract(*np.percentile(x, [75, 25]))
    bw = 0.9 * (min(sd, iqr / 1.34) if iqr > 0 else sd) * len(x) ** (-1 / 5)
    z = (grid[:, None] - x[None, :]) / bw
    return np.exp(-0.5 * z ** 2).sum(axis=1) / (len(x) * bw * np.sqrt(2 * np.pi))


def insight_pity_distribution(df, cfg, k):
    section_header("5★ Pity Distribution", "How many pulls each 5★ took to land, per banner")
    five = df[df["is_5star"]].copy()
    if five.empty:
        st.warning("No 5★ pulls in the current selection.")
        return
    banners = order_banners(cfg, five["banner_type"].dropna().unique())
    banners = [b for b in banners if (five["banner_type"] == b).any()]
    block_label("Histogram + density curve")
    for i in range(0, len(banners), 3):
        cols = st.columns(3)
        for col, banner in zip(cols, banners[i:i + 3]):
            vals = five.loc[five["banner_type"] == banner, "pity"].dropna()
            if vals.empty:
                continue
            hard = cfg.hard_pity.get(banner, cfg.default_hard_pity)
            with col:
                fig = go.Figure(go.Histogram(x=vals, xbins=dict(start=0, end=hard + 5, size=5),
                                             histnorm="probability density", opacity=0.85,
                                             marker_color=cfg.banner_colors.get(banner, "#999999"), name=banner))
                grid = np.linspace(0, hard + 5, 300)
                dens = _kde(vals, grid)
                if dens is not None:
                    fig.add_trace(go.Scatter(x=grid, y=dens, mode="lines", name="Density",
                                             line=dict(color=TEXT_PRIMARY, width=2.2), hoverinfo="skip"))
                fig.add_vline(x=vals.mean(), line_dash="dash", line_color=TEXT_PRIMARY,
                              annotation_text=f"mean {vals.mean():.1f}", annotation_font_color=TEXT_SECONDARY,
                              annotation_position="top left")
                fig.add_vline(x=hard, line_dash="dot", line_color=TEXT_MUTED,
                              annotation_text=f"hard {hard}", annotation_font_color=TEXT_MUTED,
                              annotation_position="top right")
                apply_layout(fig, f"{banner} (n={len(vals)})", "Pity at 5★", "Density", height=330, bargap=0.05)
                fig.update_xaxes(range=[0, hard + 5])
                show(fig, k, f"pity_{banner}")
    avgs = five.groupby("banner_type", observed=True)["pity"].mean()
    avg_txt = " · ".join(f"{b} <b>{avgs[b]:.1f}</b>" for b in banners if b in avgs.index and pd.notna(avgs[b]))
    softs = ", ".join(f"{b} {cfg.soft_pity[b]}" for b, _ in cfg.summary_banners if b in cfg.soft_pity)
    chart_note(f"Average 5★ pity: {avg_txt}. Bars = density of 5★ per pity bucket (5 pulls per bar), solid curve = smoothed density, dashed line = average, dotted line = hard pity. "
               f"Soft pity starts at {softs}: clusters just before it are normal, bars far left are early lucky pulls.")
    block_label("Cumulative probability (CDF)")
    fig = go.Figure()
    cdf_notes = []
    for banner in banners:
        vals = np.sort(five.loc[five["banner_type"] == banner, "pity"].dropna().to_numpy(dtype=float))
        if len(vals) == 0:
            continue
        hard = cfg.hard_pity.get(banner, cfg.default_hard_pity)
        x = np.concatenate([[0], vals, [max(hard, vals.max())]])
        y = np.concatenate([[0], np.arange(1, len(vals) + 1) / len(vals) * 100, [100]])
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", name=f"{banner} (n={len(vals)})", line=dict(shape="hv", width=2.4, color=cfg.banner_colors.get(banner, "#999999")),
            hovertemplate=f"{banner}: %{{y:.1f}}% of 5★ by pity %{{x:.0f}}<extra></extra>",
        ))
        p50, p90 = np.percentile(vals, [50, 90])
        cdf_notes.append(f"{banner} median <b>{p50:.0f}</b>, 90% by <b>{p90:.0f}</b>")
    for level in (50, 90):
        fig.add_hline(y=level, line_dash="dot", line_color=TEXT_MUTED,
                      annotation_text=f"{level}%", annotation_font_color=TEXT_MUTED, annotation_position="bottom right")
    apply_layout(fig, "Empirical CDF: share of 5★ landed by a given pity", "Pity at 5★ (pulls)",
                 "Cumulative share of 5★ (%)", height=420, legend=True, yaxis_range=[0, 102], hovermode="x unified")
    show(fig, k, "pity_cdf")
    chart_note("Read it as: by pull X, Y% of your 5★ had already landed. The steeper the curve, the more consistent the pity. "
               + " · ".join(cdf_notes) + ".")

    with st.expander("Data Details"):
        show_df(five[["account", "banner_type", "datetime", "item_name", "item_category", "pity", "win_50_50"]]
                .astype({"banner_type": str}).sort_values(["banner_type", "datetime"]))


# ----------------------------------------------------------------------------
# Additional pity / luck analyses
# ----------------------------------------------------------------------------
LOW_EXPOSURE = 20  # fewer pulls at risk than this in a hazard bucket -> faded bar


def expected_rate_5(cfg: GameConfig, banner: str):
    """Consolidated 5★ rate per pull in % (pity included) from `GameConfig.expected_rate_5`.
    Returns None for a banner that has no entry (it is then left out of the charts that need it).
    Only an older config without that field falls back to the commonly published figures below."""
    rates = getattr(cfg, "expected_rate_5", None)
    if rates:
        value = rates.get(banner)
        return float(value) if value is not None else None
    name = str(banner).lower()
    if "light cone" in name:
        return 1.87
    if "weapon" in name:
        return 1.85
    return 1.6


def _hazard_buckets(df, cfg, banner, size: int = 5):
    """P(5★ on this pull | no 5★ yet) per bucket of `size` pulls. The unfinished streak of each account
    counts as at risk but without an event (censored), so late buckets are not biased upwards."""
    hard = cfg.hard_pity.get(banner, cfg.default_hard_pity)
    b = df[df["banner_type"].astype(str) == banner]
    pity = b.loc[b["is_5star"], "pity"].dropna().astype(int).to_numpy()
    n = np.arange(1, hard + 1)
    events = np.array([(pity == i).sum() for i in n])
    at_risk = np.array([(pity >= i).sum() for i in n])
    for _, g in b.groupby("account"):
        cp = current_pity(g, banner, 5)
        if cp:
            at_risk = at_risk + (n <= cp)
    idx = (n - 1) // size
    rows = []
    for j in np.unique(idx):
        m = idx == j
        lo, hi = int(n[m].min()), int(n[m].max())
        ev, risk = int(events[m].sum()), int(at_risk[m].sum())
        rows.append(dict(banner=banner, lo=lo, hi=hi, mid=(lo + hi) / 2, events=ev, at_risk=risk,
                         hazard=ev / risk * 100 if risk else np.nan))
    return pd.DataFrame(rows), hard


def insight_hazard_rate(df, cfg, k):
    section_header("Hazard Rate", "Chance of a 5★ on each pull given none yet: where soft pity really starts for you")
    five = df[df["is_5star"]]
    if five.empty:
        st.warning("No 5★ pulls in the current selection.")
        return
    banners = order_banners(cfg, five["banner_type"].dropna().astype(str).unique())
    all_tables = []
    for i in range(0, len(banners), 3):
        cols = st.columns(3)
        for col, banner in zip(cols, banners[i:i + 3]):
            tbl, hard = _hazard_buckets(df, cfg, banner)
            if tbl.empty or tbl["at_risk"].sum() == 0:
                continue
            all_tables.append(tbl)
            soft = cfg.soft_pity.get(banner)
            with col:
                fig = go.Figure(go.Bar(
                    x=tbl["mid"], y=tbl["hazard"], width=4.6,
                    marker=dict(color=cfg.banner_colors.get(banner, "#999999"),
                                opacity=[0.35 if r < LOW_EXPOSURE else 1 for r in tbl["at_risk"]]),
                    customdata=np.stack([tbl["lo"], tbl["hi"], tbl["events"], tbl["at_risk"]], axis=-1),
                    hovertemplate="Pity %{customdata[0]}–%{customdata[1]}: %{y:.1f}%<br>"
                                  "%{customdata[2]} 5★ from %{customdata[3]} pulls at risk<extra></extra>",
                ))
                if soft:
                    fig.add_vline(x=soft, line_dash="dash", line_color=TEXT_PRIMARY,
                                  annotation_text=f"soft {soft}", annotation_font_color=TEXT_SECONDARY,
                                  annotation_position="top left")
                fig.add_vline(x=hard, line_dash="dot", line_color=TEXT_MUTED,
                              annotation_text=f"hard {hard}", annotation_font_color=TEXT_MUTED,
                              annotation_position="top right")
                top = float(np.nanmax(tbl["hazard"])) if tbl["hazard"].notna().any() else 1.0
                apply_layout(fig, f"{banner} (n={len(five[five['banner_type'].astype(str) == banner])})",
                             "Pity", "5★ chance per pull (%)", height=330, bargap=0.05,
                             yaxis_range=[0, min(100.0, max(top * 1.2, 1.0))])
                fig.update_xaxes(range=[0, hard + 3])
                show(fig, k, f"hazard_{banner}")
    chart_note(f"Each bar = 5★ obtained ÷ pulls that reached that bucket (your current unfinished streak counts as at risk). "
               f"Before soft pity the official base rate is only about 0.6–0.8%; the climb shows where your 5★ really land. "
               f"Faded bars have fewer than {LOW_EXPOSURE} pulls at risk, so treat them as noisy.")
    if all_tables:
        with st.expander("Data Details"):
            show_df(pd.concat(all_tables, ignore_index=True)
                    .rename(columns={"lo": "from", "hi": "to", "mid": "mid", "at_risk": "pulls_at_risk", "hazard": "hazard_pct"}))


def insight_pity_4(df, cfg, k):
    section_header("4★ Pity Distribution", "How many pulls each 4★ took to land, per banner")
    four = df[df["is_4star"] & df["pity"].notna()]
    if four.empty:
        st.warning("No 4★ pulls in the current selection.")
        return
    hard = cfg.hard_pity_4
    banners = order_banners(cfg, four["banner_type"].dropna().astype(str).unique())
    means = []
    for i in range(0, len(banners), 3):
        cols = st.columns(3)
        for col, banner in zip(cols, banners[i:i + 3]):
            vals = four.loc[four["banner_type"].astype(str) == banner, "pity"]
            if vals.empty:
                continue
            means.append(f"{banner} <b>{vals.mean():.1f}</b>")
            with col:
                fig = go.Figure(go.Histogram(x=vals, xbins=dict(start=0.5, end=hard + 0.5, size=1), histnorm="percent",
                                             marker_color=cfg.banner_colors.get(banner, "#999999"), name=banner))
                fig.add_vline(x=vals.mean(), line_dash="dash", line_color=TEXT_PRIMARY,
                              annotation_text=f"mean {vals.mean():.1f}", annotation_font_color=TEXT_SECONDARY,
                              annotation_position="top left")
                apply_layout(fig, f"{banner} (n={len(vals)})", "Pity at 4★", "Share of 4★ (%)", height=330, bargap=0.05)
                fig.update_xaxes(range=[0.5, hard + 0.5], dtick=1)
                show(fig, k, f"pity4_{banner}")
    chart_note(f"Average 4★ pity: {' · '.join(means)}. A 4★ is guaranteed by pull {hard}, so a tall bar at {hard} means many "
               "4★ came from the guarantee rather than the base rate.")
    with st.expander("Data Details"):
        show_df(four[["account", "banner_type", "datetime", "item_name", "item_category", "pity", "win_50_50"]]
                .astype({"banner_type": str}).sort_values(["banner_type", "datetime"]))


def _longest_runs(df) -> dict:
    """Longest run of consecutive 50-50 wins / losses (Guaranteed skipped), per account and banner."""
    best = {"Win": 0, "Lose": 0}
    d = df[df["win_50_50"].isin(["Win", "Lose"])].copy()
    d["banner_type"] = d["banner_type"].astype(str)
    for _, g in d.sort_values(["datetime", "seq"]).groupby(["account", "banner_type"]):
        prev, run = None, 0
        for v in g["win_50_50"]:
            run = run + 1 if v == prev else 1
            prev = v
            best[v] = max(best[v], run)
    return best


def insight_pity_timeline(df, cfg, k):
    section_header("5★ Pity Timeline", "Pity of every 5★ over time, coloured by 50-50 outcome")
    df = account_filter(df, k, "pity_timeline")
    df, banner = banner_filter_radio(df, cfg, k, "pity_timeline")
    five = df[df["is_5star"] & df["pity"].notna()].copy()
    if five.empty:
        st.warning("No 5★ pulls in the current selection.")
        return
    five["Result"] = five["win_50_50"].fillna("N/A")
    five["banner_str"] = five["banner_type"].astype(str)
    colors = {**RESULT_COLORS, "N/A": TEXT_MUTED}
    fig = go.Figure()
    for res in ("Win", "Lose", "Guaranteed", "N/A"):
        s = five[five["Result"] == res]
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s["datetime"], y=s["pity"], mode="markers", name=res,
            marker=dict(color=colors[res], size=10, line=dict(width=1, color=BG_APP)),
            customdata=np.stack([s["item_name"].astype(str), s["banner_str"], s["account"].astype(str)], axis=-1),
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} · %{customdata[2]}<br>"
                          "Pity %{y} · %{x|%Y-%m-%d}<extra>" + res + "</extra>",
        ))
    if banner:
        soft = cfg.soft_pity.get(banner)
        if soft:
            fig.add_hline(y=soft, line_dash="dash", line_color=TEXT_MUTED, annotation_text=f"soft pity {soft}",
                          annotation_font_color=TEXT_MUTED, annotation_position="bottom right")
        hard = cfg.hard_pity.get(banner, cfg.default_hard_pity)
        fig.add_hline(y=hard, line_dash="dot", line_color=TEXT_MUTED, annotation_text=f"hard pity {hard}",
                      annotation_font_color=TEXT_MUTED, annotation_position="top right")
    apply_layout(fig, "Pity at each 5★", "Date", "Pity at 5★", height=420, legend=True, hovermode="closest")
    show(fig, k, "pity_timeline")
    cnt = five["Result"].value_counts()
    runs = _longest_runs(df[df["is_5star"]])
    streak = (f" Longest streak of 50-50s: {runs['Win']} won in a row, {runs['Lose']} lost in a row "
              "(Guaranteed skipped, counted per account and banner)." if runs["Win"] + runs["Lose"] else "")
    chart_note(f"{int(cnt.get('Win', 0))} won, {int(cnt.get('Lose', 0))} lost, {int(cnt.get('Guaranteed', 0))} guaranteed, "
               f"{int(cnt.get('N/A', 0))} without a 50-50 (e.g. Standard).{streak} "
               "A Lose is normally followed by a Guaranteed on the next rate-up 5★.")
    with st.expander("Data Details"):
        show_df(five[["account", "banner_str", "datetime", "item_name", "pity", "Result"]]
                .rename(columns={"banner_str": "banner_type"}).sort_values("datetime", ascending=False))


def insight_expected_vs_actual(df, cfg, k):
    section_header("5★ Actual vs Expected", "Cumulative 5★ obtained against what the official consolidated rate predicts")
    df = account_filter(df, k, "expected")
    df, banner = banner_filter_radio(df, cfg, k, "expected")
    if df.empty:
        st.warning("No pulls in the current selection.")
        return
    d = df.sort_values(["datetime", "seq"]).copy()
    d["rate"] = pd.to_numeric(d["banner_type"].astype(str).map(lambda b: expected_rate_5(cfg, b)), errors="coerce") / 100
    # Banners without an expected rate are left out of actual AND expected, so the two lines stay comparable.
    skipped = order_banners(cfg, d.loc[d["rate"].isna(), "banner_type"].dropna().astype(str).unique())
    d = d[d["rate"].notna()].copy()
    if d.empty:
        st.warning("No banner in the current selection has an expected 5★ rate (see expected_rate_5 in pipeline/config.py).")
        return
    banners = order_banners(cfg, d["banner_type"].dropna().astype(str).unique())
    d["expected_cum"] = d["rate"].cumsum()
    d["actual_cum"] = d["is_5star"].astype(int).cumsum()
    daily = d.groupby("date").agg(actual=("actual_cum", "last"), expected=("expected_cum", "last")).reset_index()
    daily["gap"] = daily["actual"] - daily["expected"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["expected"], mode="lines", name="Expected (official rate)",
                             line=dict(color=TEXT_PRIMARY, width=2, dash="dash")))
    fig.add_trace(go.Scatter(x=daily["date"], y=daily["actual"], mode="lines", name="Actual 5★",
                             line=dict(color=ACCENT_GOLD, width=2.8)))
    apply_layout(fig, "Cumulative 5★: actual vs expected", "Date", "5★ obtained", height=400, legend=True, hovermode="x unified")
    show(fig, k, "exp_cum")

    fig = go.Figure()
    for name, series, color in (("Ahead of expected", daily["gap"].clip(lower=0), SUCCESS),
                                ("Behind expected", daily["gap"].clip(upper=0), DANGER)):
        fig.add_trace(go.Scatter(x=daily["date"], y=series, mode="lines", name=name, fill="tozeroy",
                                 line=dict(color=color, width=1.2)))
    apply_layout(fig, "Gap: actual − expected 5★", "Date", "5★ ahead (+) / behind (−)", height=280, legend=True,
                 hovermode="x unified")
    show(fig, k, "exp_gap")

    actual, expected = int(daily["actual"].iloc[-1]), float(daily["expected"].iloc[-1])
    gap = actual - expected
    rates = ", ".join(f"{b} {expected_rate_5(cfg, b):g}%" for b in banners)
    chart_note(f"<b>{actual}</b> five-star obtained vs <b>{expected:.1f}</b> expected: "
               f"{'ahead by' if gap >= 0 else 'behind by'} <b>{abs(gap):.1f}</b>. "
               f"Expected rates used (consolidated, pity included): {rates}. "
               + (f"Left out (no expected rate in pipeline/config.py): {', '.join(skipped)}. " if skipped else "")
               + "A gap of a few 5★ either way is normal variance, not proof of good or bad luck.")
    with st.expander("Data Details"):
        show_df(daily)


def insight_rolling_efficiency(df, cfg, k):
    section_header("Rolling Pulls per 5★", "Moving average of the pity of your last N 5★: is your efficiency improving?")
    df = account_filter(df, k, "rolling")
    five = df[df["is_5star"] & df["pity"].notna()].sort_values(["datetime", "seq"])
    if five.empty:
        st.warning("No 5★ pulls in the current selection.")
        return
    window = st.slider("Window (number of 5★)", 2, 10, 5, key=f"{k}_rolling_window")
    fig = go.Figure()
    latest, short = [], []
    for banner in order_banners(cfg, five["banner_type"].dropna().astype(str).unique()):
        s = five[five["banner_type"].astype(str) == banner]
        color = cfg.banner_colors.get(banner, "#999999")
        enough = len(s) >= window
        fig.add_trace(go.Scatter(
            x=s["datetime"], y=s["pity"], mode="markers", name=f"{banner} (each 5★)", legendgroup=banner,
            marker=dict(color=color, size=6, opacity=0.35), showlegend=not enough,
            hovertemplate=f"{banner}<br>Pity %{{y}} · %{{x|%Y-%m-%d}}<extra></extra>",
        ))
        if enough:
            roll = s["pity"].rolling(window).mean()
            fig.add_trace(go.Scatter(
                x=s["datetime"], y=roll, mode="lines", name=banner, legendgroup=banner,
                line=dict(color=color, width=2.6),
                hovertemplate=f"{banner} rolling {window}: %{{y:.1f}}<extra></extra>",
            ))
            latest.append(f"{banner} <b>{roll.iloc[-1]:.1f}</b>")
        else:
            short.append(f"{banner} ({len(s)} 5★)")
        exp_rate = expected_rate_5(cfg, banner)
        if exp_rate:
            fig.add_hline(y=100 / exp_rate, line_dash="dot", line_color=color, opacity=0.55)
    apply_layout(fig, f"Rolling average pulls per 5★ (window {window})", "Date of the 5★", "Pulls per 5★",
                 height=420, legend=True, hovermode="closest")
    show(fig, k, "rolling")
    txt = f"Latest rolling average: {' · '.join(latest)}. " if latest else ""
    if short:
        txt += f"Not enough 5★ for a window of {window}: {', '.join(short)}. "
    chart_note(txt + "Dots = pity of each 5★, line = moving average, dotted line = expected pulls per 5★ "
               "(1 ÷ official consolidated rate). A line sinking below its dotted line means your recent pulls are efficient.")
    with st.expander("Data Details"):
        show_df(five[["account", "banner_type", "datetime", "item_name", "pity"]].astype({"banner_type": str}))


def _winrate_rows(df, cfg):
    """Decisive (Win/Lose) outcomes per banner+rarity with the official baseline for 5★ rows."""
    d = df[df["win_50_50"].isin(["Win", "Lose"])].copy()
    d["banner_type"] = d["banner_type"].astype(object)
    rows = (d.groupby(["banner_type", "rarity"])["win_50_50"]
            .agg(n="size", win_rate=lambda s: (s == "Win").mean() * 100).reset_index())
    rows["baseline"] = [cfg.rateup_chance.get(b) if r == 5 else None for b, r in zip(rows["banner_type"], rows["rarity"])]
    rows["_o"] = rows["banner_type"].map(lambda b: order_banners(cfg, [b, *cfg.banner_order]).index(b))
    rows = rows.sort_values(["_o", "rarity"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)
    rows["label"] = [f"{b}<br>{int(r)}★" for b, r in zip(rows["banner_type"], rows["rarity"])]
    return rows


def insight_win_lose(df, cfg, k):
    section_header("50-50 Win/Lose", "Rate-up outcomes by banner and rarity")
    rate_df = df[df["win_50_50"].notna()].copy()
    if rate_df.empty:
        st.warning("No 50-50 data in the current selection.")
        return
    col1, col2 = st.columns(2)
    with col1:
        summary = rate_df.groupby(["banner_type", "rarity", "win_50_50"], observed=True).size().reset_index(name="count")
        pivot = summary.pivot_table(index=["banner_type", "rarity"], columns="win_50_50", values="count", fill_value=0, observed=True)
        pivot = pivot.reindex(columns=[c for c in ["Win", "Lose", "Guaranteed"] if c in pivot.columns])
        pivot = pivot.sort_index(level=[0, 1], ascending=[True, False])
        labels = [f"{b}<br>{int(r)}★" for b, r in pivot.index]
        fig = go.Figure()
        for name in pivot.columns:
            fig.add_trace(go.Bar(x=labels, y=pivot[name], name=name, marker_color=RESULT_COLORS.get(name)))
        apply_layout(fig, "Win / Lose / Guaranteed", "Banner & rarity", "Count", barmode="stack", legend=True)
        show(fig, k, "wl_stack")
        tot = rate_df["win_50_50"].value_counts()
        chart_note(f"Overall: {int(tot.get('Win', 0))} won, {int(tot.get('Lose', 0))} lost, {int(tot.get('Guaranteed', 0))} guaranteed. "
                   "Guaranteed = the rate-up item came from the guarantee after losing the previous 50-50.")
    with col2:
        wr = _winrate_rows(df, cfg)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=wr["label"], y=wr["win_rate"], marker_color=SUCCESS,
                             marker_opacity=[0.4 if n < LOW_SAMPLE else 1 for n in wr["n"]],
                             text=[f"{v:.0f}% (n={n})" for v, n in zip(wr["win_rate"], wr["n"])], textposition="outside",
                             name="Win rate"))
        base = wr.dropna(subset=["baseline"])
        if len(base):
            fig.add_trace(go.Scatter(x=base["label"], y=base["baseline"], mode="markers", name="Official 5★ rate-up chance",
                                     marker=dict(symbol="line-ew", size=38, line=dict(width=3, color=TEXT_PRIMARY))))
        apply_layout(fig, "Rate-up Win Rate (Win vs Lose)", "Banner & rarity", "Win rate (%)", yaxis_range=[0, 115], legend=True)
        show(fig, k, "wl_rate")
        chart_note(f"The marker is the official 5★ rate-up chance of each banner. Faded bars have fewer than {LOW_SAMPLE} outcomes, "
                   "so treat them as anecdotes. 4★ rows have no official baseline here.")
    with st.expander("Data Details"):
        show_df(summary.astype({"banner_type": str}))


def insight_top_items(df, cfg, k, top_n: int = 10):
    section_header(f"Top Character & {cfg.gear_label}", "Most frequently obtained 4★ and 5★ items")
    df = account_filter(df, k, "top_items")
    col1, col2 = st.columns(2)
    for col, category, label in ((col1, "character", "Character"), (col2, cfg.gear_category, cfg.gear_label)):
        with col:
            sub = df[(df["item_category"] == category) & (df["rarity"] >= 4)]
            if sub.empty:
                st.info(f"No 4★ or 5★ {label.lower()}s in the current selection.")
                continue
            top = (sub.groupby(["item_name", "rarity"]).size().reset_index(name="times_obtained")
                   .sort_values(["times_obtained", "rarity", "item_name"], ascending=[False, False, True]).head(top_n))
            fig = go.Figure(go.Bar(y=top["item_name"], x=top["times_obtained"], orientation="h",
                                   marker_color=[RARITY_COLORS.get(r, "#999999") for r in top["rarity"]],
                                   text=top["times_obtained"], textposition="outside"))
            apply_layout(fig, f"Top {label}s (4★ & 5★)", "Times obtained", label, height=480)
            fig.update_yaxes(autorange="reversed")
            show(fig, k, f"top_{category}")
            t = top.iloc[0]
            chart_note(f"Most frequent: <b>{html.escape(str(t['item_name']))}</b> ({int(t['times_obtained'])}x). "
                       f"Bar colour = rarity (gold 5★, purple 4★); top {top_n} shown.")


def insight_banner_performance(df, cfg, k):
    w = cfg.pull_word
    section_header("Banner Performance", "Volume, efficiency and rate-up win rate across banners")
    perf = (df.groupby("banner_type", observed=True)
            .agg(total_pull=("item_id", "count"), pull_5star=("is_5star", "sum"), pull_4star=("is_4star", "sum")).reset_index())
    perf["banner_type"] = perf["banner_type"].astype(str)
    perf["pull_per_5star"] = (perf["total_pull"] / perf["pull_5star"].replace(0, float("nan"))).round(1)
    perf["rate_5star_pct"] = (perf["pull_5star"] / perf["total_pull"] * 100).round(2)
    dec = df[df["win_50_50"].isin(["Win", "Lose"]) & (df["rarity"] == 5)].copy()
    dec["banner_type"] = dec["banner_type"].astype(str)
    wr = dec.groupby("banner_type")["win_50_50"].agg(n="size", win_rate_5star_pct=lambda s: (s == "Win").mean() * 100).reset_index()
    perf = perf.merge(wr, on="banner_type", how="left")
    perf["baseline_pct"] = pd.to_numeric(perf["banner_type"].map(cfg.rateup_chance), errors="coerce")
    colors = [cfg.banner_colors.get(b, "#999999") for b in perf["banner_type"]]

    def hbar(x, title, name, text, xtitle):
        fig = go.Figure(go.Bar(y=perf["banner_type"], x=x, orientation="h", marker_color=colors, text=text, textposition="outside"))
        apply_layout(fig, title, xtitle, None, height=340)
        fig.update_yaxes(autorange="reversed")
        return fig

    col1, col2, col3 = st.columns(3)
    with col1:
        fig = hbar(perf["total_pull"], f"Total {pull_plural(w)}", "total", [f"{v:,}" for v in perf["total_pull"]], f"{pull_plural(w)}")
        fig.update_xaxes(range=[0, perf["total_pull"].max() * 1.25])
        show(fig, k, "banner_total")
        top = perf.sort_values("total_pull", ascending=False).iloc[0]
        chart_note(f"<b>{top['banner_type']}</b> takes {top['total_pull'] / perf['total_pull'].sum() * 100:.0f}% of all {pull_plural(w).lower()} ({int(top['total_pull']):,}).")
    with col2:
        vals = perf["pull_per_5star"]
        fig = hbar(vals.fillna(0), f"{pull_plural(w)} per 5★ (lower = better)", "eff",
                   [f"{v:.1f}" if pd.notna(v) else "N/A" for v in vals], f"{pull_plural(w)} per 5★")
        fig.update_xaxes(range=[0, max(vals.max() * 1.25, 1)])
        show(fig, k, "banner_eff")
        eff = perf.dropna(subset=["pull_per_5star"])
        if len(eff) > 1:
            b, wst = eff.loc[eff["pull_per_5star"].idxmin()], eff.loc[eff["pull_per_5star"].idxmax()]
            chart_note(f"Most efficient: <b>{b['banner_type']}</b> ({b['pull_per_5star']:.1f}). Least: <b>{wst['banner_type']}</b> ({wst['pull_per_5star']:.1f}).")
    with col3:
        vals = perf["win_rate_5star_pct"]
        fig = hbar(vals.fillna(0), "5★ Rate-up Win Rate", "wr",
                   [f"{v:.0f}% (n={int(n)})" if pd.notna(v) else "N/A" for v, n in zip(vals, perf["n"].fillna(0))], "Win rate (%)")
        base = perf.dropna(subset=["baseline_pct"])
        if len(base):
            fig.add_trace(go.Scatter(y=base["banner_type"], x=base["baseline_pct"], mode="markers", name="Official rate-up chance",
                                     marker=dict(symbol="line-ns", size=26, line=dict(width=3, color=TEXT_PRIMARY))))
        fig.update_xaxes(range=[0, 125])
        fig.update_layout(showlegend=False)
        show(fig, k, "banner_wr")
        chart_note("Marker = official 5★ rate-up chance. Banners without a rate-up mechanic (Standard, Beginners) show N/A.")
    with st.expander("Data Details"):
        show_df(perf)


def insight_luck_score(df, cfg, k):
    section_header("Luck Score", "Pity efficiency and rate-up win luck, scored against official rates")
    if not df["is_5star"].any():
        st.warning("No 5★ pulls in the current selection. Luck Score cannot be calculated.")
        return
    luck = luck_table(df, cfg)
    col1, col2 = st.columns([3, 2])
    with col1:
        fig = go.Figure()
        for name, col, color in LUCK_SERIES:
            vals = pd.to_numeric(luck[col], errors="coerce")
            fig.add_trace(go.Bar(x=luck["account"], y=vals, name=name, marker_color=color,
                                 text=[f"{v:.0f}" if pd.notna(v) else "N/A" for v in vals], textposition="outside"))
        fig.add_hline(y=50, line_dash="dash", line_color=TEXT_PRIMARY, annotation_text="Neutral = 50",
                      annotation_font_color=TEXT_SECONDARY)
        apply_layout(fig, "Luck Score per Account", "Account", "Score (50 = as expected)", barmode="group", legend=True)
        fig.update_yaxes(range=[0, max(100, pd.to_numeric(luck[["avg_pity_luck", "win_rate_luck", "luck_score"]].stack(), errors="coerce").max() * 1.15)])
        show(fig, k, "luck")
        ranked = luck.dropna(subset=["luck_score"])
        if len(ranked):
            lead = ranked.iloc[0]
            chart_note(f"Highest score: <b>{html.escape(str(lead['account']))}</b> ({lead['luck_score']:.1f}). "
                       "50 means exactly as expected, above 50 is luckier than the official rates predict.")
    with col2:
        rates = ", ".join(f"{b} {v}%" for b, v in cfg.rateup_chance.items())
        st.markdown(
            f"""
            <div class="gx-card">
                <div class="gx-card-title">How the score works</div>
                <p style="color:{TEXT_SECONDARY}; font-size:0.88em; line-height:1.7; margin:0;">
                    <b style="color:{TEXT_PRIMARY}">60% Pity efficiency</b>: 100 for a 5★ on pull 1, 0 at hard pity, averaged over all 5★.<br>
                    <b style="color:{TEXT_PRIMARY}">40% Rate-up win luck</b>: 50 × actual rate-up win rate ÷ expected win rate (5★ only).<br>
                    <b style="color:{TEXT_PRIMARY}">Expected rates</b>: {rates}.
                </p>
                <div class="gx-card-divider"></div>
                <div class="gx-card-title" style="margin-top:12px;">Interpretation</div>
                <p style="color:{TEXT_SECONDARY}; font-size:0.88em; line-height:1.9; margin:0;">
                    {badge("&gt; 70 Very lucky", SUCCESS)}<br>
                    {badge("50–70 Above average", ACCENT_TEAL)}<br>
                    {badge("&lt; 50 Below average", DANGER)}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with st.expander("Data Details"):
        show_df(luck)


def insight_latest_5star(df, cfg, k, top_n: int = 10):
    section_header(f"Latest 5★ Characters & {cfg.gear_label}s", f"The {top_n} most recent 5★ per banner, newest first")
    df = account_filter(df, k, "latest_5star")
    five = df[df["is_5star"]].copy()
    if five.empty:
        st.warning("No 5★ pulls in the current selection.")
        return
    for banner in order_banners(cfg, five["banner_type"].dropna().unique()):
        b = five[five["banner_type"] == banner].sort_values(["datetime", "seq"], ascending=False)
        if b.empty:
            continue
        win, lose = int((b["win_50_50"] == "Win").sum()), int((b["win_50_50"] == "Lose").sum())
        guar = int((b["win_50_50"] == "Guaranteed").sum())
        rate = f"{win / (win + lose) * 100:.0f}% win rate" if win + lose else "no decisive 50-50s"
        st.markdown(
            f"""
            <div class="gx-section" style="margin-top:22px;">
                <span class="gx-section-title">{banner}</span>
                <span class="gx-section-subtitle">{badge(f"{win} Win", SUCCESS)}{badge(f"{lose} Lose", DANGER)}{badge(f"{guar} Guaranteed", ACCENT_TEAL)} · {rate}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        latest = b.head(top_n)[["datetime", "item_name", "item_category", "pity", "win_50_50"]].rename(
            columns={"datetime": "Date", "item_name": "Name", "item_category": "Type", "pity": "Pity", "win_50_50": "Result"})
        latest["Date"] = latest["Date"].dt.strftime("%Y-%m-%d %H:%M")
        latest["Type"] = latest["Type"].str.replace("_", " ").str.title()
        latest["Result"] = latest["Result"].fillna("N/A")
        show_df(style_result_column(latest, "Result"), column_config={"Pity": st.column_config.NumberColumn("Pity", format="%d")})


def _render_history_table(df, cfg, k, rarity: int):
    rdf = df[df["rarity"] == rarity].copy()
    if rdf.empty:
        st.info(f"No {rarity}★ pulls in the current selection.")
        return
    rdf = rdf.sort_values(["datetime", "seq"])
    rdf["No."] = rdf.groupby("account").cumcount() + 1

    banner_choices = ["All"] + order_banners(cfg, rdf["banner_type"].dropna().astype(str).unique())
    type_options = ["All", "Character", cfg.gear_label]
    f1, f2 = st.columns([3, 2])
    with f1:
        banner_choice = st.radio("Banner", banner_choices, horizontal=True, key=f"{k}_hist_banner_{rarity}")
    with f2:
        type_choice = st.radio("Type", type_options, horizontal=True, key=f"{k}_hist_type_{rarity}")
    if banner_choice != "All":
        rdf = rdf[rdf["banner_type"].astype(str) == banner_choice]
    if type_choice == "Character":
        rdf = rdf[rdf["item_category"] == "character"]
    elif type_choice == cfg.gear_label:
        rdf = rdf[rdf["item_category"] == cfg.gear_category]
    if rdf.empty:
        st.info(f"No {rarity}★ pulls for Banner: {banner_choice} · Type: {type_choice}.")
        return

    pity = rdf["pity"].dropna()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{rarity}★ Total", f"{len(rdf):,}")
    c2.metric("Avg Pity", f"{pity.mean():.1f}" if len(pity) else "-")
    c3.metric("Lowest Pity", f"{int(pity.min())}" if len(pity) else "-")
    c4.metric("Highest Pity", f"{int(pity.max())}" if len(pity) else "-")

    multi = df["account"].nunique() > 1
    cols = ["No.", "datetime"] + (["account"] if multi else []) + ["item_name", "item_category", "banner_type", "pity", "win_50_50"]
    view = rdf.sort_values(["datetime", "seq"], ascending=False)[cols].rename(columns={
        "datetime": "Date", "account": "Account", "item_name": "Name", "item_category": "Type",
        "banner_type": "Banner", "pity": "Pity", "win_50_50": "Result"})
    view["Date"] = view["Date"].dt.strftime("%Y-%m-%d %H:%M")
    view["Banner"] = view["Banner"].astype(str)
    view["Type"] = view["Type"].str.replace("_", " ").str.title()
    view["Result"] = view["Result"].fillna("N/A")
    max_pity = max(cfg.hard_pity.values()) if rarity == 5 else cfg.hard_pity_4
    show_df(style_result_column(view, "Result"), height=480, column_config={
        "No.": st.column_config.NumberColumn("No.", format="%d", width="small"),
        "Pity": st.column_config.ProgressColumn("Pity", format="%d", min_value=0, max_value=max_pity),
    })
    st.caption("No. = pull order within the account, counted using the current filters. Newest first.")


def insight_pull_history(df, cfg, k):
    section_header("Pull History", "Every 5★ and 4★ pull, newest first")
    df = account_filter(df, k, "history")
    tab5, tab4 = st.tabs(["5★ History", "4★ History"])
    with tab5:
        _render_history_table(df, cfg, k, 5)
    with tab4:
        _render_history_table(df, cfg, k, 4)


# ============================================================================
# One game section
# ============================================================================
def render_game(cfg: GameConfig, path: Path):
    k = cfg.key.lower()
    if not path.exists():
        st.warning(f"No data file for {cfg.title}: `{path}`")
        st.info(f"Run `{PREPROCESS_HINT[cfg.key]}` to generate it, or pass `--{k}-data <file>` to this app.")
        return

    df = load_data(str(path), path.stat().st_mtime, cfg.key)
    if df.empty:
        st.warning(f"{path.name} contains no usable rows.")
        return

    accounts = account_order(df)

    # ---- Full-width filter panel -------------------------------------------
    with st.container(border=True, key=f"{k}_filter_panel"):
        st.markdown('<div class="gx-side-section">Dashboard filters</div>', unsafe_allow_html=True)
        st.caption("All metrics and charts below follow these filters.")
        account_col, banner_col, date_col = st.columns([1.15, 2.0, 2.5], gap="large")

        with account_col:
            scope = st.selectbox(
                "Account",
                accounts + (["All accounts"] if len(accounts) > 1 else []),
                index=0,
                key=f"{k}_scope",
                help="Choose one account or combine all accounts.",
            )

        # Changing account resets dependent filters to the complete data range.
        if st.session_state.get(f"{k}_last_scope") != scope:
            st.session_state.pop(f"{k}_banners", None)
            st.session_state.pop(f"{k}_date", None)
            st.session_state[f"{k}_last_scope"] = scope

        scope_df = df if scope == "All accounts" else df[df["account"] == scope]
        banner_options = order_banners(cfg, scope_df["banner_type"].dropna().astype(str).unique())
        min_d, max_d = scope_df["datetime"].min().date(), scope_df["datetime"].max().date()

        with banner_col:
            banner_filter = st.multiselect(
                "Banners", banner_options, default=banner_options, key=f"{k}_banners",
                help="Select the banners included in the analysis.",
            )

        with date_col:
            if min_d == max_d:
                st.caption("Date range")
                st.markdown(f"**{min_d:%d %b %Y}** · Only available date")
                date_range = (min_d, max_d)
            else:
                date_range = st.slider(
                    "Date range", min_value=min_d, max_value=max_d,
                    value=(min_d, max_d), key=f"{k}_date",
                    format="DD MMM YYYY",
                )

    display_df = scope_df[
        (scope_df["datetime"].dt.date >= date_range[0])
        & (scope_df["datetime"].dt.date <= date_range[1])
        & scope_df["banner_type"].astype(str).isin(banner_filter)
    ]

    if display_df.empty:
        st.warning("No pulls match the current filters. Adjust the account, banners or date range.")
        return

    single = display_df["account"].nunique() == 1
    stats = build_summary_stats(display_df, cfg)
    wr = f"{stats['win_rate']:.0f}% 5★ rate-up win rate" if stats["win_rate"] is not None else "no rate-up data"
    render_hero(
        cfg,
        title=str(scope) if scope != "All accounts" else "All Accounts",
        subtitle=("Single-account " if scope != "All accounts" else f"Combined view across {display_df['account'].nunique()} accounts · ")
        + f"{cfg.pull_word.lower()} history and pity tracking",
        chips=[
            f"{date_range[0]} → {date_range[1]}",
            f"{int(display_df['is_5star'].sum()):,} five-star",
            f"{len(display_df):,} {pull_plural(cfg.pull_word).lower()}",
            wr,
        ],
    )

    block_label("Overview")
    st.caption("Key metrics: pull volume, number of 5★ items, average pity, win rate, and latest 5★ result.")
    render_key_parameters(cfg, stats)

    block_label("Banner Pity Meters")
    st.caption("Pity is the number of pulls since the last item of the corresponding rarity was obtained, for each banner.")
    render_pity_section(display_df, cfg)
    st.caption("Pity values are calculated from the data within the active date and banner filters.")

    block_label("Summary")
    st.caption("The automatic summary highlights the data period, rate-up outcomes, banner efficiency, monthly activity, and current pity.")
    render_executive_summary(display_df, cfg, stats, single)

    block_label("Detailed Analysis")
    st.caption("Choose an analysis group, then open a tab to view its charts and data details.")
    # Two levels: a few groups on top, the individual analyses as sub-tabs inside each group.
    groups = [
        ("Overview", [
            ("Total Pulls", insight_total_pull),
            ("Banner", insight_banner_performance),
            ("Timeline", insight_timeline),
        ]),
        ("Pity", [
            ("5★ Pity", insight_pity_distribution),
            ("Hazard Rate", insight_hazard_rate),
            ("4★ Pity", insight_pity_4),
        ]),
        ("Luck & 50-50", [
            ("Luck Score", insight_luck_score),
            ("Actual vs Expected", insight_expected_vs_actual),
            ("Rolling Efficiency", insight_rolling_efficiency),
            ("50-50", insight_win_lose),
            ("Pity Timeline", insight_pity_timeline),
        ]),
        ("Items & History", [
            ("Top Items", insight_top_items),
            ("Latest 5★", insight_latest_5star),
            ("History", insight_pull_history),
        ]),
    ]
    for group_tab, (_, views) in zip(st.tabs([name for name, _ in groups]), groups):
        with group_tab:
            for sub_tab, (_, view) in zip(st.tabs([name for name, _ in views]), views):
                with sub_tab:
                    view(display_df, cfg, k)

    st.download_button(
        label=f"Download filtered {cfg.key} data (CSV)",
        data=display_df.to_csv(index=False),
        file_name=f"{k}_gacha_data_{date_range[0]}_{date_range[1]}.csv",
        mime="text/csv",
        key=f"{k}_download",
        **STRETCH,
    )



# ============================================================================
# Main app
# ============================================================================
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gi-data", type=str, default=None, help="Genshin Impact data_clean CSV")
    parser.add_argument("--data", type=str, default=None, help="Alias of --gi-data (kept for older commands)")
    parser.add_argument("--hsr-data", type=str, default=None, help="Honkai: Star Rail data_clean_hsr CSV")
    args, _ = parser.parse_known_args()  # tolerate Streamlit's own flags
    return args


def main():
    args = parse_args()
    paths = {
        "GI": Path(args.gi_data or args.data) if (args.gi_data or args.data) else DEFAULT_DATA["GI"],
        "HSR": Path(args.hsr_data) if args.hsr_data else DEFAULT_DATA["HSR"],
    }

    st.sidebar.markdown(
        '<div class="gx-sidebar-brand">'
        '<div class="gx-sidebar-mark">Personal analytics</div>'
        '<div class="gx-sidebar-name">Gacha Analytics</div>'
        '<div class="gx-sidebar-caption">Pull history, pity, banner performance, and account comparisons.</div>'
        '<div class="gx-sidebar-caption">Data processed from Paimon.moe for Genshin Impact and '
        'StarRailStation for Honkai: Star Rail.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown('<div class="gx-side-section">Workspace</div>', unsafe_allow_html=True)
    game = st.sidebar.radio(
        "Select game", list(GAMES), format_func=lambda g: GAMES[g].title,
        key="game", label_visibility="collapsed",
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("Each game is analysed independently. Filters apply only to the selected game.")

    st.markdown(
        '<div class="gx-appbar">'
        '<div><div class="gx-app-kicker">Analytics workspace</div>'
        '<div class="gx-app-title">Gacha Analytics</div>'
        '<div class="gx-app-subtitle">Account activity, banner efficiency, and pull outcomes.</div></div>'
        '<div class="gx-app-status">PERSONAL WORKSPACE</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    render_game(GAMES[game], paths[game])

    st.markdown(
        '<div class="gx-footer">Gacha Analytics · data from your Paimon.moe export and StarRailStation backup · '
        'independent, unaffiliated with HoYoverse</div>',
        unsafe_allow_html=True,
    )



if __name__ == "__main__":
    main()
