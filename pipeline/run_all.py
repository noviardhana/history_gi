"""
run_all.py
==========
One command for the whole pipeline:

    tests -> 01 fetch lookup -> 02 preprocess -> 03 analytics -> 04 sync (optional)

The numbered scripts (01_..., 02_...) cannot be imported as modules because their
names start with a digit, so each step is started as its own process, the same way
`04_sync_gsheet.py --preprocess` already does it.

Each game runs only if its export exists in data/ (Genshin: paimon-moe-local-data.json,
Star Rail: starrailstation-backup_*.dat). Execution stops at the first failing step.

Usage (from the project root):
    python3 pipeline/run_all.py                    # tests + both games, no Google Sheets
    python3 pipeline/run_all.py --games hsr        # one game (gi / hsr)
    python3 pipeline/run_all.py --sync             # ... and sync the Google Sheet
    python3 pipeline/run_all.py --skip-tests       # skip pytest
    python3 pipeline/run_all.py --skip-fetch       # reuse existing lookup files (offline)
    python3 pipeline/run_all.py --steps preprocess,analytics   # only these steps (used by CI)
    python3 pipeline/run_all.py --mask-uid         # hide the Genshin UID in the CSV
    python3 pipeline/run_all.py --dry-run          # print the steps only
"""

import argparse
import subprocess
import sys
import time

from config import DATA_DIR, GAMES, ROOT_DIR

PIPELINE_DIR = ROOT_DIR / "pipeline"

STEPS = {
    "GI": {"fetch": "01_fetch_gi_lookup.py", "preprocess": "02_preprocess_gi.py", "analytics": "03_analytics_gi.py"},
    "HSR": {"fetch": "01_fetch_hsr_lookup.py", "preprocess": "02_preprocess_hsr.py", "analytics": "03_analytics_hsr.py"},
}


def has_export(key: str) -> bool:
    if key == "GI":
        return (DATA_DIR / "paimon-moe-local-data.json").exists()
    return any(DATA_DIR.glob("starrailstation-backup_*.dat")) or any(ROOT_DIR.glob("starrailstation-backup_*.dat"))


ALL_STEPS = ("tests", "fetch", "preprocess", "analytics", "sync")
DEFAULT_STEPS = ("tests", "fetch", "preprocess", "analytics")  # sync needs credentials, so it is opt-in


def build_plan(games, steps=DEFAULT_STEPS, mask_uid=False):
    """Return the ordered list of (label, argv) steps. Pure function, easy to test.
    The order is always tests -> fetch -> preprocess -> analytics -> sync, whatever order `steps` is given in."""
    unknown = [x for x in steps if x not in ALL_STEPS]
    if unknown:
        raise ValueError(f"Unknown step(s): {', '.join(unknown)}. Choose from: {', '.join(ALL_STEPS)}")
    plan = []
    if "tests" in steps:
        plan.append(("tests", [sys.executable, "-m", "pytest", "-q", str(ROOT_DIR / "tests")]))
    for stage in ("fetch", "preprocess", "analytics"):
        if stage not in steps:
            continue
        for key in games:
            argv = [sys.executable, str(PIPELINE_DIR / STEPS[key][stage])]
            if stage == "preprocess" and mask_uid and key == "GI":
                argv.append("--mask-uid")
            plan.append((f"{key} {stage}", argv))
    if "sync" in steps and games:
        # CSVs are built by the steps above (or already exist), so the sync must not run preprocess again
        plan.append(("sync Google Sheet", [sys.executable, str(PIPELINE_DIR / "04_sync_gsheet.py"),
                                            "--games", ",".join(g.lower() for g in games)]))
    return plan


def resolve_steps(steps_arg, sync, skip_tests, skip_fetch, skip_analytics):
    if steps_arg:
        steps = [x.strip() for x in steps_arg.split(",") if x.strip()]
    else:
        steps = list(DEFAULT_STEPS)
        if sync:
            steps.append("sync")
    skipped = {"tests": skip_tests, "fetch": skip_fetch, "analytics": skip_analytics}
    return tuple(x for x in steps if not skipped.get(x))


def parse_args():
    p = argparse.ArgumentParser(description="Run the whole gacha pipeline with one command.")
    p.add_argument("--games", default="gi,hsr", help="Comma-separated games: gi, hsr (default: both)")
    p.add_argument("--steps", default=None,
                   help=f"Comma-separated steps to run (default: {','.join(DEFAULT_STEPS)}). Choose from: {','.join(ALL_STEPS)}")
    p.add_argument("--sync", action="store_true", help="Add the Google Sheet sync (needs credentials)")
    p.add_argument("--skip-tests", action="store_true", help="Do not run pytest first")
    p.add_argument("--skip-fetch", action="store_true", help="Do not refresh the lookup files")
    p.add_argument("--skip-analytics", action="store_true", help="Do not render the PNG/CSV reports")
    p.add_argument("--mask-uid", action="store_true", help="Mask the Genshin UID in data_clean_gi.csv")
    p.add_argument("--dry-run", action="store_true", help="Print the steps without running them")
    return p.parse_args()


def main():
    args = parse_args()
    requested = [g.strip().upper() for g in args.games.split(",") if g.strip()]
    unknown = [g for g in requested if g not in GAMES]
    if unknown:
        sys.exit(f"Unknown game(s): {', '.join(unknown)}. Use gi and/or hsr.")

    games = []
    for key in requested:
        if has_export(key):
            games.append(key)
        else:
            print(f"[SKIP] {GAMES[key].title}: no export found in {DATA_DIR}")
    if not games:
        sys.exit("No export found for any selected game. Put the Paimon.moe / StarRailStation export in data/.")

    try:
        steps = resolve_steps(args.steps, args.sync, args.skip_tests, args.skip_fetch, args.skip_analytics)
        plan = build_plan(games, steps, args.mask_uid)
    except ValueError as exc:
        sys.exit(str(exc))
    for i, (label, argv) in enumerate(plan, 1):
        print(f"\n=== [{i}/{len(plan)}] {label} ===")
        print("$ " + " ".join(argv))
        if args.dry_run:
            continue
        t0 = time.time()
        result = subprocess.run(argv, cwd=ROOT_DIR)
        if result.returncode != 0:
            sys.exit(f"\n[FAIL] step '{label}' exited with code {result.returncode}. Stopped.")
        print(f"[OK] {label} ({time.time() - t0:.1f}s)")
    print("\nAll steps finished." if not args.dry_run else "\nDry run only, nothing was executed.")


if __name__ == "__main__":
    main()
