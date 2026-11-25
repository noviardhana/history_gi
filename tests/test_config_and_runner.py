from pathlib import Path

import pytest

from pipeline import __main__ as runner
from pipeline.config import GAMES


@pytest.mark.parametrize("key", sorted(GAMES))
def test_game_config_is_consistent(key):
    cfg = GAMES[key]
    banners = set(cfg.banner_order)
    assert banners <= set(cfg.hard_pity), "every banner needs a hard pity"
    assert banners <= set(cfg.banner_colors), "every banner needs a colour"
    assert set(cfg.rateup_chance) <= banners
    assert set(cfg.expected_rate_5) <= banners
    assert set(cfg.soft_pity) <= banners
    assert set(cfg.pity_card_banners) <= banners
    assert set(cfg.sheet_banners) <= banners
    assert set(cfg.sheet_banners) <= set(cfg.sheet_banner_style)
    for banner, soft in cfg.soft_pity.items():
        assert soft < cfg.hard_pity[banner]


def test_runner_builds_commands_per_game():
    cmds = runner.build_commands("preprocess", ["gi", "hsr"])
    assert [Path(c[1]).name for c in cmds] == ["02_preprocess_gi.py", "02_preprocess_hsr.py"]
    sync = runner.build_commands("sync", ["gi", "hsr"])
    assert sync[0][-2:] == ["--games", "gi,hsr"]


def test_runner_dry_run_lists_all_stages(capsys):
    assert runner.main(["all", "--games", "gi", "--no-sync", "--dry-run"]) == 0
    out = capsys.readouterr().out
    for script in ("01_fetch_gi_lookup.py", "02_preprocess_gi.py", "03_analytics_gi.py"):
        assert script in out
    assert "04_sync_gsheet.py" not in out


def test_runner_rejects_unknown_game():
    with pytest.raises(SystemExit):
        runner.main(["all", "--games", "xx", "--dry-run"])


def test_runner_without_exports_fails(monkeypatch, capsys):
    monkeypatch.setattr(runner, "detect_games", lambda: [])
    assert runner.main(["all", "--dry-run"]) == 1