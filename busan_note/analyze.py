"""수집된 레코드를 페이지용 숫자로 가공."""
import json
import statistics
from collections import defaultdict
from datetime import datetime

from . import api, collect

BANDS = ["60㎡ 미만", "60~75㎡", "84㎡형", "90㎡ 이상"]
BAND_84 = "84㎡형"
PYEONG_M2 = 3.3058          # 1평(3.3㎡)
MIN_SAMPLE = 5              # 이보다 적으면 '표본 적음'
FLOOR_BANDS = ["저층", "중층", "고층"]


def band(area):
    """전용면적 → 면적대. 84㎡형 = 75㎡ 이상 90㎡ 미만."""
    if area is None:
        return ""
    if area < 60:
        return BANDS[0]
    if area < 75:
        return BANDS[1]
    if area < 90:
        return BANDS[2]
    return BANDS[3]


def per_pyeong(price, area):
    """3.3㎡당 가격(원)."""
    if not price or not area:
        return None
    return price / (area / PYEONG_M2)


def floor_band(floor, top):
    """단지 최고층(top) 기준 3등분: 아래 1/3 저층, 위 1/3 고층."""
    try:
        f = int(floor)
    except (TypeError, ValueError):
        return ""
    if top <= 0:
        return ""
    if f <= top / 3:
        return FLOOR_BANDS[0]
    if f <= top * 2 / 3:
        return FLOOR_BANDS[1]
    return FLOOR_BANDS[2]


def jeonse_market(rows):
    """전세 보증금 목록. 신규 계약이 3건 이상이면 신규만(갱신 계약은 인상률 상한 5%로 시세보다 낮음)."""
    new = [r["deposit"] for r in rows if r.get("contract_type") == "신규" and r.get("deposit")]
    if len(new) >= 3:
        return new, "신규"
    return [r["deposit"] for r in rows if r.get("deposit")], "전체"


def median_won(values):
    """중간값을 만 원 단위로 사사오입."""
    values = [v for v in values if v]
    if not values:
        return None
    m = statistics.median(values)
    return (int(m) + 5000) // 10000 * 10000


def _norm(name):
    return (name or "").replace(" ", "")


def load_config():
    p = api.ROOT / "config" / "watchlist.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_watchlist():
    return load_config()["complexes"]


def load_meta():
    p = collect.DATA / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def ym(date_str):
    return date_str[:7]


def month_label(ym_compact):
    return f"{ym_compact[:4]}-{ym_compact[4:]}"


def shift_months(label, n):
    y, m = int(label[:4]), int(label[5:7])
    t = y * 12 + (m - 1) + n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def quarter(label):
    return f"{label[:4]} {(int(label[5:7]) - 1) // 3 + 1}분기"


def pct(a, b):
    return (a / b - 1) if a and b else None


def _match_index(complexes):
    idx = {}
    for i, c in enumerate(complexes):
        for n in c["names"]:
            idx[(c["lawd"], _norm(n))] = i
    return idx


def _pick_kind(c, mine):
    return next((k for k in c["views"] if any(r["kind"] == k for r in mine)), c["views"][0])


