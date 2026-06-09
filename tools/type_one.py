"""키로그 비교용 — pyautogui로 'a' 한 글자만 친다 (물리 입력과 이벤트 속성 비교)."""
import time
import pyautogui
pyautogui.FAILSAFE = False
time.sleep(3)
pyautogui.write("a", interval=0)
print("'a' 입력함")
