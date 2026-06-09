# 카드매입자료 자동 다운로드 (Chrome 확장)

여신금융협회 `cardsales.or.kr`은 자동화 연결(CDP/Playwright/Selenium)을 탐지해 차단한다.
이 확장은 **페이지 내부에서 도는 content script**라 탐지되지 않으면서 DOM을 직접 제어한다.

확장은 **데이터 다운로드(조회→전체체크→상세조회→엑셀)만** 담당한다.
(로그인 입력은 Python GUI가 OS 키 입력으로 처리 — 확장/JS로는 봇검사를 못 통과하기 때문.)

## 설치 (PC당 최초 1회 — 관리자)

1. Chrome 주소창에 `chrome://extensions` 입력
2. 오른쪽 위 **개발자 모드** 켜기
3. **압축해제된 확장 프로그램을 로드합니다** → 이 `extension` 폴더 선택

설치 후엔 직원이 따로 건드릴 게 없다.

## 동작

Python GUI(`gui.py`)가 매입내역 페이지로 이동할 때 URL에
`?csauto=1&csfrom=YYYYMMDD&csto=YYYYMMDD` 를 붙인다.
확장이 이를 감지해 자동으로 조회~엑셀 다운로드를 수행한다.
화면 오른쪽 위 작은 패널에 진행 상태가 표시된다.

## 파일

- `manifest.json` — 확장 정의 (MV3)
- `content.js` — 상태 패널 + inpage 주입 + URL 자동실행 감지
- `inpage.js` — 페이지 MAIN world에서 사이트 jQuery/함수로 다운로드 수행

## 메모

사이트가 `goSubExcelPrint`/`#searchBtn`/`crefia.util` 등 내부 구조를 바꾸면 `inpage.js`를 손봐야 한다.
