"""공공데이터포털 국토교통부 실거래가 API 호출 모듈.

- 인증키는 환경변수 DATA_GO_KR_KEY(로컬은 .env)에서만 읽는다.
- 로그/에러에 키가 찍히지 않도록 mask() 를 거친다.
"""
import os
import re
import time
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

warnings.filterwarnings("ignore", message=".*OpenSSL.*")
import requests  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

ENDPOINTS = {
    "trade": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    "presale": "https://apis.data.go.kr/1613000/RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade",
    "rent": "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
}

REQUEST_INTERVAL_SEC = 0.4  # 호출 사이 간격


class ApiError(Exception):
    pass


def load_dotenv(path=ROOT / ".env"):
    """.env 의 KEY=VALUE 를 환경변수로 읽는다(이미 있으면 덮어쓰지 않음)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


def get_raw_key():
    load_dotenv()
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        raise ApiError(".env 또는 환경변수에 DATA_GO_KR_KEY 가 비어 있습니다.")
    return key


_SECRETS = set()


def mask(text):
    """문자열에서 serviceKey 값과 알려진 키 문자열을 가린다."""
    text = str(text)
    text = re.sub(r"(serviceKey=)[^&\s]+", r"\1***", text, flags=re.I)
    for s in _SECRETS:
        if s:
            text = text.replace(s, "***")
    return text


def key_candidates(raw):
    """입력 키가 Encoding/Decoding 중 무엇이든 동작하도록 후보를 만든다.
    requests params 에는 Decoding 키를 넘겨야 하므로 unquote 한 값을 먼저 시도."""
    decoded = unquote(raw)
    cands = [("decoding", decoded)]
    if decoded != raw:
        cands.append(("as-is", raw))
    for _, k in cands:
        _SECRETS.add(k)
        _SECRETS.add(requests.utils.quote(k, safe=""))
    _SECRETS.add(raw)
    return cands


def _text(el, tag):
    x = el.find(tag)
    return x.text.strip() if x is not None and x.text else ""


def parse_response(content):
    """XML 응답 → (resultCode, resultMsg, totalCount, [item dict...])"""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        snippet = content[:200].decode("utf-8", "replace") if isinstance(content, bytes) else str(content)[:200]
        raise ApiError("XML 파싱 실패: " + mask(snippet))
    # 게이트웨이 오류 형식 (OpenAPI_ServiceResponse)
    if root.tag == "OpenAPI_ServiceResponse":
        hdr = root.find("cmmMsgHeader")
        raise ApiError(f"{_text(hdr, 'returnAuthMsg')} ({_text(hdr, 'errMsg')}, code {_text(hdr, 'returnReasonCode')})")
    code = _text(root, "header/resultCode")
    msg = _text(root, "header/resultMsg")
    total = int(_text(root, "body/totalCount") or 0)
    items = []
    for it in root.findall("body/items/item"):
        items.append({c.tag: (c.text or "").strip() for c in it})
    return code, msg, total, items


def call(kind, lawd_cd, deal_ymd, service_key, page=1, rows=1000, timeout=30):
    params = {
        "serviceKey": service_key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": page,
        "numOfRows": rows,
    }
    for attempt, wait in enumerate((30, 60, 120, None)):
        try:
            r = requests.get(ENDPOINTS[kind], params=params, timeout=timeout)
            break
        except requests.RequestException as e:
            if wait is None:
                raise ApiError(f"네트워크 오류({attempt + 1}회 시도): " + mask(e))
            time.sleep(wait)
    if r.status_code != 200:
        try:
            parse_response(r.content)
        except ApiError as e:
            raise ApiError(f"HTTP {r.status_code} {e}")
        raise ApiError(f"HTTP {r.status_code}: " + mask(" ".join(r.text[:200].split())))
    code, msg, total, items = parse_response(r.content)
    if code not in ("00", "000"):
        raise ApiError(f"API 오류 code={code} msg={msg}")
    return total, items


def fetch_all(kind, lawd_cd, deal_ymd, service_key, rows=1000, log=print):
    """모든 페이지를 끝까지 받는다."""
    page, out = 1, []
    while True:
        total, items = call(kind, lawd_cd, deal_ymd, service_key, page=page, rows=rows)
        out.extend(items)
        time.sleep(REQUEST_INTERVAL_SEC)
        if not items or len(out) >= total:
            break
        page += 1
    return out


def fingerprint(key):
    """키를 드러내지 않고 비교하기 위한 지문(길이 + SHA-256 앞 8자리)."""
    import hashlib
    return f"길이 {len(key)}, 지문 {hashlib.sha256(key.encode()).hexdigest()[:8]}"


def resolve_key(log=print):
    """Encoding/Decoding 키 중 실제 동작하는 쪽을 찾아 반환."""
    raw = get_raw_key()
    errors = [f"키 {fingerprint(raw)}"]
    for label, k in key_candidates(raw):
        try:
            call("trade", "26350", _recent_ym(), k, rows=1)
            return label, k
        except ApiError as e:
            errors.append(f"[{label}] {e}")
    raise ApiError("키 확인 실패 — " + " / ".join(mask(x) for x in errors))


def _recent_ym():
    from datetime import date
    d = date.today()
    y, m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    return f"{y}{m:02d}"
