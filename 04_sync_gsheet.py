"""
04_sync_gsheet.py
==================
Sync the wish / warp history of both games to one Google Sheet:

    Genshin Impact   data/data_clean.csv       (01_preprocessing.py)
    Honkai: Star Rail data/data_clean_hsr.csv  (01_preprocessing_hsr.py)

Layout
------
One tab per account, named with the game prefix:
    GI - <uid>        (e.g. "GI - 887284572")      see --gi-tab-name
    HSR - <account>   (e.g. "HSR - Default")
Each tab holds one table per banner, side by side, with the columns
No. | Date | Name | Rarity | Pity | Result.
    GI : Character Event | Weapon Event | Standard
    HSR: Character Event | Light Cone Event | Collab Character Event |
         Collab Light Cone Event | Standard | Beginners
  - By default only 4* and 5* pulls are listed (--include-3star adds 3*).
  - Newest pull first. "No." is the pull's position inside its banner.
  - Above each table: pulls, 5*/4* counts and the current 5*/4* pity.
  - Result = Win / Lose / Guaranteed (50-50 outcome; "-" on Standard/Beginners).
Banners, hard pity and colours come from game_configs.py.

Safety (existing data is never deleted)
---------------------------------------
  - Tabs of accounts that are no longer in the CSV are left untouched.
  - A tab is only rewritten if the new total pull count is >= the count
    already in the sheet (cell D2). A smaller export (e.g. a fresh browser
    with partial history) is skipped with a warning; use --force to override.
  - Old GI tabs from before the prefix change (named after the account) are
    renamed to the new "GI - ..." name, not duplicated.

Usage
-----
    pip install pandas gspread
    python3 04_sync_gsheet.py --preprocess          # raw data -> CSV -> Google Sheet
    python3 04_sync_gsheet.py                       # CSV -> Google Sheet (both games)
    python3 04_sync_gsheet.py --games hsr           # only one game (gi / hsr)
    python3 04_sync_gsheet.py --dry-run             # no Google access, just a preview

Settings, in order of priority (flag > environment > file):
    credentials/secret.toml   [gsheet] spreadsheet_id  +  [gcp_service_account] (default)
    --sheet-id / GSHEET_ID                       id of the Google Sheet
    --creds    / GOOGLE_APPLICATION_CREDENTIALS  service-account key as a JSON file

Keep the service-account key out of version control (add `credentials/`
to .gitignore) and never share it: anyone with it can edit the sheet.
"""

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from game_configs import GAMES, GameConfig

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # older Python: pip install tomli
    tomllib = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_CSV = {"GI": DATA_DIR / "data_clean.csv", "HSR": DATA_DIR / "data_clean_hsr.csv"}
PREPROCESS_SCRIPT = {"GI": "01_preprocessing.py", "HSR": "01_preprocessing_hsr.py"}
DEFAULT_SECRETS = BASE_DIR / "credentials" / "secret.toml"
DEFAULT_CREDS = BASE_DIR / "credentials" / "service_account.json"

COLUMNS = ["No.", "Date", "Name", "Rarity", "Pity", "Result"]
COL_WIDTHS = [55, 130, 200, 65, 55, 100]  # pixels, per table column
TABLE_WIDTH = len(COLUMNS)
GAP = 1

# 0-based row indexes inside a tab
ROW_TITLE, ROW_META, ROW_BANNER, ROW_SUMMARY, ROW_HEADER = 0, 1, 3, 4, 5
ROW_DATA = 6
TOTAL_CELL = "D2"  # holds the account's total pulls (used by the safety check)

NAVY, GREY, LINE = "#1e1e42", "#6b6b86", "#e3e3e8"


def n_cols(cfg: GameConfig) -> int:
    n = len(cfg.sheet_banners)
    return n * TABLE_WIDTH + (n - 1) * GAP


# ----------------------------------------------------------------------------
# Data shaping (pure functions, no Google access)
# ----------------------------------------------------------------------------
def load_clean(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df[df["datetime"].notna()].copy()
    for col in ("uid", "win_50_50"):
        if col not in df.columns:
            df[col] = np.nan
    sort_cols = ["datetime", "pull_number"] if "pull_number" in df.columns else ["datetime"]
    return df.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)


def account_order(df: pd.DataFrame) -> list:
    """Main account first (name contains 'main', else most pulls), rest A-Z."""
    counts = df["account"].value_counts()
    mains = [a for a in counts.index if "main" in str(a).lower()]
    main = mains[0] if mains else counts.idxmax()
    return [main] + sorted(a for a in df["account"].unique() if a != main)


