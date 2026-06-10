"""앱 시작 시 GitHub에 호스팅된 version.json을 fetch → 새 버전 있으면 callback.

흐름:
  1. CURRENT_VERSION 상수에 빌드 시점의 버전이 박혀 있음.
  2. 앱 시작 후 background thread에서 UPDATE_CHECK_URL을 fetch.
  3. version.json의 "version"이 CURRENT_VERSION보다 크면 callback(info) 호출.
  4. 네트워크 실패/타임아웃 등은 조용히 무시 (사용자 작업 방해 X).

배포 절차:
  - 새 버전 빌드 시 CURRENT_VERSION 올리고, GitHub Releases에 exe 올린 뒤,
    main 브랜치의 version.json 의 "version"을 같은 값으로 올려 push.
"""
import json
import threading
import urllib.request

# ───── 빌드별로 갱신 ─────
CURRENT_VERSION = "1.0.2"

# ───── GitHub 호스팅 위치 ─────
GITHUB_USER = "yeorri"
GITHUB_REPO = "CREFIA_card_auto"
UPDATE_CHECK_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/version.json"


def _parse_version(v):
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except Exception:
        return (0,)


def _check_sync():
    """동기적으로 한 번 체크. 새 버전 있으면 dict, 아니면 None."""
    try:
        req = urllib.request.Request(
            UPDATE_CHECK_URL, headers={"User-Agent": "CrefiaCardAuto-UpdateCheck"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    latest = (data.get("version") or "").strip()
    if not latest or _parse_version(latest) <= _parse_version(CURRENT_VERSION):
        return None
    return {
        "latest": latest,
        "current": CURRENT_VERSION,
        "download_url": (data.get("download_url") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
    }


def check_async(callback):
    """Background thread에서 체크. 새 버전 있으면 callback(info) 호출.
    callback 내부에서 GUI 조작 시 root.after(0, ...)로 디스패치할 것.
    """
    def _run():
        info = _check_sync()
        if info:
            try:
                callback(info)
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()
