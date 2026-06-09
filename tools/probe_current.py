"""이미 열려있는 Chrome(포트 9222)에 붙어서 현재 모든 페이지의 폼을 덤프."""
from __future__ import annotations

import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright


def dump(page):
    inputs = page.eval_on_selector_all(
        "input, select",
        """els => els.map(e => ({tag:e.tagName,id:e.id,name:e.name,type:e.type,
            placeholder:e.placeholder,maxlength:e.getAttribute('maxlength'),class:e.className}))""",
    )
    buttons = page.eval_on_selector_all(
        "button, a[role=button], input[type=submit], input[type=button], a.btn, .btn",
        """els => els.map(e => ({tag:e.tagName,id:e.id,name:e.name,type:e.type,
            text:(e.innerText||e.value||'').trim().slice(0,30),
            onclick:e.getAttribute('onclick'),class:e.className})).filter(x=>x.text||x.onclick)""",
    )
    forms = page.eval_on_selector_all(
        "form", "els => els.map(e => ({id:e.id,name:e.name,action:e.action,method:e.method}))",
    )
    print(f"\n===== {page.url} =====")
    print("TITLE:", page.title())
    print("FORMS:", json.dumps(forms, ensure_ascii=False))
    print("INPUTS:", json.dumps(inputs, ensure_ascii=False, indent=1))
    print("BUTTONS:", json.dumps(buttons, ensure_ascii=False, indent=1))


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        for ctx in browser.contexts:
            for page in ctx.pages:
                try:
                    dump(page)
                except Exception as e:
                    print("dump err:", page.url, e)


if __name__ == "__main__":
    main()
