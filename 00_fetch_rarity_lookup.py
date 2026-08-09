"""
00_fetch_rarity_lookup.py
===========================
The Paimon.moe export (paimon-moe-local-data.json) ONLY contains item id,
timestamp, type (character/weapon), and pity per pull -- it has NO rarity
info (3/4/5-star) or official item name. For EDA (5-star pity distribution,
top character, etc.) we need a reference table of id -> {name, rarity}.

This script fetches that reference table directly from Paimon.moe's own
source code on GitHub (the same repo behind the site used to generate your
export file):
    https://github.com/MadeBaruna/paimon-moe
    - src/data/characters.js   -> list of all characters + rarity
    - src/data/weaponList.js   -> list of all weapons + rarity

Output:
    data/char_full.json    -> { item_id: {"name": ..., "rarity": ...}, ... }
    data/weapon_full.json  -> { item_id: {"name": ..., "rarity": ...}, ... }

Run this script ONCE before 01_preprocessing.py (or re-run to refresh with
the latest data from the repo). Requires internet access to
raw.githubusercontent.com.
"""

import json
import re
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

REPO_RAW_BASE = "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main"
SOURCES = {
    "char_full.json": f"{REPO_RAW_BASE}/src/data/characters.js",
    "weapon_full.json": f"{REPO_RAW_BASE}/src/data/weaponList.js",
}

# Main regex: find every "id: '...'", then look for its name & rarity nearby.
# We use a window (rather than parsing the full object block) because the
# source is a JS object literal, not valid JSON, and the field order of
# name/id/rarity isn't consistent between the two files.
ID_RE = re.compile(r"id:\s*'([^']+)'")
NAME_RE = re.compile(r"name:\s*(?:'([^']*)'|\"([^\"]*)\")")
RARITY_RE = re.compile(r"rarity:\s*'?(\d+)'?")
WINDOW = 300  # characters to the left/right of "id:" to search for its name/rarity


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse_lookup(js_text: str) -> dict:
    result = {}
    id_matches = list(ID_RE.finditer(js_text))

    for i, m in enumerate(id_matches):
        item_id = m.group(1)

        # BUG FIX: a fixed +/-300 char window can bleed into the previous or
        # next item's fields when entries sit closer together than that (very
        # common), silently attaching the WRONG name/rarity to this item_id --
        # worse than a missing value, since it doesn't show up in the
        # missing_name/missing_rarity counters below. Clamp the window to the
        # midpoint boundary with neighboring "id:" matches so it can never
        # cross into another entry.
        prev_end = id_matches[i - 1].end() if i > 0 else 0
        next_start = id_matches[i + 1].start() if i + 1 < len(id_matches) else len(js_text)
        start = max(prev_end, m.start() - WINDOW)
        end = min(next_start, m.end() + WINDOW)
        window = js_text[start:end]

        name_m = NAME_RE.search(window)
        name = None
        if name_m:
            name = name_m.group(1) if name_m.group(1) is not None else name_m.group(2)

        rarity_m = RARITY_RE.search(window)
        rarity = int(rarity_m.group(1)) if rarity_m else None

        result[item_id] = {"name": name, "rarity": rarity}
    return result


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for out_filename, url in SOURCES.items():
        print(f"Fetching {url} ...")
        js_text = fetch_text(url)
        lookup = parse_lookup(js_text)

        missing_name = [k for k, v in lookup.items() if v["name"] is None]
        missing_rarity = [k for k, v in lookup.items() if v["rarity"] is None]
        print(f"  -> {len(lookup)} item(s) found "
              f"({len(missing_name)} without name, {len(missing_rarity)} without rarity)")

        out_path = DATA_DIR / out_filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(lookup, f, ensure_ascii=False, indent=2)
        print(f"  -> saved to {out_path}")

    print("\nDone. Next, run 01_preprocessing.py")


if __name__ == "__main__":
    main()