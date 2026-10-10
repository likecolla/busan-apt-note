"""한국부동산원 R-ONE Open API (부동산통계). 인증키는 환경변수 REB_KEY 에서만 읽는다."""
import os
import re
import time

from . import api  # api 를 먼저 불러 urllib3 경고 필터를 적용
import requests

BASE = "https://www.reb.or.kr/r-one/openapi/"


class RebError(Exception):
    pass


def get_key():
    api.load_dotenv()
    k = os.environ.get("REB_KEY", "").strip()
    if not k:
        raise RebError(".env 또는 환경변수에 REB_KEY 가 비어 있습니다.")
    api._SECRETS.add(k)
    return k


def mask(text):
    return api.mask(re.sub(r"(KEY=)[^&\s]+", r"\1***", str(text)))


def call(service, key, page_size=1000, max_pages=200, timeout=20, retries=(3, 10), **params):
    """모든 페이지를 받아 row 목록을 돌려준다."""
    rows, page = [], 1
    while page <= max_pages:
        q = dict(params, KEY=key, Type="json", pIndex=page, pSize=page_size)
        for wait in (*retries, None):
            try:
                r = requests.get(BASE + service, params=q, timeout=timeout)
                break
            except requests.RequestException as e:
                if wait is None:
                    raise RebError("네트워크 오류: " + mask(e))
                time.sleep(wait)
        try:
            data = r.json()
        except ValueError:
            raise RebError(f"HTTP {r.status_code}: " + mask(r.text[:200]))
        name = service.replace(".do", "")
        if name not in data:
            res = data.get("RESULT", {})
            if res.get("CODE") == "INFO-200":   # 데이터 없음
                return rows
            raise RebError(f'{res.get("CODE")} {res.get("MESSAGE")}')
        head, body = data[name][0]["head"], data[name][1]["row"]
        total = head[0]["list_total_count"]
        rows.extend(body)
        if len(rows) >= total or not body:
            break
        page += 1
        time.sleep(0.3)
    return rows


# ---- 부산 주간 아파트 가격지수 ----
TABLES = {"sale": "T244183132827305", "jeonse": "T247713133046872"}   # (주) 매매·전세가격지수
BUSAN_ROOT = "부산"
START_WEEK = "202101"
OUT = api.ROOT / "data" / "reb" / "weekly.json"
# 격차 보기용 비교 지역(부산과 따로 저장: 서울에도 중구·서구 같은 이름이 있다)
COMPARE_OUT = api.ROOT / "data" / "reb" / "compare.json"
COMPARE_TOP = {"전국", "수도권", "지방", "서울"}
COMPARE_SEOUL = {"강북지역", "강남지역", "강남구", "서초구", "송파구", "용산구", "마포구", "성동구"}


def is_compare(full):
    parts = full.split(">")
    leaf = parts[-1]
    return leaf in COMPARE_TOP or ("서울" in parts[:-1] and leaf in COMPARE_SEOUL)


def busan_regions(key):
    itm = call("SttsApiTblItm.do", key, STATBL_ID=TABLES["sale"])
    return [(r["ITM_ID"], r["ITM_FULLNM"]) for r in itm
            if r["ITM_TAG"] == "분류" and r["ITM_FULLNM"].split(">")[0] == BUSAN_ROOT]


def _week_back(keys, n):
    """저장된 주차 목록에서 n개 앞 주차(없으면 처음 주차)."""
    ks = sorted(keys)
    return ks[max(0, len(ks) - n)] if ks else START_WEEK


