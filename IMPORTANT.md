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

## Cambiar el icono

El icono vive en dos archivos generados a partir de una única imagen cuadrada (PNG con transparencia):

- `assets\tiddl.ico`: se incrusta en el `.exe` (Explorer, barra de tareas, accesos directos, panel de control) y la ventana lo carga en la barra de título.
- `assets\tiddl-icon.png`: copia maestra de 512 px para documentación y futuras regeneraciones.

Para reemplazarlo, guarda la imagen nueva y regenera ambos archivos:

```powershell
python -m pip install pillow
python tools\build_icon.py ruta\a\icono-nuevo.png
```

Sin argumentos, `build_icon.py` reconstruye el `.ico` desde `assets\tiddl-icon.png`. El script recorta el margen transparente y genera las capas de 16 a 256 px que Windows necesita.

Para que el cambio llegue al ejecutable hay que **volver a compilar** (sección anterior) y, en ejecución desde el código fuente, basta con reiniciar `python -m tiddl gui`. Puedes comprobar que todo quedó bien con:

```powershell
python tools\check_icon.py            # ventana en modo código fuente
python tools\check_icon.py dist\tiddl.exe   # recurso del .exe y ventana del ejecutable
```

## Verificación opcional

```powershell
python -m pytest -q
```
