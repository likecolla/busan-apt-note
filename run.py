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


def _record_failure(kind, error):
    """이번 실행의 실패로 meta.json 을 새로 쓴다(이전 실행의 실패 목록은 지운다)."""
    import json
    from datetime import datetime
    meta_path = collect.DATA / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta.update(last_run=datetime.now(collect.KST).strftime("%Y-%m-%dT%H:%M"), new_count=0, baseline_kinds=[],
                failures=[{"kind": kind, "gu": "전체", "ym": "", "error": " ".join(str(error).split())[:160]}])
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


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


def collect_kosis():
    """KOSIS 미분양·공급·인구이동. 키가 없거나 실패해도 전체를 멈추지 않는다."""
    import json
    from busan_note import kosis
    meta_path = collect.DATA / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    try:
        fails = kosis.collect(log=logging.info)
    except kosis.KosisError as e:
        fails = [{"kind": "KOSIS", "gu": "전체", "ym": "", "error": kosis.mask(e)[:160]}]
        logging.warning("KOSIS 건너뜀: %s", kosis.mask(e))
    meta["failures"] = meta.get("failures", []) + fails
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def collect_extra():
    """청약홈 분양·경쟁률, K-apt 단지 정보. 실패해도 전체를 멈추지 않는다."""
    import json
    from busan_note import analyze, applyhome, kapt
    meta_path = collect.DATA / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fails = []
    try:
        fails += applyhome.collect(log=logging.info)
    except api.ApiError as e:
        fails.append({"kind": "청약홈", "gu": "부산", "ym": "", "error": api.mask(e)[:160]})
    try:
        cfg = analyze.load_config()
        fails += kapt.collect(cfg["complexes"] + cfg.get("reference", []), log=logging.info)
    except api.ApiError as e:
        fails.append({"kind": "공동주택 정보", "gu": "전체", "ym": "", "error": api.mask(e)[:160]})
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
            logging.info("수집 끝 — 새 거래 %d건, 실패 %d건", meta["new_count"], len(meta["failures"]))
        except api.ApiError as e:
            # 공공데이터포털 접속 실패: 실거래만 건너뛰고 나머지 자료와 페이지 생성은 계속한다.
            logging.error("실거래 수집 건너뜀: %s", api.mask(e))
            _record_failure("실거래(공공데이터포털)", api.mask(e))
        collect_reb()
        collect_kosis()
        collect_extra()
    try:
        from busan_note import render
    except ImportError:
        return 0
    path = render.build()
    logging.info("페이지 생성: %s", path)
    try:
        from busan_note import analyze, market
        market.record_month(analyze.build_context())
        logging.info("판단 기록 저장: data/monthly_log.json")
    except Exception as e:   # 기록 실패가 갱신 전체를 멈추지 않게
        logging.warning("판단 기록 건너뜀: %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
