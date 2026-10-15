@echo off
REM ============================================================
REM  Build Privacy Browser -> dist\PrivacyBrowser\PrivacyBrowser.exe
REM  lalu (jika Inno Setup 6 terpasang) -> installer\PrivacyBrowser-Setup.exe
REM  Hanya dibutuhkan di komputer developer, BUKAN di komputer pengguna.
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/3] Memasang dependensi build...
python -m pip install -q -r requirements.txt pyinstaller pillow || goto :err

if not exist privacy_browser\logo_36.png python tools\make_icon.py

echo [2/3] Membangun EXE dengan PyInstaller...
python -m PyInstaller --noconfirm --clean --windowed --onedir ^
  --name PrivacyBrowser ^
  --icon privacy_browser\icon.ico ^
  --add-data "privacy_browser\stealth.js;privacy_browser" ^
  --add-data "privacy_browser\icon.ico;privacy_browser" ^
  --add-data "privacy_browser\logo_*.png;privacy_browser" ^
  --collect-data patchright ^
  --version-file version_info.txt ^
  main.py || goto :err

echo [3/3] Membuat installer...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist %%P set "ISCC=%%~P"
)
if defined ISCC (
  "%ISCC%" /Q installer.iss || goto :err
  echo.
  echo SELESAI: installer\PrivacyBrowser-Setup.exe
) else (
  echo Inno Setup 6 tidak ditemukan - installer dilewati.
  echo Pasang dengan:  winget install JRSoftware.InnoSetup   lalu jalankan build.bat lagi.
  echo Versi portable tetap tersedia di: dist\PrivacyBrowser\
)
exit /b 0

:err
echo.
echo BUILD GAGAL.
exit /b 1
