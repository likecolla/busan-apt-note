"""부산 대단지 실거래 노트 — 수집 + 페이지 생성.

사용법:
  python run.py             # 수집(첫 실행 6개월, 이후 3개월) 후 site/index.html 생성
  python run.py --no-fetch  # 수집 없이 페이지만 다시 생성
  python run.py --months 6  # 수집 개월 수 지정
  python run.py --months 60 --backfill  # 과거 자료 채우기(새로 신고된 거래로 세지 않음)
"""
import argparse
import logging
import sys

from busan_note import api, collect


def collect_reb():
    """부동산원 주간 지수. 키가 없거나 실패해도 전체를 멈추지 않는다."""
    import json
    from busan_note import reb
    meta_path = collect.DATA / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    try:
        fails = reb.collect_weekly(log=logging.info)
    except reb.RebError as e:
        fails = [{"kind": "부동산원 주간 지수", "gu": "전체", "ym": "", "error": reb.mask(e)[:160]}]
        logging.warning("부동산원 주간 지수 건너뜀: %s", reb.mask(e))
    meta["failures"] = meta.get("failures", []) + fails
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--months", type=int)
    ap.add_argument("--backfill", action="store_true")
    args = ap.parse_args()
    (api.ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(api.ROOT / "logs" / "run.log", encoding="utf-8")])
    if not args.no_fetch:
        try:
            meta = collect.run_collect(months=args.months, backfill=args.backfill)
        except api.ApiError as e:
            logging.error("수집 중단: %s", api.mask(e))
            return 1
        logging.info("수집 끝 — 새 거래 %d건, 실패 %d건", meta["new_count"], len(meta["failures"]))
        collect_reb()
    try:
        from busan_note import render
    except ImportError:
        return 0
    path = render.build()
    logging.info("페이지 생성: %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