def complex_stats(c, mine, now_label):
    """단지 하나의 카드용 숫자."""
    last3 = {shift_months(now_label, -i) for i in range(3)}
    prev3 = {shift_months(now_label, -12 - i) for i in range(3)}
    last6 = {shift_months(now_label, -i) for i in range(6)}
    last12 = {shift_months(now_label, -i) for i in range(12)}

    kind = _pick_kind(c, mine)
    deals = sorted((r for r in mine if r["kind"] == kind), key=lambda r: r["date"], reverse=True)
    ok = [r for r in deals if not r.get("cancelled") and r.get("price")]
    ok84 = [r for r in ok if r["band"] == BAND_84]
    in3 = [r for r in ok84 if ym(r["date"]) in last3]
    med3 = median_won([r["price"] for r in in3])

    # 3.3㎡당 (모든 면적)
    pp3 = [r["ppy"] for r in ok if ym(r["date"]) in last3]
    pp_prev = [r["ppy"] for r in ok if ym(r["date"]) in prev3]
    ppy3, ppy_prev = median_won(pp3), median_won(pp_prev)

    peak = max(ok84, key=lambda r: r["price"]) if ok84 else None

    # 층 구간 (최근 12개월, 84㎡형)
    top = max((int(r["floor"]) for r in deals if str(r.get("floor", "")).lstrip("-").isdigit()), default=0)
    fb = defaultdict(list)
    for r in ok84:
        if ym(r["date"]) in last12:
            fb[floor_band(r["floor"], top)].append(r["price"])
    floors = [{"band": b, "med": median_won(fb[b]), "n": len(fb[b])} for b in FLOOR_BANDS]
    lo, hi = floors[0]["med"], floors[2]["med"]
    floor_premium = pct(hi, lo) if floors[0]["n"] >= 2 and floors[2]["n"] >= 2 else None

    # 해제·직거래 (최근 12개월, 이 자료 종류)
    d12 = [r for r in deals if ym(r["date"]) in last12]
    cancelled = [r for r in d12 if r.get("cancelled")]
    direct = [r for r in d12 if r.get("direct") and not r.get("cancelled")]
    # 해제된 거래 중 당시 같은 면적대 최고가 이상이었던 것
    peak_cancel = []
    for r in cancelled:
        before = [x["price"] for x in ok if x["band"] == r["band"] and x["date"] <= r["date"]]
        if r.get("price") and (not before or r["price"] >= max(before)):
            peak_cancel.append(r)

    # 동별 3.3㎡당 (최근 12개월, 매매만: 동 정보는 등기 완료 거래에만 있음)
    dongs = defaultdict(list)
    for r in ok:
        if r.get("dong") and ym(r["date"]) in last12:
            label = r["apt"].replace(c["names"][0].split("(")[0], "").strip("()") if len(c["names"]) > 1 else ""
            dongs[(label + " " if label else "") + f'{r["dong"].rstrip("동")}동'].append(r["ppy"])
    dong_rows = sorted(({"dong": k, "med": median_won(v), "n": len(v)} for k, v in dongs.items() if len(v) >= 2),
                       key=lambda x: x["med"], reverse=True)
    dong_spread = pct(dong_rows[0]["med"], dong_rows[-1]["med"]) if len(dong_rows) >= 2 else None

    jeonse_ratio = None
    if kind == "trade" and med3:
        j, basis = jeonse_market([r for r in mine if r["kind"] == "rent" and r["rent_type"] == "전세"
                                  and r["band"] == BAND_84 and ym(r["date"]) in last3])
        jm = median_won(j)
        if jm:
            jeonse_ratio = {"ratio": jm / med3, "jeonse": jm, "trade": med3, "n": len(j), "basis": basis}

    return {
        "name": c["name"], "gu": c["gu"], "kind": kind, "kind_ko": collect.KIND_KO[kind],
        "latest84": ok84[0] if ok84 else None, "med3": med3, "n3": len(in3),
        "low_sample": len(in3) < MIN_SAMPLE,
        "ppy3": ppy3, "ppy3_n": len(pp3), "ppy_prev": ppy_prev, "ppy_prev_n": len(pp_prev),
        "yoy": pct(ppy3, ppy_prev) if len(pp3) >= 3 and len(pp_prev) >= 3 else None,
        "peak": peak, "vs_peak": pct(med3, peak["price"]) if peak and med3 else None,
        "floors": floors, "floor_premium": floor_premium, "top_floor": top,
        "n12": len(d12), "cancel_n": len(cancelled), "direct_n": len(direct),
        "cancel_rate": len(cancelled) / len(d12) if d12 else None,
        "peak_cancel": sorted(peak_cancel, key=lambda r: r["date"], reverse=True)[:3],
        "recent": deals[:5], "n6": sum(1 for r in deals if ym(r["date"]) in last6),
        "jeonse_ratio": jeonse_ratio, "dongs": dong_rows, "dong_spread": dong_spread,
        "_ok": ok, "_ok84": ok84,
    }


def _reb_summary():
    try:
        from . import reb
        return reb.weekly_summary()
    except Exception:   # 부동산원 자료가 없어도 페이지는 만든다
        return None


def _applyhome_summary():
    try:
        from . import applyhome
        return applyhome.summary()
    except Exception:
        return None


def _kosis_summary():
    try:
        from . import kosis
        return kosis.summary()
    except Exception:   # KOSIS 자료가 없어도 페이지는 만든다
        return None


