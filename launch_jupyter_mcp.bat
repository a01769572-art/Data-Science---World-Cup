@echo off
setlocal

cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "PYTHON=%PROJECT_ROOT%\.venv\python.exe"
set "PROJECT_JUPYTER=%PROJECT_ROOT%\.venv\Scripts\jupyter-lab.exe"
set "CONDA_PYTHON=%USERPROFILE%\anaconda3\python.exe"
set "CONDA_JUPYTER=%USERPROFILE%\anaconda3\Scripts\jupyter-lab.exe"
set "JUPYTER_RUNTIME_DIR=%PROJECT_ROOT%\.jupyter-runtime"

if not exist "%JUPYTER_RUNTIME_DIR%" mkdir "%JUPYTER_RUNTIME_DIR%"

if not exist "%PYTHON%" (
    echo ERROR: No se encontro el entorno Python del proyecto:
    echo   %PYTHON%
    echo.
    echo Ejecuta primero la instalacion del entorno .venv.
    pause
    exit /b 1
)

if not exist "%PROJECT_JUPYTER%" (
    echo ERROR: No se encontro JupyterLab:
    echo   %PROJECT_JUPYTER%
    echo.
    echo Instala las dependencias de desarrollo con:
    echo   "%PYTHON%" -m pip install -e ".[dev]"
    pause
    exit /b 1
)

if not defined JUPYTER_TOKEN set "JUPYTER_TOKEN=MY_TOKEN"

set "JUPYTER_LAB=%PROJECT_JUPYTER%"
set "COLLABORATIVE_ARG="

if exist "%CONDA_PYTHON%" if exist "%CONDA_JUPYTER%" (
    "%CONDA_PYTHON%" -c "import jupyter_collaboration" >nul 2>&1
    if not errorlevel 1 (
        set "JUPYTER_LAB=%CONDA_JUPYTER%"
        set "COLLABORATIVE_ARG=--collaborative"
    )
)

if not defined COLLABORATIVE_ARG (
    "%PYTHON%" -c "import jupyter_collaboration" >nul 2>&1
    if not errorlevel 1 set "COLLABORATIVE_ARG=--collaborative"
)

if not defined COLLABORATIVE_ARG (
    echo ERROR: No se encontro jupyter-collaboration.
    echo Las operaciones Jupyter MCP que editan celdas requieren este paquete.
    echo.
    echo Instala una vez:
    echo   "%PYTHON%" -m pip install "jupyter-collaboration>=4,<5"
    pause
    exit /b 1
)

netstat -ano | findstr /R /C:":8888 .*LISTENING" >nul
if not errorlevel 1 (
    echo ERROR: El puerto 8888 ya esta ocupado.
    echo.
    echo Cierra el servidor Jupyter anterior y vuelve a ejecutar este archivo.
    echo El servidor MCP esta configurado para usar http://localhost:8888.
    pause
    exit /b 1
)

set "KERNEL_DIR=%PROJECT_ROOT%\.venv\share\jupyter\kernels\cdd-mundial"
set "PYTHON_JSON=%PYTHON:\=\\%"
if not exist "%KERNEL_DIR%" mkdir "%KERNEL_DIR%"

> "%KERNEL_DIR%\kernel.json" (
    echo {
    echo  "argv": [
    echo   "%PYTHON_JSON%",
    echo   "-m",
    echo   "ipykernel_launcher",
    echo   "-f",
    echo   "{connection_file}"
    echo  ],
    echo  "display_name": "Python (CDD-MUNDIAL)",
    echo  "language": "python",
    echo  "metadata": {
    echo   "debugger": true
    echo  }
    echo }
)

if not exist "%KERNEL_DIR%\kernel.json" (
    echo ERROR: No se pudo crear el kernel del proyecto.
    pause
    exit /b 1
)

set "JUPYTER_PATH=%PROJECT_ROOT%\.venv\share\jupyter;%JUPYTER_PATH%"

echo Iniciando JupyterLab para CDD-MUNDIAL...
echo Raiz:   %PROJECT_ROOT%
echo URL:    http://localhost:8888/lab
echo Kernel: Python (CDD-MUNDIAL)
echo Cierre esta ventana para detener el servidor.
echo.

"%JUPYTER_LAB%" ^
    %COLLABORATIVE_ARG% ^
    --ServerApp.root_dir="%PROJECT_ROOT%" ^
    --ServerApp.ip=127.0.0.1 ^
    --ServerApp.port=8888 ^
    --ServerApp.port_retries=0 ^
    --IdentityProvider.token="%JUPYTER_TOKEN%"

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo JupyterLab termino con codigo %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
