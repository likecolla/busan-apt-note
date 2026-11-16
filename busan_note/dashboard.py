"""공부노트·특별호 맨 위 "한눈에 보기" 대시보드 HTML.

Tailwind(prefix "tw-", preflight 끔)로 미리 빌드한 CSS(dashboard.css)를 페이지에 함께 넣는다. 색은 페이지의 CSS 변수(--card, --harbor 등)를 그대로 쓴다.
숫자는 모두 저장소 데이터에서 계산한다. 차트는 외부 라이브러리 없이 인라인 SVG로 그린다.
"""
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import market
from .money import korean_unit

CSS_FILE = Path(__file__).with_name("dashboard.css")   # tailwind.config.js 로 빌드한 결과


def css():
    """페이지 <style id="dash-css"> 에 넣을 Tailwind 빌드 CSS."""
    return CSS_FILE.read_text(encoding="utf-8")


CARD = "tw-rounded-xl tw-border tw-border-solid tw-border-[color:var(--line)] tw-bg-[color:var(--card)] tw-p-4"
SUB = "tw-text-[13px] tw-leading-snug tw-text-[color:var(--muted)]"


def e(x):
    return escape(str(x))


def _sign_color(v):
    return "var(--up)" if v > 0.005 else "var(--down, var(--harbor))" if v < -0.005 else "var(--muted)"


def _pc(v, d=2):
    return "–" if v is None else f"{v:+.{d}f}%"


def _ymd(iso):
    return f"{int(iso[5:7])}. {int(iso[8:10])}."


def sparkline(vals, w=300, h=56, color="var(--harbor)"):
    """값 목록을 선 그래프로. 맨 끝 점을 강조한다."""
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = [(i * (w - 8) / (len(vals) - 1) + 4, h - 6 - (v - lo) / span * (h - 12)) for i, v in enumerate(vals)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    x, y = pts[-1]
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img" aria-hidden="true" '
            f'preserveAspectRatio="none" style="display:block">'
            f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" '
            f'vector-effect="non-scaling-stroke"/><circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/></svg>')


def bars(items, h=72):
    """[(라벨, 값, 진행중여부)] 세로 막대. 진행 중인 막대는 옅게."""
    top = max(v for _, v, _ in items) or 1
    cols = "".join(
        f'<div class="tw-flex tw-flex-1 tw-flex-col tw-items-center tw-justify-end tw-gap-1">'
        f'<span class="tw-text-[11px] tw-font-semibold">{v}</span>'
        f'<div style="height:{max(3, v / top * h):.0f}px;background:var(--harbor);opacity:{0.35 if part else 1}" '
        f'class="tw-w-full tw-rounded-t"></div>'
        f'<span class="tw-text-[11px] tw-text-[color:var(--muted)]">{e(lb)}</span></div>'
        for lb, v, part in items)
    return f'<div class="tw-flex tw-items-end tw-gap-1.5" style="height:{h + 36}px">{cols}</div>'


def progress(pct, color="var(--harbor)", label=""):
    pct = max(0, min(100, pct))
    return (f'<div class="tw-h-2.5 tw-w-full tw-overflow-hidden tw-rounded-full tw-bg-[color:var(--soft)]" '
            f'role="img" aria-label="{e(label)}"><div class="tw-h-full tw-rounded-full" '
            f'style="width:{pct:.0f}%;background:{color}"></div></div>')


def diverge(v, lim=1.5):
    """-lim~+lim(%)를 가운데 0 기준 막대로."""
    w = min(abs(v) / lim, 1) * 50
    side = f"left:50%" if v >= 0 else f"right:50%"
    return (f'<div class="tw-relative tw-h-2.5 tw-w-full tw-rounded-full tw-bg-[color:var(--soft)]">'
            f'<div class="tw-absolute tw-top-[-3px] tw-bottom-[-3px] tw-w-px tw-bg-[color:var(--muted)]" style="left:50%"></div>'
            f'<div class="tw-absolute tw-top-0 tw-h-full tw-rounded-full" style="{side};width:{w:.0f}%;background:{_sign_color(v)}"></div></div>')


