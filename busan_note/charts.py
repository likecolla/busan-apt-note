"""공부노트·특별호에 넣는 차트 다섯 가지(인라인 SVG, 외부 라이브러리 없음).

1. heatmap   구 × 주 매매지수 주간 변동
2. combo     월별 매매 거래량(막대) + 부산 매매지수(선)
3. boxplot   핵심 단지 84㎡형 최근 3개월 거래가 분포
4. bump      핵심 단지 분기별 3.3㎡당 가격 순위
5. dumbbell  두 시점 비교(격차 반년 전→지금, 3.3㎡당 1년 전→지금)

데이터 함수(*_data)는 숫자만 만들고, 그리는 함수는 그 숫자로 SVG를 만든다.
대시보드(Data 형식)도 같은 데이터 함수를 써서 JSON으로 올린다.
색은 페이지 토큰(--ink, --muted, --line)을 쓰고, 오름·내림 색은 .ch 안에서 정한다.
"""
from collections import defaultdict
from html import escape
from statistics import median

from .analyze import quarter, shift_months, ym

CSS = """.ch{--c-up:#D0493B;--c-down:#3B72C4;--c-ink:var(--ink,currentColor);--c-muted:var(--muted,#7a8591);--c-line:var(--line,#d5dbde);margin-top:10px}
.ch svg{display:block;width:100%;height:auto;overflow:visible}
.ch text{font-family:inherit;fill:var(--c-muted);font-size:11px}
.ch .t-ink{fill:var(--c-ink)}.ch .t-b{font-weight:600}
.ch .cap{font-size:14px;color:var(--c-muted);margin:6px 0 0;line-height:1.55}
.ch-legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px;color:var(--c-muted);margin-top:6px}
.ch-legend i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:5px}"""

SHORT = {"르엘 리버파크 센텀": "르엘", "써밋 리미티드 남천": "써밋 남천", "대연 디아이엘": "디아이엘",
         "드파인 광안": "드파인 광안", "동래래미안아이파크": "동래래미안", "레이카운티": "레이카운티", "남천자이": "남천자이"}
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#c98500", "#d55181", "#7a5fc2", "#5b8c2a"]


def e(x):
    return escape(str(x))


def short(name):
    return SHORT.get(name, name)


def _eok(won):
    return f"{won / 1e8:.1f}억"


# ---------------- 데이터 ----------------
def heat_data(reb_items, names, weeks=26):
    by = {r["name"]: r for r in reb_items}
    rows = []
    for n in names:
        it = by.get(n)
        if not it:
            continue
        s = it["series"]
        ch = [(s[i][1], (s[i][2] / s[i - 1][2] - 1) * 100) for i in range(len(s) - weeks, len(s)) if i > 0]
        rows.append({"name": n, "weeks": [{"date": d, "chg": round(c, 3)} for d, c in ch]})
    return rows


def combo_data(ctx, months=24):
    v = ctx["volume"]
    busan = next(r for r in ctx["reb"] if r["name"] == "부산")
    idx = {}
    for _, d, s, _ in busan["series"]:
        idx[d[:7]] = round(s, 2)
    rows = []
    for m, t in list(zip(v["months"], v["total"]))[-months:]:
        rows.append({"month": m, "volume": t, "partial": m in v["incomplete"], "index": idx.get(m)})
    return rows


def box_data(cards):
    rows = []
    for c in cards:
        prices = sorted(r["price"] for r in c["_ok84"] if c["med3"] and _in_last3(r, c))
        if len(prices) < 1:
            continue
        q = _quart(prices)
        rows.append({"name": c["name"], "kind": c["kind_ko"], "n": len(prices), "min": prices[0], "q1": q[0],
                     "median": q[1], "q3": q[2], "max": prices[-1], "few": len(prices) < 5})
    return rows


def _in_last3(r, c):
    return r["date"][:7] >= c.get("_since3", "0000-00")


