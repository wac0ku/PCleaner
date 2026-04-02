@echo off
:: PCleaner Installer — launches the PowerShell wizard
:: Double-click this file to install PCleaner

echo.
echo   PCleaner — Starting Installation Wizard...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"

if errorlevel 1 (
    echo.
    echo   Installation encountered an error. Please check above.
    pause
)
