"""진짜 Chrome(디버깅 모드)에 CDP attach 후 /signin 진입이 되는지 테스트.

목적: 봇 감지가 'Playwright Chromium' 흔적 때문인지, 'CDP 연결 자체'인지 가른다.
- 진짜 Chrome에서 /signin 폼이 보이면 → CDP attach 방식으로 가면 됨.
- 진짜 Chrome도 restricted면 → 자동화 연결 자체를 감지 → 다른 방법 필요.
"""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# 콘솔 한글/이모지 깨짐 방지
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9222
HOME = "https://www.cardsales.or.kr/"
PROFILE = Path(tempfile.gettempdir()) / "cardsales_real_chrome_profile"


def main():
    PROFILE.mkdir(exist_ok=True)
    print("진짜 Chrome 실행 (디버깅 포트 9222)...")
    proc = subprocess.Popen([
        CHROME,
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE}",
        "--no-first-run", "--no-default-browser-check",
        HOME,
    ])
    time.sleep(5)
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{PORT}")
        except Exception as e:
            print("CDP attach 실패:", e)
            return
        print("CDP attach 성공.")
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # webdriver 흔적 확인
        try:
            wd = page.evaluate("() => navigator.webdriver")
            print("navigator.webdriver =", wd)
        except Exception as e:
            print("webdriver eval err:", e)

        print("\n[A] 코드로 /signin 이동 시도...")
        try:
            page.goto("https://www.cardsales.or.kr/signin",
                      wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            print("  URL:", page.url)
            print("  RESTRICTED" if "restricted" in page.url else "  OK (차단 안됨)")
            n_inputs = len(page.query_selector_all("input"))
            print("  input 개수:", n_inputs)
        except Exception as e:
            print("  goto err:", e)

        print("\n>>> 이제 직접 상단 '로그인'도 눌러보세요. 60초간 URL 관찰합니다. <<<")
        last = ""
        for i in range(30):
            try:
                p = ctx.pages[-1]
                if p.url != last:
                    flag = "  <-- 접속제한!" if "restricted" in p.url else ""
                    print(f"[{i*2:3d}s] {p.url}{flag}")
                    last = p.url
            except Exception:
                pass
            time.sleep(2)
        print("관찰 종료. (Chrome 창은 열어둡니다)")


if __name__ == "__main__":
    main()