def current_pity(banner_df: pd.DataFrame, star: int):
    """Pulls since the last pull of this rarity (4* and 5* counters are independent)."""
    if banner_df.empty:
        return None
    pos = np.flatnonzero((banner_df["rarity"] == star).to_numpy())
    return len(banner_df) if len(pos) == 0 else len(banner_df) - int(pos[-1]) - 1


def _num(x):
    return "" if pd.isna(x) else int(x)


def uid_of(acc_df: pd.DataFrame):
    return acc_df["uid"].dropna().iloc[0] if acc_df["uid"].notna().any() else ""


def banner_table(cfg: GameConfig, acc_df: pd.DataFrame, banner: str, include_3star: bool):
    """Return (summary_text, data_rows) for one banner of one account."""
    b = acc_df[acc_df["banner_type"] == banner].reset_index(drop=True)
    b["no"] = np.arange(1, len(b) + 1)
    hard5 = cfg.hard_pity.get(banner, cfg.default_hard_pity)
    hard4 = cfg.hard_pity_4

    p5, p4 = current_pity(b, 5), current_pity(b, 4)
    summary = (
        f"Pulls {len(b):,} · 5★ {int((b['rarity'] == 5).sum())} · 4★ {int((b['rarity'] == 4).sum())}"
        f" · Pity 5★ {p5 if p5 is not None else '-'}/{hard5} · 4★ {p4 if p4 is not None else '-'}/{hard4}"
    )

    shown = b if include_3star else b[b["rarity"] >= 4]
    rows = []
    for r in shown.sort_values("no", ascending=False).itertuples(index=False):
        rarity = "" if pd.isna(r.rarity) else f"{int(r.rarity)}★"
        result = r.win_50_50 if isinstance(r.win_50_50, str) and r.win_50_50 else "-"
        rows.append([int(r.no), r.datetime.strftime("%Y-%m-%d %H:%M"), str(r.item_name), rarity, _num(r.pity), result])
    return summary, rows


def build_account_grid(cfg: GameConfig, acc_df: pd.DataFrame, label: str, synced_at: str, include_3star: bool = False):
    """Return (grid, table_row_counts). grid is a list of equal-length rows."""
    tables = [banner_table(cfg, acc_df, name, include_3star) for name in cfg.sheet_banners]
    n_data = max((len(rows) for _, rows in tables), default=0)
    width = n_cols(cfg)
    grid = [[""] * width for _ in range(ROW_DATA + n_data)]

    uid = uid_of(acc_df)
    grid[ROW_TITLE][0] = f"👤 {cfg.sheet_prefix} · {label}"
    if cfg.key == "GI":
        meta_label, meta_value = "UID", str(uid)
    else:  # StarRailStation backups carry no game UID; show the profile key instead
        key = acc_df["profile_key"].dropna().iloc[0] if "profile_key" in acc_df and acc_df["profile_key"].notna().any() else ""
        meta_label, meta_value = "Profile", str(int(key)) if key != "" else ""
    grid[ROW_META][0:6] = [meta_label, meta_value, "Total pulls", len(acc_df), "Last sync", synced_at]

    for t, (name, (summary, rows)) in enumerate(zip(cfg.sheet_banners, tables)):
        icon = cfg.sheet_banner_style.get(name, ("", ""))[0]
        c0 = t * (TABLE_WIDTH + GAP)
        grid[ROW_BANNER][c0] = f"{icon} {name}".strip()
        grid[ROW_SUMMARY][c0] = summary
        grid[ROW_HEADER][c0:c0 + TABLE_WIDTH] = COLUMNS
        for i, row in enumerate(rows):
            grid[ROW_DATA + i][c0:c0 + TABLE_WIDTH] = row
    return grid, [len(rows) for _, rows in tables]


# ----------------------------------------------------------------------------
# Formatting requests (Sheets API batchUpdate)
# ----------------------------------------------------------------------------
def rgb(hex_color: str) -> dict:
    h = hex_color.lstrip("#")
    return {k: int(h[i:i + 2], 16) / 255 for k, i in (("red", 0), ("green", 2), ("blue", 4))}


def col_letter(idx: int) -> str:
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _rng(sid, r0, r1, c0, c1):
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _repeat(sid, r0, r1, c0, c1, fmt):
    return {
        "repeatCell": {
            "range": _rng(sid, r0, r1, c0, c1),
            "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(" + ",".join(fmt) + ")",
        }
    }


