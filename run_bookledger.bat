@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto fail

set "PYTHON=.venv\Scripts\python.exe"
set "APP=.venv\Scripts\bookledger.exe"

if not exist "%PYTHON%" (
  echo Creating the BookLedger virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)

if not exist "%PYTHON%" (
  echo ERROR: The virtual environment was not created at %PYTHON%.
  goto fail
)

"%PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo Bootstrapping pip in the virtual environment...
  "%PYTHON%" -m ensurepip --upgrade
  if errorlevel 1 goto fail
)

set "NEEDS_INSTALL=0"
"%PYTHON%" -c "import importlib.metadata as m, bookledger; from pathlib import Path; d=m.distribution('bookledger'); assert any(e.name=='bookledger' and e.value=='bookledger.app:main' for e in d.entry_points); assert Path(bookledger.__file__).resolve().is_relative_to((Path.cwd()/'src'/'bookledger').resolve()); import PIL, ttkbootstrap" >nul 2>&1
if errorlevel 1 set "NEEDS_INSTALL=1"
if not exist "%APP%" set "NEEDS_INSTALL=1"
"%PYTHON%" -m pip check >nul 2>&1
if errorlevel 1 set "NEEDS_INSTALL=1"

if "%NEEDS_INSTALL%"=="1" (
  echo Installing or repairing BookLedger and its runtime dependencies...
  "%PYTHON%" -m pip install -e .
  if errorlevel 1 goto fail
  "%PYTHON%" -m pip check
  if errorlevel 1 goto fail
)

if not exist "%APP%" (
  echo ERROR: The BookLedger console entry point was not created.
  goto fail
)

echo Launching BookLedger...
call "%APP%"
if errorlevel 1 goto fail
exit /b 0

:fail
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" set "EXIT_CODE=1"
echo.
echo ERROR: BookLedger setup or startup failed with exit code %EXIT_CODE%.
echo Review the diagnostic above, correct the problem, and run this launcher again.
pause
exit /b %EXIT_CODE%
