"""로그인 직후 안착 페이지의 정체를 통째로 캡처 — 화면/프레임/링크/본문.

    python tools/diag_postlogin.py <ID> <PW>
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


def main():
    uid, pw = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{C.CDP_PORT}")
        ctx = browser.contexts[0]
        page = ctx.pages[-1] if ctx.pages else ctx.new_page()

        page.goto(C.SIGNIN_URL, wait_until="domcontentloaded", timeout=40000)
        page.wait_for_timeout(800)
        if page.locator(C.SEL_LOGIN_ID).count() > 0:
            page.fill(C.SEL_LOGIN_ID, uid)
            page.fill(C.SEL_LOGIN_PW, pw)
            page.click(C.SEL_LOGIN_BTN)
            print("로그인 클릭, 안착 대기...")
            time.sleep(5)  # dynaPath 리다이렉트 충분히 기다림

        print("\nURL:", page.url)
        print("TITLE:", page.title())
        print("\n-- FRAMES --")
        for f in page.frames:
            print("  frame:", f.url)
        print("\n-- ALL ANCHORS (text/href) --")
        anchors = page.eval_on_selector_all(
            "a",
            "els=>els.map(e=>({t:(e.innerText||'').trim().slice(0,24),h:e.getAttribute('href'),o:e.getAttribute('onclick')})).filter(x=>x.t||x.h||x.o)",
        )
        print(json.dumps(anchors, ensure_ascii=False, indent=1)[:4000])
        print("\n-- BODY TEXT (first 1200 chars) --")
        try:
            txt = page.inner_text("body")
            print(txt[:1200])
        except Exception as e:
            print("body text err:", e)
        page.screenshot(path="tools/diag_postlogin.png", full_page=True)
        import pathlib
        pathlib.Path("tools/diag_postlogin.html").write_text(page.content(), encoding="utf-8")
        print("\nSaved tools/diag_postlogin.png / .html")


if __name__ == "__main__":
    main()