def build_format_requests(cfg: GameConfig, sid: int, n_rows: int, n_existing_rules: int = 0) -> list:
    n_data = max(n_rows - ROW_DATA, 0)
    end = ROW_DATA + n_data
    reqs = [{"deleteConditionalFormatRule": {"sheetId": sid, "index": 0}} for _ in range(n_existing_rules)]
    reqs.append(
        {"repeatCell": {"range": {"sheetId": sid}, "cell": {"userEnteredFormat": {}}, "fields": "userEnteredFormat"}}
    )
    reqs.append(
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": ROW_DATA, "hideGridlines": True}},
                "fields": "gridProperties.frozenRowCount,gridProperties.hideGridlines",
            }
        }
    )
    reqs.append(_repeat(sid, ROW_TITLE, ROW_TITLE + 1, 0, 1, {"textFormat": {"bold": True, "fontSize": 16}}))
    reqs.append(_repeat(sid, ROW_META, ROW_META + 1, 0, 6, {"textFormat": {"foregroundColor": rgb(GREY)}, "horizontalAlignment": "LEFT"}))
    for c in (1, 3, 5):
        reqs.append(_repeat(sid, ROW_META, ROW_META + 1, c, c + 1, {"textFormat": {"bold": True, "foregroundColor": rgb("#222222")}, "horizontalAlignment": "LEFT"}))

    rules = []
    for t, name in enumerate(cfg.sheet_banners):
        color = cfg.sheet_banner_style.get(name, ("", "#eeeeee"))[1]
        c0 = t * (TABLE_WIDTH + GAP)
        c1 = c0 + TABLE_WIDTH
        reqs.append(_repeat(sid, ROW_BANNER, ROW_BANNER + 1, c0, c1, {"backgroundColor": rgb(color), "textFormat": {"bold": True, "fontSize": 12}}))
        reqs.append(_repeat(sid, ROW_SUMMARY, ROW_SUMMARY + 1, c0, c1, {"textFormat": {"italic": True, "foregroundColor": rgb(GREY)}}))
        reqs.append(_repeat(sid, ROW_HEADER, ROW_HEADER + 1, c0, c1, {
            "backgroundColor": rgb(NAVY), "textFormat": {"bold": True, "foregroundColor": rgb("#ffffff")}, "horizontalAlignment": "CENTER"}))
        if n_data:
            for off in (0, 3, 4, 5):  # No., Rarity, Pity, Result centred
                reqs.append(_repeat(sid, ROW_DATA, end, c0 + off, c0 + off + 1, {"horizontalAlignment": "CENTER"}))
            reqs.append({"updateBorders": {"range": _rng(sid, ROW_DATA, end, c0, c1),
                                           "innerHorizontal": {"style": "SOLID", "color": rgb(LINE)},
                                           "bottom": {"style": "SOLID", "color": rgb(LINE)}}})
            res = _rng(sid, ROW_DATA, end, c0 + 5, c0 + 6)
            for text, bg, fg in (("Win", "#cfeccf", "#1b6b2b"), ("Lose", "#f7d0d3", "#a3212e"), ("Guaranteed", "#c9ece6", "#1c6b61")):
                rules.append((res, {"type": "TEXT_EQ", "values": [{"userEnteredValue": text}]},
                              {"backgroundColor": rgb(bg), "textFormat": {"foregroundColor": rgb(fg), "bold": True}}))
            rar = col_letter(c0 + 3)
            rules.append((_rng(sid, ROW_DATA, end, c0, c1),
                          {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f'=${rar}{ROW_DATA + 1}="5★"'}]},
                          {"backgroundColor": rgb("#fff3d6")}))
        for off, w in enumerate(COL_WIDTHS):
            reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c0 + off, "endIndex": c0 + off + 1},
                                                       "properties": {"pixelSize": w}, "fields": "pixelSize"}})
        if t < len(cfg.sheet_banners) - 1:
            reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c1, "endIndex": c1 + GAP},
                                                       "properties": {"pixelSize": 24}, "fields": "pixelSize"}})
    for i, (rng, cond, fmt) in enumerate(rules):
        reqs.append({"addConditionalFormatRule": {"index": i, "rule": {"ranges": [rng], "booleanRule": {"condition": cond, "format": fmt}}}})
    return reqs


# ----------------------------------------------------------------------------
# Google Sheets sync
# ----------------------------------------------------------------------------
def clean_name(text) -> str:
    return re.sub(r"[\[\]\*\?:/\\]", "-", str(text)).strip()


