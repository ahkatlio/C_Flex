@echo off
:: Check for elevation
net session >nul 2>&1
if %errorLevel% == 0 (
    :: Already elevated, run the command
    powershell -Command "irm 'https://christitus.com/win' | iex"
) else (
    :: Not elevated, request elevation
    powershell -Command "Start-Process cmd -ArgumentList '/c %~dp0elevate.bat' -Verb RunAs"
)