"""site/index.html 한 장 생성."""
import json
from html import escape

from . import analyze, api, collect
from .money import format_won

SITE = api.ROOT / "site"


def e(x):
    return escape(str(x if x is not None else ""))


def money_html(won, stacked=False):
    """'1,080,000,000원 (10억 8,000만)' → 괄호 부분은 보조 글자색. stacked 면 둘째 줄로."""
    s = format_won(won)
    if "(" not in s:
        return e(s)
    a, b = s.split(" (", 1)
    return f'{e(a)}{"<br>" if stacked else " "}<span class="unit">({e(b)}</span>'


def deal_money(r):
    if r["kind"] == "rent":
        if r["rent_type"] == "전세":
            return money_html(r.get("deposit"), True)
        return f'{money_html(r.get("deposit"), True)}<br><span class="unit">월 {e(format_won(r.get("monthly")))}</span>'
    return money_html(r.get("price"), True)


def tags(r):
    out = []
    if r.get("is_new"):
        out.append('<span class="tag new">새로 신고</span>')
    if r.get("cancelled"):
        out.append('<span class="tag cancel">해제</span>')
    if r.get("direct"):
        out.append('<span class="tag direct">직거래</span>')
    if r["kind"] == "rent":
        out.append(f'<span class="tag">{e(r["rent_type"])}</span>')
    return " ".join(out)


def area_txt(r):
    a = r.get("area")
    return f'{a:.2f}㎡' if a is not None else "-"


def floor_txt(r):
    return f'{e(r.get("floor"))}층' if r.get("floor") else "-"


def deal_row(r, extra_cols=()):
    cls = ' class="cancelled"' if r.get("cancelled") else ""
    cells = [f"<td>{e(c)}</td>" for c in extra_cols]
    return (f"<tr{cls}>{''.join(cells)}<td>{e(r['date'][2:].replace('-', '.'))}</td>"
            f"<td>{r['area']:.1f}</td><td>{floor_txt(r)}</td>"
            f"<td class='num'>{deal_money(r)}</td><td>{tags(r)}</td></tr>")


def pct_html(v, digits=1):
    if v is None:
        return '<span class="sub">–</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "")
    return f'<b class="{cls}">{v * 100:+.{digits}f}%</b>'


def ppy_txt(won):
    return f'{won / 10000:,.0f}만원' if won else "–"


def few(n):
    return ' <span class="tag few">표본 적음</span>' if n < analyze.MIN_SAMPLE else ""


