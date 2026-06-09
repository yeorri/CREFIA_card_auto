"""열려있는 Chrome(9222)에 붙어 자동 로그인 → 기간별 매입내역 진입 → 폼 정찰.

자격증명은 명령행 인자로 받는다(리포에 저장 안 함):
    python tools/test_login_probe.py <ID> <PW>
"""
from __future__ import annotations

import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from automation import config as C  # noqa: E402
from automation.cardsales import login, goto  # noqa: E402


def log(m):
    print("·", m)


def dump(page, tag):
    inputs = page.eval_on_selector_all(
        "input, select",
        """els => els.map(e => ({tag:e.tagName,id:e.id,name:e.name,type:e.type,
            placeholder:e.placeholder,value:e.value,
            maxlength:e.getAttribute('maxlength'),class:e.className}))""",
    )
    selects = page.eval_on_selector_all(
        "select",
        """els => els.map(e => ({id:e.id,name:e.name,
            options:[...e.options].map(o=>o.text+'='+o.value)}))""",
    )
    buttons = page.eval_on_selector_all(
        "button, a[role=button], input[type=submit], input[type=button], a.btn, .btn, a[onclick], button[onclick]",
        """els => els.map(e => ({tag:e.tagName,id:e.id,
            text:(e.innerText||e.value||'').trim().slice(0,30),
            onclick:e.getAttribute('onclick'),href:e.getAttribute('href'),
            class:e.className})).filter(x=>x.text||x.onclick)""",
    )
    print(f"\n===== [{tag}] {page.url} =====")
    print("TITLE:", page.title())
    print("INPUTS:", json.dumps(inputs, ensure_ascii=False, indent=1))
    print("SELECTS:", json.dumps(selects, ensure_ascii=False, indent=1))
    print("BUTTONS:", json.dumps(buttons, ensure_ascii=False, indent=1))


def main():
    if len(sys.argv) < 3:
        print("usage: test_login_probe.py <ID> <PW>")
        return
    uid, pw = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{C.CDP_PORT}")
        ctx = browser.contexts[0]
        page = ctx.pages[-1] if ctx.pages else ctx.new_page()
        login(page, uid, pw, log)
        print("\n>>> 로그인 완료. 기간별 매입내역으로 이동...")
        goto(page, C.PURCHASE_TERM_URL, log)
        page.wait_for_timeout(1500)
        dump(page, "purchase/term")
        page.screenshot(path="tools/probe_purchase_term.png", full_page=True)
        print("\nSaved tools/probe_purchase_term.png")


if __name__ == "__main__":
    main()
