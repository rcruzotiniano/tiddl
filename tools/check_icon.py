"""Verify that the GUI window and the packaged EXE both use the new icon.

Run from a source checkout::

    python tools/check_icon.py

Run against a PyInstaller build (checks the icon resource embedded in the EXE
and the icon Tk registers on the frozen window)::

    python tools/check_icon.py dist\\tiddl.exe

The frozen run launches the EXE and reads the icon straight off its top-level
window with ``WM_GETICON``/``GCLP_HICON``, then closes it again.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICO = ROOT / "assets" / "tiddl.ico"
PNG = ROOT / "assets" / "tiddl-icon.png"
EVIDENCE = ROOT / "build" / "icon-check"

WM_GETICON = 0x007F
ICON_BIG = 1
GCLP_HICON = -14
GCLP_HICONSM = -34
EXPECTED_BACKGROUND = (245, 230, 253)  # lavender rounded square of the new mark


def _hwnd_icon_snapshot(hicon: int, out: Path) -> dict[str, object]:
    """Draw an HICON into a PNG and report stats (drawing beats GetDIBits here:
    a live window icon's bitmaps are often selected into a DC)."""
    from PIL import Image

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.c_void_p]
    user32.GetIconInfo.restype = wintypes.BOOL

    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", wintypes.BOOL),
            ("xHotspot", wintypes.DWORD),
            ("yHotspot", wintypes.DWORD),
            ("hbmMask", wintypes.HBITMAP),
            ("hbmColor", wintypes.HBITMAP),
        ]

    class BITMAP(ctypes.Structure):
        _fields_ = [
            ("bmType", wintypes.LONG),
            ("bmWidth", wintypes.LONG),
            ("bmHeight", wintypes.LONG),
            ("bmWidthBytes", wintypes.LONG),
            ("bmPlanes", wintypes.WORD),
            ("bmBitsPixel", wintypes.WORD),
            ("bmBits", ctypes.c_void_p),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    info = ICONINFO()
    if not user32.GetIconInfo(wintypes.HICON(hicon), ctypes.byref(info)):
        return {"error": f"GetIconInfo failed ({ctypes.get_last_error()})"}

    bmp = BITMAP()
    gdi32.GetObjectW(wintypes.HGDIOBJ(info.hbmColor), ctypes.sizeof(bmp), ctypes.byref(bmp))
    side = bmp.bmWidth or 32

    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = side
    header.biHeight = -side
    header.biPlanes = 1
    header.biBitCount = 32

    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    bits = ctypes.c_void_p()
    hbmp = gdi32.CreateDIBSection(hdc_mem, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
    old = gdi32.SelectObject(hdc_mem, hbmp)
    drawn = user32.DrawIconEx(hdc_mem, 0, 0, wintypes.HICON(hicon), side, side, 0, None, 0x0003)
    gdi32.SelectObject(hdc_mem, old)
    image = Image.frombuffer(
        "RGBA", (side, side), ctypes.string_at(bits, side * side * 4), "raw", "BGRA", side * 4, 1
    ).copy()

    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)
    if info.hbmColor:
        gdi32.DeleteObject(wintypes.HGDIOBJ(info.hbmColor))
    if info.hbmMask:
        gdi32.DeleteObject(wintypes.HGDIOBJ(info.hbmMask))

    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    colors = image.convert("RGB").getcolors(maxcolors=1 << 24) or []
    colors.sort(reverse=True)
    return {
        "drawn": bool(drawn),
        "size": f"{side}x{side}",
        "distinct_colors": len(colors),
        "dominant": colors[0][1] if colors else None,
        "center": image.getpixel((side // 2, side // 2)),
        "saved": str(out.relative_to(ROOT)),
    }


def check_assets() -> bool:
    from PIL import Image

    ok = True
    for path in (ICO, PNG):
        print(f"asset {path.relative_to(ROOT)}: {path.stat().st_size} bytes sha256={hashlib.sha256(path.read_bytes()).hexdigest()[:16]}")
    with Image.open(ICO) as ico:
        sizes = sorted(ico.info.get("sizes", []))
    print(f"  ico layers: {', '.join(f'{w}x{h}' for w, h in sizes)}")
    for needed in ((256, 256), (48, 48), (32, 32), (16, 16)):
        if needed not in sizes:
            print(f"  MISSING required layer {needed[0]}x{needed[1]}")
            ok = False
    return ok


def _find_tk_window(
    pid: int | None,
    exe: Path | None,
    timeout: float,
    process: subprocess.Popen | None = None,
) -> int | None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    deadline = time.time() + timeout
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return None  # the app died instead of showing a window
        found: list[int] = []

        def _visit(hwnd, _lparam):
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value != "TkTopLevel":
                return True
            if pid is not None and owner.value != pid:
                return True
            if exe is not None:
                handle = kernel32.OpenProcess(0x1000, False, owner.value)
                if not handle:
                    return True
                try:
                    size = wintypes.DWORD(32768)
                    buf = ctypes.create_unicode_buffer(size.value)
                    if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                        return True
                    if buf.value.lower() != str(exe).lower():
                        return True
                finally:
                    kernel32.CloseHandle(handle)
            found.append(int(hwnd))
            return True

        user32.EnumWindows(EnumProc(_visit), 0)
        if found:
            return found[0]
        time.sleep(0.5)
    return None


def _report_window_icon(hwnd: int, out: Path) -> bool:
    user32 = ctypes.windll.user32
    user32.GetClassLongPtrW.restype = ctypes.c_ssize_t
    user32.SendMessageW.restype = ctypes.c_ssize_t

    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(wintypes.HWND(hwnd), title, 512)
    class_icon = user32.GetClassLongPtrW(wintypes.HWND(hwnd), GCLP_HICON)
    class_icon_sm = user32.GetClassLongPtrW(wintypes.HWND(hwnd), GCLP_HICONSM)
    big = user32.SendMessageW(wintypes.HWND(hwnd), WM_GETICON, wintypes.WPARAM(ICON_BIG), 0)
    print(f"window: hwnd={hwnd} title={title.value!r} WM_GETICON={big} class={class_icon}/{class_icon_sm}")

    handle = big or class_icon or class_icon_sm
    if not handle:
        print("  FAIL: window has no icon handle (iconbitmap likely raised TclError)")
        return False
    stats = _hwnd_icon_snapshot(int(handle), out)
    print(f"  icon: {stats}")
    dominant = stats.get("dominant")
    ok = int(stats.get("distinct_colors", 0)) > 3
    if not ok:
        print(f"  FAIL: window icon is blank ({stats})")
    if dominant and tuple(dominant) != EXPECTED_BACKGROUND:
        print(f"  WARN: dominant colour {dominant} is not the expected {EXPECTED_BACKGROUND}")
    return ok


def check_source_window() -> bool:
    """Open the Tk window in-process and read its icon back."""
    sys.path.insert(0, str(ROOT))
    from tiddl.gui import ICON_FILENAME, TiddlGUI, asset_path

    icon = asset_path(ICON_FILENAME)
    print(f"source run: icon={icon} exists={icon.exists()}")
    app = TiddlGUI()
    try:
        app.root.update()
        hwnd = _find_tk_window(os.getpid(), None, 10)
        if hwnd is None:
            print("  FAIL: no TkTopLevel window for this process")
            return False
        return _report_window_icon(hwnd, EVIDENCE / "from-source-window.png")
    finally:
        app.root.destroy()


def check_exe(exe: Path) -> bool:
    if not exe.exists():
        print(f"FAIL: {exe} not found; build it first")
        return False

    from PIL import Image

    # 1. The icon resource Windows (and therefore Explorer/taskbar) reads.
    extractor = EVIDENCE / "extract_icon.ps1"
    extractor.parent.mkdir(parents=True, exist_ok=True)
    extractor.write_text(
        "Add-Type -AssemblyName System.Drawing; Add-Type -TypeDefinition @'\n"
        "using System; using System.Runtime.InteropServices;\n"
        "public static class SI {\n"
        "  [DllImport(\"shell32.dll\", CharSet=CharSet.Unicode)] public static extern int ExtractIconEx(string f, int i, IntPtr[] l, IntPtr[] s, int n);\n"
        "  [DllImport(\"user32.dll\")] public static extern bool DestroyIcon(IntPtr h); }\n"
        "'@; $l = New-Object IntPtr[] 1; $s = New-Object IntPtr[] 1; "
        "[void][SI]::ExtractIconEx($args[0], 0, $l, $s, 1); "
        "$i = [System.Drawing.Icon]::FromHandle($l[0]); $b = $i.ToBitmap(); "
        "$b.Save($args[1], [System.Drawing.Imaging.ImageFormat]::Png); "
        "Write-Output \"$($b.Width)x$($b.Height)\"; "
        "[void][SI]::DestroyIcon($l[0])",
        encoding="utf-8",
    )
    out_png = EVIDENCE / "exe-resource-large.png"
    shell = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    proc = subprocess.run(
        [str(shell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(extractor), str(exe), str(out_png)],
        capture_output=True,
        text=True,
    )
    print(f"exe resource: {proc.stdout.strip() or proc.stderr.strip()}")
    if not out_png.exists():
        print("  FAIL: could not extract the EXE icon resource")
        return False
    with Image.open(out_png) as res:
        colors = res.convert("RGB").getcolors(maxcolors=1 << 24) or []
        colors.sort(reverse=True)
        print(f"  dominant={colors[0][1] if colors else None} size={res.size} -> {out_png.relative_to(ROOT)}")

    # 2. The icon the frozen window actually shows.
    env = dict(os.environ, TIDDL_PATH=str(EVIDENCE / "app-path"))
    Path(env["TIDDL_PATH"]).mkdir(parents=True, exist_ok=True)
    log_path = EVIDENCE / "frozen-run.log"
    log = log_path.open("wb")
    process = subprocess.Popen([str(exe)], env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
    try:
        # onefile spawns a child that owns the window, so match on the EXE path
        # rather than on the bootstrap parent's pid.
        hwnd = _find_tk_window(None, exe, 90)
        if hwnd is None:
            print(f"  FAIL: frozen window did not appear (see {log_path.relative_to(ROOT)})")
            return False
        return _report_window_icon(hwnd, EVIDENCE / "from-exe-window.png")
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()
        subprocess.run(["taskkill", "/IM", exe.name, "/F"], capture_output=True)


def main() -> int:
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    print(f"repo: {ROOT}")
    ok = check_source_window() if target is None else check_exe(target)
    ok = check_assets() and ok
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