def stacked(counts):
    """시장 판단 포인트 다섯 개: 있음·애매·반대 비율 막대."""
    tot = sum(counts.values()) or 1
    seg = "".join(
        f'<div style="width:{counts[k] / tot * 100:.0f}%;background:{c}" title="{k} {counts[k]}"></div>'
        for k, c in ((market.YES, "var(--ok, var(--glass))"), (market.MID, "var(--lamp)"), (market.NO, "var(--up)"))
        if counts[k])
    return f'<div class="tw-flex tw-h-3 tw-w-full tw-overflow-hidden tw-rounded-full tw-gap-0.5">{seg}</div>'


def kpi(title, value, sub="", extra="", color="var(--ink)"):
    return (f'<div class="{CARD} tw-flex tw-flex-col tw-gap-1.5">'
            f'<div class="{SUB}">{title}</div>'
            f'<div class="tw-text-2xl tw-font-bold tw-leading-tight" style="color:{color}">{value}</div>'
            f'{f"<div class={chr(34)}{SUB}{chr(34)}>{sub}</div>" if sub else ""}{extra}</div>')


def chip(text, kind):
    col = {market.YES: "var(--ok, var(--glass))", market.MID: "var(--lamp)", market.NO: "var(--up)"}.get(kind, "var(--muted)")
    return (f'<span class="tw-inline-block tw-whitespace-nowrap tw-rounded-full tw-px-2.5 tw-py-0.5 tw-text-[12.5px] tw-font-semibold" '
            f'style="color:{col};border:1px solid {col}">{e(text)}</span>')


def _wrap(title, asof, body):
    return (f'<section id="dash" class="tw-mt-6 tw-mb-2"><div class="tw-flex tw-items-baseline tw-justify-between tw-gap-2 tw-mb-3">'
            f'<h2 class="tw-text-xl tw-m-0" style="border:0;padding:0">{e(title)}</h2>'
            f'<span class="{SUB}">{e(asof)}</span></div>{body}</section>')


