"""카드매입자료 다중 계정 자동 다운로드 — 배치 엔진.

GUI(gui.py)에서 run_batch(...)로 호출하거나, 단독 실행(accounts.csv)도 가능.

흐름(계정마다): 로그아웃 → 로그인페이지 → 스캔코드 로그인 → 매입내역 페이지(URL로 기간 전달)
  → 확장이 조회~엑셀 자동 다운로드 → Downloads 폴더 감시 → '업체명_기간.xls'로 저장.

전제: Chrome 1개 열어둠, 확장(v0.7+) 설치, 영문 입력, 실행 중 입력장치 건드리지 말 것.
"""
from __future__ import annotations

import csv
import io
import sys
import time
import urllib.parse
from pathlib import Path

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
DOWNLOADS = Path.home() / "Downloads"

DP_WAIT = 2.5
DL_TIMEOUT = 30
DL_EXTS = ("*.xls", "*.xlsx", "*.xlsm", "*.csv")


def digits(s):
    return "".join(ch for ch in str(s) if ch.isdigit())


def period_label(date_from, date_to):
    """파일명용 기간 표기: YYMMDD~YYMMDD (예: 260501~260531)."""
    f, t = digits(date_from), digits(date_to)
    return f"{f[2:8]}~{t[2:8]}"


def purchase_url(name, date_from, date_to):
    q = urllib.parse.urlencode({
        "csauto": "1",
        "csfrom": digits(date_from),
        "csto": digits(date_to),
        "csname": name,
    })
    return f"{PURCHASE}?{q}"


def focus_chrome():
    try:
        for w in pyautogui.getWindowsWithTitle("Chrome"):
            if not w.title:
                continue
            try:
                if w.isMinimized:
                    w.restore()
                w.activate()
                time.sleep(0.4)
                return True
            except Exception:
                continue
    except Exception:
        pass
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
    for pat in DL_EXTS:
        out |= set(DOWNLOADS.glob(pat))
    return out


