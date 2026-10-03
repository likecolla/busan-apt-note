"""공부노트·특별호 아티팩트에 붙일 HTML 조각을 만든다.

사용법:
  .venv/bin/python scripts/briefing_snippets.py 2026-09-17 2026-09-23 > 조각.json
인자: '이번 주 거래' 계약일 시작·끝(생략하면 최근 7일).
출력: {"core": ..., "week": ..., "movein": ..., "volume": ..., "gap": ..., "asof": ...} (각 값은 HTML 문자열)
두 페이지의 기존 CSS 클래스(scroll, num, note)를 그대로 쓴다.
"""
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from busan_note import analyze, collect, market  # noqa: E402
from busan_note.money import format_won, korean_unit, pyeong_type  # noqa: E402

GU_ORDER = ["26350", "26500", "26290", "26230", "26260", "26470"]
GU_SHORT = {"26350": "해운대", "26500": "수영", "26290": "남구", "26230": "부산진",
            "26260": "동래", "26470": "연제"}


def e(x):
    return escape(str(x))


def money2(won):
    """노트 표기: 1,298,000,000원<br>(12억 9,800만)"""
    if not won:
        return "–"
    return f"{won:,}원<br>({korean_unit(won)})"


def d_short(iso):
    y, m, d = iso.split("-")
    return f"{int(m)}. {int(d)}."


def area_floor(r):
    return f'{r["area"]:.1f}㎡ ({pyeong_type(r["area"])}) · {e(r["floor"])}층'


def pct(v):
    if v is None:
        return "–"
    cls = "plus" if v > 0 else "minus"
    return f'<span class="{cls}">{v * 100:+.1f}%</span>'


def few(n):
    return ' <span class="few">표본 적음</span>' if n < analyze.MIN_SAMPLE else ""


def ppy_txt(v):
    return f"{v / 10000:,.0f}만원" if v else "–"


def core_table(ctx):
    rows = []
    for c in ctx["cards"]:
        l = c["latest84"]
        latest = (f'{money2(l["price"])}<br><small>{d_short(l["date"])} · {area_floor(l)}</small>'
                  if l else "–")
        med = f'{money2(c["med3"])}<br><small>{c["n3"]}건</small>{few(c["n3"])}' if c["med3"] else "–"
        ppy = (f'{ppy_txt(c["ppy3"])}<br><small>{c["ppy3_n"]}건 · 1년 전 대비 {pct(c["yoy"]) if c["ppy_prev_n"] else "거래 없음"}</small>'
               if c["ppy3"] else "–")
        pk = c["peak"]
        peak = (f'{money2(pk["price"])}<br><small>{d_short(pk["date"])} · 3개월 중간값 {pct(c["vs_peak"])}</small>'
                if pk else "–")
        rows.append(f'<tr><td><b>{e(c["name"])}</b><br><small>{e(c["kind_ko"])}</small></td>'
                    f'<td class="num">{latest}</td><td class="num">{med}</td>'
                    f'<td class="num">{ppy}</td><td class="num">{peak}</td></tr>')
    return ('<div class="scroll"><table>'
            '<tr><th>단지</th><th>84㎡형(34평형) 최근 거래</th><th>최근 3개월 중간값</th><th>3.3㎡(1평)당 가격 (전체 면적)</th><th>84㎡형(34평형) 최고가 (최근 5년)</th></tr>'
            + "".join(rows) + "</table></div>")


def compare_table(ctx):
    rows = ""
    for cp in ctx["compares"]:
        last = [r for r in cp["rows"] if r["gap"] is not None][-2:]
        cells = " → ".join(f'{e(r["q"])} {pct(r["gap"])}' for r in last) or "비교 가능한 분기 없음"
        rows += f'<tr><td>{e(cp["title"])}</td><td>{cells}</td></tr>'
    return ('<div class="scroll"><table><tr><th>비교</th><th>3.3㎡당 가격차 (최근 두 분기)</th></tr>'
            + rows + "</table></div>")


def prediction_table(ctx):
    from busan_note import predict
    rows = ""
    for p in ctx["predictions"]:
        op = {">=": "이상", ">": "초과", "<=": "이하", "<": "미만"}[p["op"]]
        rows += (f'<tr><td>{e(p["question"])}<br><small>{e(p.get("why", ""))}</small></td>'
                 f'<td class="num">{e(predict.fmt_value(p["metric"], p["value"]))} {op}</td>'
                 f'<td>{e(p["status"])}<br><small>채점 {e(p["score_after"])}</small></td></tr>')
    return ('<div class="scroll"><table><tr><th>질문</th><th>기준</th><th>상태</th></tr>' + rows + "</table></div>")