# ---- 특별호 ----
def special(ctx, kosis, cfg, cmp_items=()):
    reb = ctx["reb"]
    busan = next(r for r in reb if r["name"] == "부산")
    vals = [x[2] for x in busan["series"][-52:]]
    pts = market.points(ctx, kosis, cfg)
    n, lean = market.verdict(pts, None)
    rows = market.region_rows(reb, kosis)
    sp = market.spread_rows(reb, "부산", [], group=("상급지", market.UPPER))
    up = sp[-1]
    have = [r for r in cmp_items if len(r["series"]) >= 60]
    seoul = market.spread_rows(list(reb) + list(have), "부산", ["서울"])[1] if any(r["name"] == "서울" for r in have) else None

    st, nst = busan["sale_streak"]
    jst, njst = busan["jeonse_streak"]
    u = kosis.get("unsold", {}).get("부산", {})
    unsold = ""
    if u:
        ks = sorted(u)
        now, yago = u[ks[-1]], u.get(f"{int(ks[-1][:4]) - 1}{ks[-1][4:]}")
        top = max(now, yago or 0) or 1
        unsold = kpi(f"부산 미분양 ({ks[-1][:4]}. {int(ks[-1][4:])}.)", f"{now:,}호",
                     f"1년 전 {yago:,}호 ({(now / yago - 1) * 100:+.0f}%)" if yago else "",
                     f'<div class="tw-mt-1 tw-grid tw-gap-1">{progress(now / top * 100, "var(--up)", "지금")}'
                     f'{progress((yago or 0) / top * 100, "var(--muted)", "1년 전")}</div>')
    rate = cfg.get("base_rate", {})
    cards = [
        kpi(f"부산 매매 주간 ({_ymd(busan['date'])} 조사)", _pc(busan["sale_wk"]), f"{nst}주 연속 {st} · 최근 1년 지수",
            f'<div class="tw-mt-1">{sparkline(vals)}</div>', _sign_color(busan["sale_wk"])),
        kpi("부산 전세 주간", _pc(busan["jeonse_wk"]), f"{njst}주 연속 {jst}", color=_sign_color(busan["jeonse_wk"])),
        kpi("시장 판단 (포인트 다섯)", e(lean), f"있음 {n[market.YES]} · 애매 {n[market.MID]} · 반대 {n[market.NO]}",
            f'<div class="tw-mt-1">{stacked(n)}</div>'),
        unsold,
        kpi("기준금리", f"{rate.get('value', 0):.2f}%", f"{e(rate.get('asof', ''))} 기준 · 손으로 적는 값") if rate else "",
        kpi("상급지 격차 (1년)", f"{up['gap']:+.1f}%p", f"해운대·수영·동래·남구 평균 − 부산 · 반년 전 {up['gap_prev']:+.1f}%p"),
    ]
    if seoul:
        cards.append(kpi("서울 격차 (1년)", f"{seoul['gap']:+.1f}%p", f"서울 − 부산 · 반년 전 {seoul['gap_prev']:+.1f}%p"))
    grid = '<div class="tw-grid tw-grid-cols-2 sm:tw-grid-cols-3 tw-gap-3">' + "".join(c for c in cards if c) + "</div>"

    prow = "".join(
        f'<tr><td class="tw-py-2.5 tw-pr-2 tw-align-top"><b>{e(nm)}</b><div class="{SUB}">{e(txt)}</div></td>'
        f'<td class="tw-py-2.5 tw-text-right tw-align-top">{chip(v, v)}</td></tr>' for nm, txt, v, _ in pts)
    ptable = (f'<div class="{CARD}"><div class="tw-mb-2 tw-font-semibold">핵심 요약 · 상승장 전환 포인트</div>'
              f'<table class="tw-w-full" style="min-width:0;border-collapse:collapse"><tbody>{prow}</tbody></table></div>')
    rrow = "".join(
        f'<div class="tw-grid tw-grid-cols-[5.5em_1fr_4.5em] tw-items-center tw-gap-2 tw-py-1.5">'
        f'<span class="tw-text-[14px]">{e(r["name"])}</span>{diverge(r["pos"]["ch26"] or 0)}'
        f'<span class="tw-text-right tw-text-[13px] tw-font-semibold" style="color:{_sign_color(r["pos"]["ch26"] or 0)}">{_pc(r["pos"]["ch26"])}</span></div>'
        for r in rows)
    states = " · ".join(f'{r["name"]} {r["pos"]["state"]}' for r in rows)
    rbox = (f'<div class="{CARD}"><div class="tw-mb-1 tw-font-semibold">권역별 최근 26주 지수 변동</div>'
            f'<div class="{SUB} tw-mb-2">+0.5% 이상 회복, −0.5% 이하 하락. {e(states)}</div>{rrow}</div>')
    body = grid + f'<div class="tw-mt-3 tw-grid tw-gap-3 md:tw-grid-cols-2">{ptable}{rbox}</div>'
    return _wrap("한눈에 보기", f"부동산원 {_ymd(busan['date'])} 조사 · 실거래 {ctx['meta'].get('last_run', '')[:10]}", body)


# ---- 공부노트 ----
def _weeks(end_iso, n=8):
    end = date.fromisoformat(end_iso)
    return [((end - timedelta(days=7 * i + 6)).isoformat(), (end - timedelta(days=7 * i)).isoformat()) for i in range(n)][::-1]


