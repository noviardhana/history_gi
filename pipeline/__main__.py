"""
python -m pipeline  --  run the whole pipeline (or one stage) with one command.

    python -m pipeline all                     # fetch -> preprocess -> analytics -> sync
    python -m pipeline all --no-sync           # skip the Google Sheets step
    python -m pipeline fetch|preprocess|analytics|sync [--games gi,hsr]
    python -m pipeline all --dry-run           # only print what would run

Games: by default every game whose export exists in data/ (paimon-moe-local-data.json for
Genshin, starrailstation-backup_*.dat for Star Rail). Use --games gi / hsr / gi,hsr to choose.
Sync runs only if Google credentials are available (credentials/secret.toml, or the env
variables GSHEET_ID + GOOGLE_APPLICATION_CREDENTIALS / GCP_SERVICE_ACCOUNT_JSON), unless
--sync / --no-sync is given.
A failing step stops the run; the Sheet sync is the only step that reports its failure at the end.

Every stage is a module of this package (fetch_lookup, preprocess, analytics_core,
sync_gsheet) and is called in the same process. Extra options for one stage are still
available by running that module directly, e.g. `python pipeline/preprocess.py --game gi --uid ...`.
"""

import argparse
import importlib
import os
import sys

if __package__:  # python -m pipeline
    from .config import CREDENTIALS_DIR, DATA_DIR, ROOT_DIR
else:  # python pipeline/__main__.py
    from config import CREDENTIALS_DIR, DATA_DIR, ROOT_DIR

# stage -> module that provides main(argv) -> int
STAGE_MODULE = {
    "fetch": "fetch_lookup",
    "preprocess": "preprocess",
    "analytics": "analytics_core",
    "sync": "sync_gsheet",
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
    has_sheet = bool(os.environ.get("GSHEET_ID"))
    has_key = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get("GCP_SERVICE_ACCOUNT_JSON"))
    return has_sheet and has_key


def build_calls(stage: str, games: list) -> list:
    """[(shown command, module argv)] for one stage."""
    if stage == "sync":
        return [(f"python -m pipeline sync --games {','.join(games)}", ["--games", ",".join(games)])]
    return [(f"python -m pipeline {stage} --game {g}", ["--game", g]) for g in games]


def run_stage(stage: str, argv: list) -> int:
    module = STAGE_MODULE[stage]
    mod = importlib.import_module(f"{__package__}.{module}" if __package__ else module)
    try:
        code = mod.main(argv)
    except SystemExit as exc:  # sys.exit("message") inside a stage
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            return 1
        return exc.code or 0
    except Exception as exc:  # noqa: BLE001 - report like a failed step, not a traceback
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return code or 0


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
        for shown, call_argv in build_calls(stage, games):
            print(f"\n$ {shown}")
            if args.dry_run:
                continue
            code = run_stage(stage, call_argv)
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
