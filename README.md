# Gacha Analytics: Genshin Impact & Honkai: Star Rail

Analytics, an interactive dashboard and an optional auto-updating Google Sheet built from your gacha history.

**Live demo:** [mygacha-mihoyo.streamlit.app](https://mygacha-mihoyo.streamlit.app/)

| Game | Source | Accounts |
|---|---|---|
| Genshin Impact | [Paimon.moe](https://paimon.moe) export (JSON) | one per UID |
| Honkai: Star Rail | [StarRailStation](https://starrailstation.com) backup (`.dat`) | one per profile |

## Features

- **Analytics:** pulls by rarity, monthly timeline, 5★ pity, 50/50 win rate, top items, Luck Score
- **Dashboard (Streamlit):** game picker, filters (account, banners, date range), KPIs, banner pity meters, nine analysis tabs, CSV export
- **Google Sheets (optional):** one tab per account, one table per banner
- **CI:** GitHub Actions rebuilds data and outputs whenever a new export is pushed

## Project Structure

```
.
├── dashboard.py              # Streamlit dashboard
├── pipeline/                 # data and analytics scripts
│   ├── __main__.py           # `python -m pipeline ...`
│   ├── config.py             # pity rules, banners, colours, paths, timezone
│   ├── luck.py               # Luck Score formula
│   ├── analytics_core.py     # shared chart engine
│   ├── 01_fetch_*_lookup.py  # item id -> name / rarity
│   ├── 02_preprocess_*.py    # raw export -> clean CSV
│   ├── 03_analytics_*.py     # clean CSV -> outputs/
│   └── 04_sync_gsheet.py     # clean CSV -> Google Sheet (optional)
├── tests/                    # pytest suite
├── data/                     # exports, lookups, clean CSVs
├── outputs/                  # generated charts and tables (gi/, hsr/)
├── requirements.txt / requirements-dev.txt
├── runtime.txt               # Python version used by CI
└── .github/workflows/cml.yml
```

Scripts are numbered by stage (`01` fetch → `02` preprocess → `03` analytics → `04` sync); `_gi` / `_hsr` marks the game.

## Quick Start

```bash
pip install -r requirements.txt
```

1. Export your data and save it in `data/`:
   - Genshin: Paimon.moe → **Wish Counter → Export Data** → `data/paimon-moe-local-data.json`
   - Star Rail: StarRailStation backup → `data/starrailstation-backup_YYYY-MM-DD.dat`
2. Run the pipeline from the project root:

```bash
python -m pipeline all --no-sync          # fetch -> preprocess -> analytics
streamlit run dashboard.py                # http://localhost:8501
```

| Command | Effect |
|---|---|
| `python -m pipeline all` | all stages, including Google Sheets sync when credentials exist |
| `python -m pipeline all --dry-run` | print what would run |
| `python -m pipeline preprocess --games gi` | one stage (`fetch`, `preprocess`, `analytics`, `sync`) and/or one game |

Games are detected from the files in `data/`. Requires Python 3.9+.

## Outputs

- **Clean data:** `data/data_clean_gi.csv`, `data/data_clean_hsr.csv`
- **Analytics:** `outputs/gi/` and `outputs/hsr/`, each insight as a `.csv` + `.png` pair:

| # | Insight |
|---|---|
| 01 | Total pulls and account progress |
| 02 | Timeline |
| 03 | 5★ pity distribution |
| 04 | 50/50 win/lose |
| 05 | Top characters and weapons / light cones |
| 06 | Banner performance |
| 07 | Luck Score |

Single scripts accept extra options, for example Genshin `--uid`, `--tz`, `--mask-uid` and Star Rail `--profile`, `--input`, `--tz`. Timestamps are written in `DEFAULT_TZ` (`pipeline/config.py`, default `Asia/Jakarta`).

## Automation (GitHub Actions)

`.github/workflows/cml.yml` runs when an export or the workflow file is pushed to `main`, or manually from the **Actions** tab.

1. Install dependencies and run the tests (a failure stops the run before any data changes)
2. Detect exports and fetch lookups
3. Preprocess, sync to Google Sheets (optional), run analytics
4. Smoke-test the dashboard
5. Commit `data/` and `outputs/` to `main` (`[skip ci]`) and post a report as a commit comment

Actions are pinned to a commit SHA; update the SHA by hand to upgrade an action.

| Setting | Purpose |
|---|---|
| Secrets `GSHEET_ID`, `GCP_SERVICE_ACCOUNT_JSON` | enable the Google Sheets sync (skipped without them) |
| Variable `GACHA_MASK_UID=1` | mask the Genshin UID in `data_clean_gi.csv` |

In a private repository the report links to charts instead of embedding them.

**Updating data:**

```bash
git pull --rebase origin main
# replace or add the export in data/
git add data/ && git commit -m "update gacha data" && git push
```

## Google Sheets Sync (optional)

1. Create a Google Sheet and copy its ID.
2. In Google Cloud, enable the **Google Sheets API** and create a **service account** with a JSON key.
3. Share the Sheet with the service account's `client_email` as **Editor**.
4. Create `credentials/secret.toml` (git-ignored):

```toml
[gsheet]
spreadsheet_id = "<sheet id>"

[gcp_service_account]
# paste the fields of the JSON key here
```

```bash
python pipeline/04_sync_gsheet.py --preprocess   # raw data -> CSV -> Sheet
python pipeline/04_sync_gsheet.py --dry-run      # preview, no Google access
```

Existing data is never deleted: a tab is replaced only after the new content is fully written, and skipped if the new export has fewer pulls (`--force` overrides).

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Covers the Star Rail backup decoder, Luck Score, lookup parsing and validation, Genshin preprocessing, game configs and the pipeline runner.

## Security & Privacy

- Never commit the service-account key; `credentials/` must stay in `.gitignore`.
- The Paimon.moe export and `data_clean_gi.csv` contain your Genshin UID. For a public repository, use a private repo or mask the UID with `--mask-uid` / `GACHA_MASK_UID=1`. Masking affects only the generated output, not the raw export in `data/`.
- If a key leaks, delete it in Google Cloud and create a new one.

## Troubleshooting

| Issue | Fix |
|---|---|
| "No export found" | Put an export in `data/` or pass `--games gi` / `--games hsr` |
| `FileNotFoundError` for lookup | Run the matching `01_fetch_*` script first |
| Rows without rarity / name mapping | New item: re-run `01_fetch_*`, then `02_preprocess_*` |
| `ModuleNotFoundError: pipeline` | Run `streamlit run dashboard.py` from the project root |
| `git push` rejected | `git pull --rebase origin main`, then push |
| `403` / `SpreadsheetNotFound` | Share the Sheet with `client_email` as Editor and enable the Sheets API |
| Streamlit Cloud "file not found" | Set the app's main file to `dashboard.py` |

## Credits

Genshin data from [Paimon.moe](https://github.com/MadeBaruna/paimon-moe); Star Rail data from [StarRailStation](https://starrailstation.com). Genshin Impact and Honkai: Star Rail are trademarks of HoYoverse/miHoYo. This is an independent, unaffiliated project.