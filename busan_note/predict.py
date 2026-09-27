"""예측 기록장: config/predictions.json 의 예측을 실거래로 채점한다.

예측 항목 예:
  {"id": "p1", "made": "2026-09-27", "question": "...",
   "complex": "동래래미안아이파크", "metric": "med84", "kind": "trade",
   "period": ["2026-10", "2026-12"], "op": ">=", "value": 1100000000}

metric
  med84        84㎡형 거래가 중간값(원)
  ppy          3.3㎡당 중간값(원, 모든 면적)
  count        거래 건수(해제 제외)
  jeonse_count 전세 신고 건수
  gap_ppy      complex 와 other 의 3.3㎡당 중간값 차이 비율(complex ÷ other − 1)
  reb_sale     부동산원 주간 매매지수의 기간 변동률(%). complex 대신 region(예: "부산", "남구")
  reb_jeonse   부동산원 주간 전세지수의 기간 변동률(%)

lag: 기간이 끝난 뒤 채점까지 기다릴 개월 수. 실거래는 신고 기한 때문에 기본 2, 부동산원 지수는 0.
"""
import json
import operator

from . import analyze, api

OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt}
REPORT_LAG_MONTHS = 2     # 기간이 끝난 뒤 신고를 기다리는 개월 수
MIN_N = 3                 # 중간값 채점에 필요한 최소 건수


def load():
    p = api.ROOT / "config" / "predictions.json"
    return json.loads(p.read_text(encoding="utf-8")).get("predictions", []) if p.exists() else []


def _in_period(r, period):
    m = r["date"][:7]
    return period[0] <= m <= period[1]


def _deals(recs, kind, period):
    return [r for r in recs if r["kind"] == kind and not r.get("cancelled") and _in_period(r, period)]


def _reb_change(region, kind, period):
    """주간 지수에서 기간 직전 주 대비 기간 마지막 주의 변동률(%)과 기간 안 주 수."""
    path = api.ROOT / "data" / "reb" / "weekly.json"
    if not path.exists():
        return None, 0
    data = json.loads(path.read_text(encoding="utf-8"))
    weeks = sorted((v["date"], v.get(kind)) for v in data.get(region, {}).get("weeks", {}).values() if v.get(kind))
    before = [v for d, v in weeks if d[:7] < period[0]]
    inside = [v for d, v in weeks if period[0] <= d[:7] <= period[1]]
    if not before or not inside:
        return None, len(inside)
    return (inside[-1] / before[-1] - 1) * 100, len(inside)


def lag_of(p):
    return p.get("lag", 0 if p["metric"].startswith("reb_") else REPORT_LAG_MONTHS)


def measure(p, recs_by_name, kind_by_name):
    """예측 기간의 실제 값과 건수."""
    if p["metric"] in ("reb_sale", "reb_jeonse"):
        return _reb_change(p["region"], p["metric"][4:], p["period"])
    recs = recs_by_name.get(p["complex"], [])
    kind = p.get("kind") or kind_by_name.get(p["complex"], "trade")
    m = p["metric"]
    if m == "med84":
        d = [r["price"] for r in _deals(recs, kind, p["period"]) if r["band"] == analyze.BAND_84]
        return analyze.median_won(d), len(d)
    if m == "ppy":
        d = [r["ppy"] for r in _deals(recs, kind, p["period"]) if r.get("ppy")]
        return analyze.median_won(d), len(d)
    if m == "count":
        d = _deals(recs, kind, p["period"])
        return len(d), len(d)
    if m == "jeonse_count":
        d = [r for r in recs if r["kind"] == "rent" and r["rent_type"] == "전세" and _in_period(r, p["period"])]
        return len(d), len(d)
    if m == "gap_ppy":
        other = recs_by_name.get(p["other"], [])
        okind = p.get("other_kind") or kind_by_name.get(p["other"], "trade")
        a = [r["ppy"] for r in _deals(recs, kind, p["period"]) if r.get("ppy")]
        b = [r["ppy"] for r in _deals(other, okind, p["period"]) if r.get("ppy")]
        ma, mb = analyze.median_won(a), analyze.median_won(b)
        return (ma / mb - 1 if ma and mb else None), min(len(a), len(b))
    raise ValueError(f"알 수 없는 metric: {m}")


def status(p, now_label, actual, n):
    start, end = p["period"]
    if now_label < start:
        return "대기"
    if now_label <= end:
        return "진행 중"
    if now_label <= analyze.shift_months(end, lag_of(p)):
        return "신고 기다림"
    counts = p["metric"] in ("count", "jeonse_count", "reb_sale", "reb_jeonse")
    if actual is None or (not counts and n < MIN_N):
        return "표본 부족"
    return "적중" if OPS[p["op"]](actual, p["value"]) else "빗나감"


def evaluate(recs_by_name, kind_by_name, now_label):
    out = []
    for p in load():
        actual, n = measure(p, recs_by_name, kind_by_name)
        out.append(dict(p, actual=actual, n=n, status=status(p, now_label, actual, n),
                        score_after=analyze.shift_months(p["period"][1], lag_of(p) + 1)))
    return out


def fmt_value(metric, v):
    """표시용 값."""
    from .money import format_won
    if v is None:
        return "–"
    if metric in ("med84",):
        return format_won(v)
    if metric == "ppy":
        return f"3.3㎡당 {v / 10000:,.0f}만원"
    if metric == "gap_ppy":
        return f"{v * 100:+.1f}%"
    if metric.startswith("reb_"):
        return f"{v:+.2f}%"
    return f"{v:,}건"
