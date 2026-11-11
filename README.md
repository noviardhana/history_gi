# Gacha Analytics: Genshin Impact & Honkai: Star Rail

Turn your gacha history into analytics, an interactive dashboard, and an auto-updating Google Sheet. Two games are supported, each with its own data pipeline and its own section in the dashboard:

| Game | Source | Accounts |
|---|---|---|
| Genshin Impact | [Paimon.moe](https://paimon.moe) export (JSON) | one per UID |
| Honkai: Star Rail | [StarRailStation](https://starrailstation.com) backup (`.dat`) | one per StarRailStation profile (e.g. Default, second) |

**Live demo:** [history-gi-noviardhana.streamlit.app](https://history-gi-noviardhana.streamlit.app/)

## Overview

```
Genshin Impact                              Honkai: Star Rail
Paimon.moe export (JSON)                    StarRailStation backup (.dat)
        │                                           │
00_fetch_rarity_lookup.py                   00_fetch_hsr_lookup.py
        │                                           │
01_preprocessing.py                         01_preprocessing_hsr.py
        │                                           │
  data/data_clean.csv                       data/data_clean_hsr.csv
        │                                           │
        └──────────────────┬────────────────────────┘
                           │      game_configs.py (pity, rate-up, banners, colours)
                           ▼
        ├──► 02_analytics.py / 02_analytics_hsr.py   7 insights (CSV + PNG) → outputs/GI, outputs/HSR
        ├──► 03_dashboard.py                         Streamlit dashboard, one section per game
        └──► 04_sync_gsheet.py                       (optional) Google Sheets, one tab per account
```

Both games run through the same code. Only `game_configs.py` differs per game, so charts, the dashboard and the Luck Score are consistent.

## Features

**Analytics**
- Total pulls per account by rarity (Genshin also shows Adventure Rank and World Level; Star Rail shows the 5★/4★ rate, since its backup has no account level data)
- Monthly timeline by banner
- 5★ pity distribution and rate-up win rate per banner, compared with the official rate-up chance
- Top characters and top weapons / light cones, banner performance
- Luck Score: 60% pity efficiency + 40% rate-up win luck (5★ only, 50 = exactly as expected)

**Dashboard**
- Two top-level sections, **Genshin Impact** and **Honkai: Star Rail**, each with its own KPIs, filters and charts
- Inside each game: account selector (every account found, or "All accounts" to see them side by side), date range and banner filters
- Sections: Overview (KPIs) → Banner Pity Meters → Summary → Detailed Analysis (9 tabs)
- Pity meters show hard pity and soft pity, with one tab per account
- Latest 5★ and Pull History tables, a one-line commentary under every chart, and CSV export per game
- A game without a data file shows a hint instead of breaking the page

**Google Sheets sync (optional)**
- One tab per account: `GI - <uid>` and `HSR - <account>`
- Genshin tabs: Character / Weapon / Standard. Star Rail tabs: all six banners (Character, Light Cone, Collab Character, Collab Light Cone, Standard, Beginners)
- Each table lists pity and rate-up result; current pity is shown above it
- Never deletes existing data

**Automation**
- GitHub Actions regenerates everything (and the Sheet) when a new export is pushed. Each game runs only if its export is in the repo.

## Quick Start

```bash
pip install -r requirements.txt
```

**Genshin Impact**
1. Export your data from [paimon.moe](https://paimon.moe): **Wish Counter → Export Data**.
2. Save it as `data/paimon-moe-local-data.json`.

```bash
python3 00_fetch_rarity_lookup.py   # once, or to refresh after new releases
python3 01_preprocessing.py
```

**Honkai: Star Rail**
1. Export a backup from StarRailStation's warp tracker.
2. Save it as `data/starrailstation-backup_YYYY-MM-DD.dat` (the newest file is picked automatically).

```bash
python3 00_fetch_hsr_lookup.py      # once, or to refresh after new releases
python3 01_preprocessing_hsr.py
```

**Dashboard** (either game, or both)

```bash
streamlit run 03_dashboard.py
```

Requires Python 3.9+ (CI uses the version in `runtime.txt`). On Windows use `python` or `py` instead of `python3`.

## Project Structure

```
.
├── 00_fetch_rarity_lookup.py        # Genshin lookup
├── 00_fetch_hsr_lookup.py           # Star Rail lookup
├── 01_preprocessing.py              # Genshin export → CSV
├── 01_preprocessing_hsr.py          # Star Rail backup → CSV
├── 02_analytics.py                  # Genshin report
├── 02_analytics_hsr.py              # Star Rail report
├── 03_dashboard.py                  # dashboard (both games)
├── 04_sync_gsheet.py                # Google Sheets (both games)
├── analytics_common.py              # shared chart engine + Luck Score
├── game_configs.py                  # per-game rules: pity, rate-up, banners, colours, sheet styles
├── requirements.txt
├── runtime.txt
├── .gitignore
├── .streamlit/config.toml           # dashboard theme (dark navy + gold)
├── .github/workflows/cml.yml        # CI pipeline
├── credentials/                     # git-ignored: secret.toml (Google service account)
├── data/
│   ├── paimon-moe-local-data.json         # Genshin export (input)
│   ├── char_full.json, weapon_full.json   # generated by 00_fetch_rarity_lookup.py
│   ├── data_clean.csv                     # generated by 01_preprocessing.py
│   ├── starrailstation-backup_*.dat       # Star Rail backup (input)
│   ├── hsr_char_full.json, hsr_lc_full.json  # generated by 00_fetch_hsr_lookup.py
│   └── data_clean_hsr.csv                 # generated by 01_preprocessing_hsr.py
└── outputs/
    ├── GI/                          # generated by 02_analytics.py (CSV + PNG per insight)
    └── HSR/                         # generated by 02_analytics_hsr.py
```

`game_configs.py` is the single place to change a pity value, rate-up chance, soft pity, banner colour or sheet style. The dashboard, analytics and sync all read it. `.streamlit/config.toml` is separate: it only holds the Streamlit theme.

## Usage

| Step | Command | Output |
|---|---|---|
| 00 | `python3 00_fetch_rarity_lookup.py` / `python3 00_fetch_hsr_lookup.py` | lookup JSON files in `data/` |
| 01 | `python3 01_preprocessing.py` / `python3 01_preprocessing_hsr.py` | `data/data_clean.csv` / `data/data_clean_hsr.csv` |
| 02 | `python3 02_analytics.py` / `python3 02_analytics_hsr.py` | `outputs/GI/…` / `outputs/HSR/…` (`01_…` to `07_…`, CSV + PNG) |
| 03 | `streamlit run 03_dashboard.py` | dashboard at `http://localhost:8501` |
| 04 | `python3 04_sync_gsheet.py --preprocess` | Google Sheet (optional) |

**Notes**
- **00:** reads each game's public data source (needs access to `raw.githubusercontent.com`). The exports hold only item IDs, time, type and pity, so names and rarity come from these lookups.
- **01:** every export contains the full history, so re-running rebuilds the CSV from scratch.
  - Genshin options: `--list-uid`, `--uid <uid>` (single account → `data_clean_<uid>.csv`).
  - Star Rail options: `--list-profile`, `--profile <name or key>` (single profile → `data_clean_hsr_<profile>.csv`), `--input <backup.dat>`, `--tz <timezone>`.
- **02:** options `--input <csv>`, `--outdir <folder>`.
- **03:** point to specific files per game, e.g. `streamlit run 03_dashboard.py -- --gi-data data/data_clean_887284572.csv --hsr-data data/data_clean_hsr.csv` (`--data` still works as an alias of `--gi-data`).

## Google Sheets Sync

Writes both CSV files to one Google Sheet, one tab per account:

| Tab name | Content |
|---|---|
| `GI - <uid>` (e.g. `GI - 887284572`) | Character Event, Weapon Event, Standard |
| `HSR - <account>` (e.g. `HSR - Default`) | Character Event, Light Cone Event, Collab Character Event, Collab Light Cone Event, Standard, Beginners |

Each table lists 4★/5★ pulls: date, name, rarity, pity, rate-up result. Genshin tabs show the UID in the header; Star Rail tabs show the StarRailStation profile key, because the backup has no game UID.

**One-time setup**
1. Create a Google Sheet and copy its ID (the part of the URL between `/d/` and `/edit`).
2. In [Google Cloud Console](https://console.cloud.google.com), create a project and enable the **Google Sheets API**.
3. Create a **service account**, then add a **JSON key** to it (Keys → Add key).
4. Share the Sheet with the service account's `client_email` as **Editor**.
5. Create `credentials/secret.toml` (git-ignored):

```toml
[gsheet]
spreadsheet_id = "<sheet id>"

[gcp_service_account]
type = "service_account"
project_id = "<project id>"
private_key_id = "<from the JSON key>"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "<name>@<project>.iam.gserviceaccount.com"
token_uri = "https://oauth2.googleapis.com/token"
```

**Run**

```bash
python3 04_sync_gsheet.py --preprocess   # raw data → CSV → Sheet (both games)
python3 04_sync_gsheet.py                # CSV → Sheet
python3 04_sync_gsheet.py --games hsr    # one game only (gi / hsr)
python3 04_sync_gsheet.py --dry-run      # preview only, no Google access
```

| Option | Effect |
|---|---|
| `--games gi,hsr` | which games to sync (default: both; a game whose CSV is missing is skipped with a warning) |
| `--gi-tab-name uid\|account` | name Genshin tabs `GI - <uid>` (default) or `GI - <account>` |
| `--include-3star` | also list 3★ pulls (default: 4★ and 5★ only) |
| `--force` | overwrite a tab even if the new data has fewer pulls |
| `--sheet-id`, `--creds`, `--secrets`, `--csv`, `--hsr-csv` | override sheet id, key file, `secret.toml` path, Genshin CSV path, Star Rail CSV path |

**Safety:** tabs of accounts missing from the CSV are left untouched, and a tab is skipped with a warning if the new export has fewer pulls than the sheet already shows. Genshin tabs created before the `GI - …` naming (named after the account) are renamed, not duplicated.

## Automation (GitHub Actions)

`.github/workflows/cml.yml` runs on every push that changes `data/paimon-moe-local-data.json`, a `data/starrailstation-backup_*.dat` file, or the workflow file, and manually via **Actions → Run workflow**.

**Pipeline:** detect which exports exist → fetch lookups → preprocess → sync Google Sheets (if secrets are set) → analytics → dashboard smoke test → commit `data/` and `outputs/` back to `main` → post a report as a commit comment.

- Each game runs only if its export exists. If neither exists, the run fails with a clear error.
- The smoke test renders the whole dashboard headlessly and flags any exception. It never blocks the data commit.
- The report lists the CSV and PNG outputs of both games (`outputs/GI/…`, `outputs/HSR/…`).

**Optional repository secrets** (*Settings → Secrets and variables → Actions*):

| Secret | Value |
|---|---|
| `GSHEET_ID` | the Google Sheet ID |
| `GCP_SERVICE_ACCOUNT_JSON` | the entire service-account JSON key file |

Without them the sync step is skipped with a notice. The step uses `continue-on-error`, so a Google/API problem never blocks the data commit.

**Updating your data**

```bash
git pull --rebase origin main    # the bot commits to main after each run
# replace data/paimon-moe-local-data.json and/or add the new data/starrailstation-backup_*.dat
git add data/
git commit -m "update gacha data"
git push
```

## Security

- Never commit the service-account key. `credentials/` and common key filenames are in `.gitignore`.
- The Genshin export and CSV contain your UIDs. Make sure that is acceptable for the repository's visibility.
- If a key is ever exposed, delete it in Google Cloud (Service Accounts → Keys) and create a new one.

## Troubleshooting

| Issue | Fix |
|---|---|
| `FileNotFoundError` for rarity lookup | Run `00_fetch_rarity_lookup.py` (Genshin) or `00_fetch_hsr_lookup.py` (Star Rail) before the matching `01_…` script. |
| `[WARN] N row(s) have no rarity / name mapping` | New character, weapon or light cone not in the lookup yet. Re-run `00`, then `01`. |
| Connection error in a `00_…` script | Check access to `raw.githubusercontent.com` (proxy/firewall). |
| Dashboard section says "No data file" | Run the matching `01_…` script, or pass `-- --gi-data <path>` / `-- --hsr-data <path>`. |
| Dashboard: `ModuleNotFoundError: matplotlib` | `pip install -r requirements.txt`. The dashboard uses `analytics_common.py` for the Luck Score, which needs matplotlib. |
| Star Rail has no Adventure Rank / UID | Expected. The StarRailStation backup has neither; accounts are its profiles. |
| `git push` rejected (non-fast-forward) | The CI bot committed after your last pull. Run `git pull --rebase origin main`, then push. |
| `credentials/` shows up in `git status` | `.gitignore` is missing the `credentials/` rule. It must be named `.gitignore` (with the leading dot). |
| `secret.toml: private_key is not a real key yet` | `private_key` is still a placeholder. Paste the full value from the JSON key (one line, keep the `\n`). |
| `403` / `PERMISSION_DENIED` / `SpreadsheetNotFound` | Share the Sheet with the service account's `client_email` as Editor, and enable the Google Sheets API. |
| Sync prints `[SKIP] '<tab>'` | Safety check: the new data has fewer pulls than the sheet. Export your full history again, or use `--force` if intended. |
| CI fails with "No export found" | Add `data/paimon-moe-local-data.json` and/or `data/starrailstation-backup_YYYY-MM-DD.dat` to the repo. |
| Streamlit Cloud install error | Avoid strict version pins in `requirements.txt`; pin Python via `runtime.txt`. |
| Streamlit Cloud: "You do not have access to this app" | Re-check the app's linked repo, or grant access at `github.com/settings/installations`. |

## Changelog

**Added**
- Honkai: Star Rail support: `01_preprocessing_hsr.py`, `02_analytics_hsr.py`, a dashboard section and Google Sheet tabs (all six banners).
- `game_configs.py`: one source of truth for pity, soft pity, rate-up chance, banners, colours and sheet styles of each game.
- Dashboard: one section per game with its own KPIs, account selector, filters and tabs.
- CI: games detected automatically, each processed only if its export exists; dashboard smoke test now renders the page and reports exceptions.

**Changed**
- Google Sheet tabs are now named `GI - <uid>` and `HSR - <account>`; old Genshin tabs are renamed automatically.
- Dashboard Luck Score uses `compute_luck` from `analytics_common.py`, matching the PNG reports (5★ rate-up win luck against the official rate-up chance).
- The "50-50 win rate" KPI counts 5★ only and shows the expected rate.
- Weapon Event hard pity is 80 everywhere (the analytics script used 77 before).
- "Compare Accounts" mode merged into "All accounts", which shows per-account charts side by side.
- Reports are written per game to `outputs/GI/` and `outputs/HSR/`.

**Earlier**
- `04_sync_gsheet.py` and the optional CI sync step; Latest 5★ tab; the dark theme; page-wide filters, per-account pity tabs and chart commentary.
- Fixed: the 4★ pity counter resets only on a 4★; pulls sharing a timestamp are ordered by row order or pull number; analytics no longer crash on datasets without 5★ pulls.

## Credits

- Genshin character and weapon name/rarity data from [Paimon.moe](https://github.com/MadeBaruna/paimon-moe) (`src/data/characters.js`, `src/data/weaponList.js`).
- Honkai: Star Rail warp history from [StarRailStation](https://starrailstation.com) backups.
- Genshin Impact and Honkai: Star Rail are trademarks of HoYoverse/miHoYo. This is an independent, unaffiliated personal-data analysis tool.
