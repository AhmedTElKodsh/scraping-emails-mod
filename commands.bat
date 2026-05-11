@echo off
REM Command shortcuts for scraping-emails-mod (Windows)

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="install" goto install
if "%1"=="test" goto test
if "%1"=="lint" goto lint
if "%1"=="format" goto format
if "%1"=="clean" goto clean
if "%1"=="check-branch" goto check-branch
if "%1"=="switch-main" goto switch-main
if "%1"=="switch-apollo" goto switch-apollo
if "%1"=="ui" goto ui
if "%1"=="acquisition-ui" goto acquisition-ui
goto help

:help
echo Available commands:
echo   commands.bat install        - Install dependencies
echo   commands.bat test          - Run tests
echo   commands.bat lint          - Run linting
echo   commands.bat format        - Format code
echo   commands.bat clean         - Clean temporary files
echo   commands.bat check-branch  - Check current branch and features
echo   commands.bat switch-main   - Switch to main branch
echo   commands.bat switch-apollo - Switch to apollo-integration branch
echo   commands.bat ui            - Launch main UI
echo   commands.bat acquisition-ui - Launch acquisition UI
goto end

:install
echo Installing dependencies...
pip install -r requirements.txt
playwright install chromium
goto end

:test
echo Running tests...
pytest tests/unit -v
goto end

:lint
echo Running linting...
ruff check src/ tests/
goto end

:format
echo Formatting code...
ruff format src/ tests/
goto end

:clean
echo Cleaning temporary files...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
for /d /r . %%d in (.pytest_cache) do @if exist "%%d" rd /s /q "%%d"
for /d /r . %%d in (.ruff_cache) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
if exist htmlcov rd /s /q htmlcov
if exist .coverage del .coverage
echo Done!
goto end

:check-branch
python check_branch.py
goto end

:switch-main
echo Switching to main branch (core features only)...
git checkout main
python check_branch.py
goto end

:switch-apollo
echo Switching to apollo-integration branch (full features)...
git checkout apollo-integration
python check_branch.py
goto end

:ui
echo Launching main UI...
python -m scraper ui
goto end

:acquisition-ui
echo Launching acquisition UI...
python -m scraper acquisition-ui
goto end

:end