def _quart(v):
    n = len(v)
    if n == 1:
        return v[0], v[0], v[0]
    m = median(v)
    lo, hi = v[: n // 2], v[(n + 1) // 2:]
    return median(lo), m, median(hi)


def bump_data(cards, quarters=6, min_n=3):
    """분기별 3.3㎡당 중간값(모든 면적, 해제 제외)과 순위. 거래 min_n건 미만 분기는 비움."""
    per = defaultdict(dict)
    qs = set()
    for c in cards:
        g = defaultdict(list)
        for r in c["_ok"]:
            if r.get("ppy"):
                g[quarter(ym(r["date"]))].append(r["ppy"])
        for q, v in g.items():
            qs.add(q)
            if len(v) >= min_n:
                per[q][c["name"]] = (median(v), len(v))
    keep = sorted(qs)[-quarters:]
    rows = []
    for q in keep:
        ranked = sorted(per[q].items(), key=lambda kv: -kv[1][0])
        for i, (name, (val, n)) in enumerate(ranked):
            rows.append({"quarter": q, "name": name, "rank": i + 1, "ppy_man": round(val / 10000), "n": n})
    return rows


def ppy_dumbbell_data(cards):
    return [{"name": c["name"], "before": round(c["ppy_prev"] / 10000), "after": round(c["ppy3"] / 10000),
             "label_before": "1년 전 같은 3개월", "label_after": "최근 3개월"}
            for c in cards if c.get("ppy_prev") and c.get("ppy3") and c.get("ppy_prev_n", 0) >= 3 and c.get("ppy3_n", 0) >= 3]


def spread_dumbbell_data(spread_rows):
    return [{"name": "부산 전체" if r["name"] == "부산" else r["name"], "before": round(r["gap_prev"], 1), "after": round(r["gap"], 1)}
            for r in spread_rows if r["name"] != "부산" and r["gap"] is not None and r["gap_prev"] is not None]


# ---------------- 그리기 ----------------
def _wrap(svg, cap="", legend=""):
    return f'<div class="ch">{svg}{legend}{f"<p class={chr(34)}cap{chr(34)}>{cap}</p>" if cap else ""}</div>'


def heatmap(rows, lim=0.15, label_w=58):
    """행: 지역, 열: 주. 빨강 상승, 파랑 하락, 진할수록 큼(±lim% 이상은 가장 진함)."""
    if not rows:
        return ""
    n = len(rows[0]["weeks"])
    W, cell_h, top, bottom = 360, 15, 4, 20
    cw = (W - label_w) / n
    H = top + cell_h * len(rows) + bottom
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="지역별 최근 {n}주 매매지수 주간 변동 히트맵">']
    for i, r in enumerate(rows):
        y = top + i * cell_h
        out.append(f'<text x="{label_w - 6}" y="{y + cell_h - 4}" text-anchor="end" class="t-ink">{e(r["name"].replace("구", "") if len(r["name"]) > 2 else r["name"])}</text>')
        for j, w in enumerate(r["weeks"]):
            c = w["chg"]
            a = min(abs(c) / lim, 1) * 0.9 + (0.08 if c else 0)
            col = "var(--c-up)" if c > 0 else "var(--c-down)" if c < 0 else "var(--c-line)"
            op = a if c else 0.5
            out.append(f'<rect x="{label_w + j * cw:.1f}" y="{y + 1}" width="{cw - 1:.1f}" height="{cell_h - 2}" rx="2" '
                       f'style="fill:{col}" fill-opacity="{op:.2f}"><title>{e(r["name"])} {w["date"]} 조사 {c:+.2f}%</title></rect>')
    seen = None
    for j, w in enumerate(rows[0]["weeks"]):
        m = w["date"][5:7]
        if m != seen:
            seen = m
            out.append(f'<text x="{label_w + j * cw:.1f}" y="{H - 6}">{int(m)}월</text>')
    out.append("</svg>")
    legend = ('<div class="ch-legend"><span><i style="background:var(--c-up)"></i>상승(진할수록 큼)</span>'
              '<span><i style="background:var(--c-down)"></i>하락</span>'
              f'<span>가장 진한 색 = 주간 ±{lim:.2f}% 이상</span></div>')
    return _wrap("".join(out), legend=legend)


def combo(rows):
    """월별 거래량 막대(왼쪽 축) + 부산 매매지수 선(오른쪽 축)."""
    if not rows:
        return ""
    W, H, ml, mr, mt, mb = 360, 200, 34, 34, 12, 22
    n = len(rows)
    bw = (W - ml - mr) / n
    raw = max(r["volume"] for r in rows) or 1
    step = 500 if raw > 1500 else 200 if raw > 600 else 100
    vmax = -(-raw // (step * 4)) * step * 4
    ix = [r["index"] for r in rows if r["index"] is not None]
    lo, hi = (min(ix), max(ix)) if ix else (0, 1)
    pad = (hi - lo) * 0.15 or 0.5
    lo, hi = lo - pad, hi + pad
    y_v = lambda v: H - mb - v / vmax * (H - mt - mb)
    y_i = lambda v: H - mb - (v - lo) / (hi - lo) * (H - mt - mb)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="월별 매매 거래량 막대와 부산 매매지수 선">']
    for k in range(0, 5):
        v = vmax * k / 4
        y = y_v(v)
        out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y:.1f}" y2="{y:.1f}" style="stroke:var(--c-line)" stroke-width="0.6"/>'
                   f'<text x="{ml - 4}" y="{y + 3:.1f}" text-anchor="end">{v:,.0f}</text>'
                   f'<text x="{W - mr + 4}" y="{y + 3:.1f}">{lo + (hi - lo) * k / 4:.1f}</text>')
    pts = []
    for i, r in enumerate(rows):
        x = ml + i * bw
        tip = f'{r["month"]} 매매 {r["volume"]:,}건' + (" (신고 진행 중)" if r["partial"] else "")
        if r["index"] is not None:
            tip += f' · 지수 {r["index"]:.2f}'
        out.append(f'<rect x="{x + 1:.1f}" y="{y_v(r["volume"]):.1f}" width="{bw - 2:.1f}" height="{H - mb - y_v(r["volume"]):.1f}" rx="1.5" '
                   f'style="fill:var(--c-muted)" fill-opacity="{0.25 if r["partial"] else 0.55}"><title>{e(tip)}</title></rect>')
        if r["index"] is not None:
            pts.append((x + bw / 2, y_i(r["index"])))
        if i % 6 == 0 or i == n - 1:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{H - 6}" text-anchor="middle">{r["month"][2:4]}.{int(r["month"][5:])}</text>')
    if pts:
        out.append('<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) +
                   '" fill="none" style="stroke:var(--c-up)" stroke-width="2" stroke-linejoin="round"/>')
        x, y = pts[-1]
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" style="fill:var(--c-up)"/>')
    out.append("</svg>")
    legend = ('<div class="ch-legend"><span><i style="background:var(--c-muted);opacity:.55"></i>월별 매매 건수(왼쪽, 옅은 막대는 신고 진행 중)</span>'
              '<span><i style="background:var(--c-up);height:3px"></i>부산 매매지수(오른쪽)</span></div>')
    return _wrap("".join(out), legend=legend)


