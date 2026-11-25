"""
Regenerates tests/fixtures/hsr_backup.dat (+ lookups) -- a small, FAKE StarRailStation backup used by the tests.

Needs the reference package:  pip install lzstring
Run from the project root:    python3 tests/fixtures/make_hsr_backup.py
Nothing here is real account data.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import lzstring

OUT = Path(__file__).parent
T0 = int(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)  # 2026-01-01 00:00 UTC = 07:00 Jakarta


def pulls(n, five, four, gacha_id, three_id=20000):
    """five/four: {pullNo: (itemId, result)}.  pity counters are computed like the game does."""
    out, p5, p4 = [], 0, 0
    for i in range(1, n + 1):
        p5 += 1
        p4 += 1
        if i in five:
            item, res, rarity = five[i][0], five[i][1], 5
            rec = dict(rarity=5, itemId=item, result=res, pity5=p5, pity4=p4)
            p5 = 0
        elif i in four:
            item, res, rarity = four[i][0], four[i][1], 4
            rec = dict(rarity=4, itemId=item, result=res, pity5=p5, pity4=p4)
            p4 = 0
        else:
            rec = dict(rarity=3, itemId=three_id, result=0, pity5=p5, pity4=p4)
        rec.update(pullNo=i, gachaId=gacha_id, timestamp=T0 + i * 60_000, uid=f"{gacha_id}-{i}", manual=False)
        out.append(rec)
    return out


raw = {
    "profiles": {"1": {"name": "Default"}, "2": {"name": "second"}, "3": {"name": "empty"}},
    "data": {"stores": {
        "1_warp-v2": {
            # 120 character-event warps: 5* at 30 (win), 85 (lose), 120 (guaranteed); a few 4*
            "items_11": pulls(120, {30: (1003, 2), 85: (1004, 4), 120: (1003, 3)},
                              {10: (1001, 2), 20: (1002, 4), 50: (1001, 3)}, 2001),
            # 20 light cone warps: 5* at 15 (win)
            "items_12": pulls(20, {15: (23001, 2)}, {5: (21001, 2)}, 3001),
        },
        "2_warp-v2": {"items_1": pulls(15, {12: (1003, 0)}, {}, 4001)},
        "3_warp-v2": {},
    }},
}
lookups = {
    "hsr_char_full.json": {"1001": {"name": "March 7th", "rarity": 4}, "1002": {"name": "Dan Heng", "rarity": 4},
                           "1003": {"name": "Himeko", "rarity": 5}, "1004": {"name": "Welt", "rarity": 5}},
    "hsr_lc_full.json": {"20000": {"name": "Arrows", "rarity": 3}, "21001": {"name": "Good Night", "rarity": 4},
                         "23001": {"name": "In the Night", "rarity": 5}},
}
(OUT / "hsr_backup.dat").write_text("srs" + lzstring.LZString().compressToUTF16(json.dumps(raw)), encoding="utf-8")
for name, data in lookups.items():
    (OUT / name).write_text(json.dumps(data, indent=1), encoding="utf-8")
print("written to", OUT)
