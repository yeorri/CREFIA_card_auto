"""카드매입자료 다중 계정 자동 다운로드 — 배치 엔진.

GUI(gui.py)에서 run_batch(...)로 호출하거나, 단독 실행(accounts.csv)도 가능.

흐름(계정마다): 로그아웃 → 로그인페이지 → 스캔코드 로그인 → 매입내역 페이지(URL로 기간 전달)
  → 확장이 조회~엑셀 자동 다운로드 → Downloads 폴더 감시 → '업체명_기간.xls'로 저장.

전제: Chrome 1개 열어둠, 확장(v0.7+) 설치, 영문 입력, 실행 중 입력장치 건드리지 말 것.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path

try:
    import winreg
except Exception:
    winreg = None

import pyautogui
import pyperclip

if isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from os_type_scancode import login as sc_login  # noqa: E402

pyautogui.FAILSAFE = False

SIGNIN = "https://www.cardsales.or.kr/signin"
SIGNOUT = "https://www.cardsales.or.kr/signout"
PURCHASE = "https://www.cardsales.or.kr/page/purchase/term"
def _known_downloads():
    """Windows 레지스트리에서 '실제' Downloads 폴더 경로를 읽는다(OneDrive 리디렉션 반영).

    Path.home()/Downloads 는 OneDrive로 리디렉션된 환경(바탕화면/다운로드가 OneDrive 밑으로
    옮겨진 PC)에서 실제 다운로드 위치와 어긋난다. Known Folder GUID로 진짜 경로를 가져온다."""
    try:
        import winreg
        guid = "{374DE290-123F-4565-9164-39C4925E467B}"  # Downloads Known Folder
        key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            val, _ = winreg.QueryValueEx(k, guid)
            if val:
                return Path(os.path.expandvars(val))
    except Exception:
        pass
    return None


def _build_download_dirs():
    """브라우저가 파일을 떨어뜨릴 수 있는 후보 폴더들(중복 제거, 순서=우선순위)."""
    dirs = []

    def add(p):
        if not p:
            return
        p = Path(p)
        if p not in dirs:
            dirs.append(p)

    add(_known_downloads())                       # 레지스트리(리디렉션 반영) — 가장 정확
    add(Path.home() / "Downloads")                # 표준 위치
    add(Path.home() / "OneDrive" / "Downloads")   # OneDrive 리디렉션 흔한 위치
    for env in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        v = os.environ.get(env)
        if v:
            add(Path(v) / "Downloads")
    return dirs


# 감시할 후보 다운로드 폴더 전체(OneDrive/커스텀 환경 무관하게 잡기 위함)
DOWNLOAD_DIRS = _build_download_dirs()
# 단일 기본값(저장 폴더 미지정 시 저장 위치 등): 레지스트리 우선, 없으면 표준
DOWNLOADS = DOWNLOAD_DIRS[0] if DOWNLOAD_DIRS else (Path.home() / "Downloads")

DP_WAIT = 2.5
DL_TIMEOUT = 15   # 자료 있으면 보통 3~10초 내 다운. 데이터없음은 확장 신호로 더 빨리 잡음.
DL_EXTS = ("*.xls", "*.xlsx", "*.xlsm", "*.csv")


def digits(s):
    return "".join(ch for ch in str(s) if ch.isdigit())


def period_label(date_from, date_to):
    """파일명용 기간 표기: YYMMDD~YYMMDD (예: 260501~260531)."""
    f, t = digits(date_from), digits(date_to)
    return f"{f[2:8]}~{t[2:8]}"


def _url_safe_name(name):
    """URL(csname)용 안전 이름. 사이트 보안(WAF)이 ( ) < > 따옴표 등 특수문자를 차단할 수 있어
    한글/영문/숫자/공백/_/-만 남긴다. (파일 이름은 진짜 이름을 그대로 쓰므로 무관)"""
    s = re.sub(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ _\-]", "", str(name))
    return s.strip() or "거래처"


def purchase_url(name, date_from, date_to):
    q = urllib.parse.urlencode({
        "csauto": "1",
        "csfrom": digits(date_from),
        "csto": digits(date_to),
        "csname": _url_safe_name(name),
    })
    return f"{PURCHASE}?{q}"


# 지원 브라우저(크로미움 계열): 창 제목으로 찾는다. Chrome / 네이버 웨일 / Edge
BROWSER_TITLE_KEYS = ("Chrome", "Whale", "웨일", "Edge")

# 작업 시작 시 고른 브라우저 창을 고정해 끝까지 같은 창만 사용(여러 브라우저 혼선 방지).
_target_win = None


def _is_browser_title(t):
    return bool(t) and any(k.lower() in t.lower() for k in BROWSER_TITLE_KEYS)


def _first_browser_window():
    seen = set()
    for key in BROWSER_TITLE_KEYS:
        try:
            for w in pyautogui.getWindowsWithTitle(key):
                h = getattr(w, "_hWnd", None) or id(w)
                if not w.title or h in seen:
                    continue
                seen.add(h)
                return w
        except Exception:
            continue
    return None


def pick_browser():
    """사용할 브라우저 창을 결정해 고정. 현재 앞에 있는 창이 브라우저면 그걸, 아니면 처음 찾은 브라우저."""
    global _target_win
    _target_win = None
    try:
        aw = pyautogui.getActiveWindow()
        if aw and _is_browser_title(aw.title):
            _target_win = aw
            return aw
    except Exception:
        pass
    _target_win = _first_browser_window()
    return _target_win


def _activate(w):
    try:
        if w.isMinimized:
            w.restore()
        w.activate()
        time.sleep(0.4)
        return True
    except Exception:
        return False


def focus_chrome():
    """고정된 브라우저 창을 앞으로. 없거나 닫혔으면 다시 고른다."""
    global _target_win
    if _target_win is not None and _activate(_target_win):
        return True
    _target_win = None
    w = _first_browser_window()
    if w and _activate(w):
        _target_win = w
        return True
    return False


def goto(url):
    """주소창에 URL 붙여넣기로 즉시 이동."""
    focus_chrome()
    pyperclip.copy(url)
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)
    pyautogui.press("enter")


def read_url():
    """현재 탭의 URL을 주소창에서 읽어온다(Ctrl+L → Ctrl+C → 클립보드)."""
    try:
        focus_chrome()
        pyperclip.copy("__NOURL__")
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.25)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.25)
        pyautogui.press("escape")
        return pyperclip.paste() or ""
    except Exception:
        return ""


def dismiss_alert():
    """로그인 실패 알림창(아이디/비번 입력하세요, 회원정보 없음 등)의 '확인'을 누른다.

    네이티브 alert는 Enter=확인. 알림이 없으면 무해. (alert가 떠 있으면 goto가 막히므로 먼저 닫아야 함)
    """
    focus_chrome()
    pyautogui.press("enter")
    time.sleep(0.3)


class _Stop(Exception):
    """중단 요청 시 즉시 빠져나오기 위한 예외."""


def _nap(seconds, should_stop):
    """중단을 자주 확인하며 자는 sleep. 중단되면 _Stop 발생."""
    end = time.time() + seconds
    while time.time() < end:
        if should_stop():
            raise _Stop()
        time.sleep(0.1)


def snapshot_downloads():
    out = set()
    for d in DOWNLOAD_DIRS:
        if not d.exists():
            continue
        for pat in DL_EXTS:
            try:
                out |= set(d.glob(pat))
            except Exception:
                pass
    return out


def _safe_mtime(p):
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _safe_size(p):
    try:
        return p.stat().st_size
    except OSError:
        return -1


def _browser_title():
    """현재 사용 중인 브라우저 창의 제목(확장이 'CSNODATA'로 바꾸면 감지용)."""
    try:
        if _target_win is not None:
            return _target_win.title or ""
    except Exception:
        pass
    w = _first_browser_window()
    try:
        return (w.title if w else "") or ""
    except Exception:
        return ""


def wait_new_file(before, should_stop, timeout=DL_TIMEOUT, log=None):
    """반환: Path(완료된 새 파일) / "NODATA"(확장 '데이터없음' 신호) / None(타임아웃).

    판정 원리:
    - 브라우저는 다운로드 '중'엔 .crdownload 임시파일을 쓰고, '완료된 뒤에야' 최종
      .xls 로 이름을 바꾼다. 따라서 before에 없던 최종 .xls 가 보이면 = 다운로드 완료.
    - 안전장치로 그 파일 크기가 한 번 더 같은지(쓰기 끝)만 확인하고 채택한다.
    - '진행 중 다운로드가 있나'는 보지 않는다(죽은 .crdownload/.tmp 가 감지를 막던 버그 제거).
    - CSNODATA 신호는 '새 파일이 하나도 없을 때만' 신뢰(파일 있는데 신호로 무시 방지)."""
    deadline = time.time() + timeout
    last_size = {}
    while time.time() < deadline:
        if should_stop():
            raise _Stop()
        cands = [f for f in snapshot_downloads() if f not in before]
        if cands:
            f = max(cands, key=_safe_mtime)
            sz = _safe_size(f)
            if sz > 0 and last_size.get(f) == sz:   # 직전 폴링과 크기 동일 = 쓰기 끝
                if log:
                    log(f"  ↳ 다운로드 감지: {f.name} ({sz:,}B)")
                time.sleep(0.2)
                return f
            last_size[f] = sz
        else:
            # 새 파일이 아직 없을 때만 '데이터없음' 신호를 신뢰
            if "CSNODATA" in _browser_title():
                return "NODATA"
        time.sleep(0.4)
    return None


def sanitize(name):
    return "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "거래처"


# ── 로그인 / 단일구간 다운로드 헬퍼 ───────────────────────
def do_login(name, uid, pw, log, should_stop):
    log(f"[{name}] 로그아웃...")
    goto(SIGNOUT)
    _nap(2.0, should_stop)
    log(f"[{name}] 로그인 페이지...")
    goto(SIGNIN)
    _nap(2.5, should_stop)
    focus_chrome()
    log(f"[{name}] 로그인 입력...")
    sc_login(uid, pw, dp_wait=DP_WAIT)
    _nap(3.0, should_stop)
    dismiss_alert()   # 실패 알림창 닫기


def download_range(name, date_from, date_to, log, should_stop, check_login=False):
    """매입내역 한 구간 조회. 반환: ("signin"|"file"|"nofile", file_or_None).

    - signin : 로그인 안 됨(로그인 화면으로 리다이렉트) → 재시도 대상
    - file   : 다운로드 성공
    - nofile : 로그인은 됐는데 파일 없음(해당 기간 데이터 없음 등) → 재로그인 무의미
    """
    before = snapshot_downloads()
    log(f"[{name}] 매입 {digits(date_from)}~{digits(date_to)} 조회...")
    goto(purchase_url(name, date_from, date_to))
    _nap(2.5, should_stop)
    if check_login:
        url = read_url()
        if "signin" in url.lower():
            return ("signin", None)
    f = wait_new_file(before, should_stop, log=log)
    if f == "NODATA":
        log(f"[{name}] · 확장 '데이터없음' 신호(CSNODATA) 감지 → 데이터 없음 처리")
        return ("nofile", None)
    if f is None:
        # 진단: 타임아웃이면 '그동안 새로 생긴 파일'을 그대로 보여줌(감지 실패 원인 추적용)
        seen = sorted(p.name for p in snapshot_downloads() if p not in before)
        log(f"[{name}] · {DL_TIMEOUT}초 내 다운로드 감지 실패. 그동안 새로 생긴 파일: {seen or '없음'}")
        return ("nofile", None)
    return ("file", f)


# ── 매입일자 기간조회 (기존 방식) ─────────────────────────
def _target_dir(save_dir, safe, per_company_folder):
    d = Path(save_dir) / safe if per_company_folder else Path(save_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def process(name, uid, pw, date_from, date_to, period, save_dir, log, should_stop,
            sort_by_card=False, per_company_folder=False):
    """반환: (status, detail). status ∈ ok/nodata/login_fail."""
    import postprocess
    do_login(name, uid, pw, log, should_stop)
    status, f = download_range(name, date_from, date_to, log, should_stop, check_login=True)
    if status == "signin":
        log(f"[{name}] ✗ 로그인 실패(로그인 화면으로 이동됨)")
        return ("login_fail", "로그인 실패 (비밀번호 오류/조작 등)")
    if status == "nofile":
        log(f"[{name}] · 조회결과 없음 (로그인 성공 · 해당 기간 데이터 없음)")
        return ("nodata", "조회결과 없음 (데이터 없음)")
    safe = sanitize(name)
    target = _target_dir(save_dir, safe, per_company_folder)
    if not sort_by_card:
        dest = target / f"{safe}_{period}{f.suffix}"
        if dest.exists():
            dest.unlink()
        f.replace(dest)
        log(f"[{name}] ✓ 저장: {dest.name}")
        return ("ok", f"저장: {dest.name}")
    raw = target / f"[원본]{safe}_{period}{f.suffix}"
    if raw.exists():
        raw.unlink()
    f.replace(raw)
    proc = target / f"[정리]{safe}_{period}.xlsx"
    try:
        postprocess.process_file(raw, proc)
        log(f"[{name}] ✓ 저장: {raw.name} + {proc.name}")
        return ("ok", f"저장: {proc.name} (+원본)")
    except Exception as e:
        log(f"[{name}] ✓ 저장: {raw.name} (정리본 생성 실패: {e})")
        return ("ok", f"저장: {raw.name} (정리 실패)")


# ── 월조회 (거래일/승인일 기준 정리) ──────────────────────
def process_monthly(name, uid, pw, year, month, save_dir, log, should_stop, next_days=5,
                    per_company_folder=False):
    """반환: (status, detail). status ∈ ok/nodata/login_fail."""
    import calendar
    import postprocess
    last = calendar.monthrange(year, month)[1]
    r1f, r1t = f"{year:04d}{month:02d}01", f"{year:04d}{month:02d}{last:02d}"
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    r2f, r2t = f"{ny:04d}{nm:02d}01", f"{ny:04d}{nm:02d}{int(next_days):02d}"
    period = f"{year:04d}-{month:02d}"

    do_login(name, uid, pw, log, should_stop)
    # 1구간(매입 당월)
    s1, f1 = download_range(name, r1f, r1t, log, should_stop, check_login=True)
    if s1 == "signin":
        log(f"[{name}] ✗ 로그인 실패(로그인 화면으로 이동됨)")
        return ("login_fail", "로그인 실패 (비밀번호 오류/조작 등)")
    # ★ 1구간이 비어도 2구간은 반드시 검색한다 (월말 거래가 다음달 초 매입으로만 잡힐 수 있음)
    s2, f2 = download_range(name, r2f, r2t, log, should_stop, check_login=False)

    # 두 구간 다 비면 진짜 데이터 없음
    if s1 != "file" and s2 != "file":
        log(f"[{name}] · 조회결과 없음 (1·2구간 모두 데이터 없음)")
        return ("nodata", "조회결과 없음 (1·2구간 모두 없음)")

    safe = sanitize(name)
    target = _target_dir(save_dir, safe, per_company_folder)
    raws = []
    if s1 == "file" and f1:
        raw1 = target / f"[원본]{safe}_{period}_구간1{f1.suffix}"
        if raw1.exists():
            raw1.unlink()
        f1.replace(raw1)
        raws.append(raw1)
    else:
        log(f"[{name}] · 당월 매입구간 비어있음 — 다음달 정산분(2구간)만으로 정리")
    if s2 == "file" and f2:
        raw2 = target / f"[원본]{safe}_{period}_구간2{f2.suffix}"
        if raw2.exists():
            raw2.unlink()
        f2.replace(raw2)
        raws.append(raw2)

    seg = f"1구간 {'O' if s1 == 'file' else 'X'} · 2구간 {'O' if s2 == 'file' else 'X'}"
    proc = target / f"[정리]{safe}_{period}.xlsx"
    try:
        postprocess.process_monthly_files(raws, filter_from=r1f, filter_to=r1t,
                                          out=proc, label=period)
        log(f"[{name}] ✓ 저장: {proc.name} + 원본 {len(raws)}구간")
        return ("ok", f"{seg} → 저장: {proc.name}")
    except Exception as e:
        log(f"[{name}] ✓ 원본 저장됨 (정리본 생성 실패: {e})")
        return ("ok", f"{seg} → 원본 저장 (정리 실패)")


# ── 계정 순회(재시도 포함) 공통 ───────────────────────────
_LABEL = {"ok": "성공", "nodata": "조회없음", "login_fail": "로그인실패", "error": "실패"}


def _run_accounts(accounts, do_account, log, should_stop, start_delay, retries):
    """각 계정 처리 + 재시도. 반환: results = [(업체명, 결과라벨, 상세), ...]."""
    results = []
    if start_delay:
        log(f"{start_delay}초 안에 사용할 브라우저 창을 클릭해 앞에 두세요. (이후엔 건드리지 마세요)")
        for _ in range(start_delay * 2):
            if should_stop():
                log("취소됨"); return results
            time.sleep(0.5)
    win = pick_browser()   # 사용할 브라우저 창 고정
    log(f"사용 브라우저: {win.title[:40] if win else '못 찾음(브라우저를 열어두세요)'}")
    log("다운로드 감시 폴더: " + " | ".join(str(d) for d in DOWNLOAD_DIRS))

    stopped = False
    for name, uid, pw in accounts:
        if should_stop():
            stopped = True; break
        status, detail = "error", "미실행"
        for attempt in range(retries + 1):
            if should_stop():
                stopped = True; break
            if attempt > 0:
                log(f"[{name}] ↻ 재시도 {attempt}/{retries} ...")
            try:
                status, detail = do_account(name, uid, pw)
            except _Stop:
                log("■ 즉시 중단됨 (현재 작업 취소)")
                stopped = True; break
            except Exception as e:
                status, detail = "error", str(e)
                log(f"[{name}] 오류: {e}")
            if status in ("ok", "nodata"):   # 성공/데이터없음 → 재시도 안 함
                break
            # login_fail / error → 재시도
        if stopped:
            break
        label = _LABEL.get(status, "실패")
        if status not in ("ok", "nodata"):
            log(f"[{name}] ✗ 최종 {label} ({retries + 1}회 시도)")
        results.append((name, label, detail))

    ok = sum(1 for r in results if r[1] == "성공")
    summary = f"━━ 완료: {ok}/{len(results)} 성공"
    for lab in ("조회없음", "로그인실패", "실패"):
        names = [r[0] for r in results if r[1] == lab]
        if names:
            summary += f" · {lab}: {', '.join(names)}"
    log(summary)
    return results


def _write_results_report(results, save_dir, period, log):
    """실행 결과 리포트 엑셀(업체명/결과/상세)을 저장폴더에 저장."""
    if not results:
        return
    try:
        import postprocess
        out = Path(save_dir) / f"[결과]실행리포트_{period}.xlsx"
        if out.exists():
            out.unlink()
        postprocess.build_results_report(results, out)
        ok = sum(1 for r in results if r[1] == "성공")
        log(f"★ 결과 리포트 저장: {out.name}  ({ok}/{len(results)} 성공)")
    except Exception as e:
        log(f"결과 리포트 생성 실패: {e}")


def run_batch(accounts, date_from, date_to, save_dir=None, log=print,
              should_stop=lambda: False, start_delay=5, retries=1, sort_by_card=False,
              per_company_folder=False, consolidate=False):
    """매입일자 기간조회. accounts: [(name, id, pw), ...]."""
    period = period_label(date_from, date_to)
    sd = Path(save_dir) if save_dir else DOWNLOADS
    log(f"[매입일자 기간조회] 총 {len(accounts)}건, 매입 {digits(date_from)}~{digits(date_to)}")
    log(f"저장 폴더: {sd}" + ("  (업체명별 하위폴더)" if per_company_folder else ""))
    results = _run_accounts(
        accounts,
        lambda n, u, p: process(n, u, p, date_from, date_to, period, sd, log, should_stop,
                                sort_by_card=sort_by_card, per_company_folder=per_company_folder),
        log, should_stop, start_delay, retries)
    if consolidate:
        _write_results_report(results, sd, period, log)


def run_batch_monthly(accounts, year, month, next_days=5, save_dir=None, log=print,
                      should_stop=lambda: False, start_delay=5, retries=1,
                      per_company_folder=False, consolidate=False):
    """월조회(거래일 기준). 계정당 2구간 조회 → 합쳐 거래일 필터 → 카드사별 정리."""
    sd = Path(save_dir) if save_dir else DOWNLOADS
    period = f"{year:04d}-{month:02d}"
    log(f"[월조회·거래일 기준] 총 {len(accounts)}건, {year}-{month:02d} (다음달 {next_days}일까지)")
    log(f"저장 폴더: {sd}" + ("  (업체명별 하위폴더)" if per_company_folder else ""))
    results = _run_accounts(
        accounts,
        lambda n, u, p: process_monthly(n, u, p, year, month, sd, log, should_stop,
                                        next_days=next_days, per_company_folder=per_company_folder),
        log, should_stop, start_delay, retries)
    if consolidate:
        _write_results_report(results, sd, period, log)


def _load_csv():
    p = Path(__file__).resolve().parent / "accounts.csv"
    out = []
    with open(p, encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if len(row) >= 2 and row[0].strip():
                # CLI: name,id,pw  (gui와 동일 순서)
                name = row[0].strip() or "거래처"
                out.append((name, row[1].strip(), row[2].strip() if len(row) > 2 else ""))
    return out


if __name__ == "__main__":
    # 단독 실행: accounts.csv(업체명,아이디,비번) + 아래 기간
    DATE_FROM = "20260501"
    DATE_TO = "20260531"
    run_batch(_load_csv(), DATE_FROM, DATE_TO)
