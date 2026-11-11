"""
02_analytics_hsr.py
===================
Analytics / EDA pipeline (Honkai: Star Rail): data_clean_hsr.csv -> summary CSV + chart PNG.

Same 7 insights as 02_analytics.py (Total Pull, Timeline, 5-Star Pity, Win/Lose
50-50, Top Character & Light Cone, Banner Performance, Luck Score), written to
outputs/HSR/isi_hasil_alitic/ as <number>_<insight_name>.csv + .png.

The chart style and the Luck Score formula live in analytics_common.py and are
shared with the Genshin script, so both games are scored the same way.

HSR specifics:
    * The StarRailStation backup has no UID / Adventure Rank / World Level, so
      insight 1 shows the 5*/4* rate per account instead.
    * Light Cone Event replaces Weapon Event; Collab banners are included.
    * Hard pity: Character 90, Light Cone 80, Standard 90, Beginners 50.
    * 5* rate-up chance: Character 50%, Light Cone 75%.

Usage:
    python3 02_analytics_hsr.py                       # uses data/data_clean_hsr.csv
    python3 02_analytics_hsr.py --input data/data_clean_hsr_second.csv --outdir outputs/HSR/second
"""

from pathlib import Path

from analytics_common import run_cli
from game_configs import HSR as CONFIG  # per-game settings (pity, rate-up, colours) live in game_configs.py

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "HSR"

if __name__ == "__main__":
    run_cli(CONFIG, DATA_DIR / "data_clean_hsr.csv", OUTPUT_DIR, "01_preprocessing_hsr.py")