def collect_weekly(log=print, refetch_weeks=6):
    """부산 주간 매매/전세 지수를 받아 data/reb/weekly.json 에 합쳐 저장. 실패 목록 반환.

    - 저장된 자료가 있으면 최근 refetch_weeks 주만 다시 받아 합친다(수정 반영).
    - 지역을 지정하지 않고 전국을 한 번에 받아 부산만 골라, 호출 수를 줄인다.
    - 받지 못한 자료는 기존 값을 그대로 둔다.
    """
    import json
    key = get_key()
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    t0 = time.time()
    try:
        itm = call("SttsApiTblItm.do", key, timeout=15, retries=(5, 20), STATBL_ID=TABLES["sale"])
    except RebError as e:
        raise RebError(f"부동산원 접속 실패({time.time() - t0:.0f}초): " + mask(e))
    log(f"부동산원 접속 확인 ({time.time() - t0:.1f}초)")
    regions = {r["ITM_ID"]: r["ITM_FULLNM"] for r in itm
               if r["ITM_TAG"] == "분류" and r["ITM_FULLNM"].split(">")[0] == BUSAN_ROOT}
    out = {full.split(">")[-1]: old.get(full.split(">")[-1], {"full": full, "weeks": {}}) for full in regions.values()}
    cmp_ids = {r["ITM_ID"]: r["ITM_FULLNM"] for r in itm if r["ITM_TAG"] == "분류" and is_compare(r["ITM_FULLNM"])}
    cmp_old = json.loads(COMPARE_OUT.read_text(encoding="utf-8")) if COMPARE_OUT.exists() else {}
    cmp_out = {full.split(">")[-1]: cmp_old.get(full.split(">")[-1], {"full": full, "weeks": {}}) for full in cmp_ids.values()}
    all_weeks = {k for v in out.values() for k in v["weeks"]}
    start = _week_back(all_weeks, refetch_weeks) if all_weeks else START_WEEK
    failures = []
    for kind, tbl in TABLES.items():
        label = f"부동산원 {'매매' if kind == 'sale' else '전세'}지수"
        try:
            rows = call("SttsApiTblData.do", key, timeout=30, retries=(5, 20, 60),
                        STATBL_ID=tbl, DTACYCLE_CD="WK", START_WRTTIME=start)
        except RebError as e:
            msg = mask(e)[:160]
            failures.append({"kind": label, "gu": "부산 전체", "ym": start, "error": msg})
            log(f"실패: {label} — {msg} (기존 자료 유지)")
            continue
        n = 0
        for r in rows:
            full = cmp_ids.get(r["CLS_ID"])
            if full:
                cmp_out[full.split(">")[-1]]["weeks"].setdefault(
                    r["WRTTIME_IDTFR_ID"], {"date": r["WRTTIME_DESC"]})[kind] = r["DTA_VAL"]
            full = regions.get(r["CLS_ID"])
            if not full:
                continue
            w = out[full.split(">")[-1]]["weeks"].setdefault(r["WRTTIME_IDTFR_ID"], {"date": r["WRTTIME_DESC"]})
            w[kind] = r["DTA_VAL"]
            n += 1
        log(f"{label}: {start}부터 부산 {n}건")
        time.sleep(1)
    for v in out.values():
        v["weeks"] = dict(sorted(v["weeks"].items()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"부동산원 주간 지수: {len(out)}개 지역, 실패 {len(failures)}건")
    _backfill_compare(key, cmp_ids, cmp_out, log)
    for v in cmp_out.values():
        v["weeks"] = dict(sorted(v["weeks"].items()))
    COMPARE_OUT.write_text(json.dumps(cmp_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"비교 지역(서울 등): {', '.join(cmp_out) or '없음'}")
    return failures


def _backfill_compare(key, cmp_ids, cmp_out, log, max_calls=12):
    """비교 지역 중 과거 자료가 모자란 곳만 지역별로 처음부터 받는다(한 번에 max_calls회까지).
    실패해도 멈추지 않고 다음 갱신 때 다시 시도한다."""
    calls = 0
    order = ["서울", "강남구", "서초구", "송파구", "용산구", "마포구", "성동구", "강남지역", "강북지역", "전국", "수도권", "지방"]
    rank = lambda kv: order.index(kv[1].split(">")[-1]) if kv[1].split(">")[-1] in order else 99
    for cid, full in sorted(cmp_ids.items(), key=rank):
        weeks = cmp_out[full.split(">")[-1]]["weeks"]
        if len(weeks) >= 100:
            continue
        for kind, tbl in TABLES.items():
            if calls >= max_calls:
                log("비교 지역 과거 자료: 나머지는 다음 갱신 때 받음")
                return
            calls += 1
            try:
                rows = call("SttsApiTblData.do", key, timeout=30, retries=(5, 20), max_pages=2,
                            STATBL_ID=tbl, DTACYCLE_CD="WK", START_WRTTIME=START_WEEK, CLS_ID=cid)
            except RebError as e:
                log(f"비교 지역 과거 자료 실패: {full} — {mask(e)[:120]}")
                return
            for r in rows:
                if r.get("CLS_ID") == cid:
                    weeks.setdefault(r["WRTTIME_IDTFR_ID"], {"date": r["WRTTIME_DESC"]})[kind] = r["DTA_VAL"]
            time.sleep(1)
        log(f"비교 지역 과거 자료: {full} {len(weeks)}주")


def _chg(a, b):
    return (a / b - 1) * 100 if a and b else None


def weekly_summary(path=None):
    """지역별 주간 변동률(%)·연속 주수·올해 누계·4주 변동. 파일이 없으면 None."""
    import json
    path = path or OUT
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for name, d in data.items():
        weeks = [(k, v) for k, v in d["weeks"].items() if v.get("sale")]
        if len(weeks) < 6:
            continue
        ks = [k for k, _ in weeks]
        last_k, last = weeks[-1]
        prev = weeks[-2][1]
        base_k = max((k for k in ks if k < last_k[:4] + "01"), default=None)
        base = d["weeks"].get(base_k, {}) if base_k else {}

        def rounded(x):
            return round(x, 2) if x is not None else None

        sale_chg = [rounded(_chg(weeks[i][1]["sale"], weeks[i - 1][1]["sale"])) for i in range(1, len(weeks))]
        jeon_chg = [rounded(_chg(weeks[i][1].get("jeonse"), weeks[i - 1][1].get("jeonse"))) for i in range(1, len(weeks))]

        def streak(ch):
            sign = lambda v: (v > 0) - (v < 0)
            s0, n = sign(ch[-1]), 0
            for v in reversed(ch):
                if v is None or sign(v) != s0:
                    break
                n += 1
            return {1: "상승", -1: "하락", 0: "보합"}[s0], n

        depth = len(d["full"].split(">"))
        rows.append({
            "name": name, "full": d["full"], "level": depth,
            "week": last_k, "date": last["date"],
            "sale_wk": sale_chg[-1], "jeonse_wk": jeon_chg[-1],
            "sale_streak": streak(sale_chg), "jeonse_streak": streak(jeon_chg),
            "sale_4w": rounded(_chg(last["sale"], weeks[-5][1]["sale"])),
            "sale_ytd": rounded(_chg(last["sale"], base.get("sale"))),
            "jeonse_ytd": rounded(_chg(last.get("jeonse"), base.get("jeonse"))),
            "series": [(k, v["date"], v["sale"], v.get("jeonse")) for k, v in weeks],
        })
    return rows