def tab_title(cfg: GameConfig, acc, uid, used: set, gi_tab_name: str = "uid") -> str:
    """'GI - <uid>' (or 'GI - <account>') and 'HSR - <account>'."""
    if cfg.key == "GI" and gi_tab_name == "uid" and str(uid):
        suffix = str(int(uid)) if isinstance(uid, (int, float, np.integer, np.floating)) else str(uid)
    else:
        suffix = clean_name(acc) or "account"
    title = f"{cfg.sheet_prefix} - {suffix}"[:95]
    if title in used:
        title = f"{title} ({clean_name(acc)})"[:99]
    used.add(title)
    return title


def legacy_titles(acc, uid) -> list:
    """Names GI tabs had before the prefix change (account label, or 'label (uid)')."""
    base = clean_name(acc)[:90] or "account"
    return [base, f"{base} ({uid})"]


def existing_total(ws):
    try:
        raw = ws.acell(TOTAL_CELL).value
        return int(str(raw).replace(",", "").replace(".", "")) if raw else None
    except Exception:
        return None


def sync(frames, sh, include_3star=False, force=False, gi_tab_name="uid"):
    """frames: list of (GameConfig, DataFrame). Returns the number of tabs written."""
    synced_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    existing = {ws.title: ws for ws in sh.worksheets()}
    try:
        meta = sh.fetch_sheet_metadata({"fields": "sheets(properties.sheetId,conditionalFormats)"})
        rule_counts = {s["properties"]["sheetId"]: len(s.get("conditionalFormats", [])) for s in meta.get("sheets", [])}
    except Exception:
        rule_counts = {}

    used, written, pos = set(), 0, 0
    for cfg, df in frames:
        for acc in account_order(df):
            acc_df = df[df["account"] == acc]
            uid = uid_of(acc_df)
            title = tab_title(cfg, acc, uid, used, gi_tab_name)
            grid, _ = build_account_grid(cfg, acc_df, str(acc), synced_at, include_3star)
            width = n_cols(cfg)

            ws = existing.get(title)
            if ws is None and cfg.key == "GI":
                # migrate a tab created before the "GI - ..." naming instead of making a duplicate
                for old in legacy_titles(acc, uid):
                    if old in existing and old not in used:
                        ws = existing.pop(old)
                        ws.update_title(title)
                        existing[title] = ws
                        print(f"[RENAME] '{old}' -> '{title}'")
                        break

            if ws is not None:
                old_total = existing_total(ws)
                if old_total is not None and len(acc_df) < old_total and not force:
                    msg = (f"'{title}': new data has {len(acc_df):,} pulls but the sheet already has {old_total:,}. "
                           f"Nothing was changed (use --force to overwrite).")
                    print(f"[SKIP] {msg}")
                    if os.environ.get("GITHUB_ACTIONS"):
                        print(f"::warning::Google Sheets sync skipped {msg}")
                    pos += 1
                    continue
            else:
                ws = sh.add_worksheet(title=title, rows=max(len(grid) + 5, 50), cols=width, index=pos)

            ws.clear()
            ws.resize(rows=max(len(grid) + 5, 50), cols=width)
            ws.update(values=grid, range_name="A1")
            sh.batch_update({"requests": build_format_requests(cfg, ws.id, len(grid), rule_counts.get(ws.id, 0))})
            print(f"[OK]   '{title}': {len(acc_df):,} pulls synced")
            written += 1
            pos += 1
            time.sleep(1.5)  # stay well below the API rate limit

    # remove the empty default tab of a brand-new spreadsheet
    if written:
        for ws in sh.worksheets():
            if ws.title in ("Sheet1", "Sheet 1", "Lembar1") and ws.title not in used:
                try:
                    if not ws.get_all_values():
                        sh.del_worksheet(ws)
                except Exception:
                    pass
    return written


# ----------------------------------------------------------------------------
def load_secrets(path: Path) -> dict:
    """Read credentials/secret.toml (returns {} if the file does not exist)."""
    if not path.exists():
        return {}
    if tomllib is None:
        try:
            import tomli as tomllib_  # type: ignore
        except ModuleNotFoundError:
            sys.exit("Reading secret.toml needs Python 3.11+ or `pip install tomli`.")
        return tomllib_.loads(path.read_text(encoding="utf-8"))
    return tomllib.loads(path.read_text(encoding="utf-8"))


def check_service_account(info: dict):
    missing = [k for k in ("client_email", "private_key", "token_uri") if not info.get(k)]
    if missing:
        sys.exit(f"secret.toml [gcp_service_account] is missing: {', '.join(missing)}")
    if "BEGIN PRIVATE KEY" not in info["private_key"]:
        sys.exit("secret.toml: private_key is not a real key yet (it should start with "
                 "-----BEGIN PRIVATE KEY-----). Paste the value from the service-account JSON file.")


