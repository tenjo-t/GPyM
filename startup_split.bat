@echo off
if not exist scripts (
echo %CD%にはscriptsという名前のフォルダーが存在しません
set /p __=
exit /b
)
if not exist scripts\MAIN.py (
echo %CD%\scriptsにはMAIN.pyが存在しません
set /p __=
exit /b
)
echo on
py scripts\MAIN.py SPLIT