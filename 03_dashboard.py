"""
03_dashboard.py
================
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
game_configs.py, and the Luck Score is computed by compute_luck() from
analytics_common.py, so the dashboard, the PNG reports and the Google Sheet agree.

Usage:
    pip install streamlit pandas plotly matplotlib
    streamlit run 03_dashboard.py

    Custom data files:
    streamlit run 03_dashboard.py -- --gi-data data/data_clean_887284572.csv --hsr-data data/data_clean_hsr.csv

Run from the project root so Streamlit picks up .streamlit/config.toml (dark navy theme).
"""

import argparse
import copy
import html
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from analytics_common import compute_luck
from game_configs import GAMES, GameConfig

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DATA = {"GI": DATA_DIR / "data_clean.csv", "HSR": DATA_DIR / "data_clean_hsr.csv"}
PREPROCESS_HINT = {"GI": "01_preprocessing.py", "HSR": "01_preprocessing_hsr.py"}

# ----------------------------------------------------------------------------
# Design tokens — restrained dark analytics theme
# ----------------------------------------------------------------------------
BG_APP = "#0b1220"
BG_SIDEBAR = "#0e1828"
BG_CARD = "#121e2f"
BG_CARD_ALT = "#17263a"
BG_ELEVATED = "#1b2b40"
TEXT_PRIMARY = "#eef3f9"
TEXT_SECONDARY = "#a8b6c8"
TEXT_MUTED = "#78899f"
DIVIDER = "rgba(157, 178, 202, 0.16)"

ACCENT_GOLD = "#e9b65f"
ACCENT_PURPLE = "#a78bfa"
ACCENT_BLUE = "#69a9ec"
ACCENT_TEAL = "#55b8ad"
SUCCESS = "#57b88c"
DANGER = "#e2767a"

FONT_DISPLAY = "'Manrope', sans-serif"
FONT_BODY = "'Inter', sans-serif"
FONT_MONO = "'JetBrains Mono', monospace"

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

# Dark plotly template so every chart matches the app background
_dark_template = copy.deepcopy(pio.templates["plotly_dark"])
_dark_template.layout.paper_bgcolor = "rgba(0,0,0,0)"
_dark_template.layout.plot_bgcolor = "rgba(0,0,0,0)"
_dark_template.layout.font.color = TEXT_PRIMARY
pio.templates["gacha_dark"] = _dark_template
pio.templates.default = "gacha_dark"

