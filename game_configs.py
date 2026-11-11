"""
game_configs.py
===============
Single source of truth for per-game settings. Imported by:
    - analytics_common.py / 02_analytics.py / 02_analytics_hsr.py  (charts + Luck Score)
    - 03_dashboard.py                                              (Streamlit dashboard)
    - 04_sync_gsheet.py                                            (Google Sheets)

Pure standard library on purpose (no pandas / matplotlib), so lightweight
scripts such as the Google Sheets sync can import it without extra packages.

To change a pity value, a rate-up chance or a banner colour, change it here
and every script follows.
"""

from dataclasses import dataclass, field


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
        "Beginners": 20,
    },
    rateup_chance={
        "Character Event": 50,
        "Weapon Event": 75,
    },
    gear_category="weapon",
    gear_label="Weapon",
    soft_pity={"Character Event": 74, "Standard": 74, "Weapon Event": 63},
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
