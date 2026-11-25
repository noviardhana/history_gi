"""
utils.py
========
Small standard-library helpers shared by every script in pipeline/
(merged from the former logsetup.py and lookup_utils.py).

1. Logging
    from utils import get_logger          # inside the package: from .utils import get_logger
    log = get_logger("preprocess")
   * Output goes to stdout, so it stays in order with the normal prints.
   * Level: env GACHA_LOG_LEVEL (DEBUG / INFO / WARNING / ERROR), default INFO.
   * In GitHub Actions, warnings and errors are written as ::warning:: / ::error::
     annotations, so they show up on the workflow summary page.

2. Lookup download + validation (used by fetch_lookup.py)
   The lookup files (id -> {name, rarity}) feed every later step, so a bad
   download must never overwrite a good file. A new lookup is only written when:
       * it has at least `min_items` entries,
       * it has no fewer than 95% of the entries of the existing file,
       * every entry has a name and a rarity between 1 and 5.
   Otherwise the existing file is kept (and the problem is reported).
   The file is written to a temporary file first and swapped in atomically.

3. UID masking helpers (887284572 -> 88xxxxx72) and env_flag.
"""

import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_configured = False


class _ConsoleHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if os.environ.get("GITHUB_ACTIONS") and record.levelno >= logging.WARNING:
                tag = "error" if record.levelno >= logging.ERROR else "warning"
                self.stream.write(f"::{tag}::{msg.replace(chr(10), '%0A')}\n")
            else:
                label = {"WARNING": "[WARN]", "ERROR": "[ERROR]", "INFO": "", "DEBUG": "[DEBUG]"}.get(record.levelname, "")
                self.stream.write(f"{label} {msg}\n" if label else f"{msg}\n")
            self.flush()
        except Exception:  # noqa: BLE001 - logging must never crash a script
            self.handleError(record)


def get_logger(name: str) -> logging.Logger:
    global _configured
    root = logging.getLogger("gacha")
    if not _configured:
        handler = _ConsoleHandler(sys.stdout)
        root.addHandler(handler)
        root.setLevel(os.environ.get("GACHA_LOG_LEVEL", "INFO").upper())
        root.propagate = False
        _configured = True
    return root.getChild(name)


log = get_logger("utils")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def mask_uid(uid, keep: int = 2) -> str:
    """887284572 -> 88xxxxx72 (first and last `keep` digits stay)."""
    u = str(uid)
    if len(u) <= keep * 2:
        return "x" * len(u)
    return u[:keep] + "x" * (len(u) - keep * 2) + u[-keep:]


def same_uid(a, b) -> bool:
    """True if a and b are the same UID, where either one may be the masked form of the other."""
    a, b = str(a), str(b)
    if a == b:
        return True
    return any(mask_uid(a, k) == b or mask_uid(b, k) == a for k in (2, 3, 4))


# ---------------------------------------------------------------------------
# Lookup download + validation
# ---------------------------------------------------------------------------
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
            log.warning(f"download attempt {attempt}/{retries} failed: {exc}")
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
        log.warning("new lookup not written:")
        for p in problems:
            log.warning(f"  - {p}")
        if previous is not None:
            log.warning(f"kept the existing {path.name} ({len(previous)} items)")
            return "kept"
        return "failed"

    if previous:
        changed = [k for k in lookup if k in previous and lookup[k].get("rarity") != previous[k].get("rarity")]
        if changed:
            log.warning(f"rarity changed for {len(changed)} existing item(s) (e.g. {changed[:5]}) - check the source format.")
        print(f"  -> {len(lookup) - len(previous):+d} item(s) vs the previous file")

    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lookup, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print(f"  -> saved to {path}")
    return "updated"


def finish(results: dict) -> int:
    """Print a summary and return the exit code (1 only if a file has no usable version)."""
    print("\nSummary: " + ", ".join(f"{name}={status}" for name, status in results.items()))
    if any(s == "failed" for s in results.values()):
        return 1
    if any(s == "kept" for s in results.values()):
        print("Some lookups were not refreshed; the existing files were kept.")
    return 0
