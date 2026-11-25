
from pipeline.utils import mask_uid, same_uid


def test_same_uid_matches_masked_and_real_forms():
    assert same_uid("887284572", "88xxxxx72")
    assert same_uid("88xxxxx72", "887284572")
    assert same_uid(887284572, "887284572")
    assert not same_uid("887284572", "12xxxxx72")


def test_mask_uid_short_values_are_fully_masked():
    assert mask_uid("1234") == "xxxx"


def test_masked_gi_tab_is_found_after_masking_is_switched_on():
    from pipeline.config import GI
    from pipeline.sync_gsheet import find_renamed_gi_tab
    existing = {"GI - 887284572": object(), "HSR - Default": object(), "GI - 700123456": object()}
    assert find_renamed_gi_tab(existing, GI, "88xxxxx72", set()) == "GI - 887284572"
    assert find_renamed_gi_tab(existing, GI, "99xxxxx00", set()) is None
    assert find_renamed_gi_tab(existing, GI, "88xxxxx72", {"GI - 887284572"}) is None
