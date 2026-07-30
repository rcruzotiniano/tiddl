@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set TIDDL=.venv\Scripts\tiddl.exe
set CONFIG=settings.ini
set LASTLOG=%TEMP%\tiddl_last.log

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

if exist "%LASTLOG%" (
    set TOTAL=
    for /f "tokens=3" %%A in ('findstr /C:"Total downloads:" "%LASTLOG%"') do set TOTAL=%%A

    echo ---------- Ultima descarga ----------
    if defined TOTAL (
        echo Descargados: !TOTAL!/!TOTAL! archivos ^
u2713
    ) else (
        echo Descarga finalizada.
    )
    echo -------------------------------------
    echo.
)

echo Pega un enlace de TIDAL o escribe un comando.
echo.
echo Comandos:
echo   login   - Iniciar sesion
echo   config  - Configuracion
echo   folder  - Abrir carpeta de descargas
echo   exit    - Salir
echo.

set /p "url=Enlace o comando: "

if /I "%url%"=="exit" exit
if /I "%url%"=="login" goto login
if /I "%url%"=="config" goto config
if /I "%url%"=="folder" goto folder

if exist "%LASTLOG%" del "%LASTLOG%"

echo.
echo Descargando...
echo.

%TIDDL% download -q %QUALITY% -vid %VIDEOS% -vq %VIDEOQUALITY% url "%url%" > "%LASTLOG%" 2>&1

goto download


:login
cls
echo Iniciando sesion...
echo.

%TIDDL% auth login

echo.
pause
goto download


:config
cls
echo =========================
echo      CONFIGURACION
echo =========================
echo.
echo Audio : %QUALITY%
echo Videos: %VIDEOS%
echo Video : %VIDEOQUALITY%
echo.
echo 1 - Calidad Audio
echo 2 - Videos
echo 3 - Calidad Video
echo 4 - Volver
echo.

set /p "c=Selecciona: "

if "%c%"=="1" goto audio
if "%c%"=="2" goto videos
if "%c%"=="3" goto videoquality
goto download


:audio
cls
echo Calidad Audio
echo.
echo 1 - max
echo 2 - high
echo 3 - normal
echo 4 - low
echo.

set /p "a=Selecciona: "

if "%a%"=="1" set QUALITY=max
if "%a%"=="2" set QUALITY=high
if "%a%"=="3" set QUALITY=normal
if "%a%"=="4" set QUALITY=low

goto save


:videos
cls
echo Videos
echo.
echo 1 - allow
echo 2 - none
echo 3 - only
echo.

set /p "v=Selecciona: "

if "%v%"=="1" set VIDEOS=allow
if "%v%"=="2" set VIDEOS=none
if "%v%"=="3" set VIDEOS=only

goto save


:videoquality
cls
echo Calidad Video
echo.
echo 1 - fhd
echo 2 - hd
echo 3 - sd
echo.

set /p "q=Selecciona: "

if "%q%"=="1" set VIDEOQUALITY=fhd
if "%q%"=="2" set VIDEOQUALITY=hd
if "%q%"=="3" set VIDEOQUALITY=sd

goto save


:save
(
echo QUALITY=%QUALITY%
echo VIDEOS=%VIDEOS%
echo VIDEOQUALITY=%VIDEOQUALITY%
)> "%CONFIG%"

echo.
echo Configuracion guardada.
timeout /t 1 >nul

goto download


:folder
explorer "%USERPROFILE%\Music\tiddl"
goto download


:loadconfig
for /f "tokens=1,2 delims==" %%A in (%CONFIG%) do (
    set %%A=%%B
)
exit /b