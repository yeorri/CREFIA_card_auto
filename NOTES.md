# CREFIA 카드자료 자동 다운로드 — 운영/유지보수 노트

여신금융협회 `cardsales.or.kr` 가맹점 매입내역 엑셀을 다중 거래처 자동 다운로드/정리하는 도구.
(컨텍스트 압축 대비 핵심 정리. 2026-06-12 기준, 앱 v1.0.4 / 확장 0.8.3)

## 구조 (왜 하이브리드인가)
- **Python GUI (`gui.py`)** + **Chrome 확장 (`extension/`)** 하이브리드.
- 이 사이트는 **CDP/Selenium/순수HTTP 전부 봇으로 차단**. 확장(content script)만 통과.
- **로그인 입력**은 `event.code`(물리 스캔코드)가 있어야 통과 → **OS 스캔코드 입력**(`tools/os_type_scancode.py`,
  SendInput+KEYEVENTF_SCANCODE). JS/CDP/pyautogui(가상키)로는 `code`가 비어 차단됨. → 그래서 Python이 로그인 타이핑.
- **데이터 다운로드**는 확장(`inpage.js`)이 페이지 내부에서 조회→전체체크→상세조회→`goSubExcelPrint('Excel')`.
- **오케스트레이션** `orchestrate.py`: 계정 순회·로그인·브라우저창 고정·파일 이동/정리·결과집계.
- **후공정** `postprocess.py`: 카드사별 정렬+합계(수식), 월조회 합치기+거래일자 필터, 실행결과 리포트.

## 핵심 셀렉터/엔드포인트
- 로그인: `/signin`, 폼 input id는 매 세션 랜덤 → `input[placeholder='사용자 아이디']`, `input[type=password]`, 버튼 `#goLogin`.
- 매입내역: `/page/purchase/term`. 날짜 `#searchStrDate`/`#searchEndDate`(YYYY-MM-DD), 조회 `#searchBtn`.
- 상세 엑셀: `goSubExcelPrint('Excel')` → `/page/api/purchase/termDetailExcel`. 로그아웃 `/signout`.
- 데이터 열(0-based): 거래일자=1(승인/거래일), 카드사=4, 매입금액=8, 수수료합계=13, 지급금액=15.

## ★ 다운로드 폴더 (제일 흔한 함정)
- 프로그램은 **`Path.home()/Downloads` 한 곳만 감시** → 브라우저 다운로드 위치가 거기여야 파일을 찾아 옮김.
- 다운로드 위치는 **브라우저별 설정**(시스템 공통 아님):
  - 웨일: 설정→다운로드→위치 = Downloads, "매번 위치 확인" 끄기.
  - Edge: edge://settings/downloads → 위치 변경 = Downloads.
  - Chrome: chrome://settings/downloads.
- 증상(파일은 다른 폴더(예 바탕화면)에 떨어지고, 프로그램은 "조회없음"+이동 안 함)이면 이 설정부터 확인.

## 동작 모드
- **매입일자 기간조회**: 시작~종료(최대 31일).
- **월조회(거래일 기준)**: 연/월 선택 → 매입일자 2구간(당월 + 다음달 N일) 조회 → 합쳐 **거래일자=당월**만 필터.
  ★ 1구간 비어도 2구간 반드시 검색(월말 거래가 익월초 매입으로만 잡힐 수 있음). 둘 다 비어야 "데이터 없음".
- 옵션: 카드사별 정렬 정리본, 업체명별 하위폴더, 실행 결과 리포트(`[결과]실행리포트_기간.xlsx`).

## 안정성 장치 (PC 환경차 대응)
- 브라우저창 **고정**: 시작 시 포커스된 크로미움 창(Chrome/웨일/Edge) 하나를 잡아 끝까지 사용(혼선 방지).
- 로그인 전 `clear_field`(저장된 아이디 덧붙음 방지), `force_english`(한글IME 방지; 크롬 TSF라 가끔 실패→재시도).
- 로그인 실패(=매입내역 가도 signin으로 튕김) → 재시도 / 데이터없음 → 재시도 안 함 / 성공 3분기.
- **데이터없음 판정**: 확장이 조회 후 요약행을 **3초 유예** 후에도 0이면 `document.title='CSNODATA'` →
  Python이 창 제목으로 감지. 단 Python은 **파일 먼저 확인 → 그 다음 신호**(파일 있으면 무조건 사용, 이중안전).