def parse_args():
    p = argparse.ArgumentParser(description="Sync Genshin Impact and Honkai: Star Rail pull history to Google Sheets.")
    p.add_argument("--csv", "--gi-csv", dest="gi_csv", default=str(DEFAULT_CSV["GI"]), help="Genshin data_clean.csv")
    p.add_argument("--hsr-csv", default=str(DEFAULT_CSV["HSR"]), help="Honkai: Star Rail data_clean_hsr.csv")
    p.add_argument("--games", default="gi,hsr", help="Comma-separated games to sync: gi, hsr (default: both)")
    p.add_argument("--gi-tab-name", choices=["uid", "account"], default="uid",
                   help="Genshin tab name: 'GI - <uid>' (default) or 'GI - <account>'")
    p.add_argument("--sheet-id", default=os.environ.get("GSHEET_ID"), help="Google Sheet id (or env GSHEET_ID)")
    p.add_argument("--secrets", default=str(DEFAULT_SECRETS), help="Path to secret.toml")
    p.add_argument("--creds", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
                   help="Service-account JSON key (alternative to secret.toml)")
    p.add_argument("--preprocess", action="store_true", help="Run the 01_preprocessing script of each selected game first")
    p.add_argument("--include-3star", action="store_true", help="Also list 3* pulls")
    p.add_argument("--force", action="store_true", help="Overwrite tabs even if the new data has fewer pulls")
    p.add_argument("--dry-run", action="store_true", help="Build tables and print a preview; no Google access")
    return p.parse_args()


def main():
    args = parse_args()
    selected = [g.strip().upper() for g in args.games.split(",") if g.strip()]
    unknown = [g for g in selected if g not in GAMES]
    if unknown:
        sys.exit(f"Unknown game(s): {', '.join(unknown)}. Use gi and/or hsr.")
    csv_paths = {"GI": Path(args.gi_csv), "HSR": Path(args.hsr_csv)}

    if args.preprocess:
        for key in selected:
            print(f"Running {PREPROCESS_SCRIPT[key]} ...")
            subprocess.run([sys.executable, str(BASE_DIR / PREPROCESS_SCRIPT[key])], check=True)

    frames = []
    for key in selected:
        path = csv_paths[key]
        if not path.exists():
            print(f"[WARN] {GAMES[key].title}: {path} not found, skipped "
                  f"(run {PREPROCESS_SCRIPT[key]} or use --preprocess).")
            continue
        frames.append((GAMES[key], load_clean(path)))
    if not frames:
        sys.exit("No data to sync: none of the selected CSV files exist.")

    if args.dry_run:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        used = set()
        for cfg, df in frames:
            for acc in account_order(df):
                acc_df = df[df["account"] == acc]
                title = tab_title(cfg, acc, uid_of(acc_df), used, args.gi_tab_name)
                grid, counts = build_account_grid(cfg, acc_df, str(acc), stamp, args.include_3star)
                print(f"\n=== Tab '{title}' ({len(acc_df):,} pulls, {n_cols(cfg)} columns) ===")
                for t, (name, n) in enumerate(zip(cfg.sheet_banners, counts)):
                    print(f"  {name}: {n:,} rows | {grid[ROW_SUMMARY][t * (TABLE_WIDTH + GAP)]}")
                for row in grid[ROW_HEADER:ROW_HEADER + 4]:
                    print("   ", row[:6])
        return

    secrets = load_secrets(Path(args.secrets))
    sheet_id = args.sheet_id or secrets.get("gsheet", {}).get("spreadsheet_id")
    if not sheet_id:
        sys.exit("No Google Sheet id. Set [gsheet] spreadsheet_id in credentials/secret.toml, "
                 "or pass --sheet-id / set GSHEET_ID.")

    import gspread  # imported here so --dry-run works without it

    if args.creds:
        if not Path(args.creds).exists():
            sys.exit(f"Service-account key not found: {args.creds}")
        client = gspread.service_account(filename=args.creds)
    elif secrets.get("gcp_service_account"):
        info = dict(secrets["gcp_service_account"])
        check_service_account(info)
        client = gspread.service_account_from_dict(info)
    elif DEFAULT_CREDS.exists():
        client = gspread.service_account(filename=str(DEFAULT_CREDS))
    else:
        sys.exit(f"No credentials found. Fill in {args.secrets} (see [gcp_service_account]).")

    sh = client.open_by_key(sheet_id)
    n = sync(frames, sh, include_3star=args.include_3star, force=args.force, gi_tab_name=args.gi_tab_name)
    print(f"\nDone. {n} tab(s) updated: {sh.url}")


if __name__ == "__main__":
    main()
