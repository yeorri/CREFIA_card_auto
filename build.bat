@echo off
chcp 65001 >nul
cd /d %~dp0
echo === 여신금융협회 카드자료 자동 다운로드 — 빌드 ===
pyinstaller --noconfirm --onefile --windowed ^
  --name "CREFIA_card_auto" ^
  --icon "icon.ico" ^
  --add-data "icon.ico;." ^
  --paths "tools" ^
  --hidden-import os_type_scancode ^
  --hidden-import postprocess ^
  gui.py
echo.
echo === 완료: dist\ 폴더의 exe 확인 ===
pause
