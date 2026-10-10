"""자산 흐름 노트용 API 시험 호출: 각 API의 응답 필드와 예시 2건을 보여 준다(키는 출력하지 않음).

GitHub Actions `자산 API 시험` 워크플로에서 실행한다. 클라우드 세션에는 키가 없다.
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from busan_note import api  # noqa: E402

import requests  # noqa: E402

FSC = "https://apis.data.go.kr/1160100/service"
TESTS = [
    ("지수시세(코스피)", f"{FSC}/GetMarketIndexInfoService/getStockMarketIndex", {"idxNm": "코스피"}),
    ("일반상품시세(금)", f"{FSC}/GetGeneralProductInfoService/getGoldPriceInfo", {}),
    ("주식시세(리츠)", f"{FSC}/GetStockSecuritiesInfoService/getStockPriceInfo", {"likeItmsNm": "리츠"}),
    ("주식배당(A)", "https://apis.data.go.kr/1160100/GetStocDiviInfoService/getDiviInfo", {"stckIssuCmpyNm": "SK리츠"}),
    ("주식배당(B)", f"{FSC}/GetStocDiviInfoService_V2/getDiviInfo_V2", {"stckIssuCmpyNm": "SK리츠"}),
    ("주식배당(C)", "https://apis.data.go.kr/1160100/GetStocDiviInfoService_V2/getDiviInfo_V2", {"stckIssuCmpyNm": "SK리츠"}),
    ("채권시세(국고채)", f"{FSC}/GetBondSecuritiesInfoService/getBondPriceInfo", {"likeItmsNm": "국고채"}),
]


def show(label, r):
    print(f"\n== {label}: HTTP {r.status_code}")
    try:
        body = r.json()
    except ValueError:
        print("  JSON 아님:", api.mask(r.text[:300]))
        return
    b = body.get("response", {}).get("body", {})
    h = body.get("response", {}).get("header", {})
    print("  header:", h, "totalCount:", b.get("totalCount"))
    items = (b.get("items") or {}).get("item") or []
    if isinstance(items, dict):
        items = [items]
    for it in items[:2]:
        print("  ", json.dumps(it, ensure_ascii=False))
    if not items:
        print("  본문:", api.mask(json.dumps(body, ensure_ascii=False)[:400]))


def main():
    raw = api.get_raw_key()
    cands = api.key_candidates(raw)
    begin = (date.today() - timedelta(days=10)).strftime("%Y%m%d")
    for label, url, extra in TESTS:
        ok = False
        for klabel, k in cands:
            p = dict(serviceKey=k, resultType="json", numOfRows=2, pageNo=1, beginBasDt=begin, **extra)
            try:
                r = requests.get(url, params=p, timeout=20)
            except requests.RequestException as e:
                print(f"\n== {label} [{klabel}]: 네트워크 오류 {api.mask(e)}")
                continue
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                show(f"{label} [{klabel}]", r)
                ok = True
                break
            print(f"\n== {label} [{klabel}]: HTTP {r.status_code} {api.mask(r.text[:200])}")
        if not ok:
            print(f"  → {label}: 실패")

    ek = os.environ.get("KOREAEXIM_KEY", "").strip()
    if not ek:
        print("\n== 환율: KOREAEXIM_KEY 없음(건너뜀)")
        return
    api._SECRETS.add(ek)
    d = date.today()
    for host in ["https://oapi.koreaexim.go.kr", "https://www.koreaexim.go.kr"]:
        for back in range(0, 6):
            day = (d - timedelta(days=back)).strftime("%Y%m%d")
            try:
                r = requests.get(f"{host}/site/program/financial/exchangeJSON",
                                 params={"authkey": ek, "searchdate": day, "data": "AP01"}, timeout=20)
            except requests.RequestException as e:
                print(f"\n== 환율 {host}: 네트워크 오류 {api.mask(e)}")
                break
            txt = r.text.strip()
            if r.status_code == 200 and txt.startswith("[") and txt != "[]":
                rows = r.json()
                usd = [x for x in rows if x.get("cur_unit") == "USD"]
                print(f"\n== 환율 {host} {day}: {len(rows)}개 통화, USD 예시:", json.dumps(usd[:1], ensure_ascii=False))
                return
            print(f"\n== 환율 {host} {day}: HTTP {r.status_code} {api.mask(txt[:120])}")


if __name__ == "__main__":
    main()
