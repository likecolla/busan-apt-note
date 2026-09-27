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


def card_html(c):
    l84 = c["latest84"]
    if l84:
        latest = (f'<div class="big">{money_html(l84["price"])}</div>'
                  f'<div class="sub">{e(l84["date"])} · {floor_txt(l84)} · 전용 {area_txt(l84)}'
                  f'{" · 직거래" if l84.get("direct") else ""}</div>')
    else:
        latest = '<div class="sub">최근 6개월 84㎡형 거래 없음</div>'
    med = (f'{money_html(c["med3"])} <span class="sub">({c["n3"]}건)</span>'
           if c["med3"] else '<span class="sub">최근 3개월 84㎡형 거래 없음</span>')
    jr = ""
    if c["jeonse_ratio"]:
        j = c["jeonse_ratio"]
        jr = (f'<div class="stat"><div class="label">전세가율 (84㎡형, 최근 3개월)</div>'
              f'<div><strong>{j["ratio"] * 100:.0f}%</strong> '
              f'<span class="sub">= 전세 중간값 {e(format_won(j["jeonse"]))} ÷ 매매 중간값 {e(format_won(j["trade"]))}'
              f' · 전세 {j["n"]}건</span></div></div>')
    rows = "".join(deal_row(r) for r in c["recent"]) or \
        '<tr><td colspan="5" class="sub">최근 6개월 거래 없음</td></tr>'
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
    {jr}
  </div>
  <h4>최근 {e(c["kind_ko"])} 거래 5건 <span class="sub">(6개월 전체 {c["total"]}건)</span></h4>
  <div class="scroll"><table>
    <thead><tr><th>계약일</th><th>전용㎡</th><th>층</th><th>금액</th><th>표시</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  {move_in}
</article>'''


def new_section(ctx):
    meta = ctx["meta"]
    if not ctx["new_total"]:
        if meta.get("baseline_kinds"):
            return ('<p class="sub">이번 실행은 ' + e("·".join(meta["baseline_kinds"])) +
                    ' 자료의 첫 수집이라 기준선으로 저장했습니다. 다음 갱신부터 새로 신고된 거래가 여기에 표시됩니다.</p>')
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


def chart_table(ch):
    head = "".join(f"<th>{e(m[2:])}</th>" for m in ch["months"])
    body = ""
    for s in ch["series"]:
        cells = "".join(
            f'<td class="num">{e(format_won(p).split(" (")[1][:-1]) if p else "-"}'
            f'{f"<br><span class=unit>{n}건</span>" if n else ""}</td>'
            for p, n in zip(s["points"], s["counts"]))
        body += f'<tr><td>{e(s["name"])}<br><span class="unit">{e(s["kind"])}</span></td>{cells}</tr>'
    return f'<div class="scroll"><table class="compact"><thead><tr><th>단지</th>{head}</tr></thead><tbody>{body}</tbody></table></div>'


CSS = """
:root{--bg:#F2F4F3;--surface:#FBFCFB;--text:#1E2733;--muted:#5B6673;--line:#D5DBDE;
--accent:#1B3A5C;--accent2:#5E9C97;--point:#D8962B;--up:#B4412E;--tag-bg:#E6EAEA;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#12171D;--surface:#1A2129;--text:#E4E8EC;--muted:#9AA6B2;--line:#2C3642;
--accent:#9CC0E6;--accent2:#7FC0B9;--point:#E8AC4E;--up:#E27A66;--tag-bg:#26303B;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#2f9a2f;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#12171D;--surface:#1A2129;--text:#E4E8EC;--muted:#9AA6B2;--line:#2C3642;
--accent:#9CC0E6;--accent2:#7FC0B9;--point:#E8AC4E;--up:#E27A66;--tag-bg:#26303B;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#2f9a2f;color-scheme:dark}
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
"""

JS = r"""
(function(){
  var data = JSON.parse(document.getElementById('chart-data').textContent);
  function unit(won){ if(won==null) return '-'; var man=Math.floor((won+5000)/10000);
    var eok=Math.floor(man/10000), rest=man%10000, p=[];
    if(eok) p.push(eok.toLocaleString('ko-KR')+'억'); if(rest) p.push(rest.toLocaleString('ko-KR')+'만');
    return p.join(' ')||'0'; }
  function css(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  if(!window.Chart){ document.getElementById('chart-fallback').hidden=false; return; }
  var chart;
  function draw(){
    var muted=css('--muted'), line=css('--line'), surface=css('--surface');
    var ds = data.series.map(function(s,i){ var c=css('--s'+(i+1));
      return {label:s.name+' ('+s.kind+')', data:s.points, borderColor:c, backgroundColor:c,
        borderWidth:2, pointRadius:4, pointHoverRadius:6, pointBorderColor:surface, pointBorderWidth:2,
        spanGaps:true, tension:0.2, counts:s.counts}; });
    if(chart) chart.destroy();
    chart = new Chart(document.getElementById('trend'), {type:'line',
      data:{labels:data.months.map(function(m){return m.slice(2).replace('-','.');}), datasets:ds},
      options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index', intersect:false},
        plugins:{legend:{position:'bottom', labels:{color:muted, boxWidth:10, boxHeight:10, font:{size:11}}},
          tooltip:{callbacks:{label:function(c){ if(c.raw==null) return null;
            var n=c.dataset.counts[c.dataIndex]; return c.dataset.label+': '+unit(c.raw)+' ('+n+'건)'; }}}},
        scales:{x:{ticks:{color:muted}, grid:{display:false}, border:{color:line}},
          y:{ticks:{color:muted, callback:function(v){return (v/1e8).toFixed(1)+'억';}},
             grid:{color:line}, border:{display:false}}}}});
  }
  draw();
  if(window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
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
    chart_json = json.dumps(ctx["chart"], ensure_ascii=False).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>부산 대단지 실거래 노트</title>
<meta name="description" content="부산 관심 단지 6곳의 매매·분양권·전월세 실거래 기록">
<meta name="color-scheme" content="light dark">
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
<p class="sub">84㎡형 = 전용 75~90㎡. 해제된 거래는 가격 계산에서 빼고 표에만 취소선으로 남깁니다. 직거래는 계산에 포함합니다.</p>
{"".join(card_html(c) for c in ctx["cards"])}

<h2>가격 흐름 <span class="sub">(84㎡형 월별 중간값)</span></h2>
<p class="sub">분양권 단지는 분양권 거래가(분양가+웃돈), 나머지는 매매가입니다. 거래가 없는 달은 선을 이어 그립니다.</p>
<div class="chart-box"><canvas id="trend" role="img" aria-label="단지별 84㎡형 월별 중간값 꺾은선 그래프"></canvas></div>
<p id="chart-fallback" class="sub" hidden>그래프를 불러오지 못했습니다. 아래 표를 참고하세요.</p>
<details><summary>표로 보기</summary>{chart_table(ctx["chart"])}</details>

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
