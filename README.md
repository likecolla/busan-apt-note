# 부산 대단지 실거래 노트

국토교통부 실거래가 공개 API로 부산 관심 단지 6곳의 매매·분양권·전월세 실거래를 모아 휴대폰용 페이지 한 장을 만듭니다.

- 페이지: https://likecolla.github.io/busan-apt-note/
- 자동 갱신: 매주 월·목 오전 11시(한국시간), GitHub Actions
- 2021년 10월부터 5년치를 모았고, 갱신 때마다 이번 달과 직전 2개월을 다시 받아 합칩니다.

## 페이지에서 볼 수 있는 것
- **단지 카드:** 84㎡형 최근 거래·3개월 중간값, 3.3㎡당 가격과 1년 전 대비, 수집 기간 최고가 대비, 전세가율, 층 구간별 가격, 해제·직거래 비율. 거래가 5건 미만이면 "표본 적음"이 붙습니다.
- **가격 흐름:** 84㎡형 가격과 3.3㎡당 가격을 바꿔 보고, 기간(1년·3년·전체)을 고를 수 있습니다.
- **두 단지 비교:** 분기별 3.3㎡당 가격과 가격차
- **거래량 온도:** 관심 6개 구 월별 매매 건수와 월평균 비교
- **예측 기록장:** `config/predictions.json`의 질문을 기간이 끝나고 2개월 뒤 실거래로 자동 채점합니다. 예측을 더하려면 항목 하나를 복사해 `id`, `question`, 기준값을 바꾸세요.

## 앞으로 내가 할 일

### 지금 바로 갱신하기
- **GitHub에서:** 저장소 → Actions → "실거래 갱신" → Run workflow
- **내 PC에서:** 터미널에서 아래 명령을 실행하고, 끝나면 `site/index.html`을 더블클릭해 엽니다.
  ```bash
  cd ~/busan-apt-note && .venv/bin/python run.py
  ```
  PC에서 갱신한 결과를 GitHub 페이지에 반영하려면 `git pull` 후 실행하고 `git push`까지 해야 합니다. 보통은 GitHub에서 실행하는 쪽이 편합니다.

### 쓰는 API 키 (모두 `.env`와 GitHub Secret에 같은 이름으로)
| 이름 | 발급처 | 쓰는 곳 |
|---|---|---|
| `DATA_GO_KR_KEY` | 공공데이터포털 | 매매·분양권·전월세 실거래 (필수) |
| `REB_KEY` | 한국부동산원 R-ONE | 구별 온도(주간 매매·전세 지수) |
| `KOSIS_KEY` | 통계청 KOSIS | 미분양, 착공·준공, 인구 이동 |

`REB_KEY`나 `KOSIS_KEY`가 없거나 접속이 실패해도 실거래 수집은 계속되고, 해당 섹션만 이전 자료로 남습니다.

### API 키 바꾸기
1. 공공데이터포털에서 새 키를 받습니다. **Decoding(일반) 인증키**를 권장합니다.
2. **GitHub:** 저장소 → Settings → Secrets and variables → Actions → 해당 이름(`DATA_GO_KR_KEY` 등) → Update secret에 붙여 넣습니다.
3. **내 PC:** 프로젝트 폴더의 `.env` 파일에서 `DATA_GO_KR_KEY=` 뒤의 값을 바꿉니다. 숨김 파일이라 Finder에서는 `Cmd+Shift+.`을 눌러야 보입니다.
4. 키는 코드, 채팅, 이슈 어디에도 붙여 넣지 마세요.

### 단지 추가·삭제
`config/watchlist.json`만 고치면 됩니다.
1. API에 등록된 단지명을 찾습니다(PC에서 한 번 이상 수집한 뒤).
   ```bash
   .venv/bin/python scripts/find_candidates.py 검색어1 검색어2
   ```
2. `complexes` 목록에 한 줄을 추가하거나 지웁니다.
   - `names`: 위에서 찾은 API 단지명(여러 개면 한 단지로 묶임)
   - `lawd`: 구 코드 (해운대 26350, 수영 26500, 남구 26290, 부산진 26230, 동래 26260, 연제 26470)
   - `views`: `["presale"]`(분양권) 또는 `["trade"]`(매매). `["trade", "presale"]`이면 매매가 생기기 전까지 분양권을 보여 줍니다.
   - `move_in_watch`: `true`면 입주장 관찰 표(월별 전세)를 만듭니다.
3. 저장 후 GitHub 웹에서 파일을 직접 고쳤다면 다음 갱신 때 반영됩니다.
4. **비교 단지쌍**은 같은 파일의 `compare`에서 바꿉니다. 카드 없이 비교에만 쓸 단지는 `reference`에 넣습니다.

### 과거 자료 다시 채우기
```bash
.venv/bin/python run.py --months 60 --backfill
```
`--backfill`을 붙이면 옛 거래를 "새로 신고된 거래"로 세지 않습니다.

### 공부노트·특별호에 실거래 수치 넣기
새 호를 만들 때 Claude에게 "실거래 데이터 넣어줘"라고 하면 됩니다. Claude는 `git pull` 후 아래 명령으로 표를 뽑아 넣습니다(인자는 '이번 주 거래' 계약일 범위).
```bash
.venv/bin/python scripts/briefing_snippets.py 2026-09-17 2026-09-23
```

### 갱신이 실패했을 때
- 일부 요청만 실패하면 페이지 맨 아래 "갱신 실패 항목"에 적히고, 다음 갱신 때 다시 받습니다.
- 전체가 실패하면(키 만료 등) GitHub이 가입 이메일로 알림을 보냅니다. 키를 확인하세요.

## 구조
| 경로 | 역할 |
|---|---|
| `run.py` | 수집 + 페이지 생성 (`--no-fetch`: 페이지만, `--months N`: 수집 개월 수) |
| `busan_note/api.py` | API 호출, 키 읽기·가리기 |
| `busan_note/collect.py` | 수집·정규화·중복 제거, `data/`에 월별 JSON 저장 |
| `busan_note/analyze.py` | 면적대·중간값·전세가율 계산 |
| `busan_note/render.py` | `site/index.html` 생성 |
| `busan_note/money.py` | 금액 표기 (`tests/test_money.py`로 검증) |

테스트: `.venv/bin/python -m unittest`

자료 출처: 국토교통부 실거래가 공개시스템 API. 학습용 자료이며 투자 판단의 근거가 아닙니다.