def study(ctx, recs, start, end):
    reb = ctx["reb"]
    busan = next(r for r in reb if r["name"] == "부산")
    trades = [r for r in recs if r["kind"] == "trade" and not r["cancelled"]]
    wk = []
    for a, b in _weeks(end):
        cnt = sum(1 for r in trades if a <= r["date"] <= b)
        part = (date.fromisoformat(ctx["meta"]["last_run"][:10]) - date.fromisoformat(b)).days < 30
        wk.append((f"{int(a[5:7])}/{int(a[8:10])}", cnt, part))
    this = wk[-1][1]
    ah = ctx["applyhome"]
    short = ah["last12_short"] / ah["last12_n"] * 100 if ah.get("last12_n") else None
    cards = [
        kpi(f"이번 주 매매 신고 ({_ymd(start)}~{_ymd(end)})", f"{this:,}건", "관심 6개 구, 해제 제외 · 신고는 30일 안에 계속 늘어남"),
        kpi(f"부산 매매 주간 ({_ymd(busan['date'])} 조사)", _pc(busan["sale_wk"]),
            f"{busan['sale_streak'][1]}주 연속 {busan['sale_streak'][0]}", color=_sign_color(busan["sale_wk"])),
        kpi("부산 전세 주간", _pc(busan["jeonse_wk"]), f"{busan['jeonse_streak'][1]}주 연속 {busan['jeonse_streak'][0]}",
            color=_sign_color(busan["jeonse_wk"])),
    ]
    if short is not None:
        cards.append(kpi("최근 12개월 부산 청약", f"{ah['last12_short']}/{ah['last12_n']}건 미달",
                         "미달 주택형이 있는 분양 단지 비율", f'<div class="tw-mt-1">{progress(short, "var(--up)", "미달 비율")}</div>'))
    grid = '<div class="tw-grid tw-grid-cols-2 sm:tw-grid-cols-4 tw-gap-3">' + "".join(cards) + "</div>"
    chart = (f'<div class="{CARD}"><div class="tw-mb-1 tw-font-semibold">주별 매매 계약 (현재까지 신고된 건수)</div>'
             f'<div class="{SUB} tw-mb-3">목~수 계약 주 기준. 옅은 막대는 신고 기한(30일)이 안 지나 더 늘어날 주</div>{bars(wk)}</div>')
    rows = ""
    for c in ctx["cards"]:
        ratio = c["med3"] / c["peak"]["price"] * 100 if c["med3"] and c.get("peak") else None
        yoy = (f'<span style="color:{_sign_color(c["yoy"] * 100)}" class="tw-font-semibold">{c["yoy"] * 100:+.1f}%</span>'
               if c.get("yoy") is not None else '<span class="tw-text-[color:var(--muted)]">–</span>')
        few = ' <span class="few">표본 적음</span>' if c.get("low_sample") else ""
        rows += (f'<div class="tw-py-2.5 tw-border-0 tw-border-t tw-border-solid tw-border-[color:var(--line)]">'
                 f'<div class="tw-flex tw-items-baseline tw-justify-between tw-gap-2">'
                 f'<b class="tw-text-[15px]">{e(c["name"])}</b>'
                 f'<span class="tw-text-[15px] tw-font-semibold tw-text-[color:var(--harbor)] tw-whitespace-nowrap">'
                 f'{korean_unit(c["med3"]) if c["med3"] else "–"}</span></div>'
                 f'<div class="tw-mt-1.5 tw-grid tw-grid-cols-[1fr_auto] tw-items-center tw-gap-x-3 tw-gap-y-1">')
        if ratio:
            rows += (f'{progress(ratio, "var(--harbor)", "최고가 대비")}'
                     f'<span class="{SUB} tw-whitespace-nowrap">최고가의 {ratio:.0f}%</span>')
        rows += (f'<span class="{SUB}">{e(c["kind_ko"])} · 84㎡형 3개월 {c["n3"]}건{few}</span>'
                 f'<span class="{SUB} tw-whitespace-nowrap">3.3㎡당 1년 {yoy}</span></div></div>')
    table = (f'<div class="{CARD}"><div class="tw-font-semibold">핵심 요약 · 핵심 단지 84㎡형(34평형)</div>'
             f'<div class="{SUB} tw-mb-1">오른쪽 금액은 최근 3개월 중간값, 막대는 최근 5년 최고가 대비 위치</div>{rows}</div>')
    body = grid + f'<div class="tw-mt-3 tw-grid tw-gap-3 md:tw-grid-cols-2">{table}{chart}</div>'
    return _wrap("한눈에 보기", f"실거래 {ctx['meta'].get('last_run', '')[:10]} · 부동산원 {_ymd(busan['date'])} 조사", body)
