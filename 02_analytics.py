"""
02_analytics.py
=================
Analytics / EDA pipeline (Genshin Impact): data_clean.csv -> summary CSV + chart PNG.

Generates 7 insights for the storytelling dashboard, in this order:
    1. Total Pull & Account Progress
    2. Wish Timeline
    3. 5-Star Pity Distribution
    4. Win/Lose 50-50
    5. Top Character & Top Weapon
    6. Banner Performance
    7. Luck Score

Each insight produces a matching pair of files in outputs/GI/:
    <number>_<insight_name>.csv   -> summary table (reusable)
    <number>_<insight_name>.png   -> ready-to-use chart

The chart style and the Luck Score formula live in analytics_common.py and are
shared with 02_analytics_hsr.py, so both games are scored the same way.

Usage:
    python3 02_analytics.py                       # uses data/data_clean.csv
    python3 02_analytics.py --input data/data_clean_887284572.csv --outdir outputs/GI/887284572
"""

from pathlib import Path

from analytics_common import run_cli
from game_configs import GI as CONFIG  # per-game settings (pity, rate-up, colours) live in game_configs.py

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "GI"

if __name__ == "__main__":
    run_cli(CONFIG, DATA_DIR / "data_clean.csv", OUTPUT_DIR, "01_preprocessing.py")