def card_html(c):
    l84 = c["latest84"]
    if l84:
        latest = (f'<div class="big">{money_html(l84["price"])}</div>'
                  f'<div class="sub">{e(l84["date"])} · {floor_txt(l84)} · 전용 {area_txt(l84)}'
                  f'{" · 직거래" if l84.get("direct") else ""}</div>')
    else:
        latest = '<div class="sub">84㎡형 거래 없음</div>'
    med = (f'{money_html(c["med3"])} <span class="sub">({c["n3"]}건)</span>{few(c["n3"])}'
           if c["med3"] else '<span class="sub">최근 3개월 84㎡형 거래 없음</span>')
    ppy = (f'<div class="stat"><div class="label">3.3㎡당 중간값 (최근 3개월, 모든 면적)</div>'
           f'<div><b>{ppy_txt(c["ppy3"])}</b> <span class="sub">({c["ppy3_n"]}건)</span>{few(c["ppy3_n"])}'
           + (f'<br><span class="sub">1년 전 같은 3개월 {ppy_txt(c["ppy_prev"])} ({c["ppy_prev_n"]}건) 대비</span> {pct_html(c["yoy"])}'
              if c["ppy_prev_n"] else '<br><span class="sub">1년 전 같은 기간 거래 없음</span>')
           + '</div></div>'
           if c["ppy3"] else "")
    peak = ""
    if c["peak"]:
        pk = c["peak"]
        peak = (f'<div class="stat"><div class="label">84㎡형 최고가 (수집 기간 중)</div>'
                f'<div>{money_html(pk["price"])}<br><span class="sub">{e(pk["date"])} · {floor_txt(pk)} · 전용 {area_txt(pk)}'
                f' · 3개월 중간값은 이보다</span> {pct_html(c["vs_peak"])}</div></div>')
    jr = ""
    if c["jeonse_ratio"]:
        j = c["jeonse_ratio"]
        jr = (f'<div class="stat"><div class="label">전세가율 (84㎡형, 최근 3개월)</div>'
              f'<div><strong>{j["ratio"] * 100:.0f}%</strong> '
              f'<span class="sub">= 전세 중간값 {e(format_won(j["jeonse"]))} ÷ 매매 중간값 {e(format_won(j["trade"]))}'
              f' · 전세 {j["n"]}건({"신규 계약" if j.get("basis") == "신규" else "신규·갱신 합산"})</span>{few(j["n"])}</div></div>')
    rows = "".join(deal_row(r) for r in c["recent"]) or \
        '<tr><td colspan="5" class="sub">거래 없음</td></tr>'

    # 더 보기: 층 구간, 해제·직거래
    frows = "".join(
        f'<tr><td>{f["band"]}</td><td class="num">{money_html(f["med"], True) if f["med"] else "–"}</td>'
        f'<td class="num">{f["n"]}건{few(f["n"]) if f["n"] else ""}</td></tr>' for f in c["floors"])
    prem = (f'고층이 저층보다 {pct_html(c["floor_premium"])}' if c["floor_premium"] is not None
            else '<span class="sub">저층·고층 거래가 각각 2건 이상일 때 차이를 계산합니다.</span>')
    cr = f'{c["cancel_rate"] * 100:.1f}%' if c["cancel_rate"] is not None else "–"
    pc = "".join(f'<li>{e(r["date"])} · 전용 {area_txt(r)} · {floor_txt(r)} · {e(format_won(r["price"]))}</li>'
                 for r in c["peak_cancel"])
    pc_html = (f'<p class="sub">당시 같은 면적대 최고가 이상이었다가 해제된 거래:</p><ul class="plain">{pc}</ul>'
               if pc else '<p class="sub">최고가를 찍었다가 해제된 거래는 없습니다.</p>')
    if c["kind"] != "trade":
        dong_html = '<h4>동별 가격</h4><p class="sub">분양권 거래에는 동 정보가 없습니다. 입주 후 등기가 끝난 매매부터 동이 공개됩니다.</p>'
    elif c["dongs"]:
        show = c["dongs"] if len(c["dongs"]) <= 6 else c["dongs"][:3] + c["dongs"][-3:]
        drows = "".join(f'<tr><td>{e(d["dong"])}</td><td class="num">{ppy_txt(d["med"])}</td><td class="num">{d["n"]}건{few(d["n"])}</td></tr>'
                        for d in show)
        spread = (f'<p>3.3㎡당 가장 비싼 동이 가장 싼 동보다 {pct_html(c["dong_spread"])} '
                  f'<span class="sub">(2건 이상 거래된 {len(c["dongs"])}개 동 중 {"위·아래 3개" if len(c["dongs"]) > 6 else "전체"}). '
                  f'동 차이에는 조망뿐 아니라 역·학교까지 거리, 평형 구성, 단지 안 위치가 함께 섞여 있습니다.</span></p>')
        dong_html = (f'<h4>동별 3.3㎡당 중간값 <span class="sub">(최근 12개월, 등기 완료 매매)</span></h4>'
                     f'<div class="scroll"><table><thead><tr><th>동</th><th>3.3㎡당</th><th>건수</th></tr></thead><tbody>{drows}</tbody></table></div>{spread}')
    else:
        dong_html = '<h4>동별 가격</h4><p class="sub">동 정보가 있는 거래가 부족합니다.</p>'
    more = f'''
  <details class="more"><summary>층·동·해제·직거래 더 보기</summary>
    <h4>층 구간별 84㎡형 중간값 <span class="sub">(최근 12개월, 최고 {c["top_floor"]}층 기준 3등분)</span></h4>
    <div class="scroll"><table><thead><tr><th>구간</th><th>중간값</th><th>건수</th></tr></thead><tbody>{frows}</tbody></table></div>
    <p>{prem}</p>
    {dong_html}
    <h4>해제·직거래 <span class="sub">(최근 12개월 {e(c["kind_ko"])} {c["n12"]}건)</span></h4>
    <p>해제 <b>{c["cancel_n"]}건 ({cr})</b> · 직거래 <b>{c["direct_n"]}건</b></p>
    {pc_html}
  </details>'''

    move_in = ""
    if c.get("move_in"):
        mrows = "".join(
            f'<tr><td>{e(m["month"])}</td><td class="num">{m["jeonse_n"]}건</td>'
            f'<td class="num">{money_html(m["jeonse_med84"], True) if m["jeonse_med84"] else "-"}</td>'
            f'<td class="num">{m["wolse_n"]}건</td><td class="num">{m["trade_n"]}건</td></tr>'
            for m in c["move_in"]["rows"])
        empty = all(m["jeonse_n"] == 0 and m["trade_n"] == 0 for m in c["move_in"]["rows"])
        note = ('<p class="sub">아직 매매·전월세 신고가 없습니다. 보존등기 전에는 거래가 분양권으로 신고되고, '
                '입주 뒤 전세 계약이 신고되면 이 표에 나타납니다.</p>' if empty else "")
        move_in = (f'<h4>입주장 관찰 <span class="sub">({e(c["move_in"]["start"])} 입주 시작)</span></h4>{note}'
                   '<div class="scroll"><table><thead><tr><th>월</th><th>전세 건수</th>'
                   '<th>전세 중간값(84㎡형)</th><th>월세 건수</th><th>매매 건수</th></tr></thead>'
                   f'<tbody>{mrows}</tbody></table></div>')
    return f'''
<article class="card">
  <header><h3>{e(c["name"])}</h3><span class="chip">{e(c["gu"])} · {e(c["kind_ko"])} 기준</span></header>
  <div class="stats">
    <div class="stat"><div class="label">84㎡형 최근 거래</div>{latest}</div>
    <div class="stat"><div class="label">84㎡형 최근 3개월 중간값</div><div>{med}</div></div>
    {ppy}
    {peak}
    {jr}
  </div>
  <h4>최근 {e(c["kind_ko"])} 거래 5건 <span class="sub">(최근 6개월 {c["n6"]}건)</span></h4>
  <div class="scroll"><table>
    <thead><tr><th>계약일</th><th>전용㎡</th><th>층</th><th>금액</th><th>표시</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  {more}
  {move_in}
</article>'''


