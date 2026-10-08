"""Small desktop interface for the focused album-download workflow."""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import webbrowser
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tkinter import StringVar, TclError, Tk, messagebox, ttk

# ``python tiddl/gui.py`` is convenient during development.  Add the project
# root in that case; normal package/module execution does not need this.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tiddl.cli.config import APP_PATH, CONFIG
from tiddl.cli.utils.auth.core import AuthData, load_auth_data, save_auth_data
from tiddl.cli.utils.resource import TidalResource
from tiddl.core.auth import AuthAPI, AuthClientError


SETTINGS_FILE = APP_PATH / "gui-settings.json"
PROGRESS_FILE = APP_PATH / "gui-progress.json"
ICON_FILENAME = "tiddl.ico"
QUALITIES = {
    "Básica · 96 kbps": "low",
    "Alta · 320 kbps": "normal",
    "Lossless · FLAC 16-bit": "high",
    "Máxima · HiRes FLAC": "max",
}


def asset_path(filename: str) -> Path:
    """Locate bundled assets in both source and PyInstaller builds."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / "assets" / filename


class TiddlGUI:
    """Native UI which keeps the CLI as the single download implementation."""

    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("tiddl")
        try:
            self.root.iconbitmap(str(asset_path(ICON_FILENAME)))
        except TclError:
            pass
        self.root.geometry("780x520")
        self.root.minsize(680, 450)
        self.root.configure(bg="#101114")
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False
        self.quality = StringVar(value=self._saved_quality_label())
        self.album_url = StringVar()
        self.status = StringVar(value="Listo para descargar")
        self.now_playing = StringVar(value="")
        self.progress_text = StringVar(value="")
        self.account = StringVar()
        self._configure_style()
        self._build()
        self._refresh_account()
        self.root.after(100, self._process_events)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#101114")
        style.configure("Card.TFrame", background="#1b1d22")
        style.configure("Title.TLabel", background="#101114", foreground="#f5f7fb", font=("Segoe UI", 24, "bold"))
        style.configure("Sub.TLabel", background="#101114", foreground="#a8adb9", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#1b1d22", foreground="#f5f7fb", font=("Segoe UI", 14, "bold"))
        style.configure("Card.TLabel", background="#1b1d22", foreground="#b8bec9", font=("Segoe UI", 10))
        style.configure("Primary.TButton", background="#13c8a3", foreground="#07120f", font=("Segoe UI", 10, "bold"), padding=(18, 10))
        style.map("Primary.TButton", background=[("active", "#24d9b4"), ("disabled", "#52635f")])
        style.configure("Muted.TButton", background="#2a2e36", foreground="#f1f4f8", padding=(14, 8))
        style.map("Muted.TButton", background=[("active", "#363c46")])
        style.configure("TEntry", fieldbackground="#292d35", foreground="#f5f7fb", insertcolor="#f5f7fb", padding=10)
        style.configure("TCombobox", fieldbackground="#292d35", background="#292d35", foreground="#f5f7fb", padding=8)
        style.configure("Gui.Horizontal.TProgressbar", background="#13c8a3", troughcolor="#292d35", bordercolor="#292d35", lightcolor="#13c8a3", darkcolor="#13c8a3")

    def _build(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame", padding=32)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="tiddl", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Descargas de álbumes de TIDAL, sencillas y en tu equipo.", style="Sub.TLabel").pack(anchor="w", pady=(0, 22))

        content = ttk.Frame(outer, style="App.TFrame")
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        download = ttk.Frame(content, style="Card.TFrame", padding=24)
        download.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ttk.Label(download, text="Descargar música", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(download, text="Pega un enlace de álbum o pista de TIDAL.", style="Card.TLabel").pack(anchor="w", pady=(5, 18))
        url_row = ttk.Frame(download, style="Card.TFrame")
        url_row.pack(fill="x")
        url_row.columnconfigure(0, weight=1)
        ttk.Entry(url_row, textvariable=self.album_url).grid(row=0, column=0, sticky="ew")
        ttk.Button(url_row, text="Pegar", style="Muted.TButton", command=self.paste_url).grid(row=0, column=1, padx=(8, 0))
        self.download_button = ttk.Button(download, text="Descargar", style="Primary.TButton", command=self.start_download)
        self.download_button.pack(anchor="w", pady=(18, 10))
        ttk.Label(download, textvariable=self.status, style="Card.TLabel", wraplength=390).pack(anchor="w", pady=(8, 0))
        ttk.Label(download, textvariable=self.now_playing, style="CardTitle.TLabel", wraplength=600).pack(anchor="w", pady=(16, 0))
        self.progress = ttk.Progressbar(
            download,
            style="Gui.Horizontal.TProgressbar",
            mode="determinate",
            maximum=1,
            value=0,
        )
        self.progress.pack(fill="x", pady=(16, 4))
        ttk.Label(download, textvariable=self.progress_text, style="Card.TLabel").pack(anchor="w")

        side = ttk.Frame(content, style="App.TFrame")
        side.grid(row=0, column=1, sticky="nsew")
        settings = ttk.Frame(side, style="Card.TFrame", padding=20)
        settings.pack(fill="x")
        ttk.Label(settings, text="Configuración", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(settings, text="Calidad de audio", style="Card.TLabel").pack(anchor="w", pady=(14, 5))
        picker = ttk.Combobox(settings, state="readonly", values=list(QUALITIES), textvariable=self.quality)
        picker.pack(fill="x")
        picker.bind("<<ComboboxSelected>>", lambda _: self._save_settings())
        ttk.Label(settings, text="La calidad se aplica a las próximas descargas.", style="Card.TLabel", wraplength=230).pack(anchor="w", pady=(10, 0))

        account = ttk.Frame(side, style="Card.TFrame", padding=20)
        account.pack(fill="x", pady=(12, 0))
        ttk.Label(account, text="Cuenta", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(account, textvariable=self.account, style="Card.TLabel", wraplength=230).pack(anchor="w", pady=(8, 14))
        self.login_button = ttk.Button(account, text="Iniciar sesión", style="Primary.TButton", command=self.start_login)
        self.login_button.pack(anchor="w")
        self.logout_button = ttk.Button(account, text="Cerrar sesión", style="Muted.TButton", command=self.logout)
        self.logout_button.pack(anchor="w", pady=(8, 0))

    def _saved_quality_label(self) -> str:
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            value = saved.get("track_quality")
            return next(label for label, key in QUALITIES.items() if key == value)
        except (OSError, ValueError, StopIteration):
            return next(label for label, key in QUALITIES.items() if key == CONFIG.download.track_quality)

    def _save_settings(self) -> None:
        SETTINGS_FILE.write_text(json.dumps({"track_quality": QUALITIES[self.quality.get()]}), encoding="utf-8")
        self.status.set("Calidad guardada")

    def _refresh_account(self) -> None:
        auth = load_auth_data()
        logged_in = bool(auth.token)
        self.account.set("Sesión activa en TIDAL" if logged_in else "No has iniciado sesión")
        self.login_button.configure(state="disabled" if logged_in else "normal")
        self.logout_button.configure(state="normal" if logged_in else "disabled")

    def paste_url(self) -> None:
        try:
            self.album_url.set(self.root.clipboard_get().strip())
        except TclError:
            self.status.set("El portapapeles no contiene texto")

    def start_download(self) -> None:
        try:
            resource = TidalResource.from_string(self.album_url.get().strip())
            if resource.type not in ("album", "track"):
                raise ValueError("Solo se admiten enlaces de álbum o pista de TIDAL.")
        except ValueError as exc:
            messagebox.showerror("Enlace no válido", str(exc))
            return
        if not load_auth_data().token:
            messagebox.showinfo("Inicia sesión", "Inicia sesión en TIDAL antes de descargar.")
            return
        self._save_settings()
        self.running = True
        self.download_button.configure(state="disabled")
        self.progress.configure(maximum=1, value=0)
        self.now_playing.set("")
        self.progress_text.set("Preparando descarga...")
        try:
            PROGRESS_FILE.unlink()
        except FileNotFoundError:
            pass
        self.status.set("Preparando descarga…")
        threading.Thread(target=self._run_download, args=(resource.url,), daemon=True).start()

    def _run_download(self, url: str) -> None:
        download_args = ["download", "--track-quality", QUALITIES[self.quality.get()], "url", url]
        output = StringIO()
        previous_progress_file = os.environ.get("TIDDL_GUI_PROGRESS_FILE")
        try:
            os.environ["TIDDL_GUI_PROGRESS_FILE"] = str(PROGRESS_FILE)
            from tiddl.cli.app import app

            # Running the CLI application in this worker thread avoids a
            # second Windows process (and its brief black console window).
            with redirect_stdout(output), redirect_stderr(output):
                app(args=download_args, prog_name="tiddl", standalone_mode=False)
            self.events.put(("complete", "Álbum descargado correctamente."))
        except SystemExit as exc:
            if exc.code not in (None, 0):
                self.events.put(("error", output.getvalue().strip() or "La descarga no pudo iniciarse."))
            else:
                self.events.put(("complete", "Álbum descargado correctamente."))
        except Exception as exc:
            details = output.getvalue().strip()
            self.events.put(("error", details or f"No se pudo descargar: {exc}"))
        finally:
            if previous_progress_file is None:
                os.environ.pop("TIDDL_GUI_PROGRESS_FILE", None)
            else:
                os.environ["TIDDL_GUI_PROGRESS_FILE"] = previous_progress_file

    def start_login(self) -> None:
        self.login_button.configure(state="disabled")
        self.account.set("Abriendo TIDAL para iniciar sesión…")
        threading.Thread(target=self._run_login, daemon=True).start()

    def _run_login(self) -> None:
        try:
            api = AuthAPI()
            device = api.get_device_auth()
            webbrowser.open(f"https://{device.verificationUriComplete}")
            deadline = time.time() + device.expiresIn
            while time.time() < deadline:
                time.sleep(device.interval)
                try:
                    response = api.get_auth(device.deviceCode)
                except AuthClientError as exc:
                    if exc.error == "authorization_pending":
                        continue
                    if exc.error == "expired_token":
                        self.events.put(("error", "El tiempo para iniciar sesión expiró."))
                        return
                    raise
                save_auth_data(AuthData(token=response.access_token, refresh_token=response.refresh_token, expires_at=response.expires_in + int(time.time()), user_id=str(response.user_id), country_code=response.user.countryCode))
                self.events.put(("login", "Sesión iniciada correctamente."))
                return
            self.events.put(("error", "El tiempo para iniciar sesión expiró."))
        except Exception as exc:
            self.events.put(("error", f"No se pudo iniciar sesión: {exc}"))

    def logout(self) -> None:
        auth = load_auth_data()
        try:
            if auth.token:
                AuthAPI().logout_token(auth.token)
        except Exception:
            # The local token must still be removable when the remote session is unavailable.
            pass
        save_auth_data(AuthData())
        self._refresh_account()
        self.status.set("Sesión cerrada")

    def _process_events(self) -> None:
        self._read_progress()
        try:
            while True:
                kind, message = self.events.get_nowait()
                if kind == "complete":
                    self.status.set(message)
                    self.progress.configure(value=self.progress.cget("maximum"))
                    self.progress_text.set("Completado")
                elif kind == "login":
                    self._refresh_account()
                    self.status.set(message)
                else:
                    self.status.set("Ocurrió un problema")
                    messagebox.showerror("tiddl", message[-1500:])
                    self._refresh_account()
                self.running = False
                self.download_button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._process_events)

    def _read_progress(self) -> None:
        if not self.running:
            return
        try:
            data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            total = max(float(data["total"]), 1)
            completed = min(float(data["completed"]), total)
        except (FileNotFoundError, ValueError, KeyError, OSError):
            return

        self.progress.configure(maximum=total, value=completed)
        self.progress_text.set(f"{int(completed)} de {int(total)} pistas completadas")
        artist = data.get("artist", "")
        title = data.get("title", "")
        if title:
            self.now_playing.set(f"{artist} — {title}" if artist else title)

    def run(self) -> None:
        self.root.mainloop()


def run_gui() -> None:
    """Launch the desktop app. Kept separate to make importing it safe in tests."""
    TiddlGUI().run()


if __name__ == "__main__":
    if getattr(sys, "frozen", False) and len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from tiddl.cli.app import app

        sys.argv = [sys.argv[0], *sys.argv[2:]]
        app()
    else:
        run_gui()
