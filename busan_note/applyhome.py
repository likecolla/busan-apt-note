"""청약홈(한국부동산원) 분양정보·경쟁률: 부산 APT 분양 공고.

공공데이터포털 인증키(DATA_GO_KR_KEY)를 그대로 쓴다. 자료는 data/applyhome/busan.json 에 합쳐 저장한다.
"""
import json
import re
import time
from collections import defaultdict
from datetime import date, timedelta

from . import api
import requests

NOTICE_URL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"
CMPET_URL = "https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet"
OUT = api.ROOT / "data" / "applyhome" / "busan.json"
FIRST_DAY = "2023-01-01"
KEEP = ("HOUSE_MANAGE_NO", "HOUSE_NM", "HSSPLY_ADRES", "TOT_SUPLY_HSHLDCO", "RCRIT_PBLANC_DE",
        "RCEPT_BGNDE", "RCEPT_ENDDE", "PRZWNER_PRESNATN_DE", "MVN_PREARNGE_YM", "CNSTRCT_ENTRPS_NM",
        "HOUSE_DTL_SECD_NM", "RENT_SECD_NM", "PBLANC_URL")


def _get(url, key, **params):
    params = dict(params, serviceKey=key)
    for wait in (5, 20, None):
        try:
            r = requests.get(url, params=params, timeout=60)
            break
        except requests.RequestException as e:
            if wait is None:
                raise api.ApiError("네트워크 오류: " + api.mask(e))
            time.sleep(wait)
    try:
        return r.json()
    except ValueError:
        raise api.ApiError(f"HTTP {r.status_code}: " + api.mask(" ".join(r.text[:160].split())))


def _all(url, key, **cond):
    rows, page = [], 1
    while True:
        j = _get(url, key, page=page, perPage=500, **cond)
        if "data" not in j:
            raise api.ApiError(api.mask(str(j)[:160]))
        rows.extend(j["data"])
        if len(rows) >= j.get("matchCount", 0) or not j["data"]:
            return rows
        page += 1
        time.sleep(0.3)


def collect(log=print):
    """부산 분양 공고와 경쟁률을 받아 합쳐 저장. 실패 목록 반환(실패해도 기존 자료 유지)."""
    _, key = api.resolve_key(log=log)
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"notices": {}, "cmpet": {}}
    failures = []
    since = (date.today() - timedelta(days=120)).isoformat() if old["notices"] else FIRST_DAY
    try:
        rows = _all(NOTICE_URL, key, **{"cond[SUBSCRPT_AREA_CODE_NM::EQ]": "부산",
                                        "cond[RCRIT_PBLANC_DE::GTE]": since})
        for r in rows:
            old["notices"][r["HOUSE_MANAGE_NO"]] = {k: r.get(k) for k in KEEP}
        log(f"청약홈 분양 공고: {since}부터 {len(rows)}건")
    except api.ApiError as e:
        failures.append({"kind": "청약홈 분양정보", "gu": "부산", "ym": "", "error": str(e)[:160]})
        log(f"실패: 청약홈 분양정보 — {e}")
    # 경쟁률: 없거나 접수 후 60일 안인 공고만 다시 받는다
    recent = (date.today() - timedelta(days=60)).isoformat()
    for no, n in old["notices"].items():
        if no in old["cmpet"] and (n.get("RCEPT_ENDDE") or "") < recent:
            continue
        if (n.get("RCEPT_BGNDE") or "9999") > date.today().isoformat():
            continue   # 아직 접수 전
        try:
            old["cmpet"][no] = [{k: r.get(k) for k in ("HOUSE_TY", "SUPLY_HSHLDCO", "REQ_CNT", "CMPET_RATE",
                                                        "RESIDE_SENM", "SUBSCRPT_RANK_CODE")}
                                for r in _all(CMPET_URL, key, **{"cond[HOUSE_MANAGE_NO::EQ]": no})]
        except api.ApiError as e:
            failures.append({"kind": "청약홈 경쟁률", "gu": n.get("HOUSE_NM", no), "ym": "", "error": str(e)[:160]})
        time.sleep(0.3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(old, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"청약홈: 공고 {len(old['notices'])}건, 경쟁률 {len(old['cmpet'])}건, 실패 {len(failures)}건")
    return failures


def _int(v):
    try:
        return int(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0


def competition(rows):
    """1순위 경쟁률(해당지역, 전체)과 미달 주택형 수."""
    if not rows:
        return None
    supply = {}
    req_local, req_all, req_by_type = 0, 0, defaultdict(int)
    for r in rows:
        ty = r["HOUSE_TY"]
        supply[ty] = _int(r["SUPLY_HSHLDCO"])
        req_by_type[ty] += _int(r["REQ_CNT"])
        if r["SUBSCRPT_RANK_CODE"] == 1:
            req_all += _int(r["REQ_CNT"])
            if r["RESIDE_SENM"] == "해당지역":
                req_local += _int(r["REQ_CNT"])
    total = sum(supply.values())
    if not total:
        return None
    short = sum(1 for ty, s in supply.items() if req_by_type[ty] < s)
    return {"supply": total, "local": req_local / total, "all": req_all / total,
            "types": len(supply), "short": short}


def _gu(addr):
    m = re.search(r"부산광역시\s+(\S+[구군])", addr or "")
    return m.group(1) if m else ""


def summary(today=None):
    if not OUT.exists():
        return None
    d = json.loads(OUT.read_text(encoding="utf-8"))
    today = (today or date.today()).isoformat()
    items = []
    for no, n in d["notices"].items():
        if n.get("RENT_SECD_NM") and "임대" in n["RENT_SECD_NM"] and "분양" not in n["RENT_SECD_NM"]:
            continue
        items.append(dict(n, gu=_gu(n.get("HSSPLY_ADRES")), comp=competition(d["cmpet"].get(no))))
    items.sort(key=lambda x: x.get("RCRIT_PBLANC_DE") or "", reverse=True)
    upcoming = [x for x in items if (x.get("RCEPT_BGNDE") or "") >= today]
    past = [x for x in items if (x.get("RCEPT_BGNDE") or "") < today]
    by_year = defaultdict(int)
    for x in items:
        y = (x.get("MVN_PREARNGE_YM") or "")[:4]
        if y and y >= today[:4]:
            by_year[y] += _int(x.get("TOT_SUPLY_HSHLDCO"))
    last12 = [x for x in past if (x.get("RCRIT_PBLANC_DE") or "") >= f"{int(today[:4]) - 1}{today[4:]}"]
    comps = [x["comp"] for x in last12 if x["comp"]]
    return {
        "upcoming": upcoming, "recent": past[:15],
        "movein_by_year": dict(sorted(by_year.items())),
        "last12_n": len(last12),
        "last12_supply": sum(c["supply"] for c in comps),
        "last12_short": sum(1 for c in comps if c["short"]),
        "last12_req": sum(c["all"] * c["supply"] for c in comps),
    }
