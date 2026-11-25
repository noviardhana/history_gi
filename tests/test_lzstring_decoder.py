"""The Star Rail backup decoder (own LZString implementation) against the reference lz-string library.

tests/fixtures/lzstring_cases.json was produced by the JavaScript lz-string package
(compressToUTF16), which is what StarRailStation uses to write the .dat file.
"""
import json
from pathlib import Path

import pytest

CASES = json.loads((Path(__file__).parent / "fixtures" / "lzstring_cases.json").read_text(encoding="utf-8"))


def decompress(mod, body: str) -> str:
    return mod._lz_decompress(len(body), 16384, lambda i: ord(body[i]) - 32)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_decoder_matches_reference(load_script, case):
    mod = load_script("02_preprocess_hsr.py")
    assert decompress(mod, case["compressed"]) == case["text"]


def test_decode_backup_reads_file(load_script, tmp_path):
    mod = load_script("02_preprocess_hsr.py")
    case = next(c for c in CASES if c["name"] == "backup_like")
    f = tmp_path / "starrailstation-backup_2026-01-01.dat"
    f.write_text("srs" + case["compressed"], encoding="utf-8")
    raw = mod.decode_backup(f)
    assert raw["profiles"]["4"]["name"] == "second"
    assert len(raw["data"]["stores"]["1_warp-v2"]["items_11"]) == 60


def test_decode_backup_rejects_wrong_header(load_script, tmp_path):
    mod = load_script("02_preprocess_hsr.py")
    f = tmp_path / "x.dat"
    f.write_text("xyz" + CASES[0]["compressed"], encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        mod.decode_backup(f)


def test_decode_backup_rejects_garbage(load_script, tmp_path):
    mod = load_script("02_preprocess_hsr.py")
    f = tmp_path / "x.dat"
    f.write_text("srs" + "!" * 40, encoding="utf-8")
    with pytest.raises(Exception):
        mod.decode_backup(f)
