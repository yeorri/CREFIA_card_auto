"""로그인 후 dynaPath 리다이렉트가 어디로 안착하는지 관찰 + 메뉴 클릭 이동 테스트.

    python tools/test_login2.py <ID> <PW>
"""
from __future__ import annotations

import io
import json
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from automation import config as C  # noqa: E402


def watch_settle(page, secs=12, label=""):
    """URL이 멈출 때까지 관찰."""
    last = None
    stable = 0
    for i in range(secs * 2):
        u = page.url
        if u != last:
            print(f"   [{label} {i*0.5:.1f}s] {u}")
            last = u
            stable = 0
        else:
            stable += 1
            if stable >= 4:  # 2초간 안 변하면 안착
                break
        time.sleep(0.5)
    return last


def header_links(page):
    return page.eval_on_selector_all(
        "header a, .top_menu a, nav a",
        "els => els.map(e=>({text:(e.innerText||'').trim().slice(0,20),href:e.getAttribute('href')})).filter(x=>x.text)",
    )


def main():
    uid, pw = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{C.CDP_PORT}")
        ctx = browser.contexts[0]
        page = ctx.pages[-1] if ctx.pages else ctx.new_page()

        print("현재 URL:", page.url)
        # 1) 로그인 페이지로
        page.goto(C.SIGNIN_URL, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(800)
        if page.locator(C.SEL_LOGIN_ID).count() == 0:
            print("로그인 폼이 없음 — 이미 로그인 상태일 수 있음")
        else:
            print("로그인 입력 + 클릭...")
            page.fill(C.SEL_LOGIN_ID, uid)
            page.fill(C.SEL_LOGIN_PW, pw)
            page.click(C.SEL_LOGIN_BTN)
            time.sleep(1)
            print("== 로그인 후 안착 관찰 ==")
            watch_settle(page, 14, "login")

        print("\n현재 헤더 링크:")
        print(json.dumps(header_links(page), ensure_ascii=False, indent=1))

        # 2) 메뉴 클릭으로 기간별 매입내역 이동 시도
        print("\n== '기간별 매입내역' 링크 클릭 이동 ==")
        clicked = False
        for sel in ["a[href='/page/purchase/term']",
                    "a:has-text('기간별 매입내역')"]:
            loc = page.locator(sel).first
            if loc.count() > 0:
                try:
                    loc.click(timeout=5000)
                    clicked = True
                    print(f"clicked: {sel}")
                    break
                except Exception as e:
                    print(f"click {sel} err:", e)
        if not clicked:
            print("메뉴 링크를 못 찾음 — goto로 시도")
            page.goto(C.PURCHASE_TERM_URL, wait_until="domcontentloaded")
        watch_settle(page, 10, "nav")

        print("\n최종 URL:", page.url, "| TITLE:", page.title())
        page.screenshot(path="tools/probe_purchase_term.png", full_page=True)
        # 폼 덤프
        inputs = page.eval_on_selector_all(
            "input,select",
            "els=>els.map(e=>({tag:e.tagName,id:e.id,type:e.type,placeholder:e.placeholder,value:e.value,class:e.className}))",
        )
        print("INPUTS:", json.dumps(inputs, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
