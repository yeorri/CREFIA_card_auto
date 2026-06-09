"""cardsales.or.kr 로그인 페이지 정찰 — 로그인 폼의 실제 셀렉터를 덤프한다.

이 사이트는 headless/봇 트래픽을 'dynaPath' 단계에서 차단(접속 제한)한다.
그래서 실제 앱과 동일하게 headed + 영구 프로필 + automation 플래그 끄고 접근한다.

실행:  python tools/recon_login.py
결과:  콘솔에 input/button 목록 + tools/recon_signin.png + tools/recon_signin.html
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
PROFILE = OUT.parent / ".recon_profile"
HOME_URL = "https://www.cardsales.or.kr/"
SIGNIN_URL = "https://www.cardsales.or.kr/signin"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def dump(page, tag: str):
    inputs = page.eval_on_selector_all(
        "input",
        """els => els.map(e => ({id:e.id,name:e.name,type:e.type,
            placeholder:e.placeholder,class:e.className}))""",
    )
    buttons = page.eval_on_selector_all(
        "button, a[role=button], input[type=submit], input[type=button]",
        """els => els.map(e => ({tag:e.tagName,id:e.id,name:e.name,
            type:e.type,text:(e.innerText||e.value||'').trim().slice(0,40),
            class:e.className}))""",
    )
    forms = page.eval_on_selector_all(
        "form", "els => els.map(e => ({id:e.id,name:e.name,action:e.action,method:e.method}))",
    )
    print(f"\n===== [{tag}] {page.url} =====")
    print("TITLE:", page.title())
    print("--- FORMS ---");  print(json.dumps(forms, ensure_ascii=False, indent=2))
    print("--- INPUTS ---"); print(json.dumps(inputs, ensure_ascii=False, indent=2))
    print("--- BUTTONS ---");print(json.dumps(buttons, ensure_ascii=False, indent=2))


def main():
    headless = "--headed" not in sys.argv  # 기본 headless 시도, --headed로 강제 표시
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            user_agent=UA,
            viewport=None,
            locale="ko-KR",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for attempt in range(3):
            try:
                page.goto(HOME_URL, wait_until="domcontentloaded", timeout=40000)
                break
            except Exception as e:
                print(f"home goto attempt {attempt+1} err:", e)
                page.wait_for_timeout(2000)
        page.wait_for_timeout(2500)
        dump(page, "home")
        # 홈의 모든 링크/클릭가능요소 텍스트 덤프 (로그인 진입점 찾기)
        links = page.eval_on_selector_all(
            "a, button, [role=button], [onclick]",
            """els => els.map(e => ({tag:e.tagName, href:e.getAttribute('href'),
                text:(e.innerText||'').trim().slice(0,30)})).filter(x=>x.text)""",
        )
        print("\n--- HOME LINKS ---")
        print(json.dumps(links, ensure_ascii=False, indent=2))
        # SPA 내부 라우팅: '로그인' 텍스트 클릭
        clicked = False
        for sel in ["a:has-text('로그인')", "button:has-text('로그인')",
                    "text=로그인"]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.click(timeout=5000)
                    clicked = True
                    print(f"\nclicked login via {sel}")
                    break
            except Exception as e:
                print(f"click {sel} err:", e)
        page.wait_for_timeout(3000)
        dump(page, "signin")
        (OUT / "recon_signin.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(OUT / "recon_signin.png"), full_page=True)
        print("\nSaved recon_signin.html / recon_signin.png")
        if not headless:
            page.wait_for_timeout(8000)
        ctx.close()


if __name__ == "__main__":
    main()
