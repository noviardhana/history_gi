"""04_sync_gsheet (data shaping, no Google), analytics_core (all 7 insights) on fake data."""
import sys

import pandas as pd

import analytics_core
from config import GI, HSR


def test_sync_grid_and_tab_names_gi(sync_mod, gi_csv):
    df = sync_mod.load_clean(gi_csv)
    acc = df[df["account"] == "main"]
    grid, counts = sync_mod.build_account_grid(GI, acc, "main", "2026-01-01 00:00", include_3star=False)
    assert grid[sync_mod.ROW_META][3] == len(acc)                    # TOTAL_CELL D2 = total pulls
    assert len({len(r) for r in grid}) == 1                          # rectangular
    char_rows = counts[0]
    assert char_rows == int(((acc["banner_type"] == "Character Event") & (acc["rarity"] >= 4)).sum())
    first_data = grid[sync_mod.ROW_DATA]
    assert first_data[0] > 0 and first_data[3] in ("4★", "5★")       # newest first, only 4*/5*
    assert sync_mod.tab_title(GI, "main", sync_mod.uid_of(acc), set()) == "GI - 800000001"
    assert sync_mod.tab_title(GI, "main", "800000001", set(), gi_tab_name="account") == "GI - main"


def test_sync_tab_name_with_masked_uid(sync_mod, gi_pre, gi_csv, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["x", "--mask-uid"])
    gi_pre.main()
    df = sync_mod.load_clean(gi_csv)
    uids = {sync_mod.tab_title(GI, a, sync_mod.uid_of(df[df["account"] == a]), set()) for a in df["account"].unique()}
    assert uids == {"GI - 800***001", "GI - 800***002"}
    assert all(c not in "".join(uids) for c in ("800000001", "800000002"))


def test_sync_current_pity_and_hsr_grid(sync_mod, hsr_csv):
    df = sync_mod.load_clean(hsr_csv)
    char = df[(df["account"] == "Default") & (df["banner_type"] == "Character Event")].reset_index(drop=True)
    assert sync_mod.current_pity(char, 5) == 0          # the last warp (120) was a 5*
    assert sync_mod.current_pity(char, 4) == 70         # last 4* was warp 50 of 120
    grid, _ = sync_mod.build_account_grid(HSR, df[df["account"] == "Default"], "Default", "now")
    assert grid[sync_mod.ROW_META][0] == "Profile"
    assert sync_mod.tab_title(HSR, "Default", "", set()) == "HSR - Default"


def test_sync_dry_run_main(sync_mod, gi_csv, hsr_csv, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["x", "--dry-run", "--gi-csv", str(gi_csv), "--hsr-csv", str(hsr_csv)])
    sync_mod.main()
    out = capsys.readouterr().out
    assert "Tab 'GI - 800000001'" in out and "Tab 'HSR - Default'" in out


def test_analytics_writes_all_seven_insights(gi_csv, hsr_csv, tmp_path):
    for cfg, path in ((GI, gi_csv), (HSR, hsr_csv)):
        df = pd.read_csv(path)
        df["datetime"] = pd.to_datetime(df["datetime"])
        out = tmp_path / f"out_{cfg.key}"
        out.mkdir()
        analytics_core.run_all(df, out, cfg)
        names = {p.name for p in out.iterdir()}
        for n in ("01_total_pull_progress", "02_timeline", "03_pity_distribution_5star", "04_win_lose_50_50",
                  f"05_top_character_{cfg.gear_category}", "06_banner_performance", "07_luck_score"):
            assert f"{n}.png" in names, (cfg.key, n)
        assert "05_top_character.csv" in names and "07_luck_score.csv" in names
    luck = pd.read_csv(tmp_path / "out_HSR" / "07_luck_score.csv")
    assert set(luck["account"]) == {"Default", "second"}
