@echo off
setlocal

cd /d "%~dp0"

set "APP_FILE=youtube_toolbox.py"
set "APP_PORT=8502"
set "CONDA_ENV=whisper"

echo Starting YouTube Toolbox...
echo Project folder: %CD%
echo.

call :activate_conda

where streamlit >nul 2>nul
if errorlevel 1 (
    echo Streamlit was not found in the current environment.
    echo.
    echo Try this once in PowerShell or Anaconda Prompt:
    echo   conda activate %CONDA_ENV%
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:%APP_PORT%'"
streamlit run "%APP_FILE%" --server.port %APP_PORT%

echo.
echo Streamlit stopped.
pause
exit /b 0

:activate_conda
where conda >nul 2>nul
if not errorlevel 1 (
    call conda activate "%CONDA_ENV%" >nul 2>nul
    if not errorlevel 1 (
        echo Activated conda environment: %CONDA_ENV%
        exit /b 0
    )
)

if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" "%CONDA_ENV%" >nul 2>nul
    if not errorlevel 1 (
        echo Activated conda environment: %CONDA_ENV%
        exit /b 0
    )
)

if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" "%CONDA_ENV%" >nul 2>nul
    if not errorlevel 1 (
        echo Activated conda environment: %CONDA_ENV%
        exit /b 0
    )
)

echo Could not auto-activate conda environment: %CONDA_ENV%
echo Continuing with the current environment...
echo.
exit /b 0
