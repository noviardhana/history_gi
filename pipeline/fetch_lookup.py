"""
fetch_lookup.py
===============
Builds the id -> {name, rarity} lookup files that preprocess.py needs
(merged from the former 01_fetch_gi_lookup.py and 01_fetch_hsr_lookup.py).

Genshin Impact (--game gi)
    The Paimon.moe export only has item id, timestamp, type and pity per pull, no rarity
    or name. The reference table is read from Paimon.moe's own source on GitHub
    (https://github.com/MadeBaruna/paimon-moe: src/data/characters.js, weaponList.js).
    Output: data/char_full.json, data/weapon_full.json

Honkai: Star Rail (--game hsr)
    Source: Mar-7th/StarRailRes (index_new/en) on GitHub.
    Output: data/hsr_char_full.json, data/hsr_lc_full.json

Run again whenever a new patch adds items that show up as "unmapped" in the output of
preprocess.py. Requires internet access to raw.githubusercontent.com.

Usage:
    python -m pipeline fetch                      # both games found in data/
    python pipeline/fetch_lookup.py --game gi
    python pipeline/fetch_lookup.py --game hsr --force
"""

import argparse
import json
import re
import sys

if __package__:
    from .config import DATA_DIR
    from .utils import fetch_text, finish, get_logger, publish_lookup
else:
    from config import DATA_DIR
    from utils import fetch_text, finish, get_logger, publish_lookup

log = get_logger("fetch_lookup")

# ---------------------------------------------------------------------------
# Genshin Impact
# ---------------------------------------------------------------------------
GI_REPO_RAW_BASE = "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main"
GI_SOURCES = {  # output file -> (url, minimum number of items)
    "char_full.json": (f"{GI_REPO_RAW_BASE}/src/data/characters.js", 50),
    "weapon_full.json": (f"{GI_REPO_RAW_BASE}/src/data/weaponList.js", 100),
}

# The source is a JS object literal, not valid JSON, and the field order of name/id/rarity
# differs between the two files. So: find every "id: '...'" and read name & rarity only from
# the same entry (see parse_lookup).
ID_RE = re.compile(r"id:\s*'([^']+)'")
NAME_RE = re.compile(r"name:\s*(?:'([^']*)'|\"([^\"]*)\")")
RARITY_RE = re.compile(r"rarity:\s*'?(\d+)'?")
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


def _gi_items(url: str) -> dict:
    return parse_lookup(fetch_text(url))


# ---------------------------------------------------------------------------
# Honkai: Star Rail
# ---------------------------------------------------------------------------
HSR_BASE_URL = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/index_new/en"
HSR_SOURCES = {  # output file -> (url, minimum number of items)
    "hsr_char_full.json": (f"{HSR_BASE_URL}/characters.json", 30),
    "hsr_lc_full.json": (f"{HSR_BASE_URL}/light_cones.json", 50),
}


def fetch_json(url: str) -> dict:
    return json.loads(fetch_text(url))


def _hsr_items(url: str) -> dict:
    raw = fetch_json(url)
    return {str(k): {"name": v.get("name"), "rarity": v.get("rarity")} for k, v in raw.items()}


# ---------------------------------------------------------------------------
GAME_SOURCES = {"gi": (GI_SOURCES, _gi_items), "hsr": (HSR_SOURCES, _hsr_items)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch the Genshin / Star Rail id -> name/rarity lookup.")
    parser.add_argument("--game", required=True, choices=sorted(GAME_SOURCES), help="gi or hsr")
    parser.add_argument("--force", action="store_true", help="Write the result even if it fails the sanity checks.")
    args = parser.parse_args(argv)

    sources, loader = GAME_SOURCES[args.game]
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    for filename, (url, min_items) in sources.items():
        print(f"Fetching {url} ...")
        out_path = DATA_DIR / filename
        try:
            lookup = loader(url)
        except (ConnectionError, ValueError) as exc:
            log.error(f"{exc}")
            results[filename] = "kept" if out_path.exists() else "failed"
            continue
        print(f"  -> {len(lookup)} item(s) found")
        results[filename] = publish_lookup(out_path, lookup, min_items, force=args.force)

    code = finish(results)
    if code == 0:
        print(f"\nDone. Next, run: python -m pipeline preprocess --games {args.game}")
    return code


if __name__ == "__main__":
    sys.exit(main())
