"""다운로드 이벤트만 가볍게 캡처 — navigate/Network감시 안 함, 세션 안 건드림.

사용자가 손으로 로그인~엑셀다운로드 하는 동안, 엑셀 다운로드의 URL/파일만 잡는다.
실행 후 사용자가 브라우저에서 직접 작업. 결과는 tools/captured/ 에 저장 + tools/dl_capture.txt 로그.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "captured"
OUT.mkdir(exist_ok=True)
LOG = open(Path(__file__).resolve().parent / "dl_capture.txt", "w", encoding="utf-8", buffering=1)
RUN_SECONDS = 360


def w(msg):
    LOG.write(msg + "\n")
    print(msg)


def on_download(dl):
    try:
        w(f"** DOWNLOAD 감지")
        w(f"   url: {dl.url}")
        w(f"   suggested_filename: {dl.suggested_filename}")
        dest = OUT / dl.suggested_filename
        dl.save_as(str(dest))
        w(f"   저장됨: {dest}  ({dest.stat().st_size} bytes)")
    except Exception as e:
        w(f"   (download 처리 err: {e})")


def attach(page):
    try:
        page.on("download", on_download)
    except Exception:
        pass


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0]
        for pg in ctx.pages:
            attach(pg)
        ctx.on("page", lambda pg: (attach(pg), w(f"** 새 탭: {pg.url}")))
        w("=== 다운로드 캡처 시작. 브라우저에서 직접 로그인→기간별 매입내역→조회→엑셀다운로드 하세요. ===")
        w("=== (이 스크립트는 navigate/감시 안 함. 세션 안 건드림.) ===")
        t0 = time.time()
        while time.time() - t0 < RUN_SECONDS:
            time.sleep(1)
        w("=== 캡처 종료 ===")
        LOG.close()


if __name__ == "__main__":
    main()
