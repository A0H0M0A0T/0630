@echo off
chcp 65001 >nul
echo === START TEST ===
echo Current dir: %cd%
start "Test Window" cmd /k echo Hello ^&^& echo World ^&^& pause
echo === DONE ===
pause