def build_context():
    recs = collect.load_all()
    cfg = load_config()
    watch = cfg["complexes"]
    refs = cfg.get("reference", [])
    meta = load_meta()
    now = datetime.now(collect.KST)
    now_label = now.strftime("%Y-%m")
    last_run = meta.get("last_run")

    for r in recs:
        r["band"] = band(r.get("area"))
        r["is_new"] = bool(last_run) and r.get("first_seen") == last_run
        r["ppy"] = per_pyeong(r.get("price"), r.get("area"))

    allcx = watch + refs
    index = _match_index(allcx)
    by_cx = defaultdict(list)
    for r in recs:
        i = index.get((r["lawd"], _norm(r["apt"])))
        r["watch"] = i is not None and i < len(watch)
        if i is not None:
            r["cx"] = allcx[i]["name"]
            by_cx[i].append(r)

    all_months = sorted({ym(r["date"]) for r in recs if r["date"]})
    stats = [complex_stats(c, by_cx[i], now_label) for i, c in enumerate(allcx)]
    by_name = {s["name"]: s for s in stats}

    cards, series = [], []
    for i, c in enumerate(watch):
        s = stats[i]
        mine = by_cx[i]
        m84, mpp = defaultdict(list), defaultdict(list)
        for r in s["_ok"]:
            mpp[ym(r["date"])].append(r["ppy"])
            if r["band"] == BAND_84:
                m84[ym(r["date"])].append(r["price"])
        series.append({"name": c["name"], "kind": s["kind_ko"],
                       "p84": [median_won(m84.get(m, [])) for m in all_months],
                       "n84": [len(m84.get(m, [])) for m in all_months],
                       "ppy": [median_won(mpp.get(m, [])) for m in all_months],
                       "nppy": [len(mpp.get(m, [])) for m in all_months]})
        if c.get("move_in_watch"):
            start = c.get("move_in_start", all_months[0] if all_months else "")
            months = [m for m in all_months if m >= start] or [start]
            rows = []
            for m in months:
                rent_m = [r for r in mine if r["kind"] == "rent" and ym(r["date"]) == m]
                j_all = [r for r in rent_m if r["rent_type"] == "전세"]
                rows.append({"month": m, "jeonse_n": len(j_all),
                             "wolse_n": sum(1 for r in rent_m if r["rent_type"] == "월세"),
                             "jeonse_med84": median_won([r["deposit"] for r in j_all if r["band"] == BAND_84]),
                             "trade_n": sum(1 for r in mine if r["kind"] == "trade" and ym(r["date"]) == m
                                            and not r.get("cancelled"))})
            s["move_in"] = {"start": start, "rows": rows}
        try:
            from . import kapt
            s["kapt"] = kapt.load().get(c["name"])
        except Exception:
            s["kapt"] = None
        cards.append(s)

    # 두 단지 비교: 분기별 3.3㎡당 중간값
    compares = []
    for cp in cfg.get("compare", []):
        a, b = by_name.get(cp["a"]), by_name.get(cp["b"])
        if not a or not b:
            continue
        qa, qb = defaultdict(list), defaultdict(list)
        for r in a["_ok"]:
            qa[quarter(ym(r["date"]))].append(r["ppy"])
        for r in b["_ok"]:
            qb[quarter(ym(r["date"]))].append(r["ppy"])
        quarters = sorted(set(qa) | set(qb))
        rows = []
        for q in quarters:
            ma, mb = median_won(qa.get(q, [])), median_won(qb.get(q, []))
            rows.append({"q": q, "a": ma, "an": len(qa.get(q, [])), "b": mb, "bn": len(qb.get(q, [])),
                         "gap": pct(ma, mb) if len(qa.get(q, [])) >= 3 and len(qb.get(q, [])) >= 3 else None})
        compares.append({"title": cp.get("title", f'{cp["a"]} vs {cp["b"]}'), "note": cp.get("note", ""),
                         "a": cp["a"], "b": cp["b"], "a_kind": a["kind_ko"], "b_kind": b["kind_ko"],
                         "rows": rows})

    # 거래량: 구별 월별 매매 건수(해제 제외)
    vol = defaultdict(int)
    for r in recs:
        if r["kind"] == "trade" and not r.get("cancelled") and r["date"]:
            vol[(r["lawd"], ym(r["date"]))] += 1
    incomplete = {now_label, shift_months(now_label, -1)}   # 신고 기한이 남은 달
    complete = [m for m in all_months if m not in incomplete]
    recent3 = complete[-3:]
    volume = []
    for lawd, gu in collect.LAWD.items():
        base = [vol[(lawd, m)] for m in complete]
        avg = sum(base) / len(base) if base else 0
        r3 = sum(vol[(lawd, m)] for m in recent3) / len(recent3) if recent3 else 0
        volume.append({"gu": gu, "avg": avg, "recent": r3, "ratio": r3 / avg if avg else None,
                       "series": [vol[(lawd, m)] for m in all_months]})
    total_series = [sum(vol[(l, m)] for l in collect.LAWD) for m in all_months]

    from . import predict
    predictions = predict.evaluate({c["name"]: by_cx[i] for i, c in enumerate(allcx)},
                                   {st["name"]: st["kind"] for st in stats}, now_label)

    new = [r for r in recs if r["is_new"]]
    new_watch = sorted((r for r in new if r["watch"]), key=lambda r: r["date"], reverse=True)
    new_other = sorted((r for r in new if not r["watch"]),
                       key=lambda r: r.get("price") or r.get("deposit") or 0, reverse=True)[:20]

    return {
        "now": now, "meta": meta, "cards": cards,
        "chart": {"months": all_months, "series": series},
        "compares": compares, "predictions": predictions, "reb": _reb_summary(), "kosis": _kosis_summary(), "applyhome": _applyhome_summary(),
        "volume": {"rows": volume, "months": all_months, "total": total_series,
                   "incomplete": sorted(incomplete), "recent3": recent3,
                   "span": (complete[0], complete[-1]) if complete else ("", "")},
        "new_total": len(new), "new_watch": new_watch, "new_other": new_other,
        "range": (all_months[0], all_months[-1]) if all_months else ("", ""),
    }
