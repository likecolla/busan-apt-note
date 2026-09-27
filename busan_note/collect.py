"""수집 → 정규화 → data/ 에 월별 JSON 으로 누적 저장."""
import json
import logging
from datetime import date, datetime, timezone, timedelta

from . import api

KST = timezone(timedelta(hours=9))
DATA = api.ROOT / "data"
KINDS = ("trade", "presale", "rent")
KIND_KO = {"trade": "매매", "presale": "분양권", "rent": "전월세"}
LAWD = {
    "26350": "해운대구", "26500": "수영구", "26290": "남구",
    "26230": "부산진구", "26260": "동래구", "26470": "연제구",
}
log = logging.getLogger("busan_note")


def months_back(n, today=None):
    """이번 달 포함 최근 n개월 YYYYMM 목록(오래된 순)."""
    d = today or datetime.now(KST).date()
    y, m, out = d.year, d.month, []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]


def _num(s):
    s = (s or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _manwon_to_won(s):
    v = _num(s)
    return None if v is None else int(round(v * 10000))


def normalize(kind, raw):
    """API 원본 항목 → 공통 레코드. 원본은 raw 로 그대로 보관."""
    y, m, d = raw.get("dealYear", ""), raw.get("dealMonth", ""), raw.get("dealDay", "")
    rec = {
        "kind": kind,
        "lawd": raw.get("sggCd", ""),
        "umd": raw.get("umdNm", ""),
        "apt": raw.get("aptNm", ""),
        "aptSeq": raw.get("aptSeq", ""),
        "jibun": raw.get("jibun", ""),
        "dong": raw.get("aptDong", ""),
        "date": f"{int(y):04d}-{int(m):02d}-{int(d):02d}" if y and m and d else "",
        "area": _num(raw.get("excluUseAr")),
        "floor": raw.get("floor", ""),
    }
    if kind in ("trade", "presale"):
        rec["price"] = _manwon_to_won(raw.get("dealAmount"))
        rec["cancelled"] = bool(raw.get("cdealType", "").strip())
        rec["cancel_date"] = raw.get("cdealDay", "")
        rec["direct"] = raw.get("dealingGbn", "").strip() == "직거래"
        if kind == "presale":
            rec["ownership"] = raw.get("ownershipGbn", "")
    else:
        rec["deposit"] = _manwon_to_won(raw.get("deposit"))
        rec["monthly"] = _manwon_to_won(raw.get("monthlyRent")) or 0
        rec["rent_type"] = "전세" if rec["monthly"] == 0 else "월세"
        rec["contract_type"] = raw.get("contractType", "")
    return rec


def rec_key(r):
    """중복 판정 키. 해제 여부는 나중에 바뀌므로 키에서 제외."""
    money = r.get("price") if r["kind"] != "rent" else f'{r.get("deposit")}/{r.get("monthly")}'
    return "|".join(str(x) for x in (
        r["kind"], r["lawd"], r["aptSeq"] or r["apt"], r["jibun"], r["dong"],
        r["date"], r["area"], r["floor"], money))


def _month_file(kind, ym):
    return DATA / kind / f"{ym}.json"


def load_month(kind, ym):
    p = _month_file(kind, ym)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_month(kind, ym, recs):
    p = _month_file(kind, ym)
    p.parent.mkdir(parents=True, exist_ok=True)
    recs = sorted(recs, key=lambda r: (r["lawd"], r["date"], r["apt"], str(r["floor"])))
    lines = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in recs)
    p.write_text("[\n" + lines + "\n]\n", encoding="utf-8")


def has_data(kind):
    d = DATA / kind
    return d.exists() and any(d.glob("*.json"))


def run_collect(months=None, kinds=KINDS, backfill=False):
    """수집 실행. 자료 종류별로 기존 데이터가 없으면 6개월(기준선), 있으면 3개월.
    기준선 수집분은 '새로 신고된 거래'로 세지 않는다."""
    run_id = datetime.now(KST).strftime("%Y-%m-%dT%H:%M")
    label, key = api.resolve_key()
    log.info("키 확인 OK (%s 키 방식)", label)
    failures, new_count, baseline_kinds, all_yms = [], 0, [], set()
    for kind in kinds:
        baseline = backfill or not has_data(kind)
        if baseline:
            baseline_kinds.append(KIND_KO[kind])
        yms = months_back(months or (6 if baseline else 3))
        all_yms.update(yms)
        log.info("[%s] %s ~ %s %s", KIND_KO[kind], yms[0], yms[-1], "(첫 수집·기준선)" if baseline else "")
        for ym in yms:
            existing = {rec_key(r): r for r in load_month(kind, ym)}
            got_any = False
            for lawd in LAWD:
                try:
                    items = api.fetch_all(kind, lawd, ym, key)
                except api.ApiError as e:
                    msg = " ".join(api.mask(e).split())[:160]
                    log.warning("실패: %s %s %s — %s", KIND_KO[kind], LAWD[lawd], ym, msg)
                    failures.append({"kind": KIND_KO[kind], "gu": LAWD[lawd], "ym": ym, "error": msg})
                    continue
                got_any = True
                for raw in items:
                    r = normalize(kind, raw)
                    r["lawd"] = r["lawd"] or lawd
                    k = rec_key(r)
                    if k in existing:
                        r["first_seen"] = existing[k].get("first_seen", run_id)
                    else:
                        r["first_seen"] = "baseline" if baseline else run_id
                        if not baseline:
                            new_count += 1
                    existing[k] = r
                log.info("%s %s %s: %d건", KIND_KO[kind], LAWD[lawd], ym, len(items))
            if got_any:
                save_month(kind, ym, existing.values())
    meta = {"last_run": run_id, "baseline_kinds": baseline_kinds, "new_count": new_count,
            "months": sorted(all_yms), "failures": failures}
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def load_all(kinds=KINDS):
    out = []
    for k in kinds:
        d = DATA / k
        if d.exists():
            for p in sorted(d.glob("*.json")):
                out.extend(json.loads(p.read_text(encoding="utf-8")))
    return out
