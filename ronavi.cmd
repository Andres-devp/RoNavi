@echo off
rem RoNavi Studio launcher for Windows (cmd and PowerShell: type "ronavi" or ".\ronavi").
rem Finds Python 3.11+, prepares .venv on first run and opens the TUI.
setlocal
set "RONAVI_BOOT=%~dp0ronavi\bootstrap.py"
where py >nul 2>nul && goto :use_py
where python >nul 2>nul && goto :use_python
goto :no_python

:use_py
py -3 "%RONAVI_BOOT%" %*
exit /b

:use_python
python "%RONAVI_BOOT%" %*
exit /b

:no_python
echo RoNavi Studio necesita Python 3.11 o superior y no lo encuentra.
where winget >nul 2>nul || goto :manual
choice /c SN /m "Instalar Python 3.12 con winget ahora"
if errorlevel 2 goto :manual
winget install --id Python.Python.3.12 -e
echo.
echo Listo. Abre una terminal nueva y vuelve a ejecutar ronavi.
exit /b 1

:manual
echo Instala Python desde https://www.python.org/downloads/ y vuelve a ejecutar ronavi.
exit /b 1
