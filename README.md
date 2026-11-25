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
│   ├── __main__.py              # `python -m pipeline ...`: one command for the whole pipeline
│   ├── config.py                # pity, soft pity, rate-up, banners, colours, sheet styles, project paths, timezone
│   ├── luck.py                  # Luck Score formula (pandas only; used by analytics_core.py and dashboard.py)
│   ├── analytics_core.py        # shared chart engine for the PNG reports
│   ├── lookup_utils.py          # safe download + validation for the lookup files
│   ├── logsetup.py              # logging used by the scripts (GitHub Actions annotations)
│   ├── 01_fetch_gi_lookup.py    # Genshin id -> name/rarity lookup
│   ├── 01_fetch_hsr_lookup.py   # Star Rail id -> name/rarity lookup
│   ├── 02_preprocess_gi.py      # Paimon.moe JSON  -> data/data_clean_gi.csv
│   ├── 02_preprocess_hsr.py     # StarRailStation  -> data/data_clean_hsr.csv
│   ├── 03_analytics_gi.py       # CSV -> outputs/gi/
│   ├── 03_analytics_hsr.py      # CSV -> outputs/hsr/
│   ├── 03_radiance_check_gi.py  # tests the Capturing Radiance counter model on your Genshin data
│   └── 04_sync_gsheet.py        # CSV -> Google Sheet (optional)
├── tests/                       # pytest suite (decoder, Luck Score, lookup parser, preprocessing, runner)
├── data/                        # exports, lookup JSON, data_clean_gi.csv, data_clean_hsr.csv
├── outputs/                     # generated charts + tables
│   ├── gi/
│   └── hsr/
├── credentials/                 # secret.toml (git-ignored)
├── requirements.txt / requirements-dev.txt   # run / run + tests
├── runtime.txt                  # Python version used by CI
└── .github/workflows/           # workflow (cml.yml)
```

File names follow the pipeline step: `01` fetch → `02` preprocess → `03` analytics → `04` sync. `_gi` / `_hsr` marks the game.

## Pipeline

```
Export → 01_fetch_*_lookup → 02_preprocess_* → data/data_clean_gi.csv / data_clean_hsr.csv
                                                    ├─► 03_analytics_*.py → outputs/gi, outputs/hsr
                                                    ├─► dashboard.py      (Streamlit)
                                                    └─► 04_sync_gsheet.py (Google Sheets, optional)
```

All stages in one command: `python -m pipeline all` (see Quick Start).

`pipeline/config.py` is the single place for pity, soft pity, rate-up chance, banners, colours, sheet styles, the project paths (`data/`, `outputs/`, `credentials/`) and the timezone (`DEFAULT_TZ`). The dashboard and the analytics both use the same `GameConfig` and the same Luck Score (`pipeline/luck.py`).

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

All commands run from the project root.

**Genshin:** export from paimon.moe (**Wish Counter → Export Data**) → save as `data/paimon-moe-local-data.json`

```bash
python3 pipeline/01_fetch_gi_lookup.py
python3 pipeline/02_preprocess_gi.py
```

**Star Rail:** export from StarRailStation → save as `data/starrailstation-backup_YYYY-MM-DD.dat`

```bash
python3 pipeline/01_fetch_hsr_lookup.py
python3 pipeline/02_preprocess_hsr.py
```

**Everything in one command**

```bash
python -m pipeline all                  # fetch -> preprocess -> analytics -> sync, for every game with an export in data/
python -m pipeline all --no-sync        # without the Google Sheets step
python -m pipeline preprocess --games gi   # one stage / one game (fetch | preprocess | analytics | sync)
python -m pipeline all --dry-run        # only print what would run
```

Games are detected from `data/` (`paimon-moe-local-data.json`, `starrailstation-backup_*.dat`) unless `--games gi,hsr` is given. With `all`, the sheet sync runs only when Google credentials exist (`credentials/secret.toml`, or `GSHEET_ID` + `GOOGLE_APPLICATION_CREDENTIALS`). A failing step stops the run. Options of single scripts (`--uid`, `--tz`, …) are used by calling the script directly, as shown above.

**Dashboard**

```bash
streamlit run dashboard.py
```

Fonts load from Google Fonts (`.streamlit/config.toml`), so the browser needs internet and a recent Streamlit version.

Python 3.9+. On Windows use `python` or `py`.

## Usage

| Step | Command | Output |
|---|---|---|
| 01 | `pipeline/01_fetch_gi_lookup.py` / `pipeline/01_fetch_hsr_lookup.py` | lookup JSON in `data/` |
| 02 | `pipeline/02_preprocess_gi.py` / `pipeline/02_preprocess_hsr.py` | `data/data_clean_gi.csv` / `data/data_clean_hsr.csv` |
| 03 | `pipeline/03_analytics_gi.py` / `pipeline/03_analytics_hsr.py` | `outputs/gi/` / `outputs/hsr/` |
| 03 | `pipeline/03_radiance_check_gi.py` | `outputs/gi/08_radiance_check.csv` (optional check, Genshin only) |
| 04 | `pipeline/04_sync_gsheet.py --preprocess` | Google Sheet |
| – | `python -m pipeline all` | all stages above |
| – | `python -m pytest` | unit tests |
| – | `streamlit run dashboard.py` | `http://localhost:8501` |