def boxplot(rows):
    """단지별 가로 상자: 선은 최저~최고, 상자는 가운데 절반, 굵은 선은 중간값."""
    if not rows:
        return ""
    W, lw, rw, rh, top = 360, 0, 54, 34, 18
    lo = min(r["min"] for r in rows)
    hi = max(r["max"] for r in rows)
    pad = (hi - lo) * 0.04 or 1e7
    lo, hi = lo - pad, hi + pad
    x = lambda v: 4 + (v - lo) / (hi - lo) * (W - rw - 8)
    H = top + rh * len(rows) + 4
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="핵심 단지 84㎡형 최근 3개월 거래가 분포 상자 그림">']
    step = 2e8 if hi - lo > 6e8 else 1e8
    t = (int(lo // step) + 1) * step
    while t < hi:
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 4}" y2="{H - 4}" style="stroke:var(--c-line)" stroke-width="0.6"/>'
                   f'<text x="{x(t):.1f}" y="{top - 7}" text-anchor="middle">{t / 1e8:.0f}억</text>')
        t += step
    for i, r in enumerate(rows):
        y = top + i * rh
        cy = y + 22
        out.append(f'<text x="4" y="{y + 11}" class="t-ink t-b">{e(short(r["name"]))}</text>'
                   f'<text x="{4 + len(short(r["name"])) * 11 + 6}" y="{y + 11}">{r["n"]}건{" · 표본 적음" if r["few"] else ""}</text>')
        out.append(f'<line x1="{x(r["min"]):.1f}" x2="{x(r["max"]):.1f}" y1="{cy}" y2="{cy}" style="stroke:var(--c-muted)" stroke-width="1.2"/>'
                   f'<rect x="{x(r["q1"]):.1f}" y="{cy - 6}" width="{max(2, x(r["q3"]) - x(r["q1"])):.1f}" height="12" rx="2" '
                   f'style="fill:#2a78d6" fill-opacity="0.35"/>'
                   f'<line x1="{x(r["median"]):.1f}" x2="{x(r["median"]):.1f}" y1="{cy - 8}" y2="{cy + 8}" style="stroke:#2a78d6" stroke-width="2.5">'
                   f'<title>{e(r["name"])} 중간값 {_eok(r["median"])}, 최저 {_eok(r["min"])}, 최고 {_eok(r["max"])}</title></line>'
                   f'<text x="{W - rw + 4}" y="{cy + 4}" class="t-ink t-b">{_eok(r["median"])}</text>')
    out.append("</svg>")
    legend = ('<div class="ch-legend"><span>가로선 = 최저~최고</span><span>상자 = 가운데 절반</span>'
              '<span>굵은 세로선·오른쪽 숫자 = 중간값</span></div>')
    return _wrap("".join(out), legend=legend)


