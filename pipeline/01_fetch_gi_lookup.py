"""
01_fetch_gi_lookup.py
=====================
(Genshin Impact)
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

Run this script ONCE before 02_preprocess_gi.py (or re-run to refresh with
the latest data from the repo). Requires internet access to
raw.githubusercontent.com.
"""

import argparse
import re
import sys

from config import DATA_DIR
from logsetup import get_logger
from lookup_utils import fetch_text, finish, publish_lookup

log = get_logger("fetch_gi")

REPO_RAW_BASE = "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main"
SOURCES = {
    "char_full.json": f"{REPO_RAW_BASE}/src/data/characters.js",
    "weapon_full.json": f"{REPO_RAW_BASE}/src/data/weaponList.js",
}

# The source is a JS object literal, not valid JSON, and the field order of name/id/rarity
# differs between the two files. So: find every "id: '...'" and read name & rarity only from
# the same entry (see parse_lookup).
ID_RE = re.compile(r"id:\s*'([^']+)'")
NAME_RE = re.compile(r"name:\s*(?:'([^']*)'|\"([^\"]*)\")")
RARITY_RE = re.compile(r"rarity:\s*'?(\d+)'?")
MIN_ITEMS = {"char_full.json": 50, "weapon_full.json": 100}  # sanity floor; real files are larger
# Top-level entries of the JS object, e.g. "  aino: {" or "  'wolfs_gravestone': {" (2-space indent).
BLOCK_RE = re.compile(r"^ {2}['\"]?[\w$.-]+['\"]?:\s*\{\s*$", re.M)


def _name_rarity(text: str):
    name_m = NAME_RE.search(text)
    name = None
    if name_m:
        name = name_m.group(1) if name_m.group(1) is not None else name_m.group(2)
    rarity_m = RARITY_RE.search(text)
    return name, (int(rarity_m.group(1)) if rarity_m else None)


def parse_lookup(js_text: str) -> dict:
    """
    Preferred: split the file into its top-level entries and read id / name / rarity from
    inside each entry only, so a field can never come from a neighbouring entry. This is used
    when the number of entries equals the number of `id:` fields. Otherwise (format changed)
    fall back to the {...} object around each `id:`.
    """
    id_count = len(ID_RE.findall(js_text))
    starts = [m.start() for m in BLOCK_RE.finditer(js_text)]
    if starts and len(starts) == id_count:
        result = {}
        for i, start in enumerate(starts):
            chunk = js_text[start: starts[i + 1] if i + 1 < len(starts) else len(js_text)]
            id_m = ID_RE.search(chunk)
            if id_m:
                name, rarity = _name_rarity(chunk)
                result[id_m.group(1)] = {"name": name, "rarity": rarity}
        if len(result) == id_count:
            return result
    return _parse_lookup_window(js_text)


def _enclosing_object(text: str, pos: int):
    """(start, end) of the innermost {...} that contains `pos`, or None."""
    depth = 0
    start = None
    for i in range(pos - 1, -1, -1):
        c = text[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
    if start is None:
        return None
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return start, j + 1
    return None


def _parse_lookup_window(js_text: str) -> dict:
    """Fallback: read name / rarity from the {...} object that holds each `id:` (never from a neighbouring entry)."""
    result = {}
    for m in ID_RE.finditer(js_text):
        bounds = _enclosing_object(js_text, m.start())
        chunk = js_text[bounds[0]:bounds[1]] if bounds else js_text[m.start(): m.start() + 300]
        name, rarity = _name_rarity(chunk)
        result[m.group(1)] = {"name": name, "rarity": rarity}
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch the Genshin id -> name/rarity lookup.")
    parser.add_argument("--force", action="store_true", help="Write the result even if it fails the sanity checks.")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    for out_filename, url in SOURCES.items():
        print(f"Fetching {url} ...")
        out_path = DATA_DIR / out_filename
        try:
            lookup = parse_lookup(fetch_text(url))
        except ConnectionError as exc:
            log.error(f"{exc}")
            results[out_filename] = "kept" if out_path.exists() else "failed"
            continue
        print(f"  -> {len(lookup)} item(s) found")
        results[out_filename] = publish_lookup(out_path, lookup, MIN_ITEMS[out_filename], force=args.force)

    code = finish(results)
    if code == 0:
        print("\nDone. Next, run 02_preprocess_gi.py")
    sys.exit(code)


if __name__ == "__main__":
    main()
