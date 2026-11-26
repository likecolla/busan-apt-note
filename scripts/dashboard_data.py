"""종합 대시보드(부산 시장 대시보드)에 올릴 데이터 파일 15개를 만든다.

사용: python scripts/dashboard_data.py <출력 폴더> [이번 주 시작 YYYY-MM-DD] [끝]
주를 주지 않으면 실거래 갱신일 기준으로 끝난 가장 최근 목~수 주를 쓴다.
파일마다 {"rows": [...], "meta": [...]} JSON. 숫자는 모두 저장소 데이터에서 계산한다.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from busan_note import analyze, charts, collect, market, reb  # noqa: E402
from busan_note.money import pyeong_type  # noqa: E402

GU_SHORT = {"26350": "해운대", "26500": "수영", "26290": "남구", "26230": "부산진", "26260": "동래", "26470": "연제"}
REGION_OF = {g: r for r, gs in market.REGIONS.items() for g in gs}


def r2(x, d=2):
    return None if x is None else round(x, d)


def last_week(last_run):
    """last_run 날짜 기준으로 끝난 가장 최근 목~수 주."""
    d = date.fromisoformat(last_run[:10])
    end = d - timedelta(days=(d.weekday() - 2) % 7 or 7)   # 직전 수요일(오늘이 수요일이면 지난주)
    return (end - timedelta(days=6)).isoformat(), end.isoformat()


def build(start=None, end=None):
    ctx = analyze.build_context()
    recs = collect.load_all()
    kosis = market.load_kosis()
    cfg = market.load_market_cfg()
    cmp_items = reb.weekly_summary(reb.COMPARE_OUT) or []
    have = [r for r in cmp_items if len(r["series"]) >= 60]
    last_run = ctx["meta"].get("last_run", "")
    if not start:
        start, end = last_week(last_run)
    reb_rows = ctx["reb"]
    busan = next(r for r in reb_rows if r["name"] == "부산")
    asof = busan["date"]
    src_reb = {"label": "출처", "value": "한국부동산원 R-ONE 주간 아파트 가격지수(Open API)"}
    src_rt = {"label": "출처", "value": "국토교통부 아파트 매매 실거래가(공공데이터포털 Open API)"}
    out = {}

    # 1. 주간 지수 (최근 2년)
    rows = []
    for it in [r for r in reb_rows if r["name"] in ("부산", "중부산권", "동부산권", "서부산권")] + \
              [r for r in have if r["name"] == "서울"]:
        for _, d, s, j in it["series"][-104:]:
            rows.append({"week": d, "region": it["name"], "sale": r2(s, 3), "jeonse": r2(j, 3)})
    out["index_weekly"] = {"rows": rows, "meta": [src_reb, {"label": "기준", "value": "주간 매매·전세 가격지수, 최근 104주"}]}

    # 2. 구별 최신 주간 변동
    rows = []
    for it in reb_rows:
        if it["level"] != 3:
            continue
        rows.append({"gu": it["name"], "region": REGION_OF.get(it["name"], ""), "week": it["date"],
                     "sale_wk": it["sale_wk"], "sale_ytd": it["sale_ytd"],
                     "sale_streak": f"{it['sale_streak'][1]}주 {it['sale_streak'][0]}",
                     "jeonse_wk": it["jeonse_wk"], "jeonse_ytd": it["jeonse_ytd"],
                     "jeonse_streak": f"{it['jeonse_streak'][1]}주 {it['jeonse_streak'][0]}",
                     "mine": it["name"] in ("해운대구", "수영구", "남구", "부산진구", "동래구", "연제구")})
    rows.sort(key=lambda r: -(r["sale_wk"] or 0))
    out["gu_weekly"] = {"rows": rows, "meta": [src_reb, {"label": "기준", "value": f"{asof} 조사, 주간 변동률(%)·올해 누계(%)"}]}

    # 3. 부산 전체 요약 한 줄
    b = busan
    out["busan_now"] = {"rows": [{"week": b["date"], "sale_wk": b["sale_wk"], "sale_streak_n": b["sale_streak"][1],
                                  "sale_streak_dir": b["sale_streak"][0], "jeonse_wk": b["jeonse_wk"],
                                  "jeonse_streak_n": b["jeonse_streak"][1], "jeonse_streak_dir": b["jeonse_streak"][0],
                                  "sale_ytd": b["sale_ytd"], "jeonse_ytd": b["jeonse_ytd"]}], "meta": [src_reb]}

    # 4. 시장 판단 포인트
    pts = market.points(ctx, kosis, cfg)
    grade = {"g1": "실거래", "g2": "공식 통계", "g3": "보도"}
    out["points"] = {"rows": [{"point": n, "detail": t, "verdict": v, "grade": grade[g]} for n, t, v, g in pts],
                     "meta": [{"label": "기준", "value": "busan_note/market.py: 다섯 중 셋 이상 '있음'이면 상승 쪽, 셋 이상 '반대'면 하락 쪽"},
                              {"label": "기준금리", "value": f"config/market.json 손으로 적는 값({cfg.get('base_rate', {}).get('asof', '')} 기준)"}]}

    # 5. 권역
    rows = []
    for r in market.region_rows(reb_rows, kosis):
        p = r["pos"]
        rows.append({"region": r["name"], "sub": r["sub"], "ch26": r2(p["ch26"]), "state": p["state"],
                     "vs_peak": r2(p["vs_peak"], 1), "now": r2(p["now"], 1), "low": r2(p["low"], 1),
                     "unsold": r["unsold"], "unsold_yago": r["unsold_yago"], "done": r["done"], "mig12": r["mig12"]})
    out["regions"] = {"rows": rows, "meta": [src_reb, {"label": "출처", "value": "통계청 KOSIS(미분양, 인구이동) Open API"},
                                             {"label": "기준", "value": "26주 변동 +0.5% 이상 회복, −0.5% 이하 하락, 그 사이 보합"}]}

    # 6. 미분양 월별(부산)
    u = kosis.get("unsold", {}).get("부산", {})
    dn = kosis.get("unsold_done", {}).get("부산", {})
    out["unsold_monthly"] = {"rows": [{"month": f"{k[:4]}-{k[4:]}", "unsold": u[k], "done": dn.get(k)} for k in sorted(u)[-24:]],
                             "meta": [{"label": "출처", "value": "통계청 KOSIS 미분양주택현황(국토교통부)"}]}

    # 7. 격차
    rows = []
    sp = market.spread_rows(reb_rows, "부산", market.UPPER + ["서부산권"], group=("상급지 4개 구 평균", market.UPPER))
    for r in sp:
        rows.append({"name": "부산 전체" if r["name"] == "부산" else r["name"], "group": "부산",
                     "ch52": r2(r["ch52"]), "ch13": r2(r["ch13"]), "gap": r2(r["gap"], 1), "gap_prev": r2(r["gap_prev"], 1),
                     "trend": "" if r["name"] == "부산" else market.spread_trend(r["gap"], r["gap_prev"]),
                     "vs_peak": r2(r["vs_peak"], 1)})
    seoul_names = [n for n in market.SEOUL_ROWS if n in {r["name"] for r in have}]
    if "서울" in seoul_names:
        for r in market.spread_rows(list(reb_rows) + have, "부산", seoul_names)[1:]:
            rows.append({"name": r["name"], "group": "서울", "ch52": r2(r["ch52"]), "ch13": r2(r["ch13"]),
                         "gap": r2(r["gap"], 1), "gap_prev": r2(r["gap_prev"], 1),
                         "trend": market.spread_trend(r["gap"], r["gap_prev"]), "vs_peak": r2(r["vs_peak"], 1)})
    out["spread"] = {"rows": rows, "meta": [src_reb, {"label": "기준", "value": "최근 52주 매매지수 변동에서 부산 전체의 변동을 뺀 값(%p), 반년 전은 같은 계산을 26주 전에 한 값"}]}

    # 8. 판단 기록
    rows = []
    for h in market.history_rows(reb_rows, have, months=12):
        lg = h["log"] or {}
        c = lg.get("count", {})
        rows.append({"month": h["month"], "asof": h["asof"], "state": h["state"], "ch26": r2(h["ch26"]),
                     "lean": lg.get("lean", ""), "yes": c.get("있음"), "mid": c.get("애매"), "no": c.get("반대"),
                     "upper_gap": r2(h["upper_gap"], 1), "seoul_gap": r2(h["seoul_gap"], 1)})
    out["history"] = {"rows": rows, "meta": [src_reb, {"label": "기준", "value": "달마다 마지막 조사 주로 다시 계산. 포인트 판정은 data/monthly_log.json(2026. 9.부터)"}]}

    # 9. 핵심 단지
    rows = []
    for c in ctx["cards"]:
        l, pk = c.get("latest84"), c.get("peak")
        rows.append({"name": c["name"], "gu": c["gu"], "kind": c["kind_ko"], "med3": c["med3"], "n3": c["n3"],
                     "few": bool(c.get("low_sample")),
                     "peak": pk["price"] if pk else None, "peak_date": pk["date"] if pk else None,
                     "to_peak": r2(c["med3"] / pk["price"] * 100, 1) if c["med3"] and pk else None,
                     "ppy3_man": round(c["ppy3"] / 10000) if c["ppy3"] else None,
                     "yoy": r2(c["yoy"] * 100, 1) if c.get("yoy") is not None else None,
                     "latest": l["price"] if l else None, "latest_date": l["date"] if l else None,
                     "latest_floor": l.get("floor") if l else None})
    out["core"] = {"rows": rows, "meta": [src_rt, {"label": "기준", "value": f"{last_run[:10]} 기준. 84㎡형 = 전용 75~90㎡, 해제 거래 제외, 최근 3개월 중간값, 최고가는 최근 5년. 3.3㎡당은 전용면적 기준"}]}

    # 10. 주별 거래 건수
    trades = [r for r in recs if r["kind"] == "trade" and not r["cancelled"]]
    e = date.fromisoformat(end)
    rows = []
    for i in range(11, -1, -1):
        b_ = e - timedelta(days=7 * i)
        a_ = b_ - timedelta(days=6)
        cnt = sum(1 for r in trades if a_.isoformat() <= r["date"] <= b_.isoformat())
        rows.append({"week_start": a_.isoformat(), "week_end": b_.isoformat(), "count": cnt,
                     "partial": (date.fromisoformat(last_run[:10]) - b_).days < 30})
    out["weekly_trades"] = {"rows": rows, "meta": [src_rt, {"label": "기준", "value": f"관심 6개 구 매매, 해제 제외, 계약일 목~수 주. {last_run[:10]}까지 신고분(30일 안에 늘어남)"}]}

    # 11. 이번 주 상위 거래
    wk = sorted([r for r in trades if start <= r["date"] <= end], key=lambda r: -(r["price"] or 0))[:10]
    out["top_trades"] = {"rows": [{"rank": i + 1, "gu": GU_SHORT.get(r["lawd"], r["lawd"]), "dong": r["umd"], "apt": r["apt"],
                                   "date": r["date"], "area": r["area"], "pyeong": pyeong_type(r["area"]), "floor": r["floor"],
                                   "price": r["price"], "direct": bool(r["direct"])} for i, r in enumerate(wk)],
                         "meta": [src_rt, {"label": "기준", "value": f"{start}~{end} 계약, 금액 순 10건, {last_run[:10]}까지 신고분"}]}

    # 12~15. 차트용(공부노트·특별호와 같은 busan_note/charts.py 데이터 함수)
    mine = {"해운대구", "수영구", "남구", "부산진구", "동래구", "연제구"}
    all_gu = [g for gs in market.REGIONS.values() for g in gs]
    out["gu_heat"] = {"rows": [{"name": h["name"], "week": w["date"], "chg": w["chg"], "mine": h["name"] in mine}
                               for h in charts.heat_data(reb_rows, ["부산"] + all_gu) for w in h["weeks"]],
                      "meta": [src_reb, {"label": "기준", "value": "최근 26주, 주간 매매지수 변동률(%)"}]}
    out["volume_index"] = {"rows": charts.combo_data(ctx),
                           "meta": [src_rt, src_reb, {"label": "기준", "value": "관심 6개 구 월별 매매 건수(해제·중복 제외), 부산 매매지수는 달마다 마지막 조사 주. partial은 신고 기한이 남은 달"}]}
    cards = charts.prepare(ctx["cards"], ctx["now"].strftime("%Y-%m"))
    out["core_box"] = {"rows": charts.box_data(cards),
                       "meta": [src_rt, {"label": "기준", "value": "핵심 단지 84㎡형(전용 75~90㎡) 최근 3개월 거래가, 해제 제외. q1·q3는 아래·위 절반의 중간값"}]}
    out["core_rank"] = {"rows": charts.bump_data(cards),
                        "meta": [src_rt, {"label": "기준", "value": "분기별 3.3㎡당 중간값(전용면적 기준, 모든 면적, 해제 제외) 순위. 거래 3건 미만 분기는 빠짐"}]}
    return out, {"start": start, "end": end, "last_run": last_run, "reb_asof": asof}


def main():
    out_dir = Path(sys.argv[1])
    start, end = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else (None, None)
    out, info = build(start, end)
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, v in out.items():
        (out_dir / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