- **01 options:** `--force` (write the lookup even if it fails the sanity checks)
- **02 options:** Genshin `--list-uid`, `--uid`, `--source-tz`, `--tz`, `--keep-duplicates`, `--mask-uid`; Star Rail `--list-profile`, `--profile`, `--input`, `--tz`
- **03 options:** `--input`, `--outdir`; radiance check also `--start` (default 2024-08-28)
- **Dashboard custom files:** `streamlit run dashboard.py -- --gi-data <csv> --hsr-data <csv>`

### Safety checks

- **Tests:** `pip install -r requirements-dev.txt`, then `python -m pytest`. They cover the Star Rail backup decoder (checked against the JavaScript `lz-string` library), the Luck Score, the lookup parser and its validation, Genshin duplicate/timezone/UID-mask logic, the radiance model, game configs and the runner. CI runs them before anything else.
- **Lookup files (01):** a new download only replaces the existing JSON if it has enough items, did not shrink by more than 5%, and every item has a name and a rarity (1–5). Otherwise the old file is kept and the reason is printed. If there is no network, the existing file is kept too. The script only fails when there is no usable lookup file at all.
- **Timezone (02):** both games write `datetime` in `DEFAULT_TZ` (`pipeline/config.py`, default `Asia/Jakarta`). The Star Rail backup stores UTC timestamps and is converted. The Paimon.moe export has no timezone, so its timestamps are assumed to be in `--source-tz` (default: the same as `--tz`, so nothing is shifted). If your Genshin export was made in another timezone, pass `--source-tz`.
- **Duplicate pulls (02, Genshin):** Paimon.moe pulls have no unique id and every 3★ row has pity 1, so single rows can't be compared (a real 10-pull often contains the same item several times). What a merge of overlapping exports produces is a whole 10-pull twice, i.e. more than 10 rows in one second. Only such a block that is an exact repeat is cut back to one copy and `pull_number` is renumbered; anything else is only reported. Use `--keep-duplicates` to turn it off. (Star Rail drops duplicates by `pull_uid`.)

### Data file names

Cleaned CSVs are `data/data_clean_gi.csv` and `data/data_clean_hsr.csv` (per account/profile: `data_clean_gi_<uid>.csv`, `data_clean_hsr_<profile>.csv`). Genshin's file used to be `data/data_clean.csv`; scripts and the dashboard still read the old name if the new one doesn't exist yet. To migrate: run `02_preprocess_gi.py` (or `git mv data/data_clean.csv data/data_clean_gi.csv`), then remove the old file; CI does the removal itself (`git rm`).

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

