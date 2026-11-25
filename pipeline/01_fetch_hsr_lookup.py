"""
01_fetch_hsr_lookup.py
======================
Builds the Honkai: Star Rail id -> {name, rarity} lookup files used by
02_preprocess_hsr.py (same idea as 01_fetch_gi_lookup.py for Genshin).

Source: Mar-7th/StarRailRes (index_new/en) on GitHub.

Output:
    data/hsr_char_full.json   -> characters   {"1003": {"name": "Himeko", "rarity": 5}, ...}
    data/hsr_lc_full.json     -> light cones  {"23001": {"name": "...", "rarity": 5}, ...}

Run again whenever a new patch adds characters / light cones that show up as
"unmapped" in the output of 02_preprocess_hsr.py.

Usage:
    python3 pipeline/01_fetch_hsr_lookup.py
"""

import argparse
import json
import sys

from config import DATA_DIR
from lookup_utils import fetch_text, finish, publish_lookup

BASE_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/index_new/en"
MIN_ITEMS = {"characters.json": 30, "light_cones.json": 50}  # sanity floor; real files are larger
SOURCES = {
    "characters.json": DATA_DIR / "hsr_char_full.json",
    "light_cones.json": DATA_DIR / "hsr_lc_full.json",
}


def fetch_json(url: str) -> dict:
    return json.loads(fetch_text(url))


def main():
    parser = argparse.ArgumentParser(description="Fetch the Star Rail id -> name/rarity lookup.")
    parser.add_argument("--force", action="store_true", help="Write the result even if it fails the sanity checks.")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    for filename, out_path in SOURCES.items():
        print(f"Fetching {BASE_URL}/{filename} ...")
        try:
            raw = fetch_json(f"{BASE_URL}/{filename}")
        except (ConnectionError, ValueError) as exc:
            print(f"  [ERROR] {exc}")
            results[filename] = "kept" if out_path.exists() else "failed"
            continue
        slim = {str(k): {"name": v.get("name"), "rarity": v.get("rarity")} for k, v in raw.items()}
        print(f"  -> {len(slim)} entries")
        results[filename] = publish_lookup(out_path, slim, MIN_ITEMS[filename], force=args.force)

    sys.exit(finish(results))


if __name__ == "__main__":
    main()
