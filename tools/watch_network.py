"""네트워크 감시 — 사용자가 손으로 로그인~엑셀다운로드 하는 동안 모든 요청/응답 기록.

연결된 Chrome(9222)의 모든 페이지/팝업의 request/response/download를 tools/netlog.txt에 남긴다.
실행: python tools/watch_network.py   (그 후 사용자가 브라우저에서 직접 작업)
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automation import config as C  # noqa: E402

LOG = open(Path(__file__).resolve().parent / "netlog.txt", "w", encoding="utf-8", buffering=1)
RUN_SECONDS = 300

# 잡음 줄이기: 정적 자원 제외
SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".css", ".woff", ".woff2", ".ico", ".svg")


def w(line: str):
    LOG.write(line + "\n")
    print(line)


def interesting(url: str) -> bool:
    u = url.lower()
    if any(u.split("?")[0].endswith(e) for e in SKIP_EXT):
        return False
    return True


def on_request(req):
    try:
        url = req.url
        if not interesting(url):
            return
        line = f">> {req.method} {url}"
        w(line)
        # 로그인/조회/다운로드성 POST는 본문도
        if req.method == "POST":
            try:
                data = req.post_data
                if data:
                    w(f"   POSTDATA: {data[:600]}")
            except Exception:
                pass
            try:
                ct = req.headers.get("content-type", "")
                w(f"   REQ-HEADERS: content-type={ct} x-requested-with={req.headers.get('x-requested-with','')}")
            except Exception:
                pass
    except Exception as e:
        w(f"   (req err {e})")


def on_response(res):
    try:
        url = res.url
        if not interesting(url):
            return
        ct = ""
        cd = ""
        try:
            h = res.headers
            ct = h.get("content-type", "")
            cd = h.get("content-disposition", "")
        except Exception:
            pass
        line = f"<< {res.status} {url}  ct={ct}"
        if cd:
            line += f"  CONTENT-DISPOSITION={cd}"
        w(line)
        # redirect Location
        if res.status in (301, 302, 303, 307, 308):
            try:
                w(f"   LOCATION: {res.headers.get('location','')}")
            except Exception:
                pass
    except Exception as e:
        w(f"   (res err {e})")


def on_download(dl):
    try:
        w(f"** DOWNLOAD: suggested={dl.suggested_filename} url={dl.url}")
    except Exception as e:
        w(f"   (dl err {e})")


def attach(page):
    page.on("request", on_request)
    page.on("response", on_response)
    page.on("download", on_download)


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{C.CDP_PORT}")
        ctx = browser.contexts[0]
        for pg in ctx.pages:
            attach(pg)
        ctx.on("page", lambda pg: (attach(pg), w(f"** NEW PAGE: {pg.url}")))
        # 깨끗한 출발점으로 홈 이동
        page = ctx.pages[-1] if ctx.pages else ctx.new_page()
        try:
            page.goto(C.HOME_URL, wait_until="domcontentloaded", timeout=40000)
        except Exception as e:
            w(f"home goto err: {e}")
        w("=== 감시 시작. 이제 브라우저에서 직접 로그인→기간별 매입내역→조회→엑셀다운로드 해주세요. ===")
        t0 = time.time()
        while time.time() - t0 < RUN_SECONDS:
            time.sleep(1)
        w("=== 감시 종료 ===")
        LOG.close()


if __name__ == "__main__":
    main()