Existing data is never deleted; a tab is skipped if the new export has fewer pulls. A tab is never cleared in place: the new content is written to a temporary tab (`~new <title>`) and swapped in only after it was written completely, so a quota or network error leaves the existing tab as it was. If any tab fails, the script exits with an error after trying the others. A leftover `~old <title>` tab means an earlier run was interrupted: check it and delete it by hand. Tab names contain the UID as written in the CSV: if you switch `--mask-uid` on, new tabs get the masked UID and the old `GI - <real uid>` tabs stay until you delete them.

## Automation (GitHub Actions)

`.github/workflows/cml.yml` runs on push of a new export, or manually. Each game runs only if its export exists. Steps: install (pip cached) → **tests** → detect exports → `python -m pipeline fetch` → `preprocess` → Google Sheets sync (optional) → `analytics` → dashboard smoke test (`dashboard.py`) → commit `data/` and `outputs/` → post a report (from `outputs/gi/` and `outputs/hsr/`) as a commit comment. Failing tests stop the run before any data is touched.

- Actions are pinned to a commit SHA (the tag is in a comment); update the SHA by hand to upgrade an action.
- Optional secrets: `GSHEET_ID`, `GCP_SERVICE_ACCOUNT_JSON` (without them the sync step is skipped).
- Optional repository variable: `GACHA_MASK_UID=1` masks the Genshin UID in `data_clean_gi.csv`.
- In a private repository the report links to the chart files instead of embedding them (`raw.githubusercontent.com` images only load for public repos).

**Update data**

```bash
git pull --rebase origin main
# replace/add the export in data/
git add data/ && git commit -m "update gacha data" && git push
```

## Security & Privacy

- Never commit the service-account key (`credentials/` is git-ignored).
- **UID:** the Paimon.moe export (`wish-uid`) and `data_clean_gi.csv` (`uid`) contain your Genshin UID, and it is used in Sheet tab names. The Star Rail backup has no UID. A UID is not a password but it identifies your account, so for a public repository either make the repository private (Streamlit Cloud can deploy private repos you own) or at least use `--mask-uid` / `GACHA_MASK_UID=1`.
- Masking only changes the output (`887284572` → `88xxxxx72`, more digits if two accounts would collide). It can't hide the UID in the raw export `data/paimon-moe-local-data.json`; that file stays readable in the repository.
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
| `python -m pipeline`: "No export found" | Put an export in `data/` or pass `--games gi` / `--games hsr` |
| Tests fail in CI | Run `python -m pytest -q` locally; the run stops before any data is changed |
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

- **Removed:** Dependabot (`.github/dependabot.yml`). Pinned action SHAs are now updated by hand.
- **Added:** `python -m pipeline` (one command for fetch → preprocess → analytics → sync); CI uses it instead of repeating every script.
- **Added:** pytest suite in `tests/` (Star Rail LZString decoder vs. the reference library, Luck Score, lookup parser + validation, Genshin preprocessing, radiance model, config, runner); CI runs it first.
- **Fixed:** `compute_luck` (Luck Score, also used by the dashboard) crashed on newer pandas when a selection had no 5★ Win/Lose rows (e.g. only Standard); regression tests added.
- **Fixed:** Genshin duplicate removal compared single rows, which would have removed real 3★ pulls (3★ rows always have pity 1). Now only a whole repeated 10-pull is removed. The lookup parser no longer lets an entry without rarity pick up its neighbour's.
- **Added:** `--mask-uid` / `GACHA_MASK_UID` for the Genshin UID; the CI report links to charts instead of embedding them in private repos.
- **Changed:** Genshin CSV `data_clean.csv` → `data_clean_gi.csv` (old name still read as a fallback). CI: pip cache, Actions pinned to SHA.
- **Changed:** scripts log through `pipeline/logsetup.py` (warnings/errors become GitHub Actions annotations).
- **Changed:** `analytics_core.py` now uses the `GameConfig` from `config.py` (the second copy was removed); the Luck Score moved to `pipeline/luck.py`, so the dashboard no longer loads matplotlib.
- **Added:** `pipeline/03_radiance_check_gi.py`: compares your Character Event 50/50 results with the Capturing Radiance counter model (reset vs decrement variant). The model comes from a community diagram and is not verified; the script reports how well it fits your data.
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
