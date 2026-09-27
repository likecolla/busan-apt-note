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
    try:
        from busan_note import render
    except ImportError:
        return 0
    path = render.build()
    logging.info("페이지 생성: %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
