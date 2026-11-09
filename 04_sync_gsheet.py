"""
04_sync_gsheet.py
==================
Sync the Paimon.moe wish history (data/data_clean.csv, produced by
01_preprocessing.py) to a Google Sheet.

Layout
------
One tab per account. Each tab holds three tables side by side:
    Character Event | Weapon Event | Standard
with the columns  No. | Date | Name | Rarity | Pity | Result.
  - By default only 4* and 5* pulls are listed (--include-3star adds 3*).
  - Newest pull first. "No." is the pull's position inside its banner.
  - Above each table: pulls, 5*/4* counts and the current 5*/4* pity.
  - Result = Win / Lose / Guaranteed (50-50 outcome; "-" on Standard).

Safety (existing data is never deleted)
---------------------------------------
  - Tabs of accounts that are no longer in the CSV are left untouched.
  - A tab is only rewritten if the new total pull count is >= the count
    already in the sheet (cell D2). A smaller export (e.g. a fresh browser
    with partial history) is skipped with a warning; use --force to override.

Usage
-----
    pip install pandas gspread
    python3 04_sync_gsheet.py --preprocess          # JSON -> CSV -> Google Sheet
    python3 04_sync_gsheet.py                       # CSV -> Google Sheet
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

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # older Python: pip install tomli
    tomllib = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_CSV = DATA_DIR / "data_clean.csv"
DEFAULT_SECRETS = BASE_DIR / "credentials" / "secret.toml"
DEFAULT_CREDS = BASE_DIR / "credentials" / "service_account.json"

# (banner name, icon, title colour, hard pity 5*, hard pity 4*)
BANNERS = [
    ("Character Event", "🎯", "#fde7c2", 90, 10),
    ("Weapon Event", "⚔️", "#d6e4f7", 80, 10),
    ("Standard", "🌌", "#d5efd9", 90, 10),
]
COLUMNS = ["No.", "Date", "Name", "Rarity", "Pity", "Result"]
COL_WIDTHS = [55, 130, 200, 65, 55, 100]  # pixels, per table column
TABLE_WIDTH = len(COLUMNS)
GAP = 1
N_COLS = len(BANNERS) * TABLE_WIDTH + (len(BANNERS) - 1) * GAP

# 0-based row indexes inside a tab
ROW_TITLE, ROW_META, ROW_BANNER, ROW_SUMMARY, ROW_HEADER = 0, 1, 3, 4, 5
ROW_DATA = 6
TOTAL_CELL = "D2"  # holds the account's total pulls (used by the safety check)

NAVY, GREY, LINE = "#1e1e42", "#6b6b86", "#e3e3e8"


# ----------------------------------------------------------------------------
# Data shaping (pure functions, no Google access)
# ----------------------------------------------------------------------------
def load_clean(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df[df["datetime"].notna()].copy()
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


def banner_table(acc_df: pd.DataFrame, banner: str, include_3star: bool):
    """Return (summary_text, data_rows) for one banner of one account."""
    b = acc_df[acc_df["banner_type"] == banner].reset_index(drop=True)
    b["no"] = np.arange(1, len(b) + 1)
    hard5, hard4 = next((h5, h4) for n, _, _, h5, h4 in BANNERS if n == banner)

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


def build_account_grid(acc_df: pd.DataFrame, label: str, synced_at: str, include_3star: bool = False):
    """Return (grid, table_row_counts). grid is a list of equal-length rows."""
    tables = [banner_table(acc_df, name, include_3star) for name, *_ in BANNERS]
    n_data = max((len(rows) for _, rows in tables), default=0)
    grid = [[""] * N_COLS for _ in range(ROW_DATA + n_data)]

    uid = acc_df["uid"].dropna().iloc[0] if acc_df["uid"].notna().any() else ""
    grid[ROW_TITLE][0] = f"👤 {label}"
    grid[ROW_META][0:6] = ["UID", str(uid), "Total pulls", len(acc_df), "Last sync", synced_at]

    for t, ((name, icon, *_), (summary, rows)) in enumerate(zip(BANNERS, tables)):
        c0 = t * (TABLE_WIDTH + GAP)
        grid[ROW_BANNER][c0] = f"{icon} {name}"
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


def build_format_requests(sid: int, n_rows: int, n_existing_rules: int = 0) -> list:
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
    for t, (name, _, color, *_rest) in enumerate(BANNERS):
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
        if t < len(BANNERS) - 1:
            reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c1, "endIndex": c1 + GAP},
                                                       "properties": {"pixelSize": 24}, "fields": "pixelSize"}})
    for i, (rng, cond, fmt) in enumerate(rules):
        reqs.append({"addConditionalFormatRule": {"index": i, "rule": {"ranges": [rng], "booleanRule": {"condition": cond, "format": fmt}}}})
    return reqs


# ----------------------------------------------------------------------------
# Google Sheets sync
# ----------------------------------------------------------------------------
def safe_title(label: str, uid, used: set) -> str:
    title = re.sub(r"[\[\]\*\?:/\\]", "-", str(label)).strip()[:90] or "account"
    if title in used:
        title = f"{title} ({uid})"
    used.add(title)
    return title


def existing_total(ws):
    try:
        raw = ws.acell(TOTAL_CELL).value
        return int(str(raw).replace(",", "").replace(".", "")) if raw else None
    except Exception:
        return None


def sync(df, sh, include_3star=False, force=False):
    synced_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    existing = {ws.title: ws for ws in sh.worksheets()}
    try:
        meta = sh.fetch_sheet_metadata({"fields": "sheets(properties.sheetId,conditionalFormats)"})
        rule_counts = {s["properties"]["sheetId"]: len(s.get("conditionalFormats", [])) for s in meta.get("sheets", [])}
    except Exception:
        rule_counts = {}

    used, written = set(), 0
    for pos, acc in enumerate(account_order(df)):
        acc_df = df[df["account"] == acc]
        uid = acc_df["uid"].dropna().iloc[0] if acc_df["uid"].notna().any() else ""
        title = safe_title(acc, uid, used)
        grid, _ = build_account_grid(acc_df, str(acc), synced_at, include_3star)

        ws = existing.get(title)
        if ws is not None:
            old = existing_total(ws)
            if old is not None and len(acc_df) < old and not force:
                msg = (f"'{title}': new data has {len(acc_df):,} pulls but the sheet already has {old:,}. "
                       f"Nothing was changed (use --force to overwrite).")
                print(f"[SKIP] {msg}")
                if os.environ.get("GITHUB_ACTIONS"):
                    print(f"::warning::Google Sheets sync skipped {msg}")
                continue
        else:
            ws = sh.add_worksheet(title=title, rows=max(len(grid) + 5, 50), cols=N_COLS, index=pos)

        ws.clear()
        ws.resize(rows=max(len(grid) + 5, 50), cols=N_COLS)
        ws.update(values=grid, range_name="A1")
        sh.batch_update({"requests": build_format_requests(ws.id, len(grid), rule_counts.get(ws.id, 0))})
        print(f"[OK]   '{title}': {len(acc_df):,} pulls synced")
        written += 1
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
    p = argparse.ArgumentParser(description="Sync Paimon.moe wish history to Google Sheets.")
    p.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to data_clean.csv")
    p.add_argument("--sheet-id", default=os.environ.get("GSHEET_ID"), help="Google Sheet id (or env GSHEET_ID)")
    p.add_argument("--secrets", default=str(DEFAULT_SECRETS), help="Path to secret.toml")
    p.add_argument("--creds", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
                   help="Service-account JSON key (alternative to secret.toml)")
    p.add_argument("--preprocess", action="store_true", help="Run 01_preprocessing.py first")
    p.add_argument("--include-3star", action="store_true", help="Also list 3* pulls")
    p.add_argument("--force", action="store_true", help="Overwrite tabs even if the new data has fewer pulls")
    p.add_argument("--dry-run", action="store_true", help="Build tables and print a preview; no Google access")
    return p.parse_args()


def main():
    args = parse_args()

    if args.preprocess:
        print("Running 01_preprocessing.py ...")
        subprocess.run([sys.executable, str(BASE_DIR / "01_preprocessing.py")], check=True)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        sys.exit(f"File not found: {csv_path}. Run 01_preprocessing.py first (or use --preprocess).")
    df = load_clean(csv_path)

    if args.dry_run:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        for acc in account_order(df):
            grid, counts = build_account_grid(df[df["account"] == acc], str(acc), stamp, args.include_3star)
            print(f"\n=== Tab '{acc}' ({len(df[df['account'] == acc]):,} pulls) ===")
            for name, n, cell in zip([b[0] for b in BANNERS], counts, (grid[ROW_SUMMARY][0], grid[ROW_SUMMARY][7], grid[ROW_SUMMARY][14])):
                print(f"  {name}: {n:,} rows | {cell}")
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
    n = sync(df, sh, include_3star=args.include_3star, force=args.force)
    print(f"\nDone. {n} tab(s) updated: {sh.url}")


if __name__ == "__main__":
    main()