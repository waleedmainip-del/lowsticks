@echo off
REM lowsticks clipper - one-time setup on Windows
cd /d "%~dp0"

where python >nul 2>nul || (
  echo Installing Python...
  winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
  echo Close this window, open a new one and run install.bat again.
  pause
  exit /b
)

where ffmpeg >nul 2>nul || (
  echo Installing ffmpeg...
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist fonts mkdir fonts
powershell -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-ExtraBold.ttf' -OutFile 'fonts\Poppins-ExtraBold.ttf' } catch { Write-Host 'font download failed, default font will be used' }"

echo.
echo Done. Example:
echo   python clip.py "https://www.twitch.tv/videos/123456789" --count 3
echo (If ffmpeg was just installed, open a NEW window first.)
pause
