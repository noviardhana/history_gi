"""
00_fetch_hsr_lookup.py
======================
Builds the Honkai: Star Rail id -> {name, rarity} lookup files used by
01_preprocessing_hsr.py (same idea as 00_fetch_rarity_lookup.py for Genshin).

Source: Mar-7th/StarRailRes (index_new/en) on GitHub.

Output:
    data/hsr_char_full.json   -> characters   {"1003": {"name": "Himeko", "rarity": 5}, ...}
    data/hsr_lc_full.json     -> light cones  {"23001": {"name": "...", "rarity": 5}, ...}

Run again whenever a new patch adds characters / light cones that show up as
"unmapped" in the output of 01_preprocessing_hsr.py.

Usage:
    python3 00_fetch_hsr_lookup.py
"""

import json
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

BASE_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/index_new/en"
SOURCES = {
    "characters.json": DATA_DIR / "hsr_char_full.json",
    "light_cones.json": DATA_DIR / "hsr_lc_full.json",
}


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, out_path in SOURCES.items():
        raw = fetch_json(f"{BASE_URL}/{filename}")
        slim = {
            str(k): {"name": v.get("name"), "rarity": v.get("rarity")}
            for k, v in raw.items()
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False, indent=2)
        print(f"{filename}: {len(slim)} entries -> {out_path}")


if __name__ == "__main__":
    main()
