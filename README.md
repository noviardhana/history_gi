# Gacha Analytics: Genshin Impact & Honkai: Star Rail

Analytics, an interactive dashboard and an optional auto-updating Google Sheet built from your gacha history.

**Live demo:** [mygacha-mihoyo.streamlit.app](https://mygacha-mihoyo.streamlit.app/)

| Game | Source | Accounts |
|---|---|---|
| Genshin Impact | [Paimon.moe](https://paimon.moe) export (JSON) | one per UID |
| Honkai: Star Rail | [StarRailStation](https://starrailstation.com) backup (`.dat`) | one per profile |

## Features

- **Analytics:** pulls by rarity, monthly timeline, 5★ pity, 50/50 win rate, top items, Luck Score
- **Dashboard (Streamlit):** game picker, filters (account, banners, date range), KPIs, banner pity meters, analysis tabs (pity, hazard rate, luck, 50/50, items, history), CSV export
- **Google Sheets (optional):** one tab per account, one table per banner
- **CI:** GitHub Actions rebuilds data and outputs whenever a new export is pushed

## Project Structure

```
.
├── dashboard.py              # Streamlit dashboard (UI and chart assembly)
├── charts.py                 # reusable Plotly chart helpers
├── components.py             # reusable HTML/UI helpers (KPI cards, badges)
├── insights.py               # "what it shows" texts for sections and charts
├── analytics/                # UI-independent data layer used by the dashboard
│   ├── __init__.py
│   ├── data_loader.py        # CSV loading, normalization, integrity checks
│   ├── filters.py            # account / banner / date filters
│   └── metrics.py            # current pity, rate-up stats, summary stats
├── pipeline/                 # data and analytics scripts
│   ├── __init__.py
│   ├── __main__.py           # `python -m pipeline ...`
│   ├── config.py             # pity rules, banners, colours, paths, timezone
│   ├── luck.py               # Luck Score formula
│   ├── utils.py              # logging, lookup download/validation, UID masking
│   ├── fetch_lookup.py       # item id -> name / rarity        (--game gi|hsr)
│   ├── preprocess.py         # raw export -> clean CSV         (--game gi|hsr)
│   ├── analytics_core.py     # clean CSV -> outputs/           (--game gi|hsr)
│   └── sync_gsheet.py        # clean CSV -> Google Sheet (optional)
├── tests/                    # pytest suite, fixtures/lzstring_cases.json, smoke_dashboard.py
├── data/                     # exports, lookups, clean CSVs
├── outputs/                  # generated charts and tables (gi/, hsr/)
├── credentials/              # secret.toml (git-ignored)
├── requirements.txt / requirements-dev.txt
├── pytest.ini                # test paths and import paths
├── runtime.txt               # Python version used by CI
└── .github/workflows/cml.yml
```

`pipeline/` produces the data and the PNG/CSV reports; `analytics/`, `charts.py`, `components.py` and `insights.py` are used only by the dashboard. `pipeline/config.py` is the single source of truth for per-game settings.

Stages run in this order: fetch → preprocess → analytics → sync. Each module handles both games; pick one with `--game gi|hsr` (`python -m pipeline` does this for you).

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

Games are detected from the files in `data/`. CI runs the Python version in `runtime.txt` (3.11).

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
| 08 | Radiance check (Genshin only) |

### Luck Score

Both components use a 0–100 scale where **50 means exactly as expected**, and the score is `0.6 × pity luck + 0.4 × rate-up win luck` (re-weighted if one is missing). The formula lives in `pipeline/luck.py` and is shared by the PNG reports and the dashboard.

- **Pity luck:** per 5★, `50 + 50 × (E − pity) / (E − 1)` limited to 0–100, where `E = 100 / expected_rate_5` of the banner (62.5 for a 1.6% banner). Pull 1 scores 100, pity `E` scores 50. Banners without an `expected_rate_5` entry (Beginners) are not scored.
- **Rate-up win luck:** 0 with no wins, 50 at the banner's official rate-up chance (50% character, 75% weapon / light cone), 100 with every 50/50 won.
- **Dashboard labels:** above 70 very lucky · 55–70 above average · 45–55 about average · below 45 below average.

### Banner rules (`pipeline/config.py`)

- `hard_pity` is the official 5★ guarantee. `pull_limit` is the maximum number of pulls a banner allows (Beginners: 20 wishes in Genshin, 50 warps in Star Rail); it is not a pity.
- Banners in `pity_card_banners` get a pity meter; Beginners banners do not.
- Current pity, lifetime pulls and hazard-rate exposure use the full history of the selected account(s); only the historical charts follow the date filter.
- Banner efficiency (dashboard and `06_banner_performance.png`) is the mean pity of the 5★ obtained, so the unfinished streak after the last 5★ is not counted. The dashboard does not rank banners with fewer than 3 5★.
- Banners with a `pull_limit` show that limit in the pity distribution plots and in the Google Sheet summary (`limit 20 pulls`) instead of a hard-pity line.

Modules accept extra options when run directly, for example `python pipeline/preprocess.py --game gi --uid ... --mask-uid` and `--game hsr --profile ... --input ...`. Timestamps are written in `DEFAULT_TZ` (`pipeline/config.py`, default `Asia/Jakarta`).

## Automation (GitHub Actions)

`.github/workflows/cml.yml` runs when an export, `pipeline/`, `analytics/`, `tests/`, `dashboard.py`, `charts.py`, `components.py`, `insights.py`, `requirements*.txt`, `pytest.ini`, `runtime.txt` or the workflow file is pushed to `main`, or manually from the **Actions** tab.

1. Install dependencies and run the tests (a failure stops the run before any data changes)
2. `python -m pipeline all --no-sync`: detect exports, fetch lookups, preprocess, analytics
3. Smoke-test the dashboard (`tests/smoke_dashboard.py`)
4. Commit `data/` and `outputs/` to `main` (`[skip ci]`); the run fails if the push does not succeed
5. Sync to Google Sheets (optional, key read from the `GCP_SERVICE_ACCOUNT_JSON` secret) and post a report as a commit comment

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
python pipeline/sync_gsheet.py --preprocess   # raw data -> CSV -> Sheet
python pipeline/sync_gsheet.py --dry-run      # preview, no Google access
```

Existing data is never deleted: a tab is replaced only after the new content is fully written, and skipped if the new export has fewer pulls (`--force` overrides).

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Covers the Star Rail backup decoder (against `tests/fixtures/lzstring_cases.json`), Star Rail and Genshin preprocessing, Luck Score, Radiance model, lookup parsing and validation, UID masking and Google Sheets tab matching, game configs and the pipeline runner. `tests/smoke_dashboard.py` is not collected by pytest; CI runs it as a separate step.

## Security & Privacy

- Never commit the service-account key; `credentials/` must stay in `.gitignore`.
- The Paimon.moe export and `data_clean_gi.csv` contain your Genshin UID. For a public repository, use a private repo or mask the UID with `--mask-uid` / `GACHA_MASK_UID=1`. Masking affects only the generated output, not the raw export in `data/`.
- If a key leaks, delete it in Google Cloud and create a new one.

## Troubleshooting

| Issue | Fix |
|---|---|
| "No export found" | Put an export in `data/` or pass `--games gi` / `--games hsr` |
| `FileNotFoundError` for lookup | Run `python -m pipeline fetch` first |
| Rows without rarity / name mapping | New item: re-run `python -m pipeline fetch`, then `preprocess` |
| `ModuleNotFoundError: pipeline` / `analytics` | Run `streamlit run dashboard.py` from the project root |
| `git push` rejected | `git pull --rebase origin main`, then push |
| `403` / `SpreadsheetNotFound` | Share the Sheet with `client_email` as Editor and enable the Sheets API |
| Streamlit Cloud "file not found" | Set the app's main file to `dashboard.py` |

## Credits

Genshin data from [Paimon.moe](https://github.com/MadeBaruna/paimon-moe); Star Rail data from [StarRailStation](https://starrailstation.com). Genshin Impact and Honkai: Star Rail are trademarks of HoYoverse/miHoYo. This is an independent, unaffiliated project.