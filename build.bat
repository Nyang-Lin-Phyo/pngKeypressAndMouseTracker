@echo off

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "*.spec" del /q *.spec

python -m PyInstaller ^
--onefile ^
--windowed ^
--collect-all websockets ^
--icon=assets\icon.ico ^
--name "LivelyPNG" ^
launcher.py

if %ERRORLEVEL% neq 0 (
echo Build failed.
pause
exit /b 1
)

echo Build complete:
echo dist\PNGvtuber Launcher.exe
pause
