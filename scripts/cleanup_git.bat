@echo off
setlocal
cd /d "%~dp0.."
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo This folder is not a Git working copy. Use git clone or the GitHub website instructions.
  pause
  exit /b 1
)
if not exist ".gitignore" (
  echo Copy the provided .gitignore to the project root first.
  pause
  exit /b 1
)
git rm -r --cached --ignore-unmatch -- backend/easystock/__pycache__
if errorlevel 1 goto failed
git rm --cached --ignore-unmatch -- database/easystock.db database/easystock.db-wal database/easystock.db-shm
if errorlevel 1 goto failed
echo.
echo Cleanup staged. Local database and cache files were kept.
git status --short
echo.
echo Next: git add .gitignore README.md docs scripts
echo Then: git diff --cached --stat
echo Then: git commit -m "Update reports and clean repository"
echo Then: git push origin main
pause
exit /b 0
:failed
echo Git could not stage cleanup. Read the error above; no force option was used.
pause
exit /b 1
