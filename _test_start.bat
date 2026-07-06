@echo off
echo Testing start command...
start "TestWindow" cmd /k "echo Hello && echo World && pause"
echo Start command issued.
pause
