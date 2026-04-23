@echo off
echo Building SCSS...
call npm run build:css
if %ERRORLEVEL% EQU 0 (
    echo Build successful.
) else (
    echo Build failed.
)
pause
