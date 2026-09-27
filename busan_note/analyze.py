"""수집된 레코드를 페이지용 숫자로 가공."""
import json
import statistics
from collections import defaultdict
from datetime import datetime

from . import api, collect

BANDS = ["60㎡ 미만", "60~75㎡", "84㎡형", "90㎡ 이상"]
BAND_84 = "84㎡형"


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


def median_won(values):
    """중간값을 만 원 단위로 사사오입."""
    if not values:
        return None
    m = statistics.median(values)
    return (int(m) + 5000) // 10000 * 10000


def _norm(name):
    return (name or "").replace(" ", "")


def load_watchlist():
    p = api.ROOT / "config" / "watchlist.json"
    return json.loads(p.read_text(encoding="utf-8"))["complexes"]


def load_meta():
    p = collect.DATA / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def ym(date_str):
    return date_str[:7]


def month_label(ym_compact):
    return f"{ym_compact[:4]}-{ym_compact[4:]}"


def build_context():
    recs = collect.load_all()
    watch = load_watchlist()
    meta = load_meta()
    now = datetime.now(collect.KST)
    last3 = {month_label(m) for m in collect.months_back(3, now.date())}
    last_run = meta.get("last_run")

    for r in recs:
        r["band"] = band(r.get("area"))
        r["is_new"] = bool(last_run) and r.get("first_seen") == last_run

    # 단지 매칭
    index = {}
    for i, c in enumerate(watch):
        for n in c["names"]:
            index[(c["lawd"], _norm(n))] = i
    by_cx = defaultdict(list)
    for r in recs:
        i = index.get((r["lawd"], _norm(r["apt"])))
        r["watch"] = i is not None
        if i is not None:
            r["cx"] = watch[i]["name"]
            by_cx[i].append(r)

    all_months = sorted({ym(r["date"]) for r in recs if r["date"]})
    cards, series = [], []
    for i, c in enumerate(watch):
        mine = by_cx[i]
        kind = next((k for k in c["views"] if any(r["kind"] == k for r in mine)), c["views"][0])
        deals = sorted((r for r in mine if r["kind"] == kind), key=lambda r: r["date"], reverse=True)
        ok84 = [r for r in deals if r["band"] == BAND_84 and not r.get("cancelled") and r.get("price")]
        med3 = median_won([r["price"] for r in ok84 if ym(r["date"]) in last3])
        n3 = sum(1 for r in ok84 if ym(r["date"]) in last3)

        jeonse_ratio = None
        if kind == "trade" and med3:
            j = [r["deposit"] for r in mine if r["kind"] == "rent" and r["rent_type"] == "전세"
                 and r["band"] == BAND_84 and ym(r["date"]) in last3 and r.get("deposit")]
            jm = median_won(j)
            if jm:
                jeonse_ratio = {"ratio": jm / med3, "jeonse": jm, "trade": med3, "n": len(j)}

        monthly = defaultdict(list)
        for r in ok84:
            monthly[ym(r["date"])].append(r["price"])
        series.append({"name": c["name"], "kind": collect.KIND_KO[kind],
                       "points": [median_won(monthly.get(m, [])) for m in all_months],
                       "counts": [len(monthly.get(m, [])) for m in all_months]})

        card = {"name": c["name"], "gu": c["gu"], "kind": kind, "kind_ko": collect.KIND_KO[kind],
                "latest84": ok84[0] if ok84 else None, "med3": med3, "n3": n3,
                "recent": deals[:5], "jeonse_ratio": jeonse_ratio, "total": len(deals)}

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
            card["move_in"] = {"start": start, "rows": rows}
        cards.append(card)

    new = [r for r in recs if r["is_new"]]
    new_watch = sorted((r for r in new if r["watch"]), key=lambda r: r["date"], reverse=True)
    new_other = sorted((r for r in new if not r["watch"]),
                       key=lambda r: r.get("price") or r.get("deposit") or 0, reverse=True)[:20]

    return {
        "now": now, "meta": meta, "cards": cards,
        "chart": {"months": all_months, "series": series},
        "new_total": len(new), "new_watch": new_watch, "new_other": new_other,
        "range": (all_months[0], all_months[-1]) if all_months else ("", ""),
    }
