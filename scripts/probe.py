"""매매 API 1건 시험 호출: 응답 필드 이름과 예시 값을 보여 준다(키는 출력하지 않음)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from busan_note import api  # noqa: E402

kind = sys.argv[1] if len(sys.argv) > 1 else "trade"
lawd = sys.argv[2] if len(sys.argv) > 2 else "26350"
ym = sys.argv[3] if len(sys.argv) > 3 else api._recent_ym()
try:
    label, key = api.resolve_key()
    print(f"키 확인 OK — 동작한 방식: {label}")
    total, items = api.call(kind, lawd, ym, key, rows=1)
    print(f"{kind} {lawd} {ym}: totalCount={total}")
    for it in items[:1]:
        for k, v in it.items():
            print(f"  {k:<22} {v}")
except api.ApiError as e:
    print("실패:", api.mask(e))
    sys.exit(1)
