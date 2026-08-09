# Genshin Impact Gacha Analytics

A data pipeline that turns Genshin Impact wish (gacha) history — exported from [Paimon.moe](https://paimon.moe) — into analytics and an interactive dashboard.

**Live demo:** [gacha-gi-noviardhana.streamlit.app](https://gacha-gi-noviardhana.streamlit.app)

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
```

## Features

- Total pulls and account progress by rarity, Adventure Rank, and World Level
- Monthly wish timeline by banner
- 5★ pity distribution per banner
- 50/50 win rate breakdown
- Top characters and weapons obtained
- Banner performance comparison (pulls-per-5★, win rate)
- Composite luck score (60% pity efficiency + 40% win rate)
- Interactive dashboard with account/date/banner filters, multi-account comparison, and CSV export

## Project Structure

```
.
├── 00_fetch_rarity_lookup.py
├── 01_preprocessing.py
├── 02_analytics.py
├── 03_dashboard.py
├── requirements.txt
├── runtime.txt
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

## Usage

Run the pipeline in order.

### 1. Fetch rarity lookup

The Paimon.moe export only contains item IDs, timestamps, type, and pity — no names or rarity. This step pulls a reference table from Paimon.moe's GitHub source into `data/char_full.json` and `data/weapon_full.json`. Requires internet access to `raw.githubusercontent.com`. Re-run to refresh after new character/weapon releases.

```bash
python3 00_fetch_rarity_lookup.py
```

### 2. Preprocess

Merges the raw export with the rarity lookup into one tidy table (one row per pull).

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

```bash
python3 02_analytics.py
python3 02_analytics.py --input data/data_clean_887284572.csv --outdir outputs_887284572
```

### 4. Run the dashboard

An interactive Streamlit dashboard with account selection, date/banner filters, 7 insight tabs, multi-account comparison, and CSV export. Reads `data_clean.csv` directly — not part of the automated pipeline.

```bash
streamlit run 03_dashboard.py
# or for a specific account:
streamlit run 03_dashboard.py -- --data data/data_clean_887284572.csv
```

Open `http://localhost:8501`, or use the hosted version at [https://history-gi-noviardhana.streamlit.app/](https://history-gi-noviardhana.streamlit.app/).

## Troubleshooting

| Issue | Fix |
|---|---|
| `FileNotFoundError: Lookup rarity belum ada` | Run `00_fetch_rarity_lookup.py` before `01_preprocessing.py`. |
| `[WARN] N baris tidak punya mapping rarity` | Export contains item IDs not yet in the Paimon.moe lookup (usually a newly released character/weapon). Re-run `00_fetch_rarity_lookup.py`, then re-run preprocessing. |
| Dashboard can't find data | Ensure `data/data_clean.csv` exists (run step 1), or pass a path with `-- --data <path>`. |
| Connection error in `00_fetch_rarity_lookup.py` | Check access to `raw.githubusercontent.com` (proxies/firewalls sometimes block it). |
| Streamlit Cloud install error (`installer returned a non-zero exit code`) | Avoid strict version pins in `requirements.txt`; pin Python version via `runtime.txt` instead. |

## Credits

- Character and weapon name/rarity reference data sourced from [Paimon.moe](https://github.com/MadeBaruna/paimon-moe) (`src/data/characters.js`, `src/data/weaponList.js`).
- Genshin Impact is a trademark of HoYoverse/miHoYo. This is an independent, unaffiliated personal-data analysis tool.