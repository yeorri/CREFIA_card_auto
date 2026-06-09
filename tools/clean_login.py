"""깨끗한 CDP 로그인 1회 테스트 — Network 감시 없이, 사람처럼 타이핑.

    python tools/clean_login.py <ID> <PW>
결과: 로그인 후 최종 URL이 정상 페이지인지 / restricted 인지.
"""
from __future__ import annotations

import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright

ID_SEL = "input[placeholder='사용자 아이디']"
PW_SEL = "input[type=password]"
BTN_SEL = "#goLogin"


def main():
    uid, pw = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0]
        page = ctx.pages[-1] if ctx.pages else ctx.new_page()
        print("현재 URL:", page.url)
        print("열린 탭들:", [pg.url for pg in ctx.pages])

        if page.locator(ID_SEL).count() == 0:
            print("로그인폼 없음 → /signin 으로 이동")
            page.goto("https://www.cardsales.or.kr/signin", wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(1500)
            print("이동 후 URL:", page.url)
        # signin 폼이 보일 때까지
        page.wait_for_selector(ID_SEL, timeout=15000)
        print("로그인 폼 확인됨. 사람처럼 입력...")

        page.click(ID_SEL)
        page.type(ID_SEL, uid, delay=120)
        time.sleep(0.4)
        page.click(PW_SEL)
        page.type(PW_SEL, pw, delay=120)
        time.sleep(0.5)
        print("LOGIN 클릭...")
        page.click(BTN_SEL)

        # 결과 관찰
        last = None
        for i in range(24):
            u = page.url
            if u != last:
                flag = ""
                if "restricted" in u:
                    flag = "  <-- RESTRICTED(봇차단)"
                print(f"[{i*0.5:.1f}s] {u}{flag}")
                last = u
            time.sleep(0.5)

        # 최종 판정
        body = ""
        try:
            body = page.inner_text("body")[:200]
        except Exception:
            pass
        print("\n최종 URL:", page.url)
        print("로그인폼 잔존:", page.locator(ID_SEL).count() > 0)
        print("400/에러 여부:", "Whitelabel" in body or "error" in body.lower())
        print("body 앞부분:", body.replace("\n", " ")[:160])


if __name__ == "__main__":
    main()
