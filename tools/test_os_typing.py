"""OS 레벨 로그인 — 사람처럼 '불규칙한' 타이밍으로 타이핑.

가설: dynapath는 키 입력 간격이 너무 규칙적(예: 정확히 70ms)이면 봇으로 보고
'사람 키 카운터'에서 제외한다. 그래서 랜덤한 인간적 간격으로 치면 카운트되어 통과한다.

    python tools/test_os_typing.py <ID> <PW>
"""
from __future__ import annotations

import random
import sys
import time

import pyautogui

pyautogui.FAILSAFE = False

INITIAL_DELAY = 3


def type_humanish(text):
    """한 글자씩, 불규칙한 간격으로. 가끔 더 길게 멈칫."""
    for i, ch in enumerate(text):
        pyautogui.write(ch, interval=0)
        # 기본 60~220ms 랜덤, 가끔(15%) 300~600ms 멈칫
        if random.random() < 0.15:
            time.sleep(random.uniform(0.30, 0.60))
        else:
            time.sleep(random.uniform(0.06, 0.22))


def main():
    if len(sys.argv) < 3:
        print("usage: test_os_typing.py <ID> <PW>")
        return
    uid, pw = sys.argv[1], sys.argv[2]

    time.sleep(INITIAL_DELAY)

    type_humanish(uid)
    time.sleep(random.uniform(0.3, 0.6))
    pyautogui.press("tab")
    time.sleep(random.uniform(0.2, 0.4))
    type_humanish(pw)
    time.sleep(random.uniform(0.3, 0.6))

    print("입력 완료. 제출(Tab→Enter)...")
    pyautogui.press("tab")
    time.sleep(0.3)
    pyautogui.press("enter")
    print("제출 완료. 결과 확인하세요.")


if __name__ == "__main__":
    main()
