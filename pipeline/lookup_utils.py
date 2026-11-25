"""
lookup_utils.py
===============
Safe download + validation helpers for the 01_fetch_*_lookup.py scripts.

The lookup files (id -> {name, rarity}) feed every later step, so a bad
download must never overwrite a good file. A new lookup is only written when:
    * it has at least `min_items` entries,
    * it has no fewer than 95% of the entries of the existing file,
    * every entry has a name and a rarity between 1 and 5.
Otherwise the existing file is kept (and the problem is reported).
Use --force on the fetch scripts to skip the checks.

The file is written to a temporary file first and swapped in atomically, so an
interrupted run can't leave half a JSON file behind.

Standard library only.
"""

import json
import os
import time
import urllib.request
from pathlib import Path

SHRINK_TOLERANCE = 0.95
RARITY_RANGE = range(1, 6)


def fetch_text(url: str, retries: int = 3, timeout: int = 30) -> str:
    last = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - network errors vary
            last = exc
            print(f"  [retry {attempt}/{retries}] {exc}")
            time.sleep(2 * attempt)
    raise ConnectionError(f"could not download {url}: {last}")


def problems_in(lookup: dict, min_items: int, previous: dict = None) -> list:
    """Return a list of human-readable problems (empty list = lookup is OK)."""
    problems = []
    if len(lookup) < min_items:
        problems.append(f"only {len(lookup)} item(s), expected at least {min_items}")
    if previous and len(lookup) < len(previous) * SHRINK_TOLERANCE:
        problems.append(f"{len(lookup)} item(s) vs {len(previous)} in the current file (shrunk by >5%)")
    no_name = [k for k, v in lookup.items() if not v.get("name")]
    no_rarity = [k for k, v in lookup.items() if v.get("rarity") not in RARITY_RANGE]
    if no_name:
        problems.append(f"{len(no_name)} item(s) without a name (e.g. {no_name[:3]})")
    if no_rarity:
        problems.append(f"{len(no_rarity)} item(s) without a valid rarity 1-5 (e.g. {no_rarity[:3]})")
    return problems


def publish_lookup(path: Path, lookup: dict, min_items: int, force: bool = False) -> str:
    """
    Validate `lookup` and write it to `path`.
    Returns "updated", "kept" (rejected, existing file stays) or "failed"
    (rejected and there is no existing file to fall back on).
    """
    previous = None
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None

    problems = [] if force else problems_in(lookup, min_items, previous)
    if problems:
        print(f"  [REJECTED] new lookup not written:")
        for p in problems:
            print(f"    - {p}")
        if previous is not None:
            print(f"  -> kept the existing {path.name} ({len(previous)} items)")
            return "kept"
        return "failed"

    if previous:
        changed = [k for k in lookup if k in previous and lookup[k].get("rarity") != previous[k].get("rarity")]
        if changed:
            print(f"  [WARN] rarity changed for {len(changed)} existing item(s) (e.g. {changed[:5]}) - check the source format.")
        print(f"  -> {len(lookup) - len(previous):+d} item(s) vs the previous file")

    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lookup, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print(f"  -> saved to {path}")
    return "updated"


def finish(results: dict) -> int:
    """Print a summary and return the process exit code (1 only if a file has no usable version)."""
    print("\nSummary: " + ", ".join(f"{name}={status}" for name, status in results.items()))
    if any(s == "failed" for s in results.values()):
        return 1
    if any(s == "kept" for s in results.values()):
        print("Some lookups were not refreshed; the existing files were kept.")
    return 0