def new_section(ctx):
    meta = ctx["meta"]
    if not ctx["new_total"]:
        if meta.get("baseline_kinds"):
            return ('<p class="sub">이번 실행은 ' + e("·".join(meta["baseline_kinds"])) +
                    ' 과거 자료를 채우는 수집이라 기준선으로 저장했습니다. 다음 갱신부터 새로 신고된 거래가 여기에 표시됩니다.</p>')
        return '<p class="sub">이번 갱신에서 새로 신고된 거래가 없습니다.</p>'
    head = "<thead><tr><th>단지</th><th>구분</th><th>계약일</th><th>전용㎡</th><th>층</th><th>금액</th><th>표시</th></tr></thead>"

    def rows(lst, watch):
        out = []
        for r in lst:
            name = r.get("cx") if watch else f'{r["apt"]} ({collect.LAWD.get(r["lawd"], "")})'
            out.append(deal_row(r, (name, collect.KIND_KO[r["kind"]])))
        return "".join(out)

    html = ""
    if ctx["new_watch"]:
        html += (f'<h4>핵심 6곳 <span class="sub">({len(ctx["new_watch"])}건)</span></h4>'
                 f'<div class="scroll"><table>{head}<tbody>{rows(ctx["new_watch"], True)}</tbody></table></div>')
    if ctx["new_other"]:
        html += ('<h4>관심 6개 구 나머지 <span class="sub">(금액 높은 순 최대 20건)</span></h4>'
                 f'<div class="scroll"><table>{head}<tbody>{rows(ctx["new_other"], False)}</tbody></table></div>')
    return html


