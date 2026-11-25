"""Small pure helpers in the preprocess scripts, the runner plan and the config table."""
import config
import pytest
import run_all


def test_mask_uid(gi_pre):
    assert gi_pre.mask_uid("887284572") == "887***572"
    assert gi_pre.mask_uid(887284572) == "887***572"
    assert gi_pre.mask_uid(887284572.0) == "887***572"
    assert gi_pre.mask_uid("12345") == "12345"      # too short to hide anything
    assert gi_pre.mask_uid(None) is None


def test_rarity_and_name_coerces_int_ids(gi_pre):
    assert gi_pre.rarity_and_name(10000046, "character", {"10000046": {"name": "Hu Tao", "rarity": 5}}, {}) == (5, "Hu Tao")
    assert gi_pre.rarity_and_name("nope", "weapon", {}, {}) == (None, None)


def test_hsr_item_info_and_pity(hsr):
    chars, lcs = {"1003": {"name": "Himeko", "rarity": 5}}, {"23001": {"name": "LC", "rarity": 5}}
    assert hsr.item_info(1003, chars, lcs) == ("character", "Himeko", 5)
    assert hsr.item_info(23001, chars, lcs) == ("light_cone", "LC", 5)
    assert hsr.item_info(29999, chars, lcs) == ("light_cone", None, None)   # unknown 5-digit id
    assert hsr.pity_for_rarity({"rarity": 5, "pity5": 73, "pity4": 2}) == 73
    assert hsr.pity_for_rarity({"rarity": 4, "pity5": 73, "pity4": 2}) == 2
    assert hsr.pity_for_rarity({"rarity": 3, "pity5": 73}) is None


def test_hsr_rate_labels_and_profiles(hsr):
    assert hsr.RATE_LABELS == {2: "Win", 3: "Guaranteed", 4: "Lose"}
    raw = {"profiles": {"1": {"name": "Default"}, "2": {"name": "empty"}},
           "data": {"stores": {"1_warp-v2": {"items_1": []}}}}
    assert list(hsr.build_profile_map(raw)) == ["1"]


def test_clean_csv_table_matches_games():
    assert set(config.CLEAN_CSV) == set(config.GAMES)


def test_run_all_plan_order_and_flags():
    plan = run_all.build_plan(["GI", "HSR"], run_all.DEFAULT_STEPS + ("sync",), mask_uid=True)
    labels = [l for l, _ in plan]
    assert labels[0] == "tests" and labels[-1] == "sync Google Sheet"
    assert labels.index("GI fetch") < labels.index("GI preprocess") < labels.index("GI analytics")
    assert labels.index("HSR preprocess") < labels.index("GI analytics")   # stage by stage, not game by game
    assert "--mask-uid" in dict(plan)["GI preprocess"] and "--mask-uid" not in dict(plan)["HSR preprocess"]
    assert "--preprocess" not in dict(plan)["sync Google Sheet"]


def test_run_all_steps_order_is_canonical_and_validated():
    labels = [l for l, _ in run_all.build_plan(["HSR"], ("analytics", "preprocess"))]
    assert labels == ["HSR preprocess", "HSR analytics"]
    with pytest.raises(ValueError):
        run_all.build_plan(["GI"], ("nope",))


def test_run_all_resolve_steps_flags():
    assert run_all.resolve_steps(None, False, False, False, False) == run_all.DEFAULT_STEPS
    assert "sync" in run_all.resolve_steps(None, True, False, False, False)
    assert run_all.resolve_steps(None, False, True, True, True) == ("preprocess",)
    assert run_all.resolve_steps("fetch,preprocess", False, False, True, False) == ("preprocess",)


def test_clean_csv_names_and_legacy_fallback(tmp_path, monkeypatch, capsys):
    assert config.CLEAN_CSV["GI"].name == "data_clean_gi.csv" and config.CLEAN_CSV["HSR"].name == "data_clean_hsr.csv"
    assert config.clean_csv_variant("GI", "887").name == "data_clean_gi_887.csv"
    assert config.clean_csv_variant("HSR", "second").name == "data_clean_hsr_second.csv"
    new, old = tmp_path / "data_clean_gi.csv", tmp_path / "data_clean.csv"
    monkeypatch.setitem(config.CLEAN_CSV, "GI", new)
    monkeypatch.setitem(config.LEGACY_CLEAN_CSV, "GI", old)
    assert config.resolve_clean_csv("GI") == new          # nothing exists -> the new name (writers/errors use it)
    old.write_text("x")
    assert config.resolve_clean_csv("GI") == old          # only the legacy file exists -> reader falls back
    new.write_text("x")
    assert config.resolve_clean_csv("GI") == new          # the new file always wins
    assert config.resolve_clean_csv("HSR") == config.CLEAN_CSV["HSR"]
