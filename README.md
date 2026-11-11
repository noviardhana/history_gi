# Gacha Analytics: Genshin Impact & Honkai: Star Rail

Analytics, interactive dashboard, and auto-updating Google Sheet from your gacha history.

| Game | Source | Accounts |
|---|---|---|
| Genshin Impact | [Paimon.moe](https://paimon.moe) export (JSON) | one per UID |
| Honkai: Star Rail | [StarRailStation](https://starrailstation.com) backup (`.dat`) | one per profile |

**Live demo:** [history-gi-noviardhana.streamlit.app](https://history-gi-noviardhana.streamlit.app/)

## Pipeline

```
Export → 00_fetch_*_lookup → 01_preprocessing[_hsr] → data/data_clean[_hsr].csv
                                                          ├─► 02_analytics[_hsr].py → outputs/GI, outputs/HSR
                                                          ├─► 03_dashboard.py       (Streamlit)
                                                          └─► 04_sync_gsheet.py     (Google Sheets, optional)
```

`game_configs.py` is the single place for pity, soft pity, rate-up chance, banners, colours, and sheet styles.

## Features

- **Analytics:** pulls by rarity, monthly timeline, 5★ pity and rate-up win rate, top items, Luck Score
- **Dashboard:** three zones
  - **Left sidebar:** pick the game (Genshin Impact or Honkai: Star Rail)
  - **Right panel (Filters):** account (default: main account, or *All accounts*), banners (default: all, in game order), date range (default: all). Changing account resets banners and date range.
  - **Middle:** Overview (KPIs) → Banner Pity Meters (all banners incl. Beginners) → Summary → Detailed Analysis (9 tabs) → CSV export
  - Every chart has a short commentary; chart totals follow the selected banners (e.g. only Character selected → Character numbers only)
- **Google Sheets:** one tab per account (`GI - <uid>`, `HSR - <account>`), one table per banner
  - GI: Character, Weapon, Standard, Beginners
  - HSR: Character, Light Cone, Collab Character, Collab Light Cone, Standard, Beginners
- **CI:** GitHub Actions rebuilds everything when a new export is pushed

## Quick Start

```bash
pip install -r requirements.txt
```

**Genshin:** export from paimon.moe (**Wish Counter → Export Data**) → save as `data/paimon-moe-local-data.json`

```bash
python3 00_fetch_rarity_lookup.py
python3 01_preprocessing.py
```

**Star Rail:** export from StarRailStation → save as `data/starrailstation-backup_YYYY-MM-DD.dat`

```bash
python3 00_fetch_hsr_lookup.py
python3 01_preprocessing_hsr.py
```

**Dashboard**

```bash
streamlit run 03_dashboard.py
```

Fonts load from Google Fonts (`.streamlit/config.toml`), so the browser needs internet and a recent Streamlit version.

Python 3.9+. On Windows use `python` or `py`.

## Usage

| Step | Command | Output |
|---|---|---|
| 00 | `00_fetch_rarity_lookup.py` / `00_fetch_hsr_lookup.py` | lookup JSON in `data/` |
| 01 | `01_preprocessing.py` / `01_preprocessing_hsr.py` | `data/data_clean[_hsr].csv` |
| 02 | `02_analytics.py` / `02_analytics_hsr.py` | `outputs/GI/` / `outputs/HSR/` |
| 03 | `streamlit run 03_dashboard.py` | `http://localhost:8501` |
| 04 | `04_sync_gsheet.py --preprocess` | Google Sheet |

- **01 options:** Genshin `--list-uid`, `--uid`; Star Rail `--list-profile`, `--profile`, `--input`, `--tz`
- **02 options:** `--input`, `--outdir`
- **03 custom files:** `streamlit run 03_dashboard.py -- --gi-data <csv> --hsr-data <csv>`

## Google Sheets Sync

**Setup**
1. Create a Google Sheet, copy its ID (between `/d/` and `/edit`).
2. In Google Cloud Console: create a project, enable **Google Sheets API**.
3. Create a **service account** + **JSON key**.
4. Share the Sheet with the `client_email` as **Editor**.
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
python3 04_sync_gsheet.py --preprocess   # raw data → CSV → Sheet
python3 04_sync_gsheet.py                # CSV → Sheet
python3 04_sync_gsheet.py --games hsr    # one game (gi / hsr)
python3 04_sync_gsheet.py --dry-run      # preview, no Google access
```

| Option | Effect |
|---|---|
| `--games gi,hsr` | games to sync (default: both) |
| `--gi-tab-name uid\|account` | Genshin tab naming |
| `--include-3star` | also list 3★ pulls |
| `--force` | overwrite even if new data has fewer pulls |
| `--sheet-id`, `--creds`, `--secrets`, `--csv`, `--hsr-csv` | path / ID overrides |

Existing data is never deleted; a tab is skipped if the new export has fewer pulls.

## Automation (GitHub Actions)

`.github/workflows/cml.yml` runs on push of a new export, or manually. Each game runs only if its export exists.

Optional secrets: `GSHEET_ID`, `GCP_SERVICE_ACCOUNT_JSON` (without them the sync step is skipped).

**Update data**

```bash
git pull --rebase origin main
# replace/add the export in data/
git add data/ && git commit -m "update gacha data" && git push
```

## Security

- Never commit the service-account key (`credentials/` is git-ignored).
- Exports and CSV contain your UID; check the repo visibility.
- If a key leaks, delete it in Google Cloud and create a new one.

## Troubleshooting

| Issue | Fix |
|---|---|
| `FileNotFoundError` for lookup | Run the matching `00_…` script first |
| `N row(s) have no rarity / name mapping` | New item: re-run `00`, then `01` |
| Connection error in `00_…` | Check access to `raw.githubusercontent.com` |
| Dashboard "No data file" | Run the matching `01_…` or pass `--gi-data` / `--hsr-data` |
| `ModuleNotFoundError: matplotlib` | `pip install -r requirements.txt` |
| HSR has no Adventure Rank / UID | Expected: backup has neither |
| `git push` rejected | `git pull --rebase origin main`, then push |
| `credentials/` in `git status` | `.gitignore` is missing the rule |
| `private_key is not a real key yet` | Paste the full key from the JSON (one line, keep `\n`) |
| `403` / `SpreadsheetNotFound` | Share the Sheet with `client_email` as Editor; enable Sheets API |
| Sync prints `[SKIP]` | New data has fewer pulls; re-export full history or use `--force` |
| CI "No export found" | Add a Genshin or Star Rail export to `data/` |
| Streamlit Cloud install error | Avoid strict pins in `requirements.txt`; use `runtime.txt` |

## Changelog

- **Added:** Beginners banner in the GI dashboard Pity Meters (2×2 grid) and in GI Google Sheet tabs.
- **Changed:** dashboard layout: game picker in the sidebar, filters in a right panel, content in the middle; defaults are main account, all banners, full date range.
- **Added:** total labels on the Total Pulls chart; Inter / JetBrains Mono fonts in `.streamlit/config.toml`.
- **Added:** Honkai: Star Rail support, `game_configs.py`, per-game dashboard sections, CI game detection.
- **Changed:** Sheet tabs named `GI - <uid>` / `HSR - <account>`; Weapon Event hard pity is 80; "Compare Accounts" merged into "All accounts".

## Credits

- Genshin data from [Paimon.moe](https://github.com/MadeBaruna/paimon-moe); Star Rail data from [StarRailStation](https://starrailstation.com).
- Genshin Impact and Honkai: Star Rail are trademarks of HoYoverse/miHoYo. Independent, unaffiliated project.
