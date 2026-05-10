@echo off
REM Add Python Scripts directory to PATH for current session
set PATH=%PATH%;C:\Users\Admin\AppData\Roaming\Python\Python314\Scripts

echo Python Scripts directory added to PATH for this session.
echo You can now run: scraper scrape restaurants/cairo
echo.
echo To make this permanent, add the directory to your system PATH:
echo 1. Search for "Environment Variables" in Windows
echo 2. Edit "Path" under User variables
echo 3. Add: C:\Users\Admin\AppData\Roaming\Python\Python314\Scripts
echo.
