# IMPORTANTE — instalación y compilación

Esta guía permite preparar el proyecto desde un clon limpio en Windows.

## Requisitos

- Python 3.13 o superior (instalable desde [python.org](https://www.python.org/downloads/)).
- `ffmpeg` instalado y disponible en el `PATH`. Se usa para convertir y finalizar los archivos de audio.
- Una cuenta de TIDAL con acceso al contenido que se desea descargar.

## Instalar desde un clon nuevo

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
git clone <URL-DEL-REPOSITORIO> tiddl
cd tiddl
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Si PowerShell impide activar el entorno virtual, ejecútalo solo para la ventana actual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

## Abrir la interfaz

Con el entorno virtual activo:

```powershell
python -m tiddl gui
```

Inicia sesión desde la ventana, selecciona la calidad y pega un enlace de **álbum** de TIDAL. Las preferencias y la sesión se guardan en `C:\Users\<usuario>\.tiddl`.

## Generar el ejecutable de Windows

Instala PyInstaller una vez dentro del entorno virtual:

```powershell
python -m pip install pyinstaller
```

Después de cualquier cambio en el código, recompila con:

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name tiddl --icon assets\tiddl.ico --add-data "assets\tiddl.ico;assets" --hidden-import tiddl.cli.app tiddl\gui.py
```

El resultado queda en `dist\tiddl.exe`. Ábrelo con doble clic; no requiere que el entorno virtual esté activado. Windows puede mostrar una advertencia de SmartScreen porque el ejecutable no está firmado.

## Verificación opcional

```powershell
python -m pytest -q
```
