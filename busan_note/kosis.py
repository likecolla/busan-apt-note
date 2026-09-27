"""통계청 KOSIS Open API: 부산 미분양·준공 후 미분양·착공·준공·인구이동.

인증키는 환경변수 KOSIS_KEY 에서만 읽는다. 자료는 data/kosis/busan.json 에 합쳐 저장한다.
"""
import json
import os
import re
import time

from . import api  # api 를 먼저 불러 urllib3 경고 필터를 적용
import requests

URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
OUT = api.ROOT / "data" / "kosis" / "busan.json"
FIRST_MONTHS = 60     # 처음 받을 개월 수
REFETCH_MONTHS = 6    # 이후 다시 받을 개월 수(수정 반영)

GU_CODES = {  # 행정구역 코드 → 이름 (인구이동 표)
    "26": "부산", "26110": "중구", "26140": "서구", "26170": "동구", "26200": "영도구",
    "26230": "부산진구", "26260": "동래구", "26290": "남구", "26320": "북구", "26350": "해운대구",
    "26380": "사하구", "26410": "금정구", "26440": "강서구", "26470": "연제구", "26500": "수영구",
    "26530": "사상구", "26710": "기장군",
}


class KosisError(Exception):
    pass


def get_key():
    api.load_dotenv()
    k = os.environ.get("KOSIS_KEY", "").strip()
    if not k:
        raise KosisError(".env 또는 환경변수에 KOSIS_KEY 가 비어 있습니다.")
    api._SECRETS.add(k)
    return k


def mask(text):
    return api.mask(re.sub(r"(apiKey=)[^&\s]+", r"\1***", str(text)))


def fetch(key, org, tbl, itm, months, **objs):
    p = dict(method="getList", apiKey=key, orgId=org, tblId=tbl, itmId=itm, prdSe="M",
             newEstPrdCnt=months, format="json", jsonVD="Y", **objs)
    for wait in (5, 20, None):
        try:
            r = requests.get(URL, params=p, timeout=60)
            break
        except requests.RequestException as e:
            if wait is None:
                raise KosisError("네트워크 오류: " + mask(e))
            time.sleep(wait)
    try:
        data = r.json()
    except ValueError:
        raise KosisError(f"HTTP {r.status_code}: " + mask(r.text[:160]))
    if isinstance(data, dict):
        raise KosisError(f'{data.get("err")} {data.get("errMsg")}')
    return data


def _gu(name):
    return (name or "").replace(" ", "")


