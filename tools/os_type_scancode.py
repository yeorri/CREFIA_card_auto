"""스캔코드 기반 키 입력 — SendInput + KEYEVENTF_SCANCODE.

pyautogui는 가상키코드만 보내 event.code가 비어 dynapath에 봇으로 걸린다.
스캔코드를 함께 보내면 Chrome이 event.code(예: KeyA)를 채워 물리 키와 구별 불가.

    python tools/os_type_scancode.py            # 'a' 한 글자 (검증용)
    python tools/os_type_scancode.py <문자열>   # 해당 문자열 타이핑
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

# --- SendInput 구조체 ---
INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001
VK_SHIFT = 0x10
MAPVK_VK_TO_VSC = 0


# 64비트에서 dwExtraInfo는 ULONG_PTR(8바이트), INPUT 전체는 40바이트여야 함.
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]  # mi로 union 크기 맞춤(40B)
    _anonymous_ = ("i",)
    _fields_ = [("type", wintypes.DWORD), ("i", _I)]


def _send_scan(scan, keyup):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if keyup else 0)
    inp = INPUT(type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _vk_and_shift(ch):
    """문자 → (가상키, shift필요?)."""
    res = user32.VkKeyScanW(ctypes.c_wchar(ch))
    vk = res & 0xFF
    shift = (res >> 8) & 0x01
    return vk, bool(shift)


def type_char(ch):
    vk, need_shift = _vk_and_shift(ch)
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    if need_shift:
        _send_scan(user32.MapVirtualKeyW(VK_SHIFT, MAPVK_VK_TO_VSC), False)
        time.sleep(0.01)
    _send_scan(scan, False)
    time.sleep(0.015)
    _send_scan(scan, True)
    if need_shift:
        time.sleep(0.01)
        _send_scan(user32.MapVirtualKeyW(VK_SHIFT, MAPVK_VK_TO_VSC), True)


def type_string(s, per=0.06):
    for ch in s:
        type_char(ch)
        time.sleep(per)


VK_TAB = 0x09
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_BACK = 0x08
VK_A = 0x41


def press_vk(vk):
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    _send_scan(scan, False)
    time.sleep(0.02)
    _send_scan(scan, True)


WM_IME_CONTROL = 0x0283
IMC_SETCONVERSIONMODE = 0x0002


def force_english():
    """포커스된 창의 한글 IME를 영문(알파벳) 모드로 강제 전환.

    스캔코드 입력이 IME를 거치므로, 한글 모드면 'a'가 'ㅁ'으로 들어간다.
    로그인 직전 호출해 항상 영문으로 맞춘다.
    """
    try:
        hwnd = user32.GetForegroundWindow()
        ime = user32.ImmGetDefaultIMEWnd(hwnd)
        if ime:
            # 변환모드 0 = IME_CMODE_ALPHANUMERIC(영문)
            user32.SendMessageW(ime, WM_IME_CONTROL, IMC_SETCONVERSIONMODE, 0)
            time.sleep(0.05)
    except Exception:
        pass


def clear_field():
    """현재 포커스 칸 비우기: Ctrl+A(전체선택) → Backspace. (저장된 아이디 등 잔존값 제거)"""
    ctrl = user32.MapVirtualKeyW(VK_CONTROL, MAPVK_VK_TO_VSC)
    a = user32.MapVirtualKeyW(VK_A, MAPVK_VK_TO_VSC)
    _send_scan(ctrl, False)
    time.sleep(0.01)
    _send_scan(a, False)
    time.sleep(0.01)
    _send_scan(a, True)
    _send_scan(ctrl, True)
    time.sleep(0.05)
    press_vk(VK_BACK)
    time.sleep(0.05)


def login(uid, pw, dp_wait=3.0):
    """칸비우기 → 아이디 → Tab → 칸비우기 → 비번 → (dp 대기) → Tab → Enter(제출). 전부 스캔코드."""
    force_english()   # 한글 IME 방지
    clear_field()
    type_string(uid)
    time.sleep(0.4)
    press_vk(VK_TAB)
    time.sleep(0.3)
    clear_field()
    type_string(pw)
    time.sleep(dp_wait)   # dp(dynapath) 비동기 로딩 대기 — 너무 빨리 제출하면 400
    press_vk(VK_TAB)      # 비번 → LOGIN 버튼
    time.sleep(0.3)
    press_vk(VK_RETURN)   # 제출(버튼 키보드 활성화 = 진짜 클릭)


def fill_only(uid, pw):
    """제출 없이 아이디→Tab→비번 까지만 (입력 확인용)."""
    force_english()
    clear_field()
    type_string(uid)
    time.sleep(0.4)
    press_vk(VK_TAB)
    time.sleep(0.3)
    clear_field()
    type_string(pw)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--login":
        dpw = float(sys.argv[4]) if len(sys.argv) >= 5 else 3.0
        print(f"3초 후 로그인 타이핑(스캔코드), dp대기={dpw}s ...")
        time.sleep(3)
        login(sys.argv[2], sys.argv[3], dp_wait=dpw)
        print("로그인 제출 완료")
    elif len(sys.argv) >= 4 and sys.argv[1] == "--fill":
        print("3초 후 채우기만(제출 안함)...")
        time.sleep(3)
        fill_only(sys.argv[2], sys.argv[3])
        print("fill done - check fields then click LOGIN")
    else:
        text = sys.argv[1] if len(sys.argv) > 1 else "a"
        print(f"3초 후 '{text}' 스캔코드 타이핑...")
        time.sleep(3)
        type_string(text)
        print("완료")
