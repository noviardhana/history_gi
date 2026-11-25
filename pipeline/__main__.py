"""
python -m pipeline  --  run the whole pipeline (or one stage) with one command.

    python -m pipeline all                     # fetch -> preprocess -> analytics -> sync
    python -m pipeline all --no-sync           # skip the Google Sheets step
    python -m pipeline fetch|preprocess|analytics|sync [--games gi,hsr]
    python -m pipeline all --dry-run           # only print what would run

Games: by default every game whose export exists in data/ (paimon-moe-local-data.json for
Genshin, starrailstation-backup_*.dat for Star Rail). Use --games gi / hsr / gi,hsr to choose.
Sync runs only if Google credentials are available (credentials/secret.toml, or the env
variables GSHEET_ID + GOOGLE_APPLICATION_CREDENTIALS), unless --sync / --no-sync is given.
A failing step stops the run; the Sheet sync is the only step that reports its failure at the end.

The numbered scripts are started as separate processes (their names start with a digit, so
they can not be imported); extra options for one script are still available by calling it directly.
"""

import argparse
import os
import subprocess
import sys

try:  # python -m pipeline
    from .config import CREDENTIALS_DIR, DATA_DIR, ROOT_DIR
except ImportError:  # python pipeline/__main__.py
    from config import CREDENTIALS_DIR, DATA_DIR, ROOT_DIR

HERE = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = {
    "fetch": {"gi": "01_fetch_gi_lookup.py", "hsr": "01_fetch_hsr_lookup.py"},
    "preprocess": {"gi": "02_preprocess_gi.py", "hsr": "02_preprocess_hsr.py"},
    "analytics": {"gi": "03_analytics_gi.py", "hsr": "03_analytics_hsr.py"},
}
STAGES_ALL = ["fetch", "preprocess", "analytics", "sync"]


def detect_games() -> list:
    games = []
    if (DATA_DIR / "paimon-moe-local-data.json").exists():
        games.append("gi")
    if list(DATA_DIR.glob("starrailstation-backup_*.dat")) or list(ROOT_DIR.glob("starrailstation-backup_*.dat")):
        games.append("hsr")
    return games


def has_sync_credentials() -> bool:
    if (CREDENTIALS_DIR / "secret.toml").exists():
        return True
    return bool(os.environ.get("GSHEET_ID") and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))


def build_commands(stage: str, games: list) -> list:
    py = sys.executable
    if stage == "sync":
        return [[py, os.path.join(HERE, "04_sync_gsheet.py"), "--games", ",".join(games)]]
    return [[py, os.path.join(HERE, SCRIPTS[stage][g])] for g in games]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline", description="Run the gacha pipeline.")
    ap.add_argument("stage", choices=STAGES_ALL + ["all"], help="stage to run, or 'all'")
    ap.add_argument("--games", default=None, help="gi, hsr or gi,hsr (default: every game with an export in data/)")
    sync = ap.add_mutually_exclusive_group()
    sync.add_argument("--sync", action="store_true", help="always run the Google Sheets step")
    sync.add_argument("--no-sync", action="store_true", help="never run the Google Sheets step")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = ap.parse_args(argv)

    games = [g.strip().lower() for g in args.games.split(",")] if args.games else detect_games()
    bad = [g for g in games if g not in ("gi", "hsr")]
    if bad:
        ap.error(f"unknown game(s): {', '.join(bad)} (use gi and/or hsr)")
    if not games:
        print("No export found. Add data/paimon-moe-local-data.json (Genshin) and/or "
              "data/starrailstation-backup_YYYY-MM-DD.dat (Star Rail), or pass --games.", file=sys.stderr)
        return 1

    stages = STAGES_ALL if args.stage == "all" else [args.stage]
    print(f"Games: {', '.join(games)} | stages: {', '.join(stages)}")

    sync_failed = False
    for stage in stages:
        if stage == "sync":
            if args.no_sync or (args.stage == "all" and not args.sync and not has_sync_credentials()):
                print("\n[skip] sync: " + ("--no-sync given" if args.no_sync else "no Google credentials found"))
                continue
        for cmd in build_commands(stage, games):
            shown = " ".join(["python"] + [os.path.relpath(c, ROOT_DIR) if os.path.isabs(c) else c for c in cmd[1:]])
            print(f"\n$ {shown}")
            if args.dry_run:
                continue
            code = subprocess.run(cmd, cwd=ROOT_DIR).returncode
            if code != 0:
                if stage == "sync":
                    sync_failed = True
                    print(f"[WARN] sync failed (exit code {code}); the other steps are done.")
                else:
                    print(f"[ERROR] {shown} failed (exit code {code}); stopping.", file=sys.stderr)
                    return code
    return 1 if sync_failed else 0


if __name__ == "__main__":
    sys.exit(main())
