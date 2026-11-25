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


def test_runner_builds_calls_per_game():
    calls = runner.build_calls("preprocess", ["gi", "hsr"])
    assert [argv for _, argv in calls] == [["--game", "gi"], ["--game", "hsr"]]
    sync = runner.build_calls("sync", ["gi", "hsr"])
    assert sync[0][1] == ["--games", "gi,hsr"]


@pytest.mark.parametrize("stage", sorted(runner.STAGE_MODULE))
def test_every_stage_module_has_main(stage):
    import importlib
    assert callable(importlib.import_module(f"pipeline.{runner.STAGE_MODULE[stage]}").main)


def test_runner_dry_run_lists_all_stages(capsys):
    assert runner.main(["all", "--games", "gi", "--no-sync", "--dry-run"]) == 0
    out = capsys.readouterr().out
    for cmd in ("fetch --game gi", "preprocess --game gi", "analytics --game gi"):
        assert cmd in out
    assert "pipeline sync" not in out


def test_runner_rejects_unknown_game():
    with pytest.raises(SystemExit):
        runner.main(["all", "--games", "xx", "--dry-run"])


def test_runner_without_exports_fails(monkeypatch, capsys):
    monkeypatch.setattr(runner, "detect_games", lambda: [])
    assert runner.main(["all", "--dry-run"]) == 1

def test_runner_turns_sys_exit_message_into_failure(monkeypatch, capsys):
    class Boom:
        @staticmethod
        def main(argv):
            raise SystemExit("no sheet id")
    monkeypatch.setattr("importlib.import_module", lambda name: Boom)
    assert runner.run_stage("sync", []) == 1
    assert "no sheet id" in capsys.readouterr().err


def test_sync_credentials_accept_json_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "CREDENTIALS_DIR", tmp_path)
    monkeypatch.setenv("GSHEET_ID", "abc")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", "{}")
    assert runner.has_sync_credentials()
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON")
    assert not runner.has_sync_credentials()
