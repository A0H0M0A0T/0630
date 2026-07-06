@echo off
chcp 65001 >nul
title 停止所有服务...

echo.
echo   正在停止所有 D:\0703 服务...

:: Kill by port — most reliable method
for %%p in (8000 5173 5409 5174 3000) do (
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :%%p.*LISTENING') do (
        echo   停止端口 %%p (PID %%a^)
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo   全部服务已停止。
echo.
pause