def week_table(recs, start, end, n=10):
    wk = [r for r in recs if r["kind"] == "trade" and not r["cancelled"] and start <= r["date"] <= end]
    wk.sort(key=lambda r: r["price"] or 0, reverse=True)
    rows = "".join(
        f'<tr><td>{e(GU_SHORT[r["lawd"]])} {e(r["umd"])}</td><td>{e(r["apt"])}</td><td>{d_short(r["date"])}</td>'
        f'<td>{area_floor(r)}</td><td class="num">{money2(r["price"])}</td>'
        f'<td>{"직거래" if r["direct"] else ""}</td></tr>'
        for r in wk[:n])
    return ('<div class="scroll"><table>'
            '<tr><th>지역</th><th>단지</th><th>계약일</th><th>전용·층</th><th>거래가</th><th>비고</th></tr>'
            + rows + "</table></div>"), len(wk)


def movein_table(ctx):
    c = next(c for c in ctx["cards"] if c.get("move_in"))
    rows = "".join(
        f'<tr><td>{e(m["month"].replace("-", ". "))}.</td><td class="num">{m["jeonse_n"]}건</td>'
        f'<td class="num">{money2(m["jeonse_med84"]) if m["jeonse_med84"] else "–"}</td>'
        f'<td class="num">{m["wolse_n"]}건</td><td class="num">{m["trade_n"]}건</td></tr>'
        for m in c["move_in"]["rows"])
    return ('<div class="scroll"><table>'
            '<tr><th>계약월</th><th>전세</th><th>전세 중간값(84㎡형)</th><th>월세</th><th>매매</th></tr>'
            + rows + "</table></div>"), c


def gu_stats(recs, now):
    months = collect.months_back(6, now.date())
    labels = [f"{m[:4]}-{m[4:]}" for m in months]
    last3 = set(labels[-3:])
    cnt_t = defaultdict(int)
    cnt_j = defaultdict(int)
    t84 = defaultdict(list)
    j84 = defaultdict(list)
    for r in recs:
        ym = r["date"][:7]
        if r["kind"] == "trade" and not r["cancelled"]:
            cnt_t[(r["lawd"], ym)] += 1
            if r["band"] == analyze.BAND_84 and ym in last3:
                t84[r["lawd"]].append(r["price"])
        elif r["kind"] == "rent" and r["rent_type"] == "전세":
            cnt_j[(r["lawd"], ym)] += 1
            if r["band"] == analyze.BAND_84 and ym in last3 and r.get("deposit"):
                j84[r["lawd"]].append(r)
    head = "".join(f"<th>{int(l[5:])}월</th>" for l in labels)
    vrows = ""
    for g in GU_ORDER:
        tc = "".join(f'<td class="num">{cnt_t[(g, l)]:,}</td>' for l in labels)
        jc = "".join(f'<td class="num">{cnt_j[(g, l)]:,}</td>' for l in labels)
        vrows += (f'<tr><td rowspan="2"><b>{GU_SHORT[g]}</b></td><td>매매</td>{tc}</tr>'
                  f'<tr><td>전세</td>{jc}</tr>')
    volume = (f'<div class="scroll"><table class="vol"><tr><th>구</th><th></th>{head}</tr>{vrows}</table></div>')
    grows = ""
    for g in GU_ORDER:
        jv, _ = analyze.jeonse_market(j84[g])
        tm, jm = analyze.median_won(t84[g]), analyze.median_won(jv)
        ratio = f"{jm / tm * 100:.0f}%" if tm and jm else "–"
        grows += (f'<tr><td><b>{GU_SHORT[g]}</b></td>'
                  f'<td class="num">{money2(tm)}<br><small>{len(t84[g])}건</small></td>'
                  f'<td class="num">{money2(jm)}<br><small>신규 {len(jv)}건</small></td>'
                  f'<td class="num"><b>{ratio}</b></td></tr>')
    gap = ('<div class="scroll"><table><tr><th>구</th><th>매매 중간값</th><th>전세 중간값</th><th>전세가율</th></tr>'
           + grows + "</table></div>")
    return volume, gap, labels


def _pc(v, digits=2):
    if v is None:
        return "–"
    cls = "plus" if v > 0.005 else "minus" if v < -0.005 else ""
    return f'<span class="{cls}">{v:+.{digits}f}%</span>'


def _ymd(iso):
    y, m, d = iso.split("-")
    return f"{y}. {int(m)}."


def region_table(rows):
    def tr(r, bold):
        n = f"<b>{e(r['name'])}</b>" if bold else e(r["name"])
        sub = f"<br><small>{e(r['sub'])}</small>" if r["sub"] else ""
        return (f'<tr><td>{n}{sub}</td><td class="num">{_pc(r["sale_wk"])}<br><small>올해 {r["sale_ytd"]:+.2f}%</small></td>'
                f'<td class="num">{_pc(r["jeonse_wk"])}<br><small>올해 {r["jeonse_ytd"]:+.2f}%</small></td>'
                f'<td class="num">{r["unsold"]:,}호<br><small>1년 전 {r["unsold_yago"]:,}호</small></td>'
                f'<td class="num">{r["done"]:,}호</td><td class="num">{r["mig12"]:+,}명</td></tr>')
    body = "".join(tr(r, True) for r in rows[1:]) + tr(rows[0], False)
    return ('<div class="scroll"><table><tr><th>권역</th><th>매매 주간</th><th>전세 주간</th><th>미분양</th>'
            '<th>준공 후 미분양</th><th>인구 순이동(12개월)</th></tr>' + body + "</table></div>")