def collect(log=print):
    """자료를 받아 합쳐 저장. 실패 목록 반환(실패한 항목은 기존 값 유지)."""
    key = get_key()
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    n = REFETCH_MONTHS if old else FIRST_MONTHS
    out = {k: old.get(k, {}) for k in ("unsold", "unsold_done", "starts", "completions", "migration")}
    failures = []

    def run(label, fn):
        try:
            fn()
            log(f"KOSIS {label}: 최근 {n}개월")
        except KosisError as e:
            msg = mask(e)[:160]
            failures.append({"kind": f"KOSIS {label}", "gu": "부산", "ym": "", "error": msg})
            log(f"실패: KOSIS {label} — {msg} (기존 자료 유지)")
        time.sleep(0.5)

    def unsold():   # 시·군·구별 미분양현황(국토부)
        for r in fetch(key, "116", "DT_MLTM_2082", "ALL", n, objL1="13102871087A.0003", objL2="ALL"):
            if r.get("C1_NM") == "부산":
                gu = "부산" if r["C2_NM"] == "계" else _gu(r["C2_NM"])
                out["unsold"].setdefault(gu, {})[r["PRD_DE"]] = int(r["DT"])

    def unsold_done():  # 공사완료 후 미분양(부산, 부문 계, 규모 계)
        for r in fetch(key, "116", "DT_MLTM_5328", "ALL", n, objL1="13102871088A.0003", objL2="ALL",
                       objL3="13102871088C.0001", objL4="13102871088D.0001"):
            gu = "부산" if r["C2_NM"] in ("계", "합계") else _gu(r["C2_NM"])
            out["unsold_done"].setdefault(gu, {})[r["PRD_DE"]] = int(r["DT"])

    def starts_completions():   # 착공·준공(시도별, 총계)
        for key_name, tbl, c in (("starts", "DT_MLTM_5386", "13102766971"), ("completions", "DT_MLTM_5372", "13102766972")):
            for r in fetch(key, "116", tbl, "ALL", n, objL1=f"{c}A.0001", objL2=f"{c}B.0001", objL3=f"{c}C.0005"):
                if r.get("C3_NM") == "부산" and r.get("C1_NM") == "총계" and r.get("C2_NM") == "총계":
                    out[key_name][r["PRD_DE"]] = int(r["DT"])
            time.sleep(0.5)

    def migration():    # 시군구별 이동자수(통계청): 총전입·총전출·순이동
        itm_key = {"T10": "in", "T20": "out", "T25": "net"}
        for r in fetch(key, "101", "DT_1B26001_A01", "T10+T20+T25", n, objL1="+".join(GU_CODES)):
            gu = GU_CODES.get(r["C1"], _gu(r["C1_NM"]))
            out["migration"].setdefault(gu, {}).setdefault(r["PRD_DE"], {})[itm_key[r["ITM_ID"]]] = int(r["DT"])

    run("미분양", unsold)
    run("준공 후 미분양", unsold_done)
    run("착공·준공", starts_completions)
    run("인구이동", migration)

    for k in ("unsold", "unsold_done", "migration"):
        out[k] = {g: dict(sorted(v.items())) for g, v in out[k].items()}
    for k in ("starts", "completions"):
        out[k] = dict(sorted(out[k].items()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return failures


def _ym_shift(ym, k):
    t = int(ym[:4]) * 12 + int(ym[4:]) - 1 + k
    return f"{t // 12:04d}{t % 12 + 1:02d}"


def summary():
    """페이지용 요약. 자료가 없으면 None."""
    if not OUT.exists():
        return None
    d = json.loads(OUT.read_text(encoding="utf-8"))
    un, done = d.get("unsold", {}), d.get("unsold_done", {})
    if "부산" not in un:
        return None
    last = max(un["부산"])
    prev, yago = _ym_shift(last, -1), _ym_shift(last, -12)

    def row(gu):
        u, dn = un.get(gu, {}), done.get(gu, {})
        return {"gu": gu, "now": u.get(last), "prev": u.get(prev), "yago": u.get(yago),
                "done": dn.get(last)}

    gus = sorted((g for g in un if g != "부산"), key=lambda g: un[g].get(last, 0), reverse=True)

    def sum12(series, end):
        ks = [_ym_shift(end, -i) for i in range(12)]
        vals = [series.get(k) for k in ks]
        return sum(v for v in vals if v is not None) if all(v is not None for v in vals) else None

    sc_last = max(d.get("starts", {}) or {"": 0})
    mig = d.get("migration", {})
    mig_last = max(mig.get("부산", {}) or {"": 0})
    mig_rows = []
    for g in ["부산"] + [x for x in GU_CODES.values() if x != "부산"]:
        m = mig.get(g, {})
        last3 = [m.get(_ym_shift(mig_last, -i), {}).get("net") for i in range(3)]
        last12 = [m.get(_ym_shift(mig_last, -i), {}).get("net") for i in range(12)]
        mig_rows.append({"gu": g, "net_last": last3[0],
                         "net_3m": sum(v for v in last3 if v is not None) if None not in last3 else None,
                         "net_12m": sum(v for v in last12 if v is not None) if None not in last12 else None})
    months = sorted(un["부산"])[-60:]
    return {
        "last": last, "busan": row("부산"), "gus": [row(g) for g in gus],
        "series": {"months": months, "unsold": [un["부산"].get(m) for m in months],
                   "done": [done.get("부산", {}).get(m) for m in months]},
        "supply_last": sc_last,
        "starts_12m": sum12(d.get("starts", {}), sc_last),
        "starts_prev12m": sum12(d.get("starts", {}), _ym_shift(sc_last, -12)),
        "completions_12m": sum12(d.get("completions", {}), sc_last),
        "completions_prev12m": sum12(d.get("completions", {}), _ym_shift(sc_last, -12)),
        "mig_last": mig_last, "migration": mig_rows,
    }
