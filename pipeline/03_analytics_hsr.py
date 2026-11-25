"""
03_analytics_hsr.py
===================
Analytics / EDA pipeline (Honkai: Star Rail): data_clean_hsr.csv -> summary CSV + chart PNG.

Same 7 insights as 03_analytics_gi.py (Total Pull, Timeline, 5-Star Pity, Win/Lose
50-50, Top Character & Light Cone, Banner Performance, Luck Score), written to
outputs/hsr/ as <number>_<insight_name>.csv + .png.

The chart style and the Luck Score formula live in analytics_core.py and are
shared with the Genshin script, so both games are scored the same way.

HSR specifics:
    * The StarRailStation backup has no UID / Adventure Rank / World Level, so
      insight 1 shows the 5*/4* rate per account instead.
    * Light Cone Event replaces Weapon Event; Collab banners are included.
    * Hard pity: Character 90, Light Cone 80, Standard 90, Beginners 50.
    * 5* rate-up chance: Character 50%, Light Cone 75%.

Usage:
    python3 pipeline/03_analytics_hsr.py                       # uses data/data_clean_hsr.csv
    python3 pipeline/03_analytics_hsr.py --input data/data_clean_hsr_second.csv --outdir outputs/hsr/second
"""

from analytics_core import run_cli
from config import HSR as CONFIG, HSR_CLEAN, OUTPUT_DIR  # per-game settings (pity, rate-up, colours) live in config.py

if __name__ == "__main__":
    run_cli(CONFIG, HSR_CLEAN, OUTPUT_DIR / "hsr", "pipeline/02_preprocess_hsr.py")