- 업체명 특수문자: URL(csname)엔 화이트리스트로 제거(WAF가 괄호 등 차단). 파일명은 원래 이름 유지.

## 배포 / 업데이트
- repo: **github.com/yeorri/CREFIA_card_auto** (public, main). 앱 v1.0.4 / 확장 0.8.3.
- 자동 업데이트: 앱 시작 시 main의 `version.json`(raw) 확인 → 새 버전이면 알림(`updater.py`).
- **업데이트 절차**: 코드수정 → `updater.py` CURRENT_VERSION + `version.json` 버전↑ → `build.bat`(또는 pyinstaller) →
  `git commit/push` → `gh release create vX.Y.Z dist\CREFIA_card_auto.exe dist\CREFIA_extension.zip --repo yeorri/CREFIA_card_auto --title ... --notes ...`
- gh 경로: `"C:\Program Files\GitHub CLI\gh.exe"` (로그인 완료).
- **확장은 자동업데이트 안 됨**: 바뀌면 `CREFIA_extension.zip` 새로 받아 폴더 덮어쓰기 + chrome://extensions 새로고침.
  (확장 버전은 manifest version으로 확인 가능)
- 빌드 산출물: `dist\CREFIA_card_auto.exe`(~92MB onefile) + `dist\CREFIA_extension.zip`.

## 직원 설치/사용 (요약)
1. 최초 1회: Release에서 exe + extension.zip 받기 → zip을 **고정 폴더**에 풀어 chrome://extensions(개발자모드)로 로드.
2. 브라우저 1개(영문입력, 다운로드폴더=Downloads) 열어둠 → exe 실행 → 거래처 추가/엑셀불러오기 → 기간/월 → 시작.
3. 실행 중 마우스/키보드 X. 끝나면 결과리포트 확인.

## 알려진 이슈 / TODO
- ✅ [v1.0.7 해결·진짜원인 확정] **실장님·차장님 PC "다운됐는데 조회없음" 버그 = 죽은 .crdownload/.tmp 마커가 감지를 막던 것.**
  - 헛다리 짚었던 가설들(전부 아님): 느린 PC(렌더경쟁), 다운로드 폴더 경로 불일치(OneDrive). 폴더는 위치탭·레지스트리 모두 표준 `C:\Users\<id>\Downloads`로 확인됨.
  - **진짜 원인:** 구버전 `wait_new_file`이 `if new and not downloading` 게이트를 썼는데, `downloading`=폴더에 `*.crdownload`/`*.tmp`가 하나라도 있으면 True. → **중단된 다운로드 흔적(죽은 .crdownload) 하나가 남아 있으면 새 파일을 영원히 안 집음** → 파일은 Downloads에 쌓이고 "조회없음" 오판.
  - **재현법(확정):** Downloads에 빈 `stuck.crdownload` 하나 만들고 구버전 돌리면 데이터 있는 거래처도 "조회없음" + 파일 쌓임. (이걸로 범인 확정함.)
  - **수정(v1.0.7):** '진행중 게이트' 제거 — 브라우저는 완료 후에만 최종 .xls로 rename하므로 **새 .xls=완료**로 간주 + 파일크기 안정 확인. CSNODATA는 새 파일 없을 때만 신뢰. 진단 로그 추가(감지/CSNODATA/타임아웃+생긴파일 명시).
  - (참고: v1.0.5/1.0.6의 레지스트리 Known Folder 감지 + 다중폴더 감시는 그대로 유지 — 폴더 변수는 제거된 상태라 안전망으로 둠.)
- 확장 `inpage.js`는 폴더감시 대신 `chrome.downloads` API로 다운로드를 직접 캐치할 수도 있음(경로·완료 확정). 단 "다운로드" 권한 경고 + 확장→파이썬 IPC(네이티브메시징) 필요해서 보류. 폴더감시가 더 안 나아지면 그때 전환.
- 로그인 한글IME 간헐 실패 → 재시도로 복구 중. 필요 시 정밀화.
- 계정 비번 평문(accounts.csv/메모리 미저장 정책) — 보안 강화는 추후.

## 파일 맵
- `gui.py` 메인 GUI / `orchestrate.py` 배치엔진 / `postprocess.py` 엑셀후공정 / `updater.py` 업데이트확인
- `tools/os_type_scancode.py` 스캔코드 로그인 입력 / `extension/` (manifest·content·inpage)
- `build.bat` 빌드 / `accounts.example.csv` 계정형식 / `.gitignore`(accounts.csv·.claude·dist·build 제외)