def bump(rows):
    """분기별 순위. 선 끝에 단지 이름, 위가 1위."""
    if not rows:
        return ""
    qs = sorted({r["quarter"] for r in rows})
    names = []
    for r in sorted(rows, key=lambda r: (r["quarter"], r["rank"])):
        if r["name"] not in names:
            names.append(r["name"])
    nmax = max(r["rank"] for r in rows)
    W, ml, mr, mt, mb, rowh = 360, 22, 86, 10, 22, 24
    H = mt + rowh * (nmax - 1) + mb + 8
    x = lambda i: ml + i * (W - ml - mr) / max(1, len(qs) - 1)
    y = lambda rk: mt + 4 + (rk - 1) * rowh
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="핵심 단지 분기별 3.3㎡당 가격 순위 변화">']
    for k in range(1, nmax + 1):
        out.append(f'<text x="2" y="{y(k) + 4}">{k}위</text>')
    for i, q in enumerate(qs):
        out.append(f'<text x="{x(i):.1f}" y="{H - 4}" text-anchor="middle">{q[2:4]}.{q.split()[1][0]}분기</text>')
    for ci, nm in enumerate(names):
        col = PALETTE[ci % len(PALETTE)]
        pts = [(qs.index(r["quarter"]), r) for r in rows if r["name"] == nm]
        pts.sort(key=lambda p: p[0])
        segs, cur = [], []
        for i, r in pts:
            if cur and i != cur[-1][0] + 1:
                segs.append(cur)
                cur = []
            cur.append((i, r))
        if cur:
            segs.append(cur)
        for sg in segs:
            if len(sg) > 1:
                out.append('<polyline points="' + " ".join(f"{x(i):.1f},{y(r['rank']):.1f}" for i, r in sg) +
                           f'" fill="none" stroke="{col}" stroke-width="2.4" stroke-linejoin="round"/>')
        for i, r in pts:
            out.append(f'<circle cx="{x(i):.1f}" cy="{y(r["rank"]):.1f}" r="4" fill="{col}">'
                       f'<title>{e(nm)} {r["quarter"]} {r["rank"]}위 · 3.3㎡당 {r["ppy_man"]:,}만원({r["n"]}건)</title></circle>')
        last_i, last = pts[-1]
        out.append(f'<text x="{x(last_i) + 8:.1f}" y="{y(last["rank"]) + 4:.1f}" class="t-b" fill="{col}" style="fill:{col}">{e(short(nm))}</text>')
    out.append("</svg>")
    return _wrap("".join(out))


def dumbbell(rows, unit, fmt=lambda v: f"{v:,}", zero=False, before="이전", after="지금"):
    """두 시점 비교: 옅은 점(이전) → 진한 점(지금). zero=True면 0 기준선을 그린다."""
    if not rows:
        return ""
    W, lw, rw, rh, top = 360, 86, 62, 26, 6
    vals = [v for r in rows for v in (r["before"], r["after"])] + ([0] if zero else [])
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 or 1
    lo, hi = lo - pad, hi + pad
    x = lambda v: lw + (v - lo) / (hi - lo) * (W - lw - rw)
    H = top + rh * len(rows) + 4
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="두 시점 비교 덤벨 차트">']
    if zero:
        out.append(f'<line x1="{x(0):.1f}" x2="{x(0):.1f}" y1="0" y2="{H}" style="stroke:var(--c-muted)" stroke-dasharray="3 3" stroke-width="0.8"/>')
    for i, r in enumerate(rows):
        cy = top + i * rh + rh / 2
        up = r["after"] >= r["before"]
        col = "var(--c-up)" if up else "var(--c-down)"
        out.append(f'<text x="{lw - 8}" y="{cy + 4:.1f}" text-anchor="end" class="t-ink">{e(short(r["name"]))}</text>'
                   f'<line x1="{x(r["before"]):.1f}" x2="{x(r["after"]):.1f}" y1="{cy:.1f}" y2="{cy:.1f}" style="stroke:{col}" stroke-width="3" stroke-opacity="0.5"/>'
                   f'<circle cx="{x(r["before"]):.1f}" cy="{cy:.1f}" r="4.5" style="fill:var(--c-muted)" fill-opacity="0.6"/>'
                   f'<circle cx="{x(r["after"]):.1f}" cy="{cy:.1f}" r="5.5" style="fill:{col}"><title>{e(r["name"])} {fmt(r["before"])}{unit} → {fmt(r["after"])}{unit}</title></circle>'
                   f'<text x="{W - rw + 6}" y="{cy + 4:.1f}" class="t-ink t-b">{fmt(r["after"])}{unit}</text>')
    out.append("</svg>")
    legend = (f'<div class="ch-legend"><span><i style="background:var(--c-muted);opacity:.6;border-radius:50%"></i>{e(before)}</span>'
              f'<span><i style="background:var(--c-up);border-radius:50%"></i>{e(after)}(커짐)</span>'
              f'<span><i style="background:var(--c-down);border-radius:50%"></i>{e(after)}(작아짐)</span></div>')
    return _wrap("".join(out), legend=legend)


def prepare(cards, now_label):
    """카드마다 최근 3개월 시작 달을 붙인다(box_data용)."""
    since = shift_months(now_label, -2)
    for c in cards:
        c["_since3"] = since
    return cards
