# Genshin Impact Gacha Analytics

A data pipeline that turns Genshin Impact wish (gacha) history — exported from [Paimon.moe](https://paimon.moe) — into analytics and an interactive dashboard.

**Live demo:** [history-gi-noviardhana.streamlit.app](https://history-gi-noviardhana.streamlit.app/)

## Overview

```
Paimon.moe export (JSON)
        │
        ▼
00_fetch_rarity_lookup.py   fetch item name/rarity lookup
        │
        ▼
01_preprocessing.py         merge export + lookup into data_clean.csv
        │
        ▼
02_analytics.py             generate insights (CSV + PNG)
        │
        ▼
03_dashboard.py             interactive Streamlit dashboard

data_clean.csv ──► 04_sync_gsheet.py   (optional) Google Sheets, one tab per account
```

## Features

- Total pulls and account progress by rarity, Adventure Rank, and World Level
- Monthly wish timeline by banner
- 5★ pity distribution per banner
- 50/50 win rate breakdown
- Top characters and weapons obtained
- Banner performance comparison (pulls-per-5★, win rate)
- Composite luck score (60% pity efficiency + 40% win rate)
- Latest 10 5★ characters/weapons obtained per banner, with Win/Lose/Guaranteed status
- Interactive dashboard: date/banner filters apply to the whole page, multi-account comparison, per-account pity meters, a short commentary under every chart, and CSV export
- Pull History tab (5★ / 4★) filterable by banner, type, and account
- Optional Google Sheets sync: one tab per account with Character / Weapon / Standard tables, including pity and 50/50 result
- Professional dark "Teyvat-night" UI: hero header, pity progress meters, color-coded Win/Lose/Guaranteed badges, and a consistent chart style across all 9 tabs

## Project Structure

```
.
├── 00_fetch_rarity_lookup.py
├── 01_preprocessing.py
├── 02_analytics.py
├── 03_dashboard.py
├── 04_sync_gsheet.py          # optional Google Sheets sync (step 5)
├── requirements.txt
├── runtime.txt
├── .github/workflows/       # CML pipeline (see Automation below)
├── .gitignore
├── credentials/             # git-ignored: secret.toml (Google service account)
├── data/
│   ├── paimon-moe-local-data.json   # user-provided export
│   ├── char_full.json               # generated (step 00)
│   ├── weapon_full.json             # generated (step 00)
│   └── data_clean.csv               # generated (step 01)
└── outputs/
    ├── 01_total_pull_progress_akun.(csv|png)
    ├── 02_timeline_wish.(csv|png)
    ├── 03_pity_distribution_5star.(csv|png)
    ├── 04_win_lose_50_50.(csv|png)
    ├── 05_top_character.csv, 05_top_weapon.csv, 05_top_character_weapon.png
    ├── 06_banner_performance.(csv|png)
    └── 07_luck_score.(csv|png)
```

## Getting Your Export File

1. Open [paimon.moe](https://paimon.moe) and make sure your wish history is populated (manual entry or UIGF import).
2. On the **Wish Counter** page, use **Export Data** (under settings / the "⋮" menu).
3. Save the file as `data/paimon-moe-local-data.json`.

## Installation

Requires Python 3.9+.

```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
pandas
matplotlib
streamlit
plotly
```

The optional Google Sheets sync (step 5) additionally needs `pip install gspread` (and `pip install tomli` on Python < 3.11). These are deliberately not in `requirements.txt`, so the dashboard and CI installs stay light.

## Usage

Run the pipeline in order.

### 1. Fetch rarity lookup

The Paimon.moe export only contains item IDs, timestamps, type, and pity — no names or rarity. This step pulls a reference table from Paimon.moe's GitHub source into `data/char_full.json` and `data/weapon_full.json`. Requires internet access to `raw.githubusercontent.com`. Re-run to refresh after new character/weapon releases (it always overwrites the two files).

```bash
python3 00_fetch_rarity_lookup.py
```

### 2. Preprocess

Merges the raw export with the rarity lookup into one tidy table (one row per pull). The Paimon.moe export already contains your full wish history, so re-running this after updating `paimon-moe-local-data.json` regenerates `data_clean.csv` from scratch with the latest complete history — it doesn't need to be run incrementally.

```bash
python3 01_preprocessing.py                 # all accounts → data/data_clean.csv
python3 01_preprocessing.py --list-uid      # list available UIDs
python3 01_preprocessing.py --uid 887284572 # single account → data/data_clean_887284572.csv
```

Output columns: `account`, `uid`, `adventure_rank`, `world_level`, `banner_type`, `banner_code`, `pull_number`, `datetime`, `item_id`, `item_name`, `item_category`, `rarity`, `pity`, `rate_raw`, `win_50_50`, `date`, `year_month`, `is_5star`, `is_4star`, `is_3star`.

### 3. Generate analytics

Produces 7 insights, each as a paired CSV + PNG in `outputs/`:

| # | Insight | Files |
|---|---------|-------|
| 1 | Total pulls & account progress | `01_total_pull_progress_akun.*` |
| 2 | Monthly wish timeline | `02_timeline_wish.*` |
| 3 | 5★ pity distribution | `03_pity_distribution_5star.*` |
| 4 | 50/50 win/lose | `04_win_lose_50_50.*` |
| 5 | Top characters & weapons | `05_top_character*.csv`, `05_top_character_weapon.png` |
| 6 | Banner performance | `06_banner_performance.*` |
| 7 | Luck score | `07_luck_score.*` |

The dashboard (step 4) adds dashboard-only views — Latest 5★ per banner and a Pull History table — that are not part of `02_analytics.py`'s CSV/PNG output.

```bash
python3 02_analytics.py
python3 02_analytics.py --input data/data_clean_887284572.csv --outdir outputs_887284572
```

### 4. Run the dashboard

An interactive Streamlit dashboard. Reads `data_clean.csv` directly. The page flows from **Overview** (key numbers) → **Banner Pity Meters** → **Summary** → **Detailed Analysis** (9 tabs: Total Pulls, Banner, Timeline, Pity 5★, 50-50, Luck Score, Top Items, Latest 5★, History).

- The sidebar date and banner filters apply to the entire page, including the Overview and pity meters (pity is computed from the filtered pulls).
- With several accounts selected, the pity meters get one tab per account, since pity only makes sense per account.
- Top Items, Latest 5★ and History each have their own account filter; History can also be filtered by banner (Character / Weapon / Standard) and type.
- Every chart has a one-line commentary generated from the data currently shown.

The **Latest 5★** tab lists the 10 most recent 5★ characters/weapons obtained on each banner (newest first), each row showing date, name, type, pity, and Win/Lose/Guaranteed result, plus a per-banner Win/Lose/Guaranteed count and win rate summary.

The dashboard uses a custom visual theme on top of Streamlit's dark mode: a hero header showing account context, banner pity cards with progress bars toward hard pity, color-coded Win/Lose/Guaranteed badges, and shared chart styling (typography, spacing, gridlines) across every tab.

```bash
streamlit run 03_dashboard.py
# or for a specific account:
streamlit run 03_dashboard.py -- --data data/data_clean_887284572.csv
```

Open `http://localhost:8501`, or use the hosted version at [history-gi-noviardhana.streamlit.app](https://history-gi-noviardhana.streamlit.app/).

### 5. Sync to Google Sheets (optional)

Writes `data_clean.csv` to a Google Sheet: one tab per account, each with three tables side by side (Character Event, Weapon Event, Standard) listing 4★/5★ pulls with date, name, rarity, pity and 50-50 result, plus current pity above each table.

One-time setup: create a Google Cloud service account with the Google Sheets API enabled, share your sheet with its `client_email` as **Editor**, and put the sheet id and the key in `credentials/secret.toml` (git-ignored):

```toml
[gsheet]
spreadsheet_id = "<id from the sheet URL>"

[gcp_service_account]
type = "service_account"
project_id = "<project id>"
private_key_id = "<private_key_id from the JSON key>"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "<name>@<project>.iam.gserviceaccount.com"
token_uri = "https://oauth2.googleapis.com/token"
```

```bash
python3 04_sync_gsheet.py --preprocess   # JSON -> CSV -> Google Sheet
python3 04_sync_gsheet.py                # CSV -> Google Sheet
python3 04_sync_gsheet.py --dry-run      # preview only, no Google access
python3 04_sync_gsheet.py --include-3star
```

Existing data is never deleted: tabs of accounts missing from the CSV are left alone, and a tab is skipped (with a warning) if the new export has fewer pulls than the sheet already shows. Use `--force` to override. Never commit the service-account key.

## Automation (GitHub Actions + CML)

A workflow in `.github/workflows/` runs the pipeline automatically:

- **Trigger:** any push that changes `data/paimon-moe-local-data.json`, or manually via **Actions → Run workflow**.
- **Steps:** fetch rarity lookup → verify the export file exists → run preprocessing → sync Google Sheets (only if the secrets below are set) → run analytics → smoke-test the dashboard → post a CML comment with the tables/charts → commit the regenerated `data/` and `outputs/` files back to `main`.
- **Google Sheets sync in CI:** add two repository secrets under *Settings → Secrets and variables → Actions*: `GSHEET_ID` (the sheet id) and `GCP_SERVICE_ACCOUNT_JSON` (paste the **entire** service-account JSON key file). Without them the step is skipped with a notice. The step uses `continue-on-error`, so a Google/API problem shows as a failed step but never blocks committing the regenerated data. If a tab is skipped by the safety check, a warning annotation appears on the run.
- Because the bot commits back to `main`, your local branch will fall behind after each run. Always `git pull` before pushing a new export file to avoid a rejected (non-fast-forward) push.

## Troubleshooting

| Issue | Fix |
|---|---|
| `FileNotFoundError` for rarity lookup | Run `00_fetch_rarity_lookup.py` before `01_preprocessing.py`. |
| `[WARN] N row(s) have no rarity mapping` | Export contains item IDs not yet in the Paimon.moe lookup (usually a newly released character/weapon). Re-run `00_fetch_rarity_lookup.py`, then re-run preprocessing. |
| Dashboard can't find data | Ensure `data/data_clean.csv` exists (run step 1), or pass a path with `-- --data <path>`. |
| Connection error in `00_fetch_rarity_lookup.py` | Check access to `raw.githubusercontent.com` (proxies/firewalls sometimes block it). |
| Streamlit Cloud install error (`installer returned a non-zero exit code`) | Avoid strict version pins in `requirements.txt`; pin Python version via `runtime.txt` instead. |
| `git push` rejected (non-fast-forward) after the CI bot ran | The bot committed to `main` after your last pull. Run `git pull --rebase origin main`, resolve any conflicts, then push again. |
| Streamlit Cloud: "You do not have access to this app" | The app is still linked to an old repo, or the Streamlit GitHub App isn't authorized for the current repo. Re-check the app's linked repo in Streamlit Cloud settings, or grant access at `github.com/settings/installations`. |
| `secret.toml: private_key is not a real key yet` | `private_key` still holds a placeholder. Paste the full value from the service-account JSON (one line, keep the `\n` sequences). |
| Sheets sync: `403` / `PERMISSION_DENIED` or `SpreadsheetNotFound` | The sheet is not shared with the service account's `client_email` as Editor, or the Google Sheets API is not enabled for the project. |
| Sheets sync prints `[SKIP] '<tab>'` | The new export has fewer pulls than the sheet already shows (safety check). Export the full history again, or use `--force` if the smaller export is intended. |

## Changelog

Feature additions:
- **`cml.yml`** — new optional "Sync to Google Sheets" step after preprocessing, driven by GitHub Secrets (skipped when they are not set).
- **`04_sync_gsheet.py`** — new optional step: syncs `data_clean.csv` to Google Sheets (one tab per account; Character / Weapon / Standard tables with pity and 50-50 result; never deletes existing data).
- **`03_dashboard.py`** — layout rework for presentation: Overview / Banner Pity Meters / Summary / Detailed Analysis sections, KPI cards in a 3×2 grid, date/banner filters applied to the whole page, pity meters in one tab per account, tabs reordered (History last), a short commentary under every chart, per-tab account filters, and a banner filter in Pull History. The separate TL;DR block was removed in favour of the Summary.
- **`03_dashboard.py`** — added an 8th tab, "🆕 Latest 5★", showing the 10 most recent 5★ characters/weapons per banner with date, pity, and Win/Lose/Guaranteed result, plus a per-banner Win/Lose/Guaranteed count and win rate.
- **`03_dashboard.py`** — redesigned the UI: hero header with account context chips, pity meters with progress bars, color-coded Win/Lose/Guaranteed badges, a color-coded results table on the Latest 5★ tab, and a shared chart style (typography, margins, gridlines, hover) applied across all 8 tabs.

Bug fixes applied to the pipeline scripts:
- **`03_dashboard.py`** — the 4★ pity counter now resets only on a 4★ (4★ and 5★ counters are independent; previously a 5★ also reset it), and chronological order is now stable for pulls sharing a timestamp (multi-pulls) via a `seq` column derived from the CSV row order.
- **`00_fetch_rarity_lookup.py`** — the name/rarity extraction window could bleed into a neighboring item when entries sat close together, silently attaching the wrong name or rarity. Now clamped to the boundary between adjacent entries.
- **`01_preprocessing.py`** — `--list-uid` no longer requires the rarity lookup files to exist; item ID lookups are now coerced to string to avoid silent mismatches; rows with an unparseable datetime are now flagged and dropped instead of leaking into `year_month` as `"NaT"`.
- **`02_analytics.py`** — guarded against a crash when a dataset has zero 5★ pulls; banners with no 50/50 data now show a labeled "N/A" bar instead of an unexplained gap.

## Credits

- Character and weapon name/rarity reference data sourced from [Paimon.moe](https://github.com/MadeBaruna/paimon-moe) (`src/data/characters.js`, `src/data/weaponList.js`).
- Genshin Impact is a trademark of HoYoverse/miHoYo. This is an independent, unaffiliated personal-data analysis tool.