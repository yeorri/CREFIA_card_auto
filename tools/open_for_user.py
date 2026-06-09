"""사용자 수동 클릭 테스트용 — Chromium을 띄워 홈페이지를 열고 그대로 둔다.

사용자가 직접 상단 '로그인'을 클릭했을 때 봇 감지(접속 제한)가 뜨는지 관찰한다.
2초마다 현재 URL/타이틀을 출력하고, 'restricted'가 보이면 표시한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = Path(__file__).resolve().parent.parent / ".recon_profile"
HOME_URL = "https://www.cardsales.or.kr/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
RUN_SECONDS = 240


def main():
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            user_agent=UA,
            viewport=None,
            locale="ko-KR",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            print("home goto err:", e)
        print(">>> 브라우저가 열렸습니다. 상단 '로그인'을 직접 클릭해보세요. <<<")
        last = ""
        waited = 0
        while waited < RUN_SECONDS:
            try:
                p = ctx.pages[-1]
                url = p.url
                if url != last:
                    flag = "  <-- ⚠ 접속제한!" if "restricted" in url else ""
                    print(f"[{waited:3d}s] {url}{flag}")
                    last = url
            except Exception as e:
                print("poll err:", e)
            page.wait_for_timeout(2000)
            waited += 2
        print("시간 종료. 브라우저를 닫습니다.")
        ctx.close()


if __name__ == "__main__":
    main()
