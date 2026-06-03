@echo off

echo Cleaning old builds...

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "*.spec" del /q *.spec

echo.
echo Building PNGvtuber Launcher...

python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --collect-all websockets ^
  --name "PNGvtuber Launcher" ^
  launcher.py

echo.
echo Done!
pause