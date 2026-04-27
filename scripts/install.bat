@echo off
chcp 65001 >nul
echo ========================================
echo   Mini OJ - Install Language Runtimes
echo ========================================
echo.

where winget >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo winget not found. Please install App Installer from Microsoft Store.
    pause
    exit /b 1
)

echo --- Core languages ---

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK]  Python 3
) else (
    echo [--]  Python 3 not found. Installing...
    winget install Python.Python.3 --accept-package-agreements --accept-source-agreements
)

where g++ >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK]  g++
) else (
    echo [--]  g++ not found. Installing MSYS2...
    winget install MSYS2.MSYS2 --accept-package-agreements --accept-source-agreements
    echo       After install, open MSYS2 and run:
    echo       pacman -S mingw-w64-x86_64-gcc
)

where node >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK]  Node.js
) else (
    echo [--]  Node.js not found. Installing...
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
)

where java >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK]  Java
) else (
    echo [--]  Java not found. Installing...
    winget install EclipseAdoptium.Temurin.17.JDK --accept-package-agreements --accept-source-agreements
)

echo.
echo --- Optional (uncomment to install) ---
REM winget install GoLang.Go --accept-package-agreements --accept-source-agreements
REM winget install Rustlang.Rustup --accept-package-agreements --accept-source-agreements
REM winget install Microsoft.DotNet.SDK.8 --accept-package-agreements --accept-source-agreements
REM winget install RubyInstallerTeam.Ruby.3.2 --accept-package-agreements --accept-source-agreements
REM winget install PHP.PHP.8.3 --accept-package-agreements --accept-source-agreements

echo.
echo Done. Restart Django to pick up changes.
pause
