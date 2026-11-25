"""End-to-end: fake exports -> 02_preprocess_* main() -> CSV. No network, no real data."""
import sys

import pandas as pd

from conftest import FIXTURES


def test_hsr_end_to_end(hsr_csv):
    df = pd.read_csv(hsr_csv)
    # profile 3 has an empty store, so only "Default" (140 warps) and "second" (15) remain
    assert len(df) == 120 + 20 + 15
    assert set(df["account"]) == {"Default", "second"}
    char = df[(df["account"] == "Default") & (df["banner_type"] == "Character Event")]
    five = char[char["is_5star"]].sort_values("pull_number")
    assert list(five["item_name"]) == ["Himeko", "Welt", "Himeko"]
    assert list(five["pity"]) == [30, 55, 35]
    assert list(five["win_50_50"]) == ["Win", "Lose", "Guaranteed"]
    lc = df[df["banner_type"] == "Light Cone Event"]
    assert lc[lc["is_5star"]].iloc[0]["item_category"] == "light_cone"
    assert df[df["banner_type"] == "Standard"]["win_50_50"].isna().all()   # no 50-50 on the standard banner
    # 2026-01-01 00:01 UTC must become 07:01 Asia/Jakarta
    first = char.sort_values("pull_number").iloc[0]
    assert str(first["datetime"]).startswith("2026-01-01 07:01")
    assert df["pull_uid"].is_unique


def test_hsr_profile_filter_writes_separate_file(hsr, tmp_path, monkeypatch):
    import shutil

    for name in ("hsr_char_full.json", "hsr_lc_full.json"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    monkeypatch.setattr(hsr, "DATA_DIR", tmp_path)
    monkeypatch.setattr(hsr, "CHAR_LOOKUP_PATH", tmp_path / "hsr_char_full.json")
    monkeypatch.setattr(hsr, "LC_LOOKUP_PATH", tmp_path / "hsr_lc_full.json")
    monkeypatch.setattr(hsr, "clean_csv_variant", lambda k, s: tmp_path / f"data_clean_hsr_{s}.csv")
    monkeypatch.setattr(sys, "argv", ["x", "--input", str(FIXTURES / "hsr_backup.dat"), "--profile", "second"])
    hsr.main()
    df = pd.read_csv(tmp_path / "data_clean_hsr_second.csv")
    assert set(df["account"]) == {"second"} and len(df) == 15


def test_gi_end_to_end(gi_csv):
    df = pd.read_csv(gi_csv, dtype={"uid": str})
    assert set(df["account"]) == {"main", "alt"}
    main = df[df["account"] == "main"]
    assert len(main[main["banner_type"] == "Character Event"]) == 40          # the duplicate pull was dropped
    assert list(main[main["is_5star"]].sort_values("pull_number")["win_50_50"]) == ["Win", "Lose", "Guaranteed"]
    assert main["uid"].iloc[0] == "800000001"
    alt = df[df["account"] == "alt"].iloc[0]
    assert alt["item_name"] == "Staff of Homa" and alt["rarity"] == 5 and alt["win_50_50"] == "Win"
    assert df["pull_number"].min() == 1


def test_gi_mask_uid_and_uid_filter(gi_pre, gi_csv, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["x", "--mask-uid", "--uid", "800000002"])
    gi_pre.main()
    out = tmp_path / "data_clean_gi_800000002.csv"          # the real UID selects the account ...
    df = pd.read_csv(out, dtype={"uid": str})
    assert set(df["account"]) == {"alt"}
    assert set(df["uid"]) == {"800***002"}                  # ... but only the masked one is written
    assert "800000002" not in out.read_text()
