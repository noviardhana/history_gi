"""
config.py
=========
Single source of truth for per-game settings AND project paths. Imported by:
    - pipeline/fetch_lookup.py, preprocess.py               (paths)
    - pipeline/analytics_core.py                            (charts + Luck Score)
    - pipeline/sync_gsheet.py                               (Google Sheets)
    - dashboard.py (project root)                           (Streamlit dashboard)

Pure standard library on purpose (no pandas / matplotlib), so lightweight
scripts such as the Google Sheets sync can import it without extra packages.

Project paths (relative to the project root, one level above pipeline/):
    data/          raw exports, lookup JSON, data_clean*.csv
    outputs/       gi/ and hsr/  (analytics CSV + PNG)
    credentials/   secret.toml (git-ignored)

To change a pity value, a rate-up chance or a banner colour, change it here
and every script follows.
"""

from dataclasses import dataclass, field
from pathlib import Path

# --- project paths -------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]   # project root (parent of pipeline/)
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
CREDENTIALS_DIR = ROOT_DIR / "credentials"

# Cleaned CSVs written by preprocess.py (GI used to be called data_clean.csv)
GI_CLEAN = DATA_DIR / "data_clean_gi.csv"
HSR_CLEAN = DATA_DIR / "data_clean_hsr.csv"
LEGACY_GI_CLEAN = DATA_DIR / "data_clean.csv"


def default_clean_csv(game_key: str) -> Path:
    """Default CSV of a game; Genshin falls back to the old name data_clean.csv if only that exists."""
    if game_key.upper() == "HSR":
        return HSR_CLEAN
    if not GI_CLEAN.exists() and LEGACY_GI_CLEAN.exists():
        return LEGACY_GI_CLEAN
    return GI_CLEAN


# Timezone of the `datetime` column in every data_clean*.csv, so both games are comparable.
DEFAULT_TZ = "Asia/Jakarta"


@dataclass
class GameConfig:
    # --- identity ---------------------------------------------------------
    key: str                # "GI" / "HSR"
    title: str              # "Genshin Impact"
    pull_word: str          # "Wish" / "Warp"
    source_label: str       # where the data came from (footer)
    # --- banners ----------------------------------------------------------
    banner_order: list
    banner_colors: dict
    hard_pity: dict         # per banner, official 5* hard pity
    rateup_chance: dict     # per banner, official chance (%) that a 5* is the rate-up item
    gear_category: str      # item_category value of the gear: "weapon" / "light_cone"
    gear_label: str         # "Weapon" / "Light Cone"
    default_hard_pity: int = 90
    # --- dashboard --------------------------------------------------------
    soft_pity: dict = field(default_factory=dict)         # per banner, pull where 5* rates start to ramp
    hard_pity_4: int = 10                                 # 4* guarantee
    # per banner, consolidated 5* rate per pull in % (pity included). Used by the dashboard's "Actual vs Expected"
    # and "Rolling Efficiency". A banner without an entry (e.g. Beginners) is left out of those two charts.
    expected_rate_5: dict = field(default_factory=dict)
    # per banner, maximum number of pulls the banner allows (NOT a pity): Beginners banners are capped.
    pull_limit: dict = field(default_factory=dict)
    pity_card_banners: list = field(default_factory=list) # banners shown as pity meters
    summary_banners: list = field(default_factory=list)   # [(banner, short label)] for the written summary
    currency: str = "Primogems"
    pull_cost: int = 160
    # --- google sheets ----------------------------------------------------
    sheet_prefix: str = "GI"
    sheet_banners: list = field(default_factory=list)     # banners that get a table in the sheet
    sheet_banner_style: dict = field(default_factory=dict)  # banner -> (icon, title colour)


