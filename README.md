# Gacha Analytics: Genshin Impact & Honkai: Star Rail

Analytics, interactive dashboard, and auto-updating Google Sheet from your gacha history.

| Game | Source | Accounts |
|---|---|---|
| Genshin Impact | [Paimon.moe](https://paimon.moe) export (JSON) | one per UID |
| Honkai: Star Rail | [StarRailStation](https://starrailstation.com) backup (`.dat`) | one per profile |

**Live demo:** [mygacha-mihoyo.streamlit.app/](https://mygacha-mihoyo.streamlit.app/)

## Project Structure

```
.
├── dashboard.py                 # Streamlit dashboard
├── pipeline/                    # all data / analytics scripts
│   ├── config.py                # pity, soft pity, rate-up, banners, colours, sheet styles, project paths, timezone
│   ├── luck.py                  # Luck Score formula (pandas only; used by analytics_core.py and dashboard.py)
│   ├── analytics_core.py        # shared chart engine for the PNG reports
│   ├── lookup_utils.py          # safe download + validation for the lookup files
│   ├── run_all.py               # one command: tests → fetch → preprocess → analytics → (sync)
│   ├── 01_fetch_gi_lookup.py    # Genshin id -> name/rarity lookup
│   ├── 01_fetch_hsr_lookup.py   # Star Rail id -> name/rarity lookup
│   ├── 02_preprocess_gi.py      # Paimon.moe JSON  -> data/data_clean_gi.csv
│   ├── 02_preprocess_hsr.py     # StarRailStation  -> data/data_clean_hsr.csv
│   ├── 03_analytics_gi.py       # CSV -> outputs/gi/
│   ├── 03_analytics_hsr.py      # CSV -> outputs/hsr/
│   └── 04_sync_gsheet.py        # CSV -> Google Sheet (optional)
├── tests/                       # pytest (offline): decoder, Luck Score, parser, e2e preprocess, sync, analytics, dashboard
│   └── fixtures/                # FAKE HSR backup + lookups (make_hsr_backup.py regenerates them)
├── data/                        # exports, lookup JSON, data_clean_gi*.csv / data_clean_hsr*.csv
├── outputs/                     # generated charts + tables
│   ├── gi/
│   └── hsr/
└── credentials/                 # secret.toml (git-ignored)
```

File names follow the pipeline step: `01` fetch → `02` preprocess → `03` analytics → `04` sync. `_gi` / `_hsr` marks the game.

## Pipeline

```
Export → 01_fetch_*_lookup → 02_preprocess_* → data/data_clean_gi.csv, data/data_clean_hsr.csv
                                                    ├─► 03_analytics_*.py → outputs/gi, outputs/hsr
                                                    ├─► dashboard.py      (Streamlit)
                                                    └─► 04_sync_gsheet.py (Google Sheets, optional)
```

`pipeline/config.py` is the single place for pity, soft pity, rate-up chance, banners, colours, sheet styles, the project paths (`data/`, `outputs/`, `credentials/`), the clean-CSV file names (`CLEAN_CSV`, with a fallback to the old `data_clean.csv`) and the timezone (`DEFAULT_TZ`). The dashboard and the analytics both use the same `GameConfig` and the same Luck Score (`pipeline/luck.py`).

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
pip install -r requirements.txt -r requirements-dev.txt
```

All commands run from the project root. Put your export in `data/`:

- **Genshin:** paimon.moe (**Wish Counter → Export Data**) → `data/paimon-moe-local-data.json`
- **Star Rail:** StarRailStation backup → `data/starrailstation-backup_YYYY-MM-DD.dat`

Then one command does everything (tests → fetch lookup → preprocess → analytics) for every game that has an export:

```bash
python3 pipeline/run_all.py
```

The individual steps are listed under *Usage* below, if you want to run one of them alone.

**Dashboard**

```bash
streamlit run dashboard.py
```

Fonts load from Google Fonts (`.streamlit/config.toml`), so the browser needs internet and a recent Streamlit version.

Python 3.9+. On Windows use `python` or `py`.

## One command

```bash
python3 pipeline/run_all.py                          # pytest → fetch → preprocess → analytics
python3 pipeline/run_all.py --sync                   # ... and the Google Sheet
python3 pipeline/run_all.py --games hsr --skip-fetch --skip-tests
python3 pipeline/run_all.py --steps preprocess,analytics   # only these steps (this is what CI uses)
python3 pipeline/run_all.py --mask-uid               # hide the Genshin UID in data_clean_gi.csv
python3 pipeline/run_all.py --dry-run                # show the steps only
```

Steps: `tests`, `fetch`, `preprocess`, `analytics`, `sync` (always run in this order, stage by stage across games). The numbered scripts cannot be imported (names start with a digit), so the runner starts each as its own process and stops at the first failure. The order is defined only in `pipeline/run_all.py`; `cml.yml` calls it too.

## Tests

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```

All tests run offline on fake data (no real export needed):

- `test_lz_decoder.py`: the hand-written LZString decoder against vectors from the reference `lzstring` package (`tests/lz_vectors.json`), plus header / truncation errors.
- `test_luck.py`: Luck Score (pity 1 = 100, hard pity = 0, as-expected win rate = 50, 60/40 weights, re-weighting).
- `test_lookup.py`: the Genshin lookup parser (field order, neighbours, nested objects) and `lookup_utils` checks.
- `test_preprocess.py`: UID masking, id/rarity helpers, runner plan and steps, `CLEAN_CSV` names and legacy fallback.
- `test_e2e_preprocess.py`: fake Paimon.moe export and fake StarRailStation backup → `02_preprocess_*` → CSV (pity, 50-50 labels, duplicates, timezone, `--uid`, `--profile`, `--mask-uid`).
- `test_sync_analytics.py`: Google Sheet grid / tab names (incl. masked UID) and `--dry-run`; all 7 analytics insights for both games.
- `test_dashboard.py`: renders `dashboard.py` headlessly for both games with Streamlit's `AppTest` (skipped if streamlit / plotly are missing).

To regenerate the fixtures: `pip install lzstring`, then `python3 tests/fixtures/make_hsr_backup.py` (and rebuild `lz_vectors.json` from `compressToUTF16` if you want new vectors). `.github/workflows/tests.yml` runs the tests on every push / PR, and `cml.yml` runs them before it rebuilds any data.

## Usage

| Step | Command | Output |
|---|---|---|
| 01 | `pipeline/01_fetch_gi_lookup.py` / `pipeline/01_fetch_hsr_lookup.py` | lookup JSON in `data/` |
| 02 | `pipeline/02_preprocess_gi.py` / `pipeline/02_preprocess_hsr.py` | `data/data_clean_gi.csv` / `data/data_clean_hsr.csv` |
| 03 | `pipeline/03_analytics_gi.py` / `pipeline/03_analytics_hsr.py` | `outputs/gi/` / `outputs/hsr/` |
| 04 | `pipeline/04_sync_gsheet.py --preprocess` | Google Sheet |
| all | `pipeline/run_all.py` | steps 01–03 for every game with an export |
| – | `streamlit run dashboard.py` | `http://localhost:8501` |

- **01 options:** `--force` (write the lookup even if it fails the sanity checks)
- **02 options:** Genshin `--list-uid`, `--uid`, `--mask-uid`, `--source-tz`, `--tz`, `--keep-duplicates`; Star Rail `--list-profile`, `--profile`, `--input`, `--tz`
- **03 options:** `--input`, `--outdir`
- **Dashboard custom files:** `streamlit run dashboard.py -- --gi-data <csv> --hsr-data <csv>`

### Safety checks

- **Lookup files (01):** a new download only replaces the existing JSON if it has enough items, did not shrink by more than 5%, and every item has a name and a rarity (1–5). Otherwise the old file is kept and the reason is printed. If there is no network, the existing file is kept too. The script only fails when there is no usable lookup file at all.
- **Timezone (02):** both games write `datetime` in `DEFAULT_TZ` (`pipeline/config.py`, default `Asia/Jakarta`). The Star Rail backup stores UTC timestamps and is converted. The Paimon.moe export has no timezone, so its timestamps are assumed to be in `--source-tz` (default: the same as `--tz`, so nothing is shifted). If your Genshin export was made in another timezone, pass `--source-tz`.
- **Duplicate pulls (02, Genshin):** rows with the same account, banner, time, item, pity and rate are dropped and `pull_number` is renumbered. Rows without pity are never dropped, and if more than 5% of the rows would be removed nothing is dropped and a warning is shown. Use `--keep-duplicates` to turn it off. (Star Rail already drops duplicates by `pull_uid`.)

### Analytics output

Each insight writes a `<number>_<name>.csv` + `.png` pair:

| # | Insight | Files (in `outputs/gi/` or `outputs/hsr/`) |
|---|---|---|
| 01 | Total pull & account progress | `01_total_pull_progress` |
| 02 | Timeline | `02_timeline` |
| 03 | 5★ pity distribution | `03_pity_distribution_5star` (+ `_summary.csv`) |
| 04 | Win/Lose 50-50 | `04_win_lose_50_50` (+ `04_win_rate_summary.csv`) |
| 05 | Top character & weapon / light cone | `05_top_character`, `05_top_weapon` / `05_top_light_cone` (+ combined `.png`) |
| 06 | Banner performance | `06_banner_performance` |
| 07 | Luck score | `07_luck_score` |

## Google Sheets Sync

**Setup**
1. Create a Google Sheet, copy its ID (between `/d/` and `/edit`).
2. In Google Cloud Console: create a project, enable **Google Sheets API**.
3. Create a **service account** + **JSON key**.
4. Share the Sheet with the `client_email` as **Editor**.
5. Create `credentials/secret.toml` in the project root (git-ignored):

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
python3 pipeline/04_sync_gsheet.py --preprocess   # raw data → CSV → Sheet
python3 pipeline/04_sync_gsheet.py                # CSV → Sheet
python3 pipeline/04_sync_gsheet.py --games hsr    # one game (gi / hsr)
python3 pipeline/04_sync_gsheet.py --dry-run      # preview, no Google access
```

| Option | Effect |
|---|---|
| `--games gi,hsr` | games to sync (default: both) |
| `--gi-tab-name uid\|account` | Genshin tab naming |
| `--include-3star` | also list 3★ pulls |
| `--force` | overwrite even if new data has fewer pulls |
| `--sheet-id`, `--creds`, `--secrets`, `--csv`, `--hsr-csv` | path / ID overrides |

Existing data is never deleted; a tab is skipped if the new export has fewer pulls. A tab is never cleared in place: the new content is written to a temporary tab (`~new <title>`) and swapped in only after it was written completely, so a quota or network error leaves the existing tab as it was. If any tab fails, the script exits with an error after trying the others. A leftover `~old <title>` tab means an earlier run was interrupted: check it and delete it by hand.

## Automation (GitHub Actions)

`.github/workflows/cml.yml` runs on push of a new export, or manually. Each game runs only if its export exists. Steps: pytest → detect exports → privacy check → `run_all.py --steps fetch,preprocess` → Google Sheets sync (optional) → `run_all.py --steps analytics` → dashboard smoke test → commit `data/` and `outputs/` → post a report (from `outputs/gi/` and `outputs/hsr/`) as a commit comment. The first run after the file rename also removes the old `data/data_clean.csv` from git.

Optional secrets: `GSHEET_ID`, `GCP_SERVICE_ACCOUNT_JSON` (without them the sync step is skipped). Optional repository variable: `MASK_UID=true` (masks the Genshin UID in CI; see *Security*).

**Update data**

```bash
git pull --rebase origin main
# replace/add the export in data/
git add data/ && git commit -m "update gacha data" && git push
```

## Security

- Never commit the service-account key (`credentials/` is git-ignored).
- Exports and CSV contain your UID (Genshin only; the Star Rail backup has none). Check the repo visibility: the Streamlit Cloud demo normally needs a repo it can read, and a public repo exposes the UID. A UID is not a password, but it identifies your account.
- Options, from least to most change: keep the repo private; `python3 pipeline/02_preprocess_gi.py --mask-uid` (or `run_all.py --mask-uid`) writes `887***572` instead of the UID, which also changes the dashboard text and the Sheet tab to `GI - 887***572`; `04_sync_gsheet.py --gi-tab-name account` keeps the UID out of tab names. Masking is opt-in; the raw `paimon-moe-local-data.json` still contains the full UID, so do not commit it to a public repo either.
- In CI, set the repository **variable** `MASK_UID=true` (Settings → Secrets and variables → Actions → Variables) to mask the UID. If the repo is public and the UID is not masked, the *Privacy check* step prints a warning.
- The CI report embeds images from `raw.githubusercontent.com` for public repos. For a private repo it uses `github.com/<repo>/blob/<sha>/...?raw=true` instead, which signed-in people with access can see (raw.githubusercontent.com images do not render for private repos).
- If a key leaks, delete it in Google Cloud and create a new one.

## Troubleshooting

| Issue | Fix |
|---|---|
| `FileNotFoundError` for lookup | Run the matching `pipeline/01_…` script first |
| `N row(s) have no rarity / name mapping` | New item: re-run `01_fetch_*`, then `02_preprocess_*` |
| Connection error in `01_fetch_…` | Check access to `raw.githubusercontent.com`; the existing lookup file is kept |
| `[REJECTED] new lookup not written` | The download failed the sanity checks and the old file was kept. Check the source repo's format; `--force` writes it anyway |
| `possible duplicate pull(s) … NOTHING was dropped` | More than 5% looks duplicated; check the export (merged files?) |
| Dashboard "No data file" | Run the matching `02_preprocess_…` or pass `--gi-data` / `--hsr-data` |
| `ModuleNotFoundError: matplotlib` | `pip install -r requirements.txt` |
| `ModuleNotFoundError: pipeline` | Run `streamlit run dashboard.py` from the project root |
| HSR has no Adventure Rank / UID | Expected: backup has neither |
| `git push` rejected | `git pull --rebase origin main`, then push |
| `credentials/` in `git status` | `.gitignore` is missing the rule |
| `private_key is not a real key yet` | Paste the full key from the JSON (one line, keep `\n`) |
| `403` / `SpreadsheetNotFound` | Share the Sheet with `client_email` as Editor; enable Sheets API |
| Sync prints `[SKIP]` | New data has fewer pulls; re-export full history or use `--force` |
| CI "No export found" | Add a Genshin or Star Rail export to `data/` |
| Streamlit Cloud install error | Avoid strict pins in `requirements.txt`; use `runtime.txt` |
| Streamlit Cloud "file not found" | Set the app's main file path to `dashboard.py` |

## Changelog

- **Added:** `tests/` (pytest) for the LZString decoder, Luck Score, lookup parser and `lookup_utils`, plus `.github/workflows/tests.yml`.
- **Fixed:** `01_fetch_gi_lookup.parse_lookup` could give an item the name/rarity of the neighbouring entry; it now reads only the fields of the `{...}` block around each `id`.
- **Added:** `pipeline/run_all.py`, one command for tests → fetch → preprocess → analytics → sync.
- **Added:** `--mask-uid` for Genshin preprocessing (opt-in).
- **Changed:** the Genshin CSV is now `data/data_clean_gi.csv` (single-account files: `data_clean_gi_<uid>.csv`), matching `data_clean_hsr.csv`. Names are defined once (`CLEAN_CSV` in `config.py`); readers fall back to the old `data/data_clean.csv` until the new file exists, and CI removes the old file from git on its first run. If you rename it by hand: `git mv data/data_clean.csv data/data_clean_gi.csv`.
- **Changed:** `run_all.py` has `--steps`; `cml.yml` uses it instead of repeating the fetch / preprocess / analytics steps per game. README Quick Start points to it.
- **Added:** CI privacy check (`MASK_UID` variable, public-repo warning) and a private-repo-safe image link in the CI report.
- **Added:** end-to-end tests with fake exports (preprocess GI/HSR, sync grid, all analytics insights, dashboard render).

- **Changed:** `analytics_core.py` now uses the `GameConfig` from `config.py` (the second copy was removed); the Luck Score moved to `pipeline/luck.py`, so the dashboard no longer loads matplotlib.
- **Added:** `pipeline/lookup_utils.py`: lookup files are validated and written atomically; a failed or incomplete download no longer overwrites a good file.
- **Changed:** Google Sheets sync writes to a temporary tab and swaps it in, instead of clearing the existing tab first.
- **Added:** Genshin preprocessing: `--source-tz` / `--tz` (shared `DEFAULT_TZ` with Star Rail) and duplicate-pull removal (`--keep-duplicates` to disable).
- **Changed:** restructure: all scripts except the dashboard moved to `pipeline/`; files renamed by step (`01_fetch_*`, `02_preprocess_*`, `03_analytics_*`, `04_sync_gsheet.py`); `game_configs.py` → `pipeline/config.py` (now also holds project paths); `analytics_common.py` → `pipeline/analytics_core.py`; `03_dashboard.py` → `dashboard.py`.
- **Changed:** `.github/workflows/cml.yml` now calls the scripts in `pipeline/` and smoke-tests `dashboard.py`; `.streamlit/config.toml` is unchanged.
- **Changed:** analytics output folders `outputs/GI`, `outputs/HSR` → `outputs/gi`, `outputs/hsr`; `01_total_pull_progress_akun.*` → `01_total_pull_progress.*`; `02_timeline_wish.*` → `02_timeline.*`.
- **Added:** Beginners banner in the GI dashboard Pity Meters (2×2 grid) and in GI Google Sheet tabs.
- **Changed:** dashboard layout: game picker in the sidebar, filters in a right panel, content in the middle; defaults are main account, all banners, full date range.
- **Added:** total labels on the Total Pulls chart; Inter / JetBrains Mono fonts in `.streamlit/config.toml`.
- **Added:** Honkai: Star Rail support, `game_configs.py`, per-game dashboard sections, CI game detection.
- **Changed:** Sheet tabs named `GI - <uid>` / `HSR - <account>`; Weapon Event hard pity is 80; "Compare Accounts" merged into "All accounts".

## Credits

- Genshin data from [Paimon.moe](https://github.com/MadeBaruna/paimon-moe); Star Rail data from [StarRailStation](https://starrailstation.com).
- Genshin Impact and Honkai: Star Rail are trademarks of HoYoverse/miHoYo. Independent, unaffiliated project.
