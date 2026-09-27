"""수집된 데이터에서 검색어가 들어간 단지명을 모두 찾아 보여 준다."""
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from busan_note import collect  # noqa: E402

TERMS = sys.argv[1:] or ["르엘", "리버파크", "써밋", "리미티드", "디아이엘", "드파인", "DEFINE",
                          "래미안아이파크", "레이카운티"]
recs = collect.load_all()
cnt = Counter()
for r in recs:
    name = r["apt"]
    if any(t.lower() in name.lower().replace(" ", "") or t.lower() in name.lower() for t in TERMS):
        cnt[(collect.LAWD.get(r["lawd"], r["lawd"]), r["umd"], name, r["aptSeq"], collect.KIND_KO[r["kind"]])] += 1
for (gu, umd, name, seq, kind), n in sorted(cnt.items()):
    print(f"{gu:<5} {umd:<6} {name:<24} {seq:<12} {kind:<4} {n}건")
