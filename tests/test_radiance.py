import pytest


@pytest.fixture(scope="module")
def rad(load_script):
    return load_script("03_radiance_check_gi.py")


def test_counter_transitions(rad):
    assert rad.next_counter(0, False, "reset") == 1
    assert rad.next_counter(3, False, "reset") == 3          # capped
    assert rad.next_counter(2, True, "reset") == 0
    assert rad.next_counter(2, True, "decrement") == 1
    assert rad.next_counter(0, True, "decrement") == 0


def test_expected_wins_follow_the_counter(rad):
    r = rad.run_model([False, False, True], "reset")           # k=0 (0.5), k=1 (0.5), k=2 (0.75)
    assert r["expected_model_pct"] == pytest.approx(100 * (0.5 + 0.5 + 0.75) / 3, abs=0.05)
    assert r["rolls_at_k0"] == 1 and r["rolls_at_k1"] == 1 and r["rolls_at_k2"] == 1


def test_loss_at_the_100_percent_state_is_impossible(rad):
    r = rad.run_model([False, False, False, False], "reset")
    assert r["impossible_losses"] == 1


def test_models_differ_after_a_win_at_a_high_counter(rad):
    seq = [False, False, True, False, False]
    assert rad.run_model(seq, "reset")["rolls_at_k0"] > rad.run_model(seq, "decrement")["rolls_at_k0"] - 1
    assert rad.run_model(seq, "reset")["rolls_at_k2"] != rad.run_model(seq, "decrement")["rolls_at_k2"]