def chart_table(ch, last=12):
    months = ch["months"][-last:]
    head = "".join(f"<th>{e(m[2:])}</th>" for m in months)
    body = ""
    for s in ch["series"]:
        cells = "".join(
            f'<td class="num">{e(format_won(p).split(" (")[1][:-1]) if p else "-"}'
            f'{f"<br><span class=unit>{n}건</span>" if n else ""}</td>'
            for p, n in zip(s["p84"][-last:], s["n84"][-last:]))
        body += f'<tr><td>{e(s["name"])}<br><span class="unit">{e(s["kind"])}</span></td>{cells}</tr>'
    return (f'<p class="sub">84㎡형 월별 중간값, 최근 {last}개월</p>'
            f'<div class="scroll"><table class="compact"><thead><tr><th>단지</th>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def compare_section(ctx, color_of):
    out = []
    for i, cp in enumerate(ctx["compares"]):
        rows = cp["rows"][-8:]
        trs = "".join(
            f'<tr><td>{e(r["q"])}</td><td class="num">{ppy_txt(r["a"])}<br><span class="unit">{r["an"]}건</span></td>'
            f'<td class="num">{ppy_txt(r["b"])}<br><span class="unit">{r["bn"]}건</span></td>'
            f'<td class="num">{pct_html(r["gap"])}</td></tr>' for r in rows)
        out.append(f'''
<article class="card">
  <header><h3>{e(cp["title"])}</h3></header>
  <p class="sub">{e(cp["note"])}. 가격차 = {e(cp["a"])} ÷ {e(cp["b"])} − 1 (분기별 3.3㎡당 중간값, 양쪽 3건 이상일 때)</p>
  <div class="chart-box small"><canvas id="cmp{i}" role="img" aria-label="{e(cp["title"])} 분기별 3.3㎡당 중간값"></canvas></div>
  <details><summary>표로 보기 (최근 8분기)</summary>
  <div class="scroll"><table><thead><tr><th>분기</th><th>{e(cp["a"])}<br><span class="unit">{e(cp["a_kind"])}</span></th>
  <th>{e(cp["b"])}<br><span class="unit">{e(cp["b_kind"])}</span></th><th>가격차</th></tr></thead><tbody>{trs}</tbody></table></div></details>
</article>''')
    return "".join(out)


STATUS_CLASS = {"적중": "hit", "빗나감": "miss", "표본 부족": "", "진행 중": "wait", "신고 기다림": "wait", "대기": ""}


def prediction_section(ctx):
    from . import predict
    rows = ""
    for p in ctx["predictions"]:
        op = {">=": "이상", ">": "초과", "<=": "이하", "<": "미만"}[p["op"]]
        target = f'{predict.fmt_value(p["metric"], p["value"])} {op}'
        scored = p["status"] in ("적중", "빗나감", "표본 부족")
        actual_label = "결과" if scored else "지금까지"
        rows += (f'<tr><td class="wrap"><b>{e(p["question"])}</b><br><span class="unit">{e(p.get("by", ""))} · {e(p["made"])}'
                 f' · 채점 {e(p["score_after"])}</span></td>'
                 f'<td>{e(p["period"][0][2:])}~{e(p["period"][1][2:])}</td>'
                 f'<td class="num">{e(target)}</td>'
                 f'<td class="num">{e(predict.fmt_value(p["metric"], p["actual"]))}<br><span class="unit">{actual_label} {p["n"]}건</span></td>'
                 f'<td><span class="tag {STATUS_CLASS.get(p["status"], "")}">{e(p["status"])}</span></td></tr>')
    return f'''
<p class="sub">질문에 미리 답(기준값)을 적어 두고, 기간이 끝나고 신고 기한 2개월이 지나면 실거래로 자동 채점합니다.
예측은 config/predictions.json에서 더하거나 고칩니다. 맞히는 것보다 왜 빗나갔는지 돌아보는 것이 목적입니다.</p>
<div class="scroll"><table><thead><tr><th>질문</th><th>기간</th><th>기준</th><th>실거래</th><th>상태</th></tr></thead>
<tbody>{rows}</tbody></table></div>'''


def volume_section(ctx):
    v = ctx["volume"]
    rows = ""
    for r in v["rows"]:
        ratio = r["ratio"]
        mark = ""
        if ratio is not None:
            mark = ('<span class="tag hot">평균보다 많음</span>' if ratio >= 1.15 else
                    '<span class="tag cold">평균보다 적음</span>' if ratio <= 0.85 else '<span class="tag">평균 수준</span>')
        rows += (f'<tr><td><b>{e(r["gu"])}</b></td><td class="num">{r["avg"]:.0f}건</td>'
                 f'<td class="num">{r["recent"]:.0f}건</td>'
                 f'<td class="num">{f"{ratio * 100:.0f}%" if ratio is not None else "–"}</td><td>{mark}</td></tr>')
    r3 = v["recent3"]
    span = v["span"]
    return f'''
<p class="sub">거래량은 가격보다 먼저 움직이는 경우가 많아 흐름을 읽는 보조 지표로 씁니다. 관심 6개 구 매매(해제 제외) 월별 건수이고,
신고 기한이 남은 최근 2개월({e(", ".join(v["incomplete"]))})은 흐리게 표시하고 평균에서 뺐습니다.</p>
<div class="chart-box"><canvas id="volume" role="img" aria-label="관심 6개 구 월별 매매 거래량 막대그래프"></canvas></div>
<h4>구별 비교 <span class="sub">(월평균: {e(span[0])} ~ {e(span[1])}, 최근: {e(r3[0] if r3 else "")} ~ {e(r3[-1] if r3 else "")})</span></h4>
<div class="scroll"><table><thead><tr><th>구</th><th>전체 월평균</th><th>최근 3개월 월평균</th><th>비율</th><th></th></tr></thead>
<tbody>{rows}</tbody></table></div>'''


CSS = """
:root{--bg:#F2F4F3;--surface:#FBFCFB;--text:#1E2733;--muted:#5B6673;--line:#D5DBDE;
--accent:#1B3A5C;--accent2:#5E9C97;--point:#D8962B;--up:#B4412E;--tag-bg:#E6EAEA;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--ref:#7A8591;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#12171D;--surface:#1A2129;--text:#E4E8EC;--muted:#9AA6B2;--line:#2C3642;
--accent:#9CC0E6;--accent2:#7FC0B9;--point:#E8AC4E;--up:#E27A66;--tag-bg:#26303B;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#2f9a2f;--ref:#8C97A3;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#12171D;--surface:#1A2129;--text:#E4E8EC;--muted:#9AA6B2;--line:#2C3642;
--accent:#9CC0E6;--accent2:#7FC0B9;--point:#E8AC4E;--up:#E27A66;--tag-bg:#26303B;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#2f9a2f;--ref:#8C97A3;color-scheme:dark}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);
font-family:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif;
font-size:15px;line-height:1.6;overflow-x:hidden}
main{max-width:760px;margin:0 auto;padding:24px max(16px,env(safe-area-inset-left)) 48px max(16px,env(safe-area-inset-right))}
h1,h2,h3{font-family:"Gowun Batang","Nanum Myeongjo","AppleMyungjo",serif;color:var(--accent);line-height:1.3;margin:0}
h1{font-size:1.75rem}
h2{font-size:1.3rem;margin:36px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:1.15rem}
h4{font-size:.95rem;margin:18px 0 8px}
.sub,.unit{color:var(--muted);font-weight:400}
.unit{font-size:.85em}
.masthead p{margin:6px 0 0}
.summary{display:inline-block;margin-top:12px;padding:6px 12px;border-radius:999px;
background:var(--surface);border:1px solid var(--line);font-weight:600}
.summary b{color:var(--point)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 16px}
.card header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:6px}
.chip{font-size:.8rem;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:1px 10px}
.stats{display:grid;gap:10px;margin-top:12px}
.stat{border-left:3px solid var(--accent2);padding-left:10px}
.label{font-size:.8rem;color:var(--muted)}
.big{font-size:1.1rem;font-weight:600;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px;padding:0 4px}
table{border-collapse:collapse;width:100%;font-size:.85rem;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 5px;border-bottom:1px solid var(--line);white-space:nowrap;vertical-align:top}
th{color:var(--muted);font-weight:500;font-size:.78rem}
td.num{text-align:right}
table.compact th,table.compact td{padding:5px 6px}
tr.cancelled td{color:var(--muted)}
tr.cancelled td.num{text-decoration:line-through}
.tag{display:inline-block;font-size:.72rem;padding:0 6px;border-radius:4px;background:var(--tag-bg);color:var(--muted);margin-right:2px}
.tag.new{background:var(--point);color:#1E2733;font-weight:600}
.tag.cancel{background:transparent;border:1px solid var(--up);color:var(--up)}
.tag.direct{background:transparent;border:1px solid var(--accent2);color:var(--accent2)}
.chart-box{position:relative;height:320px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:8px}
details{margin-top:10px}
summary{cursor:pointer;color:var(--accent);font-size:.9rem}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);font-size:.82rem;color:var(--muted)}
footer ul{padding-left:18px;margin:6px 0}
.fail h4{color:var(--up)}
b.up{color:var(--up)} b.down{color:var(--s1)}
.tag.few{background:transparent;border:1px dashed var(--muted);color:var(--muted)}
.tag.hot{background:transparent;border:1px solid var(--up);color:var(--up)}
.tag.cold{background:transparent;border:1px solid var(--s1);color:var(--s1)}
.chart-box.small{height:220px}
td.wrap{white-space:normal;min-width:180px;max-width:280px}
.tag.hit{background:transparent;border:1px solid var(--s3);color:var(--s3)}
.tag.miss{background:transparent;border:1px solid var(--up);color:var(--up)}
.tag.wait{background:transparent;border:1px solid var(--accent2);color:var(--accent2)}
.seg{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}
.seg button{font:inherit;font-size:.82rem;padding:4px 12px;border-radius:999px;border:1px solid var(--line);
background:var(--surface);color:var(--text);cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--bg)}
.seg button:focus-visible{outline:2px solid var(--point);outline-offset:2px}
details.more{border-top:1px dashed var(--line);margin-top:12px;padding-top:8px}
ul.plain{margin:4px 0;padding-left:18px;font-size:.85rem}
.guide{font-size:.85rem;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.guide p{margin:4px 0}
"""

JS = r"""
(function(){
  var data = JSON.parse(document.getElementById('chart-data').textContent);
  function unit(won){ if(won==null) return '-'; var man=Math.floor((won+5000)/10000);
    var eok=Math.floor(man/10000), rest=man%10000, p=[];
    if(eok) p.push(eok.toLocaleString('ko-KR')+'억'); if(rest) p.push(rest.toLocaleString('ko-KR')+'만');
    return p.join(' ')||'0'; }
  function ppy(won){ return won==null?'-':Math.round(won/10000).toLocaleString('ko-KR')+'만원'; }
  function css(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  if(!window.Chart){ document.getElementById('chart-fallback').hidden=false; return; }
  var state={metric:'p84', range:36};
  try{ var saved=JSON.parse(localStorage.getItem('trend-view')||'null'); if(saved) state=saved; }catch(e){}
  var charts={};
  function axes(fmt){ var muted=css('--muted'), line=css('--line');
    return {x:{ticks:{color:muted, maxRotation:0, autoSkipPadding:12}, grid:{display:false}, border:{color:line}},
            y:{ticks:{color:muted, callback:fmt}, grid:{color:line}, border:{display:false}}}; }
  function legend(){ return {position:'bottom', labels:{color:css('--muted'), boxWidth:10, boxHeight:10, font:{size:11}}}; }
  function line(label, vals, counts, color){ return {label:label, data:vals, counts:counts, borderColor:color,
      backgroundColor:color, borderWidth:2, pointRadius:2.5, pointHoverRadius:6, pointBorderColor:css('--surface'),
      pointBorderWidth:1, spanGaps:true, tension:0.2}; }
  function drawTrend(){
    var n=data.months.length, from=state.range?Math.max(0,n-state.range):0;
    var key=state.metric, nkey=key==='p84'?'n84':'nppy';
    var ds=data.series.map(function(s,i){ return line(s.name+' ('+s.kind+')', s[key].slice(from), s[nkey].slice(from), css('--s'+(i+1))); });
    var fmt=key==='p84'?function(v){return (v/1e8).toFixed(1)+'억';}:function(v){return Math.round(v/1e4).toLocaleString('ko-KR')+'만';};
    var tip=key==='p84'?unit:ppy;
    if(charts.trend) charts.trend.destroy();
    charts.trend=new Chart(document.getElementById('trend'), {type:'line',
      data:{labels:data.months.slice(from).map(function(m){return m.slice(2).replace('-','.');}), datasets:ds},
      options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index', intersect:false},
        plugins:{legend:legend(), tooltip:{callbacks:{label:function(c){ if(c.raw==null) return null;
          return c.dataset.label+': '+tip(c.raw)+' ('+c.dataset.counts[c.dataIndex]+'건)'; }}}},
        scales:axes(fmt)}});
    document.querySelectorAll('.seg button').forEach(function(b){
      var on=(b.dataset.metric&&b.dataset.metric===state.metric)||(b.dataset.range!=null&&+b.dataset.range===state.range);
      b.setAttribute('aria-pressed', on?'true':'false'); });
    document.getElementById('trend-title').textContent=key==='p84'?'84㎡형 월별 중간값':'3.3㎡당 월별 중간값 (모든 면적)';
  }
  document.querySelectorAll('.seg button').forEach(function(b){ b.addEventListener('click', function(){
    if(b.dataset.metric) state.metric=b.dataset.metric; else state.range=+b.dataset.range;
    try{ localStorage.setItem('trend-view', JSON.stringify(state)); }catch(e){}
    drawTrend(); }); });
  function drawCompares(){
    data.compares.forEach(function(cp,i){ var el=document.getElementById('cmp'+i); if(!el) return;
      if(charts['c'+i]) charts['c'+i].destroy();
      charts['c'+i]=new Chart(el, {type:'line', data:{labels:cp.labels, datasets:[
          line(cp.a, cp.a_vals, cp.a_n, css(cp.a_color)), line(cp.b, cp.b_vals, cp.b_n, css(cp.b_color))]},
        options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index', intersect:false},
          plugins:{legend:legend(), tooltip:{callbacks:{label:function(c){ if(c.raw==null) return null;
            return c.dataset.label+': 3.3㎡당 '+ppy(c.raw)+' ('+c.dataset.counts[c.dataIndex]+'건)'; }}}},
          scales:axes(function(v){return Math.round(v/1e4).toLocaleString('ko-KR')+'만';})}}); });
  }
  function drawVolume(){
    var v=data.volume, el=document.getElementById('volume'); if(!el) return;
    var base=css('--accent2'), faint=css('--line'), n=v.months.length, from=Math.max(0,n-36);
    var colors=v.months.slice(from).map(function(m){ return v.incomplete.indexOf(m)>=0?faint:base; });
    if(charts.vol) charts.vol.destroy();
    charts.vol=new Chart(el, {data:{labels:v.months.slice(from).map(function(m){return m.slice(2).replace('-','.');}),
        datasets:[{type:'bar', label:'월별 매매 건수', data:v.total.slice(from), backgroundColor:colors, borderRadius:3, order:2},
          {type:'line', label:'월평균 '+Math.round(v.avg)+'건', data:v.months.slice(from).map(function(){return v.avg;}),
           borderColor:css('--point'), borderWidth:2, borderDash:[5,4], pointRadius:0, order:1}]},
      options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index', intersect:false},
        plugins:{legend:legend(), tooltip:{callbacks:{label:function(c){
          if(c.datasetIndex===1) return '월평균: '+Math.round(c.raw)+'건';
          var m=v.months[from+c.dataIndex]; return '매매: '+c.raw+'건'+(v.incomplete.indexOf(m)>=0?' (신고 진행 중)':''); }}}},
        scales:axes(function(v){return v;})}});
  }
  function drawAll(){ drawTrend(); drawCompares(); drawVolume(); }
  drawAll();
  if(window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', drawAll);
})();
"""


def build():
    ctx = analyze.build_context()
    meta = ctx["meta"]
    fails = meta.get("failures", [])
    fail_html = ""
    if fails:
        items = "".join(f'<li>{e(f["kind"])} · {e(f["gu"])} · {e(f["ym"])} — {e(f["error"])}</li>' for f in fails)
        fail_html = f'<div class="fail"><h4>갱신 실패 항목 ({len(fails)}건)</h4><ul>{items}</ul></div>'
    else:
        fail_html = '<p>갱신 실패 항목: 없음</p>'
    last = meta.get("last_run", "").replace("T", " ")
    r0, r1 = ctx["range"]
    names = [x["name"] for x in ctx["chart"]["series"]]

    def color_of(name):
        return f"--s{names.index(name) + 1}" if name in names else "--ref"

    compares = []
    for cp in ctx["compares"]:
        rows = cp["rows"]
        compares.append({"title": cp["title"], "a": cp["a"], "b": cp["b"], "labels": [r["q"] for r in rows],
                         "a_vals": [r["a"] for r in rows], "b_vals": [r["b"] for r in rows],
                         "a_n": [r["an"] for r in rows], "b_n": [r["bn"] for r in rows],
                         "a_color": color_of(cp["a"]), "b_color": color_of(cp["b"])})
    v = ctx["volume"]
    base = [t for m, t in zip(v["months"], v["total"]) if m not in v["incomplete"]]
    payload = dict(ctx["chart"], compares=compares,
                   volume={"months": v["months"], "total": v["total"], "incomplete": v["incomplete"],
                           "avg": sum(base) / len(base) if base else 0})
    chart_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>부산 대단지 실거래 노트</title>
<meta name="description" content="부산 관심 단지 6곳의 매매·분양권·전월세 실거래 기록">
<meta name="color-scheme" content="light dark">
<meta name="robots" content="noindex, nofollow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main>
<header class="masthead">
  <h1>부산 대단지 실거래 노트</h1>
  <p class="sub">마지막 갱신 {e(last)} (한국시간) · 계약월 {e(r0)} ~ {e(r1)}</p>
  <div class="summary">새로 신고된 거래 <b>{ctx["new_total"]:,}건</b></div>
</header>

<h2>핵심 6곳</h2>
<div class="guide">
  <p><b>읽는 법</b> 84㎡형 = 전용 75~90㎡. 해제된 거래는 계산에서 빼고 표에만 취소선으로 남깁니다. 직거래는 계산에 포함합니다.</p>
  <p><b>3.3㎡당 가격</b>은 면적이 달라도 비교할 수 있게 거래가를 평 단위로 나눈 값입니다. 75㎡대와 84㎡대가 섞인 단지는 이 값이 더 정확합니다.</p>
  <p><b>표본 적음</b>은 거래가 5건 미만이라는 뜻입니다. 한두 건으로 시세를 판단하지 마세요.</p>
</div>
{"".join(card_html(c) for c in ctx["cards"])}

<h2>가격 흐름 <span class="sub" id="trend-title">84㎡형 월별 중간값</span></h2>
<p class="sub">분양권 단지는 분양권 거래가(분양가+웃돈), 나머지는 매매가입니다. 거래가 없는 달은 선을 이어 그립니다.</p>
<div class="seg" role="group" aria-label="그래프 보기">
  <button type="button" id="m-p84" data-metric="p84" aria-pressed="true">84㎡형 가격</button>
  <button type="button" id="m-ppy" data-metric="ppy" aria-pressed="false">3.3㎡당 가격</button>
  <button type="button" id="r-12" data-range="12" aria-pressed="false">1년</button>
  <button type="button" id="r-36" data-range="36" aria-pressed="true">3년</button>
  <button type="button" id="r-0" data-range="0" aria-pressed="false">전체</button>
</div>
<div class="chart-box"><canvas id="trend" role="img" aria-label="단지별 84㎡형 월별 중간값 꺾은선 그래프"></canvas></div>
<p id="chart-fallback" class="sub" hidden>그래프를 불러오지 못했습니다. 아래 표를 참고하세요.</p>
<details><summary>표로 보기</summary>{chart_table(ctx["chart"])}</details>

<h2>두 단지 비교</h2>
<p class="sub">노트에서 자주 비교하는 단지쌍입니다. 면적 차이를 없애려고 3.3㎡당 가격으로 봅니다. 단지쌍은 config/watchlist.json의 compare에서 바꿀 수 있습니다.</p>
{compare_section(ctx, None)}

<h2>거래량 온도</h2>
{volume_section(ctx)}

<h2 id="pred">예측 기록장</h2>
{prediction_section(ctx)}

<h2>이번에 새로 신고된 거래</h2>
{new_section(ctx)}

<footer>
  <p>자료 출처: 국토교통부 실거래가 공개시스템 API (공공데이터포털)</p>
  <ul>
    <li>실거래는 계약 후 30일 안에 신고되므로 최근 1~2개월 자료는 계속 늘어납니다. 갱신할 때마다 최근 3개월치를 다시 받습니다.</li>
    <li>학습용 자료이며 투자 판단의 근거가 아닙니다.</li>
  </ul>
  {fail_html}
</footer>
</main>
<script id="chart-data" type="application/json">{chart_json}</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>{JS}</script>
</body>
</html>
"""
    SITE.mkdir(exist_ok=True)
    out = SITE / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