def phase_tables(rows, pts):
    def tr(r):
        p = r["pos"]
        return (f'<tr><td><b>{e(r["name"])}</b></td>'
                f'<td class="num">{_pc(p["vs_peak"], 1)}<br><small>{p["peak"]:.1f} ({_ymd(p["peak_date"])})</small></td>'
                f'<td class="num">{p["low"]:.1f}<br><small>{_ymd(p["low_date"])}</small></td>'
                f'<td class="num">{p["now"]:.1f}</td><td class="num">{_pc(p["ch26"])}</td><td><b>{e(p["state"])}</b></td></tr>')
    idx = ('<div class="scroll"><table><tr><th>권역</th><th>2022년 고점 대비</th><th>최근 저점</th><th>현재 지수</th>'
           '<th>최근 26주 대비</th><th>현재 상태</th></tr>' + "".join(tr(r) for r in rows) + "</table></div>")
    cls = {market.YES: "plus", market.NO: "minus", market.MID: ""}
    prow = "".join(f'<tr><td>{e(n)}</td><td>{e(t)}<span class="gr {g}">{ {"g1": "실거래", "g2": "공식 통계", "g3": "보도"}[g] }</span></td>'
                   f'<td><span class="{cls[v]}">{e(v)}</span></td></tr>' for n, t, v, g in pts)
    ptab = '<div class="scroll"><table><tr><th>포인트</th><th>현재 수치</th><th>판정</th></tr>' + prow + "</table></div>"
    return idx, ptab


def card_facts_html(ctx, asof):
    out = {}
    for c in ctx["cards"]:
        up, down = market.card_facts(c)
        if not up and not down:
            continue
        out[c["name"]] = (f'<div class="both"><p class="h">숫자로 본 현재 위치 (자동 계산, {asof} 기준, 판단은 직접)</p>'
                          f'<p><span class="plus">상승 요인</span> {e(". ".join(up)) or "해당 없음"}</p>'
                          f'<p><span class="minus">하락 요인</span> {e(". ".join(down)) or "해당 없음"}</p></div>')
    return out


def main():
    ctx = analyze.build_context()
    recs = collect.load_all()
    for r in recs:
        r["band"] = analyze.band(r.get("area"))
    today = ctx["now"].date()
    start = sys.argv[1] if len(sys.argv) > 2 else (today - timedelta(days=7)).isoformat()
    end = sys.argv[2] if len(sys.argv) > 2 else today.isoformat()
    week, week_n = week_table(recs, start, end)
    movein, mc = movein_table(ctx)
    volume, gap, labels = gu_stats(recs, ctx["now"])
    vr = "".join(
        f'<tr><td><b>{e(v["gu"])}</b></td><td class="num">{v["avg"]:.0f}건</td><td class="num">{v["recent"]:.0f}건</td>'
        f'<td class="num">{pct(v["ratio"] - 1) if v["ratio"] else "–"}</td></tr>' for v in ctx["volume"]["rows"])
    r3 = ctx["volume"]["recent3"]
    volume_vs = ('<div class="scroll"><table><tr><th>구</th><th>5년 월평균</th>'
                 f'<th>최근 3개월 월평균<br><small>{e(r3[0])}~{e(r3[-1])}</small></th><th>평균 대비</th></tr>' + vr + "</table></div>")
    out = {
        "asof": ctx["meta"].get("last_run", "")[:10],
        "core": core_table(ctx),
        "week": week, "week_n": week_n, "week_range": [start, end],
        "movein": movein,
        "movein_latest84": format_won(mc["latest84"]["price"]) if mc["latest84"] else None,
        "movein_med3": format_won(mc["med3"]) if mc["med3"] else None,
        "movein_n3": mc["n3"], "movein_kind": mc["kind_ko"],
        "volume": volume, "gap": gap, "months": labels, "volume_vs": volume_vs,
        "compare": compare_table(ctx), "predictions": prediction_table(ctx),
    }
    kosis = market.load_kosis()
    rows = market.region_rows(ctx["reb"], kosis)
    pts = market.points(ctx, kosis, market.load_market_cfg())
    n, lean = market.verdict(pts, rows[0]["pos"]["state"])
    idx, ptab = phase_tables(rows, pts)
    out.update({
        "region": region_table(rows), "region_asof": rows[0]["date"],
        "phase_index": idx, "phase_points": ptab,
        "phase_count": n, "phase_lean": lean,
        "phase_states": {r["name"]: r["pos"]["state"] for r in rows},
        "card_facts": card_facts_html(ctx, out["asof"]),
    })
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