GI = GameConfig(
    key="GI",
    title="Genshin Impact",
    pull_word="Wish",
    source_label="Paimon.moe export",
    banner_order=["Character Event", "Weapon Event", "Standard", "Beginners"],
    banner_colors={
        "Character Event": "#D9A441",
        "Weapon Event": "#5B8FD6",
        "Standard": "#6BBF7B",
        "Beginners": "#C9576A",
    },
    hard_pity={
        "Character Event": 90,
        "Standard": 90,
        "Weapon Event": 80,   # agreed reference value (was 77 in the old analytics script)
        # Beginners' Wish has the standard 5* pity rules (90). 20 is its wish limit, see pull_limit below.
        "Beginners": 90,
    },
    rateup_chance={
        "Character Event": 50,
        "Weapon Event": 75,
    },
    gear_category="weapon",
    gear_label="Weapon",
    soft_pity={"Character Event": 74, "Standard": 74, "Weapon Event": 63},
    expected_rate_5={"Character Event": 1.6, "Weapon Event": 1.85, "Standard": 1.6},
    pull_limit={"Beginners": 20},
    pity_card_banners=["Character Event", "Weapon Event", "Standard", "Beginners"],
    summary_banners=[("Character Event", "Character"), ("Weapon Event", "Weapon")],
    currency="Primogems",
    sheet_prefix="GI",
    sheet_banners=["Character Event", "Weapon Event", "Standard", "Beginners"],
    sheet_banner_style={
        "Character Event": ("🎯", "#fde7c2"),
        "Weapon Event": ("⚔️", "#d6e4f7"),
        "Standard": ("🌌", "#d5efd9"),
        "Beginners": ("🔰", "#f6d3da"),
    },
)

HSR = GameConfig(
    key="HSR",
    title="Honkai: Star Rail",
    pull_word="Warp",
    source_label="StarRailStation backup",
    banner_order=[
        "Character Event",
        "Light Cone Event",
        "Collab Character Event",
        "Collab Light Cone Event",
        "Standard",
        "Beginners",
    ],
    banner_colors={
        "Character Event": "#D9A441",
        "Light Cone Event": "#5B8FD6",
        "Collab Character Event": "#D6783E",
        "Collab Light Cone Event": "#3EB5C9",
        "Standard": "#6BBF7B",
        "Beginners": "#C9576A",
    },
    hard_pity={
        "Character Event": 90,
        "Collab Character Event": 90,
        "Standard": 90,
        "Light Cone Event": 80,
        "Collab Light Cone Event": 80,
        "Beginners": 50,
    },
    rateup_chance={
        "Character Event": 50,
        "Collab Character Event": 50,
        "Light Cone Event": 75,
        "Collab Light Cone Event": 75,
    },
    gear_category="light_cone",
    gear_label="Light Cone",
    # Soft pity values are community-documented reference values (character 74, light cone 66).
    soft_pity={
        "Character Event": 74,
        "Collab Character Event": 74,
        "Standard": 74,
        "Light Cone Event": 66,
        "Collab Light Cone Event": 66,
    },
    # Consolidated rates as commonly published (character 1.6%, light cone 1.87%); collab banners assumed to match.
    expected_rate_5={
        "Character Event": 1.6,
        "Collab Character Event": 1.6,
        "Light Cone Event": 1.87,
        "Collab Light Cone Event": 1.87,
        "Standard": 1.6,
    },
    pull_limit={"Beginners": 50},
    pity_card_banners=[
        "Character Event",
        "Light Cone Event",
        "Collab Character Event",
        "Collab Light Cone Event",
        "Standard",
    ],
    summary_banners=[("Character Event", "Character"), ("Light Cone Event", "Light Cone")],
    currency="Stellar Jade",
    sheet_prefix="HSR",
    sheet_banners=[
        "Character Event",
        "Light Cone Event",
        "Collab Character Event",
        "Collab Light Cone Event",
        "Standard",
        "Beginners",
    ],
    sheet_banner_style={
        "Character Event": ("🎯", "#fde7c2"),
        "Light Cone Event": ("🔷", "#d6e4f7"),
        "Collab Character Event": ("🤝", "#fbd9c4"),
        "Collab Light Cone Event": ("🧩", "#cdeef3"),
        "Standard": ("🌌", "#d5efd9"),
        "Beginners": ("🔰", "#f6d3da"),
    },
)

GAMES = {"GI": GI, "HSR": HSR}
