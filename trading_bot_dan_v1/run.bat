@echo off
setlocal

where python >nul 2>nul || (echo Python 3.11+ required & exit /b 1)

set "UV_CMD=uv"
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo Installing uv...
  python -m pip install --user uv || exit /b 1
  set "UV_CMD=python -m uv"
)

%UV_CMD% sync || exit /b 1
%UV_CMD% run python -m danbot.main
