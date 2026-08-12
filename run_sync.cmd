@echo off
setlocal
set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if exist "%PY_EXE%" (
  "%PY_EXE%" "%~dp0syncPvCharge.py" %*
) else (
  py -3.11 "%~dp0syncPvCharge.py" %*
)
