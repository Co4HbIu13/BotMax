@echo off
chcp 65001 >nul
echo ========================================
echo  🎰 BotMAX Admin APK Builder
echo ========================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_apk.ps1"
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Готово! APK собран успешно.
) else (
    echo.
    echo ❌ Ошибка сборки APK!
)
pause
