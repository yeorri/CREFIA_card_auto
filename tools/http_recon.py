"""순수 HTTP로 /signin을 받아 로그인 폼(랜덤 필드명/CSRF 토큰)을 읽을 수 있는지 확인.

브라우저/CDP 없이 requests만 사용 → 봇 감지 JS가 안 돈다. 로그인 시도는 안 함(안전).
"""
from __future__ import annotations

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import requests
from bs4 import BeautifulSoup

BASE = "https://www.cardsales.or.kr"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def main():
    s = requests.Session()
    s.headers.update(HEADERS)

    print("GET / ...")
    r0 = s.get(BASE + "/", timeout=20)
    print("  status:", r0.status_code, "len:", len(r0.text))

    print("GET /signin ...")
    r = s.get(BASE + "/signin", timeout=20)
    print("  status:", r.status_code, "url:", r.url, "len:", len(r.text))
    if "restricted" in r.url or "제한" in r.text:
        print("  >>> 차단됨(restricted). HTTP 클라이언트도 막힘.")
    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.find("form")
    if not form:
        print("  폼을 못 찾음. 본문 앞부분:")
        print(r.text[:800])
        return
    print("\n--- FORM ---")
    print("  action:", form.get("action"), " method:", form.get("method"))
    print("--- INPUTS ---")
    for inp in form.find_all(["input", "select"]):
        print("  ", {
            "tag": inp.name, "type": inp.get("type"),
            "id": inp.get("id"), "name": inp.get("name"),
            "placeholder": inp.get("placeholder"),
            "value": (inp.get("value") or "")[:40],
        })
    print("\n--- COOKIES ---")
    for c in s.cookies:
        print("  ", c.name, "=", c.value[:30], "domain:", c.domain)


if __name__ == "__main__":
    main()
