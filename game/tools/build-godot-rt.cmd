@echo off
setlocal
set "ENGINE_BUILD_TARGET=editor"
if not "%~1"=="" set "ENGINE_BUILD_TARGET=%~1"
pwsh -NoProfile -File "%~dp0..\..\engine\misc\scripts\build_windows.ps1" -Target "%ENGINE_BUILD_TARGET%"
exit /b %errorlevel%
