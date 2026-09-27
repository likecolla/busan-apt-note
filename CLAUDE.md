# busan-apt-note 작업 안내 (Claude용)

사용자는 개발자가 아니다. 한국어로, 단계마다 3줄 이내로 설명한다. 공개 저장소·배포처럼 되돌리기 어려운 일은 먼저 묻는다.

## 보안 (반드시 지킬 것)
- API 키는 코드·로그·HTML·채팅 어디에도 쓰지 않는다. 사용자에게 키를 채팅으로 요구하지 않는다.
- 로컬은 `.env`, GitHub는 Repository Secrets(`DATA_GO_KR_KEY`, `REB_KEY`, `KOSIS_KEY`)로만 읽는다.
- 클라우드 세션에는 `.env`가 없다. 데이터 새로 받기는 GitHub Actions `실거래 갱신` 워크플로를 실행해서 한다.

## 실거래 노트 갱신 (자동: 월·목 11:00 KST)
- 지금 바로 갱신: `.github/workflows/update.yml`의 `workflow_dispatch` 실행 → 끝나면 `git pull`.

## 공부노트·특별호 새 호 만들기
아티팩트 두 개 (둘 다 사용자 소유, 같은 URL로 갱신한다 — 새 URL을 만들지 말 것):
- 공부노트: https://claude.ai/artifact/1bUxPJMAQMvRgMQwjGKnef
- 특별호: https://claude.ai/artifact/CXJQvQX32XyAtERxHXcXP2

순서:
1. `git pull` (최신 데이터), `pip install -r requirements.txt`
2. Artifact `read` 액션으로 위 URL을 읽어 현재 판을 받는다 (작업본은 저장소에 없다).
3. `python scripts/briefing_snippets.py <이번주 시작> <끝>` → JSON의 HTML 조각(core, week, movein, volume, gap, volume_vs, compare, predictions)으로 해당 섹션을 교체한다.
4. 호수·날짜, 지난 호 "생각해 볼 질문" 해설, 새 질문을 갱신한다. 기존 디자인·CSS 클래스·근거 등급 배지(`.gr .g1` 실거래 / `.g2` 공식 / `.g3` 보도 / `.g4` 추정·호가)는 유지한다.
5. 같은 URL로 publish.

## 내용 규칙
- 민간 사이트(리치고·KB·호갱노노) 추정치·시세는 쓰지 않는다. 국토부·부동산원·KOSIS·청약홈·K-apt 공공데이터만.
- 3.3㎡당 가격은 전용면적 기준. 전세가율은 신규 계약 기준(3건 이상일 때).
- 해제 거래는 가격 계산에서 빼고 "해제"로 표시, 직거래는 포함하고 "직거래" 표시.
- 금액은 원 단위 + (억·만) 표기.
- 독자는 사용자와 지인 몇 명. 페이지는 noindex.
