"""올인원: Chrome 띄우기 + CDP attach + 다운로드 캡처를 한 번에.

창이 뜨고 'READY'가 찍히면 바로 로그인부터 끝까지 직접 하면 된다.
다운로드 캡처는 마지막 엑셀 단계 전에 이미 붙어있으므로 타이밍 걱정 없음.
navigate/Network감시 안 함 → 세션 안 건드림.
"""
from __future__ import annotations

import io
import subprocess
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "captured"
OUT.mkdir(parents=True, exist_ok=True)
LOG = open(ROOT / "tools" / "dl_capture.txt", "w", encoding="utf-8", buffering=1)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9222
PROFILE = ROOT / ".chrome_session"
HOME = "https://www.cardsales.or.kr/"
RUN_SECONDS = 600


def w(msg):
    LOG.write(msg + "\n")
    print(msg)


def on_download(dl):
    try:
        w("** DOWNLOAD 감지!")
        w(f"   url: {dl.url}")
        w(f"   파일명: {dl.suggested_filename}")
        dest = OUT / dl.suggested_filename
        dl.save_as(str(dest))
        w(f"   저장됨: {dest} ({dest.stat().st_size} bytes)")
    except Exception as e:
        w(f"   (download err: {e})")


def attach(page):
    try:
        page.on("download", on_download)
    except Exception:
        pass


def main():
    PROFILE.mkdir(exist_ok=True)
    w("Chrome 실행 중...")
    subprocess.Popen([
        CHROME, f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE}",
        "--no-first-run", "--no-default-browser-check", "--start-maximized",
        HOME,
    ])
    # 포트 대기
    import socket
    for _ in range(40):
        s = socket.socket(); s.settimeout(0.3)
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            s.close(); break
        s.close(); time.sleep(0.25)

    with sync_playwright() as p:
        browser = None
        for _ in range(20):
            try:
                browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
                break
            except Exception:
                time.sleep(0.4)
        if not browser:
            w("CDP attach 실패"); return
        ctx = browser.contexts[0]
        for pg in ctx.pages:
            attach(pg)
        ctx.on("page", lambda pg: (attach(pg), w(f"** 새 탭: {pg.url}")))
        w("")
        w("============================================")
        w("  READY — 이제 브라우저에서 직접 진행하세요:")
        w("  로그인 → 기간별 매입내역 → 조회 → 엑셀다운로드")
        w("============================================")
        t0 = time.time()
        while time.time() - t0 < RUN_SECONDS:
            time.sleep(1)
        w("=== 종료 ===")
        LOG.close()


if __name__ == "__main__":
    main()
