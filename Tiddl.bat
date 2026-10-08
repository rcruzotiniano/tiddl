@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "TIDDL=%~dp0.venv\Scripts\tiddl.exe"
if not exist "%TIDDL%" set "TIDDL="
if not defined TIDDL for /f "delims=" %%I in ('where.exe tiddl.exe 2^>nul') do if not defined TIDDL set "TIDDL=%%I"
if not defined TIDDL (
    echo No se encontro tiddl.exe. Instala tiddl o crea el entorno .venv.
    pause
    exit /b 1
)
set "CONFIG=settings.ini"

if not exist "%CONFIG%" (
(
echo QUALITY=max
echo VIDEOS=allow
echo VIDEOQUALITY=fhd
)> "%CONFIG%"
)

call :loadconfig

:download
cls
echo ==========================================
echo            TIDDL Downloader
echo ==========================================
echo.
echo Audio : %QUALITY%
echo Videos: %VIDEOS%
echo Video : %VIDEOQUALITY%
echo.

if not "%~1"=="" (
    set "url=%~1"
    shift
) else (
    set "url="
    set /p "url=Enlace de TIDAL (o exit): "
)

if /I "%url%"=="exit" exit
if not defined url goto download

cls
echo ==========================================
echo            TIDDL Downloader
echo ==========================================
echo.
echo Descargando:
echo %url%
echo.

"%TIDDL%" download -q %QUALITY% -vid %VIDEOS% -vq %VIDEOQUALITY% url "%url%"

echo.
echo Descarga finalizada. Pulsa una tecla para pegar otro enlace...
pause >nul

goto download


:loadconfig
for /f "tokens=1,2 delims==" %%A in (%CONFIG%) do (
    set %%A=%%B
)
exit /b