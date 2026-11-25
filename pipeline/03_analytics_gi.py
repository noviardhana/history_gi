"""
03_analytics_gi.py
==================
Analytics / EDA pipeline (Genshin Impact): data_clean.csv -> summary CSV + chart PNG.

Generates 7 insights for the storytelling dashboard, in this order:
    1. Total Pull & Account Progress
    2. Wish Timeline
    3. 5-Star Pity Distribution
    4. Win/Lose 50-50
    5. Top Character & Top Weapon
    6. Banner Performance
    7. Luck Score

Each insight produces a matching pair of files in outputs/gi/:
    <number>_<insight_name>.csv   -> summary table (reusable)
    <number>_<insight_name>.png   -> ready-to-use chart

The chart style and the Luck Score formula live in analytics_core.py and are
shared with 03_analytics_hsr.py, so both games are scored the same way.

Usage:
    python3 pipeline/03_analytics_gi.py                       # uses data/data_clean.csv
    python3 pipeline/03_analytics_gi.py --input data/data_clean_887284572.csv --outdir outputs/gi/887284572
"""

from analytics_core import run_cli
from config import DATA_DIR, GI as CONFIG, OUTPUT_DIR  # per-game settings (pity, rate-up, colours) live in config.py

if __name__ == "__main__":
    run_cli(CONFIG, DATA_DIR / "data_clean.csv", OUTPUT_DIR / "gi", "pipeline/02_preprocess_gi.py")
