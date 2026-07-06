@echo off
chcp 65001 >nul
cd /d D:\0703

title D:\0703 — 全部服务启动中

echo.
echo   ============================================
echo       D:\0703 — 一键启动全部开发服务
echo   ============================================
echo.

where python >nul 2>&1 || (echo [错误] 找不到 python && pause && exit /b 1)
where node >nul 2>&1   || (echo [错误] 找不到 node && pause && exit /b 1)

echo   python: OK   node: OK
echo.

echo   [1/5] AI-Toolbox 后端 ^(FastAPI :8000^)
start "AI-Toolbox 后端 :8000" cmd /k cd /d D:\0703\ai-toolbox\work ^&^& echo FastAPI http://localhost:8000 ^&^& python server.py ^&^& pause

echo   [2/5] AI-Toolbox 前端 ^(React :5173^)
start "AI-Toolbox 前端 :5173" cmd /k cd /d D:\0703\ai-toolbox\work ^&^& echo React http://localhost:5173 ^&^& npm run dev ^&^& pause

echo   [3/5] 上传服务 后端 ^(Flask :5409^)
start "上传服务 后端 :5409" cmd /k cd /d D:\0703\social-auto-upload-main ^&^& echo Flask http://localhost:5409 ^&^& python sau_backend.py ^&^& pause

echo   [4/4] 上传服务 前端 ^(Vue :5174^)
start "上传服务 前端 :5174" cmd /k cd /d D:\0703\social-auto-upload-main\sau_frontend ^&^& echo Vue http://localhost:5174 ^&^& npx vite --port 5174 ^&^& pause

echo.
echo   ============================================
echo   全部 4 个服务已启动，各自在独立窗口运行
echo   ============================================
echo.
echo   :8000   AI-Toolbox 后端
echo   :5173   AI-Toolbox 前端
echo   :5409   上传服务 后端
echo   :5174   上传服务 前端
echo.
echo   关闭窗口 = 停止该服务。或双击 stop-all.bat
echo.
pause
