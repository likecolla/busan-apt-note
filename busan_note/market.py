"""특별호 '권역별 비교'·'시장 판단'과 공부노트 단지 카드의 '숫자로 본 현재 위치'를 계산한다.

쓰는 자료: 부동산원 주간 지수(ctx["reb"]), KOSIS(data/kosis/busan.json), 청약홈(ctx["applyhome"]),
실거래 거래량(ctx["volume"]), 기준금리(config/market.json, 사람이 적는 값).
판단 기준은 이 파일의 숫자로 고정해 두고 매달 같은 기준으로 적는다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REGIONS = {
    "중부산권": ["중구", "서구", "동구", "영도구", "남구", "부산진구", "연제구", "수영구"],
    "동부산권": ["동래구", "해운대구", "금정구", "기장군"],
    "서부산권": ["북구", "사하구", "강서구", "사상구"],
}
REGION_SUB = {"중부산권": "중·서·동·영도·남구·부산진·연제·수영",
              "동부산권": "동래·해운대·금정·기장",
              "서부산권": "북구·사하·강서·사상"}

# 지수 위치: 최근 26주 매매지수 변동(%)
RECOVER, DECLINE = 0.5, -0.5
# 포인트 판정 기준
JEONSE_UP = 0.3          # 부산 전세지수 13주 변동(%) 이상이면 '있음'
UNSOLD_UP = 1.10         # 미분양이 1년 전의 1.1배 이상이면 '반대'
UNSOLD_DOWN = 0.95       # 1년 전의 0.95배 이하이고 전월보다 줄면 '있음'
SHORT_BAD, SHORT_GOOD = 0.7, 0.4   # 미달 단지 비율

YES, MID, NO = "있음", "애매", "반대"


def load_kosis():
    p = ROOT / "data" / "kosis" / "busan.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_market_cfg():
    p = ROOT / "config" / "market.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _change(series, weeks, col=2):
    """series: [(주차, 날짜, 매매지수, 전세지수)] → 최근 weeks주 변동(%)."""
    if len(series) <= weeks:
        return None
    return (series[-1][col] / series[-1 - weeks][col] - 1) * 100


def index_position(item):
    """2022년 이후 고점, 2023년 이후 저점, 현재, 26주 변동, 상태."""
    s = item["series"]
    since22 = [x for x in s if x[0] >= "202201"]
    since23 = [x for x in s if x[0] >= "202301"]
    peak = max(since22, key=lambda x: x[2])
    low = min(since23, key=lambda x: x[2])
    now = s[-1]
    ch26 = _change(s, 26)
    return {"peak": peak[2], "peak_date": peak[1], "low": low[2], "low_date": low[1],
            "now": now[2], "now_date": now[1], "vs_peak": (now[2] / peak[2] - 1) * 100,
            "ch26": ch26, "at_low": low[0] == now[0], "state": state_of(ch26, low[0] == now[0], low[1] >= _year_ago(now[1]))}


def _year_ago(iso):
    return f"{int(iso[:4]) - 1}{iso[4:]}"


def state_of(ch26, at_low=False, recent_low=False):
    if ch26 is None:
        return "–"
    if ch26 >= RECOVER:
        return "회복"
    if ch26 <= DECLINE:
        if at_low:
            return "하락 (지금이 저점)"
        return "하락 (새 저점)" if recent_low else "하락"
    return "보합"


def _sum_latest(kosis, key, gus):
    now = yago = 0
    for g in gus:
        d = kosis.get(key, {}).get(g, {})
        if not d:
            continue
        last = max(d)
        now += d[last]
        yago += d.get(f"{int(last[:4]) - 1}{last[4:]}", 0)
    return now, yago


def _mig12(kosis, gus):
    tot = 0
    for g in gus:
        d = kosis.get("migration", {}).get(g, {})
        tot += sum(d[k]["net"] for k in sorted(d)[-12:])
    return tot


def region_rows(reb, kosis):
    by = {r["name"]: r for r in reb}
    rows = []
    for name, gus in [("부산 전체", sum(REGIONS.values(), []))] + list(REGIONS.items()):
        item = by["부산" if name == "부산 전체" else name]
        u_now, u_yago = _sum_latest(kosis, "unsold", gus)
        done, _ = _sum_latest(kosis, "unsold_done", gus)
        rows.append({"name": name, "sub": REGION_SUB.get(name, ""), "date": item["date"],
                     "sale_wk": item["sale_wk"], "sale_ytd": item["sale_ytd"],
                     "jeonse_wk": item["jeonse_wk"], "jeonse_ytd": item["jeonse_ytd"],
                     "unsold": u_now, "unsold_yago": u_yago, "done": done, "mig12": _mig12(kosis, gus),
                     "pos": index_position(item)})
    return rows


def points(ctx, kosis, cfg):
    """상승장 전환 포인트 다섯 가지: (이름, 현재 수치 문장, 판정, 근거 등급)."""
    out = []
    busan = next(r for r in ctx["reb"] if r["name"] == "부산")
    j13 = _change(busan["series"], 13, col=3)
    st = busan["jeonse_streak"]
    v = YES if j13 is not None and j13 >= JEONSE_UP else NO if j13 is not None and j13 < 0 else MID
    out.append(("전세가 꾸준히 오름", f"부산 전세 {st[1]}주 연속 {st[0]}, 최근 13주 {j13:+.2f}%", v, "g2"))

    vol = ctx["volume"]
    avg = sum(r["avg"] for r in vol["rows"])
    rec = sum(r["recent"] for r in vol["rows"])
    done_months = [m for m in vol["months"] if m not in vol["incomplete"]]
    i = vol["months"].index(done_months[-1])
    last, prev = vol["total"][i], vol["total"][i - 1]
    ratio = rec / avg - 1
    v = YES if ratio > 0 and last >= prev else NO if ratio < 0 and last < prev else MID
    r3 = vol["recent3"]
    out.append(("거래량 증가",
                f"관심 6개 구 {r3[0][5:].lstrip('0')}~{r3[-1][5:].lstrip('0')}월 월평균이 5년 평균보다 {ratio * 100:+.0f}%, "
                f"{int(prev_m(done_months[-1]))}월→{int(done_months[-1][5:])}월 {prev:,}→{last:,}건", v, "g1"))

    b = kosis.get("unsold", {}).get("부산", {})
    if b:
        ks = sorted(b)
        now, prev_u, yago = b[ks[-1]], b[ks[-2]], b.get(f"{int(ks[-1][:4]) - 1}{ks[-1][4:]}")
        v = NO if yago and now >= yago * UNSOLD_UP else YES if yago and now <= yago * UNSOLD_DOWN and now < prev_u else MID
        out.append(("미분양 감소", f"{ks[-1][:4]}. {int(ks[-1][4:])}. {now:,}호, 1년 전 {yago:,}호({(now / yago - 1) * 100:+.0f}%)", v, "g2"))

    rate = cfg.get("base_rate")
    if rate:
        chg = rate.get("last_change", 0)
        v = YES if chg < 0 else NO if chg > 0 else MID
        out.append(("금리 하락", f"기준금리 연 {rate['value']:.2f}%, {rate['note']}", v, "g3"))

    ah = ctx["applyhome"]
    if ah.get("last12_n"):
        share = ah["last12_short"] / ah["last12_n"]
        v = NO if share >= SHORT_BAD else YES if share <= SHORT_GOOD else MID
        out.append(("청약 열기", f"최근 12개월 부산 분양 {ah['last12_n']}건 중 {ah['last12_short']}건에서 미달 주택형", v, "g2"))
    return out


def prev_m(ym):
    y, m = int(ym[:4]), int(ym[5:])
    return 12 if m == 1 else m - 1


def verdict(pts, busan_state):
    n = {k: sum(1 for p in pts if p[2] == k) for k in (YES, MID, NO)}
    if n[YES] >= 3:
        lean = "상승 쪽"
    elif n[NO] >= 3:
        lean = "하락 쪽"
    else:
        lean = "중립"
    return n, lean


def card_facts(c):
    """단지 카드의 상승·하락 요인을 숫자로만 고른다. 각 쪽 최대 3개."""
    up, down = [], []
    if c.get("yoy") is not None:
        (up if c["yoy"] > 0 else down).append(f"3.3㎡당 가격이 1년 전보다 {c['yoy'] * 100:+.1f}%")
    if c.get("vs_peak") is not None and c.get("peak"):
        if c["vs_peak"] > -0.05:
            up.append(f"3개월 중간값이 84㎡형 최고가에 가까움({c['vs_peak'] * 100:+.1f}%)")
        else:
            down.append(f"3개월 중간값이 84㎡형 최고가보다 {c['vs_peak'] * 100:+.1f}%")
    if c.get("floor_premium") is not None and c["floor_premium"] >= 0.1:
        up.append(f"고층이 저층보다 {c['floor_premium'] * 100:+.1f}%로 층·조망 가치가 가격에 반영")
    if c.get("low_sample"):
        down.append(f"84㎡형 3개월 거래 {c['n3']}건뿐이라 중간값을 믿기 어려움")
    elif c.get("n3"):
        up.append(f"84㎡형 3개월 {c['n3']}건으로 표본 충분")
    if c.get("n12"):
        cr = c.get("cancel_rate") or 0
        if cr >= 0.08:
            down.append(f"최근 12개월 해제 {c['cancel_n']}건({cr * 100:.1f}%)")
        elif cr <= 0.04:
            up.append(f"최근 12개월 해제율 {cr * 100:.1f}%로 낮음")
        if c.get("direct_n", 0) / c["n12"] >= 0.15:
            down.append(f"최근 12개월 거래의 {c['direct_n'] / c['n12'] * 100:.0f}%({c['direct_n']}건)가 직거래")
    if c.get("peak_cancel"):
        down.append(f"최고가 이상이었다가 해제된 거래 {len(c['peak_cancel'])}건")
    jr = c.get("jeonse_ratio")
    if jr and jr.get("basis") == "신규":   # 신규 계약 3건 이상일 때만
        r = jr["ratio"]
        (up if r >= 0.6 else down).append(f"전세가율 {r * 100:.0f}%(신규 계약 {jr['n']}건 기준)")
    return up[:3], down[:3]


# ---- 격차 보기 ----
UPPER = ["해운대구", "수영구", "동래구", "남구"]   # 부산 상급지로 정해 둔 4개 구(바꾸지 않는다)
TURN_WEEKS = 13   # 방향 전환: 13주 변동의 부호가 바뀐 가장 최근 주


def _sale_map(item):
    return {k: (d, v) for k, d, v, _ in item["series"]}


def _ch_on(m, weeks_list, i, n):
    """weeks_list[i] 주 기준 n주 변동(%)."""
    if i - n < 0:
        return None
    a, b = m.get(weeks_list[i]), m.get(weeks_list[i - n])
    return (a[1] / b[1] - 1) * 100 if a and b else None


def last_turn(item, n=TURN_WEEKS):
    """13주 변동이 마지막으로 부호를 바꾼 주: ("상승"/"하락", 날짜). 없으면 None."""
    m = _sale_map(item)
    ks = sorted(m)
    chs = [(_ch_on(m, ks, i, n), ks[i]) for i in range(len(ks))]
    chs = [(c, k) for c, k in chs if c is not None]
    for j in range(len(chs) - 1, 0, -1):
        if (chs[j][0] > 0) != (chs[j - 1][0] > 0):
            return ("상승" if chs[j][0] > 0 else "하락", m[chs[j][1]][0])
    return None


def spread_rows(items, base, names, group=None):
    """base 지역과 비교한 격차 표. items: weekly_summary() 목록(여러 파일을 합쳐도 된다).
    group=(이름, [지역들]) 이면 그 지역들의 단순 평균 줄을 덧붙인다."""
    by = {r["name"]: r for r in items}
    bm = _sale_map(by[base])
    ks = sorted(bm)
    last = len(ks) - 1

    def one(name):
        it = by[name]
        m = _sale_map(it)
        pos = index_position(it)
        return {"name": name, "vs_peak": pos["vs_peak"], "ch52": _ch_on(m, ks, last, 52),
                "ch13": _ch_on(m, ks, last, 13), "ch52_prev": _ch_on(m, ks, last - 26, 52),
                "turn": last_turn(it)}

    rows = [one(n) for n in [base] + [n for n in names if n in by]]
    if group:
        g = [one(n) for n in group[1] if n in by]
        avg = lambda k: sum(r[k] for r in g) / len(g) if g and all(r[k] is not None for r in g) else None
        rows.append({"name": group[0], "vs_peak": avg("vs_peak"), "ch52": avg("ch52"), "ch13": avg("ch13"),
                     "ch52_prev": avg("ch52_prev"), "turn": None, "group": True})
    b = rows[0]
    for r in rows:
        r["gap"] = r["ch52"] - b["ch52"] if r["ch52"] is not None and b["ch52"] is not None else None
        r["gap_prev"] = (r["ch52_prev"] - b["ch52_prev"]
                         if r["ch52_prev"] is not None and b["ch52_prev"] is not None else None)
    return rows


def spread_trend(gap, gap_prev, band=0.5):
    """1년 변동 차이가 반년 전보다 band(%p) 넘게 커졌으면 '벌어짐', 줄었으면 '좁혀짐'."""
    if gap is None or gap_prev is None:
        return "–"
    if abs(gap) - abs(gap_prev) > band:
        return "벌어짐"
    if abs(gap_prev) - abs(gap) > band:
        return "좁혀짐"
    return "비슷"


SEOUL_ROWS = ["서울", "강남구", "서초구", "송파구", "용산구", "마포구", "성동구", "수도권", "전국"]
