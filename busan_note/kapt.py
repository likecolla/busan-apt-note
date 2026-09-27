"""공동주택관리정보(K-apt): 관심 단지의 세대수·동 수·사용승인일·주차·교통.

공공데이터포털 인증키(DATA_GO_KR_KEY)를 쓴다. 단지 코드는 이름으로 찾아 data/kapt/complexes.json 에 저장한다.
config/watchlist.json 의 단지에 "kapt": ["A1234..."] 를 적으면 이름 찾기 대신 그 코드를 쓴다.
"""
import json
import re
import time
from datetime import date

from . import api
import requests

LIST_URL = "https://apis.data.go.kr/1613000/AptListService4/getSigunguAptList4"
BASS_URL = "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5"
DTL_URL = "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusDtlInfoV5"
OUT = api.ROOT / "data" / "kapt" / "complexes.json"
REFRESH_DAYS = 30


def _json(url, key, **params):
    for wait in (5, 20, None):
        try:
            r = requests.get(url, params=dict(params, serviceKey=key, _type="json"), timeout=30)
            break
        except requests.RequestException as e:
            if wait is None:
                raise api.ApiError("네트워크 오류: " + api.mask(e))
            time.sleep(wait)
    try:
        j = r.json()["response"]
    except (ValueError, KeyError):
        raise api.ApiError(f"HTTP {r.status_code}: " + api.mask(" ".join(r.text[:160].split())))
    if j["header"]["resultCode"] not in ("00", "000"):
        raise api.ApiError(j["header"]["resultMsg"])
    return j["body"]


def _norm(s):
    return re.sub(r"[\s()\-·.]|아파트", "", (s or "").lower())


def find_codes(key, lawd, names):
    body = _json(LIST_URL, key, sigunguCode=lawd, pageNo=1, numOfRows=1000)
    items = body.get("items") or []
    items = items if isinstance(items, list) else [items.get("item")]
    base = {_norm(re.sub(r"\(.*\)|\d+단지$|\d+차$", "", n)) for n in names}
    exact = {_norm(n) for n in names}
    hit = [i for i in items if _norm(i["kaptName"]) in exact]
    if not hit:
        hit = [i for i in items if any(b and b in _norm(i["kaptName"]) for b in base)]
    return [(i["kaptCode"], i["kaptName"]) for i in hit]


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def collect(complexes, log=print):
    """단지별 기본·상세 정보를 모은다. 한 달이 지나지 않았으면 다시 받지 않는다."""
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    today = date.today().isoformat()
    _, key = api.resolve_key(log=log)
    failures = []
    for c in complexes:
        prev = old.get(c["name"])
        if prev and prev.get("fetched", "") > (date.fromisoformat(today).replace(day=1)).isoformat() and prev.get("units"):
            continue
        try:
            codes = [(k, "") for k in c["kapt"]] if c.get("kapt") else find_codes(key, c["lawd"], c["names"])
            if not codes:
                old[c["name"]] = {"fetched": today, "codes": [], "note": "K-apt 미등록(입주 전이거나 이름이 다름)"}
                continue
            parts = []
            for code, nm in codes:
                b = _json(BASS_URL, key, kaptCode=code).get("item") or {}
                dt = _json(DTL_URL, key, kaptCode=code).get("item") or {}
                parts.append({"code": code, "name": b.get("kaptName") or nm,
                              "units": _num(b.get("kaptdaCnt") or b.get("hoCnt")),
                              "dongs": _num(b.get("kaptDongCnt")), "top": _num(b.get("kaptTopFloor")),
                              "used": b.get("kaptUsedate") or "", "builder": b.get("kaptBcompany") or "",
                              "heat": b.get("codeHeatNm") or "",
                              "park": _num(dt.get("kaptdPcnt")) + _num(dt.get("kaptdPcntu")),
                              "subway": " ".join(x for x in (dt.get("subwayLine"), dt.get("subwayStation")) if x),
                              "subway_time": dt.get("kaptdWtimesub") or "",
                              "ev": _num(dt.get("groundElChargerCnt")) + _num(dt.get("undergroundElChargerCnt"))})
                time.sleep(0.3)
            units = sum(p["units"] for p in parts)
            used = sorted(p["used"] for p in parts if p["used"])
            old[c["name"]] = {
                "fetched": today, "codes": [(p["code"], p["name"]) for p in parts],
                "units": int(units), "dongs": int(sum(p["dongs"] for p in parts)),
                "top": int(max(p["top"] for p in parts)), "used": used[0] if used else "",
                "used_last": used[-1] if used else "",
                "park": int(sum(p["park"] for p in parts)),
                "park_per_unit": round(sum(p["park"] for p in parts) / units, 2) if units else None,
                "builder": ", ".join(sorted({p["builder"] for p in parts if p["builder"]})),
                "heat": parts[0]["heat"], "subway": parts[0]["subway"], "subway_time": parts[0]["subway_time"],
                "ev": int(sum(p["ev"] for p in parts)),
            }
            log(f"K-apt {c['name']}: {len(parts)}개 단지 코드, {int(units):,}세대")
        except api.ApiError as e:
            failures.append({"kind": "공동주택 정보", "gu": c["name"], "ym": "", "error": str(e)[:160]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
    return failures


def load():
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
