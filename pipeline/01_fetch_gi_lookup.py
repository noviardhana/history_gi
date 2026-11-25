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
from lookup_utils import fetch_text, finish, publish_lookup

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
MIN_ITEMS = {"char_full.json": 50, "weapon_full.json": 100}  # sanity floor; real files are larger
WINDOW = 300  # fallback only: used when an id is not inside any {...} block


def _brace_pairs(text: str) -> list:
    """(start, end) index of every {...} block. Braces inside '...', "..." and `...` strings are ignored."""
    pairs, stack, quote, i = [], [], None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            pairs.append((stack.pop(), i))
        i += 1
    return pairs


def _own_fields(text: str, pos: int, pairs: list):
    """Text of the innermost {...} block around `pos`, with nested {...} blocks blanked out.
    Returns None when `pos` is not inside any block."""
    around = [p for p in pairs if p[0] < pos < p[1]]
    if not around:
        return None
    start, end = max(around, key=lambda p: p[0])
    chars = list(text[start + 1:end])
    for s, e in pairs:
        if start < s and e < end:
            for k in range(s - start - 1, e - start):
                chars[k] = " "
    return "".join(chars)


def parse_lookup(js_text: str) -> dict:
    """
    id -> {"name", "rarity"} from a JS object-literal file.

    BUG FIX (v2): the earlier +/-300 char window, even when clamped to the neighbouring "id:" matches,
    still contained the *neighbour's* name/rarity whenever those fields sit between two ids (for
    example `{ id: 'a', name: 'A', rarity: 5 }, { name: 'B', id: 'b' }` gave 'b' the name 'A').
    Now each id only reads the fields of its own enclosing {...} block, so a missing field stays
    None (and is reported by lookup_utils) instead of silently taking a neighbour's value.
    """
    result = {}
    pairs = _brace_pairs(js_text)
    id_matches = list(ID_RE.finditer(js_text))

    for i, m in enumerate(id_matches):
        item_id = m.group(1)
        window = _own_fields(js_text, m.start(), pairs)
        if window is None:  # not inside braces (unexpected format): fall back to the clamped window
            prev_end = id_matches[i - 1].end() if i > 0 else 0
            next_start = id_matches[i + 1].start() if i + 1 < len(id_matches) else len(js_text)
            window = js_text[max(prev_end, m.start() - WINDOW):min(next_start, m.end() + WINDOW)]

        name_m = NAME_RE.search(window)
        name = None
        if name_m:
            name = name_m.group(1) if name_m.group(1) is not None else name_m.group(2)

        rarity_m = RARITY_RE.search(window)
        rarity = int(rarity_m.group(1)) if rarity_m else None

        result[item_id] = {"name": name, "rarity": rarity}
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
            print(f"  [ERROR] {exc}")
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
