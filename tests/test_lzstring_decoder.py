"""The Star Rail backup decoder (own LZString implementation) against the reference lz-string library.

tests/fixtures/lzstring_cases.json was produced by the JavaScript lz-string package
(compressToUTF16), which is what StarRailStation uses to write the .dat file.
"""
import json
from pathlib import Path

import pytest

CASES = json.loads((Path(__file__).parent / "fixtures" / "lzstring_cases.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pre():
    from pipeline import preprocess
    return preprocess


def decompress(mod, body: str) -> str:
    return mod._lz_decompress(len(body), 16384, lambda i: ord(body[i]) - 32)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_decoder_matches_reference(pre, case):
    assert decompress(pre, case["compressed"]) == case["text"]


def test_decode_backup_reads_file(pre, tmp_path):
    mod = pre
    case = next(c for c in CASES if c["name"] == "backup_like")
    f = tmp_path / "starrailstation-backup_2026-01-01.dat"
    f.write_text("srs" + case["compressed"], encoding="utf-8")
    raw = mod.decode_backup(f)
    assert raw["profiles"]["4"]["name"] == "second"
    assert len(raw["data"]["stores"]["1_warp-v2"]["items_11"]) == 60


def test_decode_backup_rejects_wrong_header(pre, tmp_path):
    mod = pre
    f = tmp_path / "x.dat"
    f.write_text("xyz" + CASES[0]["compressed"], encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        mod.decode_backup(f)


def test_decode_backup_rejects_garbage(pre, tmp_path):
    mod = pre
    f = tmp_path / "x.dat"
    f.write_text("srs" + "!" * 40, encoding="utf-8")
    with pytest.raises(Exception):
        mod.decode_backup(f)


def test_decode_backup_joins_surrogate_pairs(pre, tmp_path, monkeypatch):
    """LZString yields UTF-16 code units: an emoji arrives as two surrogates and must be re-joined."""
    text = '{"profiles": {"1": {"name": "main \ud83d\ude00"}}}'   # emoji as a surrogate pair
    monkeypatch.setattr(pre, "_lz_decompress", lambda *a: text)
    f = tmp_path / "starrailstation-backup_2026-01-01.dat"
    f.write_text("srs-", encoding="utf-8")
    name = pre.decode_backup(f)["profiles"]["1"]["name"]
    assert name == "main \U0001F600"
    name.encode("utf-8")   # must not raise (to_csv would fail on lone surrogates)