def wait_new_file(before, should_stop, timeout=DL_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if should_stop():
            raise _Stop()
        downloading = list(DOWNLOADS.glob("*.crdownload"))
        new = [f for f in snapshot_downloads() if f not in before]
        if new and not downloading:
            f = max(new, key=lambda p: p.stat().st_mtime)
            time.sleep(0.6)
            return f
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
    """매입내역 한 구간 조회 → 다운로드된 파일(Downloads 내 Path) 반환. 실패 시 None."""
    before = snapshot_downloads()
    log(f"[{name}] 매입 {digits(date_from)}~{digits(date_to)} 조회...")
    goto(purchase_url(name, date_from, date_to))
    _nap(2.5, should_stop)
    if check_login:
        url = read_url()
        if "signin" in url.lower():
            log(f"[{name}] ✗ 로그인 실패(로그인 화면으로 이동됨)")
            return None
    f = wait_new_file(before, should_stop)
    if not f:
        log(f"[{name}] ✗ 다운로드 실패(데이터 없음/타임아웃)")
    return f


# ── 매입일자 기간조회 (기존 방식) ─────────────────────────
def process(name, uid, pw, date_from, date_to, period, save_dir, log, should_stop,
            sort_by_card=False):
    do_login(name, uid, pw, log, should_stop)
    f = download_range(name, date_from, date_to, log, should_stop, check_login=True)
    if not f:
        return False
    safe = sanitize(name)
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    if not sort_by_card:
        dest = save_dir / f"{safe}_{period}{f.suffix}"
        if dest.exists():
            dest.unlink()
        f.replace(dest)
        log(f"[{name}] ✓ 저장: {dest.name}")
        return True
    raw = save_dir / f"[원본]{safe}_{period}{f.suffix}"
    if raw.exists():
        raw.unlink()
    f.replace(raw)
    proc = save_dir / f"[정리]{safe}_{period}.xlsx"
    try:
        import postprocess
        postprocess.process_file(raw, proc)
        log(f"[{name}] ✓ 저장: {raw.name} + {proc.name}")
    except Exception as e:
        log(f"[{name}] ✓ 저장: {raw.name} (정리본 생성 실패: {e})")
    return True


# ── 월조회 (거래일/승인일 기준 정리) ──────────────────────
def process_monthly(name, uid, pw, year, month, save_dir, log, should_stop, next_days=5):
    import calendar
    last = calendar.monthrange(year, month)[1]
    r1f, r1t = f"{year:04d}{month:02d}01", f"{year:04d}{month:02d}{last:02d}"
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    r2f, r2t = f"{ny:04d}{nm:02d}01", f"{ny:04d}{nm:02d}{int(next_days):02d}"
    period = f"{year:04d}-{month:02d}"

    do_login(name, uid, pw, log, should_stop)
    f1 = download_range(name, r1f, r1t, log, should_stop, check_login=True)
    if not f1:
        return False
    f2 = download_range(name, r2f, r2t, log, should_stop, check_login=False)
    if not f2:
        return False

    safe = sanitize(name)
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    raw1 = save_dir / f"[원본]{safe}_{period}_구간1{f1.suffix}"
    raw2 = save_dir / f"[원본]{safe}_{period}_구간2{f2.suffix}"
    for raw in (raw1, raw2):
        if raw.exists():
            raw.unlink()
    f1.replace(raw1)
    f2.replace(raw2)
    proc = save_dir / f"[정리]{safe}_{period}.xlsx"
    try:
        import postprocess
        postprocess.process_monthly_files([raw1, raw2], filter_from=r1f, filter_to=r1t,
                                          out=proc, label=period)
        log(f"[{name}] ✓ 저장: {proc.name} + 원본 2구간")
    except Exception as e:
        log(f"[{name}] ✓ 원본 저장됨 (정리본 생성 실패: {e})")
    return True


# ── 계정 순회(재시도 포함) 공통 ───────────────────────────
def _run_accounts(accounts, do_account, log, should_stop, start_delay, retries):
    ok, failed = 0, []
    if start_delay:
        log(f"{start_delay}초 후 시작 — 마우스/키보드 건드리지 마세요.")
        for _ in range(start_delay * 2):
            if should_stop():
                log("취소됨"); return
            time.sleep(0.5)
    stopped = False
    for name, uid, pw in accounts:
        if should_stop():
            stopped = True; break
        success = False
        for attempt in range(retries + 1):
            if should_stop():
                stopped = True; break
            if attempt > 0:
                log(f"[{name}] ↻ 재시도 {attempt}/{retries} ...")
            try:
                if do_account(name, uid, pw):
                    success = True; break
            except _Stop:
                log("■ 즉시 중단됨 (현재 작업 취소)")
                stopped = True; break
            except Exception as e:
                log(f"[{name}] 오류: {e}")
        if stopped:
            break
        if success:
            ok += 1
        else:
            failed.append(name)
            log(f"[{name}] ✗ 최종 실패 ({retries + 1}회 시도)")
    log(f"━━ 완료: {ok}/{len(accounts)} 성공" + (f" · 실패: {', '.join(failed)}" if failed else ""))


def run_batch(accounts, date_from, date_to, save_dir=None, log=print,
              should_stop=lambda: False, start_delay=5, retries=1, sort_by_card=False):
    """매입일자 기간조회. accounts: [(name, id, pw), ...]."""
    period = period_label(date_from, date_to)
    sd = Path(save_dir) if save_dir else DOWNLOADS
    log(f"[매입일자 기간조회] 총 {len(accounts)}건, 매입 {digits(date_from)}~{digits(date_to)}")
    log(f"저장 폴더: {sd}")
    _run_accounts(
        accounts,
        lambda n, u, p: process(n, u, p, date_from, date_to, period, sd, log, should_stop,
                                sort_by_card=sort_by_card),
        log, should_stop, start_delay, retries)


def run_batch_monthly(accounts, year, month, next_days=5, save_dir=None, log=print,
                      should_stop=lambda: False, start_delay=5, retries=1):
    """월조회(거래일 기준). 계정당 2구간 조회 → 합쳐 거래일 필터 → 카드사별 정리."""
    sd = Path(save_dir) if save_dir else DOWNLOADS
    log(f"[월조회·거래일 기준] 총 {len(accounts)}건, {year}-{month:02d} (다음달 {next_days}일까지)")
    log(f"저장 폴더: {sd}")
    _run_accounts(
        accounts,
        lambda n, u, p: process_monthly(n, u, p, year, month, sd, log, should_stop,
                                        next_days=next_days),
        log, should_stop, start_delay, retries)


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