# ----------------------------------------------------------------------------
# Global styling
# ----------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

    :root {{ color-scheme: dark; }}
    html, body, [class*="css"] {{ font-family: {FONT_BODY}; }}
    h1, h2, h3, h4, h5, .gx-hero-title, .gx-section-title, .gx-side-title {{
        font-family: {FONT_DISPLAY} !important;
        letter-spacing: -0.025em;
    }}

    /* ---- Application canvas --------------------------------------------- */
    .stApp {{ background: linear-gradient(180deg, {BG_APP} 0%, #0e1726 100%); }}
    .block-container {{ max-width: 1500px; padding: 1.6rem 2.1rem 2.6rem; }}
    #MainMenu, footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stSidebar"] {{
        background: {BG_SIDEBAR};
        border-right: 1px solid {DIVIDER};
    }}
    [data-testid="stSidebar"] > div:first-child {{ padding-top: 1.25rem; }}
    .gx-sidebar-brand {{ padding: 0.4rem 0.35rem 1.1rem; }}
    .gx-sidebar-mark {{
        color: {ACCENT_TEAL}; font-family: {FONT_MONO}; font-size: 0.68rem;
        font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase;
    }}
    .gx-sidebar-name {{ color: {TEXT_PRIMARY}; font-size: 1.35rem; font-weight: 800; line-height: 1.2; margin-top: 0.25rem; }}
    .gx-sidebar-caption {{ color: {TEXT_MUTED}; font-size: 0.78rem; margin-top: 0.35rem; line-height: 1.5; }}
    .gx-side-section {{
        color: {TEXT_MUTED}; font-family: {FONT_MONO}; font-size: 0.67rem;
        font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase;
        margin: 0.3rem 0 0.65rem;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label p {{ color: {TEXT_SECONDARY}; font-weight: 600; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {{ padding: 0.24rem 0; }}

    /* ---- Workspace heading ---------------------------------------------- */
    .gx-appbar {{
        display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
        padding: 0.15rem 0 1.1rem; margin-bottom: 0.25rem;
        border-bottom: 1px solid {DIVIDER};
    }}
    .gx-app-kicker {{ color: {ACCENT_TEAL}; font-family: {FONT_MONO}; font-size: 0.68rem;
        font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; }}
    .gx-app-title {{ color: {TEXT_PRIMARY}; font-family: {FONT_DISPLAY}; font-size: 1.55rem;
        font-weight: 800; letter-spacing: -0.035em; line-height: 1.2; margin-top: 0.22rem; }}
    .gx-app-subtitle {{ color: {TEXT_MUTED}; font-size: 0.82rem; margin-top: 0.25rem; }}
    .gx-app-status {{ color: {TEXT_SECONDARY}; font-family: {FONT_MONO}; font-size: 0.7rem;
        border: 1px solid {DIVIDER}; background: rgba(255,255,255,0.025);
        border-radius: 999px; padding: 0.38rem 0.75rem; white-space: nowrap; }}

    /* ---- Hero ------------------------------------------------------------ */
    .gx-hero {{
        background: linear-gradient(112deg, {BG_CARD} 0%, {BG_ELEVATED} 100%);
        border: 1px solid {DIVIDER}; border-left: 4px solid {ACCENT_TEAL};
        border-radius: 15px; padding: 1.35rem 1.55rem; margin: 0.45rem 0 1.35rem;
        box-shadow: 0 12px 28px rgba(0,0,0,0.14);
    }}
    .gx-hero-eyebrow {{
        font-family: {FONT_MONO}; font-size: 0.67rem; font-weight: 700;
        letter-spacing: 0.15em; color: {ACCENT_TEAL}; text-transform: uppercase; margin-bottom: 0.45rem;
    }}
    .gx-hero-title {{ font-size: 1.85rem; font-weight: 800; color: {TEXT_PRIMARY}; line-height: 1.15; }}
    .gx-hero-subtitle {{ color: {TEXT_SECONDARY}; font-size: 0.88rem; margin-top: 0.4rem; }}
    .gx-hero-chips {{ margin-top: 1rem; display: flex; flex-wrap: wrap; gap: 0.5rem; }}
    .gx-chip {{
        display: inline-block; background: rgba(255,255,255,0.045); border: 1px solid {DIVIDER};
        color: {TEXT_SECONDARY}; font-family: {FONT_MONO}; font-size: 0.69rem;
        padding: 0.34rem 0.65rem; border-radius: 7px;
    }}

    /* ---- Filter controls ------------------------------------------------- */
    .st-key-gi_filter_panel, .st-key-hsr_filter_panel {{
        background: rgba(18,30,47,0.74); border: 1px solid {DIVIDER};
        border-radius: 14px; padding: 0.75rem 1rem 0.4rem; margin: 0.6rem 0 1.35rem;
    }}
    [data-testid="stWidgetLabel"] p {{ color: {TEXT_SECONDARY}; font-size: 0.78rem; font-weight: 600; }}
    [data-baseweb="select"] > div {{ background: {BG_CARD_ALT}; border-color: {DIVIDER}; border-radius: 8px; }}
    [data-baseweb="tag"] {{ background: rgba(85,184,173,0.16); border: 1px solid rgba(85,184,173,0.28); }}
    [data-testid="stSlider"] [data-baseweb="slider"] {{ padding-top: 0.25rem; }}

    /* ---- Section hierarchy ---------------------------------------------- */
    .gx-section {{
        display: flex; align-items: baseline; flex-wrap: wrap; gap: 0.55rem;
        border-bottom: 1px solid {DIVIDER}; padding-bottom: 0.65rem; margin: 0.4rem 0 1.05rem;
    }}
    .gx-section-title {{ font-size: 1.08rem; font-weight: 800; color: {TEXT_PRIMARY}; }}
    .gx-section-subtitle {{ color: {TEXT_MUTED}; font-size: 0.78rem; margin-left: 0.1rem; }}
    .block-label {{ display: flex; align-items: center; gap: 0.7rem; margin: 1.65rem 0 0.8rem; }}
    .block-label-text {{
        font-family: {FONT_MONO}; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.14em;
        text-transform: uppercase; color: {TEXT_SECONDARY}; white-space: nowrap;
    }}
    .block-label-line {{ flex: 1; height: 1px; background: {DIVIDER}; }}

    /* ---- KPI and content cards ------------------------------------------ */
    .gx-card {{
        background: {BG_CARD}; border: 1px solid {DIVIDER};
        border-radius: 12px; padding: 1.05rem 1.2rem; margin-bottom: 0.75rem;
        box-shadow: 0 6px 18px rgba(0,0,0,0.1);
    }}
    .gx-card-title {{ font-family: {FONT_DISPLAY}; font-size: 0.93rem; font-weight: 700;
        color: {TEXT_PRIMARY}; margin-bottom: 0.8rem; }}
    .gx-card-row {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 0.75rem; padding: 0.5rem 0 0.15rem; }}
    .gx-card-divider {{ border-top: 1px solid {DIVIDER}; margin-top: 0.75rem; }}
    .gx-card-label {{ color: {TEXT_SECONDARY}; font-size: 0.78rem; line-height: 1.4; }}
    .gx-card-sublabel {{ color: {TEXT_MUTED}; font-size: 0.72rem; }}
    .gx-card-value {{ font-family: {FONT_MONO}; font-size: 1.35rem; font-weight: 700; color: {TEXT_PRIMARY}; }}
    .gx-gold {{ color: {ACCENT_GOLD}; }}
    .gx-purple {{ color: {ACCENT_PURPLE}; }}
    .pity-bar-track {{ height: 6px; border-radius: 999px; background: rgba(255,255,255,0.075); overflow: hidden; margin-top: 0.5rem; }}
    .pity-bar-fill {{ height: 100%; border-radius: 999px; }}

    .kpi-card {{
        background: linear-gradient(145deg, {BG_CARD} 0%, {BG_CARD_ALT} 100%);
        border: 1px solid {DIVIDER}; border-radius: 12px; padding: 1rem 1.1rem;
        min-height: 112px; margin-bottom: 0.7rem; box-shadow: 0 6px 18px rgba(0,0,0,0.09);
    }}
    .kpi-label {{ color: {TEXT_MUTED}; font-size: 0.68rem; font-weight: 700;
        letter-spacing: 0.09em; text-transform: uppercase; }}
    .kpi-value {{ font-family: {FONT_MONO}; font-weight: 700; margin: 0.55rem 0 0.3rem;
        line-height: 1.2; overflow-wrap: anywhere; }}
    .kpi-sub {{ color: {TEXT_SECONDARY}; font-size: 0.72rem; line-height: 1.4; }}

    .gx-badge {{
        display: inline-flex; align-items: center; font-family: {FONT_MONO}; font-size: 0.68rem;
        font-weight: 700; padding: 0.22rem 0.55rem; border-radius: 6px; margin-right: 0.28rem;
    }}
    .summary-list {{ color: {TEXT_SECONDARY}; font-size: 0.86rem; line-height: 1.8; padding-left: 1.1rem; margin: 0; }}
    .summary-list li {{ padding: 0.12rem 0; }}
    .summary-list b {{ color: {TEXT_PRIMARY}; }}
    .chart-note {{
        color: {TEXT_SECONDARY}; font-size: 0.78rem; line-height: 1.65;
        background: rgba(85,184,173,0.055); border-left: 3px solid {ACCENT_TEAL};
        border-radius: 0 8px 8px 0; padding: 0.65rem 0.85rem; margin: 0.6rem 0 1.1rem;
    }}
    .chart-note b {{ color: {TEXT_PRIMARY}; }}

    /* ---- Streamlit widgets ---------------------------------------------- */
    [data-testid="stMetric"] {{
        background: {BG_CARD_ALT}; border: 1px solid {DIVIDER};
        border-radius: 11px; padding: 0.8rem 0.95rem;
    }}
    [data-testid="stMetricValue"] {{ font-family: {FONT_MONO}; color: {ACCENT_GOLD}; font-size: 1.35rem; }}
    [data-testid="stMetricLabel"] {{ color: {TEXT_SECONDARY}; font-size: 0.75rem; }}
    [data-baseweb="tab-list"] {{ gap: 0.25rem; border-bottom: 1px solid {DIVIDER}; overflow-x: auto; }}
    [data-baseweb="tab"] {{ font-family: {FONT_DISPLAY}; font-weight: 700; font-size: 0.8rem;
        color: {TEXT_MUTED}; padding: 0.65rem 0.8rem; white-space: nowrap; }}
    [data-baseweb="tab"][aria-selected="true"] {{ color: {TEXT_PRIMARY}; }}
    [data-baseweb="tab-highlight"] {{ background: {ACCENT_TEAL} !important; height: 2px; }}
    [data-baseweb="tab-panel"] {{ padding-top: 1rem; }}
    [data-testid="stDataFrame"] {{ border: 1px solid {DIVIDER}; border-radius: 10px; overflow: hidden; }}
    [data-testid="stExpander"] {{ border: 1px solid {DIVIDER}; border-radius: 11px; background: rgba(18,30,47,0.55); }}
    [data-testid="stPlotlyChart"] {{
        background: {BG_CARD}; border: 1px solid {DIVIDER}; border-radius: 12px;
        padding: 0.35rem 0.45rem 0.15rem; box-shadow: 0 5px 16px rgba(0,0,0,0.08);
    }}
    .stDownloadButton > button {{
        background: rgba(85,184,173,0.12); color: {TEXT_PRIMARY};
        border: 1px solid rgba(85,184,173,0.38); border-radius: 9px;
        font-weight: 700; min-height: 2.65rem;
    }}
    .stDownloadButton > button:hover {{ background: rgba(85,184,173,0.2); border-color: {ACCENT_TEAL}; color: {TEXT_PRIMARY}; }}
    [data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED}; }}
    .gx-footer {{
        text-align: center; color: {TEXT_MUTED}; font-size: 0.72rem;
        padding: 1.2rem 0 0.35rem; border-top: 1px solid {DIVIDER}; margin-top: 2.2rem;
    }}

    /* ---- Responsive spacing -------------------------------------------- */
    @media (max-width: 900px) {{
        .block-container {{ padding: 1.1rem 1rem 2rem; }}
        .gx-hero {{ padding: 1.1rem 1.15rem; }}
        .gx-hero-title {{ font-size: 1.5rem; }}
        .gx-appbar {{ align-items: flex-start; flex-direction: column; }}
    }}
    @media (max-width: 600px) {{
        .block-container {{ padding: 0.8rem 0.65rem 1.5rem; }}
        .gx-chip {{ font-size: 0.64rem; }}
        .gx-section {{ gap: 0.35rem; }}
        .gx-section-subtitle {{ width: 100%; margin-left: 0; }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# Presentation helpers
# ============================================================================
def section_header(title: str, subtitle: str = ""):
    sub = f'<span class="gx-section-subtitle">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f'<div class="gx-section"><span class="gx-section-title">{title}</span>{sub}</div>',
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


def show(fig, k: str, name: str):
    """Render a Plotly figure with a unique key (both games render on the same page)."""
    st.plotly_chart(fig, key=f"{k}_{name}", **STRETCH)


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
    """Luck Score per account using the shared formula from analytics_common."""
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
    cards = [kpi_card(f"Total {w}s", f"{stats['total']:,}", f"≈ {stats['total'] * cfg.pull_cost:,} {cfg.currency}")]

    per5 = f"1 per {stats['per_5']:.1f} {w.lower()}s" if stats["per_5"] else "no 5★ yet"
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
                            <div class="gx-card-label">Lifetime {cfg.pull_word}s</div>
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
    overall = f"<b>Period:</b> {start} – {end} · 5★ rate {stats['rate_5']:.2f}% ({stats['n5']} of {stats['total']:,} {cfg.pull_word.lower()}s)"
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
                f"<b>Banner efficiency:</b> {best} is the most efficient ({ppf[best]:.1f} {cfg.pull_word.lower()}s per 5★), "
                f"{worst} the least ({ppf[worst]:.1f})."
            )

    monthly = df.groupby("year_month").size()
    items.append(
        f"<b>Activity:</b> busiest month was {monthly.idxmax()} ({monthly.max():,} {cfg.pull_word.lower()}s); "
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
def account_filter(df: pd.DataFrame, k: str, key: str) -> pd.DataFrame:
    """Per-tab account selector, shown only when several accounts are in the selection."""
    accounts = account_order(df)
    if len(accounts) <= 1:
        return df
    choice = st.radio("Account", ["All"] + accounts, horizontal=True, key=f"{k}_accfilter_{key}")
    return df if choice == "All" else df[df["account"] == choice]


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
        fig = go.Figure()
        for r in (3, 4, 5):
            fig.add_trace(go.Bar(x=summary["account"], y=summary[f"pull_{r}star"], name=f"{r}★", marker_color=RARITY_COLORS[r]))
        fig.add_trace(go.Scatter(x=summary["account"], y=summary["total_pull"], mode="text",
                                 text=[f"{int(v):,}" for v in summary["total_pull"]], textposition="top center",
                                 textfont=dict(color=TEXT_PRIMARY, size=12), showlegend=False, hoverinfo="skip", cliponaxis=False))
        apply_layout(fig, f"Total {w}s per Account", "Account", f"{w}s", barmode="stack", hovermode="x unified", legend=True)
        fig.update_yaxes(range=[0, summary["total_pull"].max() * 1.15])
        show(fig, k, "total_pull")
        top = summary.sort_values("total_pull", ascending=False).iloc[0]
        if len(summary) > 1:
            chart_note(f"<b>{html.escape(str(top['account']))}</b> has the most {w.lower()}s ({int(top['total_pull']):,}). "
                       f"5★ share ranges from {summary['pct_5star'].min():.2f}% to {summary['pct_5star'].max():.2f}%.")
        else:
            chart_note(f"{int(top['total_pull']):,} {w.lower()}s: {int(top['pull_5star'])} five-star ({top['pct_5star']:.2f}%), "
                       f"{int(top['pull_4star'])} four-star, {int(top['pull_3star'])} three-star.")

    with col2:
        has_progress = summary["adventure_rank"].notna().any()
        fig = go.Figure()
        if has_progress:
            fig.add_trace(go.Bar(x=summary["account"], y=summary["adventure_rank"], name="Adventure Rank", marker_color=ACCENT_GOLD))
            fig.add_trace(go.Bar(x=summary["account"], y=summary["world_level"], name="World Level", marker_color=ACCENT_BLUE))
            apply_layout(fig, "Account Progress (AR & WL)", "Account", "Level", barmode="group", legend=True)
            show(fig, k, "progress")
            ar = summary.dropna(subset=["adventure_rank"]).sort_values("adventure_rank", ascending=False).iloc[0]
            wl = f" (World Level {int(ar['world_level'])})" if pd.notna(ar["world_level"]) else ""
            chart_note(f"Progression context only: highest Adventure Rank is {int(ar['adventure_rank'])}{wl} on "
                       f"<b>{html.escape(str(ar['account']))}</b>. It shows how far an account has advanced, not how lucky it was.")
        else:
            fig.add_trace(go.Bar(x=summary["account"], y=summary["pct_5star"], name="5★ rate", marker_color=RARITY_COLORS[5],
                                 text=[f"{p:.2f}%" for p in summary["pct_5star"]], textposition="outside"))
            fig.add_trace(go.Bar(x=summary["account"], y=summary["pct_4star"], name="4★ rate", marker_color=RARITY_COLORS[4],
                                 text=[f"{p:.2f}%" for p in summary["pct_4star"]], textposition="outside"))
            apply_layout(fig, "5★ & 4★ Rate per Account", "Account", f"Share of {w.lower()}s (%)", barmode="group", legend=True)
            fig.update_yaxes(range=[0, max(summary["pct_4star"].max(), summary["pct_5star"].max()) * 1.25])
            show(fig, k, "rates")
            chart_note(f"{cfg.title} exports contain no account level data, so this shows the observed 5★ and 4★ rate per account "
                       "(base rates are about 0.6% for 5★ and 5.1% for 4★).")

    with st.expander("Data Details"):
        show_df(summary)


def insight_timeline(df, cfg, k):
    w = cfg.pull_word
    section_header(f"{w} Timeline", f"Monthly {w.lower()} volume by banner")
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
    apply_layout(fig, f"Monthly {w}s by Banner", "Month", f"{w}s", height=460, barmode="stack", hovermode="x unified", legend=True)
    fig.update_yaxes(range=[0, total.max() * 1.15])
    show(fig, k, "timeline")
    top_banner = pivot.sum().idxmax()
    share = pivot[top_banner].sum() / pivot.values.sum() * 100
    active = total[total > 0]
    chart_note(f"Busiest month: <b>{total.idxmax()}</b> ({int(total.max()):,} {w.lower()}s); average {active.mean():.0f} per active month. "
               f"{top_banner} makes up {share:.0f}% of all {w.lower()}s.")
    with st.expander("Data Details"):
        show_df(timeline)


def insight_pity_distribution(df, cfg, k):
    section_header("5★ Pity Distribution", "How many pulls each 5★ took to land, per banner")
    five = df[df["is_5star"]].copy()
    if five.empty:
        st.warning("No 5★ pulls in the current selection.")
        return
    banners = order_banners(cfg, five["banner_type"].dropna().unique())
    banners = [b for b in banners if (five["banner_type"] == b).any()]
    for i in range(0, len(banners), 3):
        cols = st.columns(3)
        for col, banner in zip(cols, banners[i:i + 3]):
            vals = five.loc[five["banner_type"] == banner, "pity"].dropna()
            if vals.empty:
                continue
            hard = cfg.hard_pity.get(banner, cfg.default_hard_pity)
            with col:
                fig = go.Figure(go.Histogram(x=vals, xbins=dict(start=0, end=hard + 5, size=5),
                                             marker_color=cfg.banner_colors.get(banner, "#999999"), name=banner))
                fig.add_vline(x=vals.mean(), line_dash="dash", line_color=TEXT_PRIMARY,
                              annotation_text=f"mean {vals.mean():.1f}", annotation_font_color=TEXT_SECONDARY,
                              annotation_position="top left")
                fig.add_vline(x=hard, line_dash="dot", line_color=TEXT_MUTED,
                              annotation_text=f"hard {hard}", annotation_font_color=TEXT_MUTED,
                              annotation_position="top right")
                apply_layout(fig, f"{banner} (n={len(vals)})", "Pity at 5★", "5★ count", height=330, bargap=0.05)
                fig.update_xaxes(range=[0, hard + 5])
                show(fig, k, f"pity_{banner}")
    avgs = five.groupby("banner_type", observed=True)["pity"].mean()
    avg_txt = " · ".join(f"{b} <b>{avgs[b]:.1f}</b>" for b in banners if b in avgs.index and pd.notna(avgs[b]))
    softs = ", ".join(f"{b} {cfg.soft_pity[b]}" for b, _ in cfg.summary_banners if b in cfg.soft_pity)
    chart_note(f"Average 5★ pity: {avg_txt}. Bars count 5★ by pity bucket (5 per bar); dashed line = average, dotted line = hard pity. "
               f"Soft pity starts at {softs}: clusters just before it are normal, bars far left are early lucky pulls.")
    with st.expander("Data Details"):
        show_df(five[["account", "banner_type", "datetime", "item_name", "item_category", "pity", "win_50_50"]]
                .astype({"banner_type": str}).sort_values(["banner_type", "datetime"]))


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
    perf["baseline_pct"] = perf["banner_type"].map(cfg.rateup_chance)
    colors = [cfg.banner_colors.get(b, "#999999") for b in perf["banner_type"]]

    def hbar(x, title, name, text, xtitle):
        fig = go.Figure(go.Bar(y=perf["banner_type"], x=x, orientation="h", marker_color=colors, text=text, textposition="outside"))
        apply_layout(fig, title, xtitle, None, height=340)
        fig.update_yaxes(autorange="reversed")
        return fig

    col1, col2, col3 = st.columns(3)
    with col1:
        fig = hbar(perf["total_pull"], f"Total {w}s", "total", [f"{v:,}" for v in perf["total_pull"]], f"{w}s")
        fig.update_xaxes(range=[0, perf["total_pull"].max() * 1.25])
        show(fig, k, "banner_total")
        top = perf.sort_values("total_pull", ascending=False).iloc[0]
        chart_note(f"<b>{top['banner_type']}</b> takes {top['total_pull'] / perf['total_pull'].sum() * 100:.0f}% of all {w.lower()}s ({int(top['total_pull']):,}).")
    with col2:
        vals = perf["pull_per_5star"]
        fig = hbar(vals.fillna(0), f"{w}s per 5★ (lower = better)", "eff",
                   [f"{v:.1f}" if pd.notna(v) else "N/A" for v in vals], f"{w}s per 5★")
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
    st.caption("No. = order of the pull within its account, counted inside the current filters. Newest first.")


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
            f"{len(display_df):,} {cfg.pull_word.lower()}s",
            wr,
        ],
    )

    block_label("Overview")
    render_key_parameters(cfg, stats)

    block_label("Banner Pity Meters")
    render_pity_section(display_df, cfg)
    st.caption("Pity counters are computed from the pulls inside the active date and banner filters.")

    block_label("Summary")
    render_executive_summary(display_df, cfg, stats, single)

    block_label("Detailed Analysis")
    tabs = st.tabs([
        "Total Pulls", "Banner", "Timeline", "Pity 5★", "50-50",
        "Luck Score", "Top Items", "Latest 5★", "History",
    ])
    views = [
        insight_total_pull, insight_banner_performance, insight_timeline,
        insight_pity_distribution, insight_win_lose, insight_luck_score,
        insight_top_items, insight_latest_5star, insight_pull_history,
    ]
    for tab, view in zip(tabs, views):
        with tab:
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
        '<div class="gx-sidebar-name">Gacha<br>Analytics</div>'
        '<div class="gx-sidebar-caption">A consolidated view of pull history, pity and banner performance.</div>'
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
        '<div class="gx-app-title">Gacha performance overview</div>'
        '<div class="gx-app-subtitle">Track account activity, banner efficiency and pull outcomes.</div></div>'
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
