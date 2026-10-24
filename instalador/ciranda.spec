# PyInstaller: monta o Ciranda como pasta (modo "onedir"), com o motor dentro.
# Rodar da raiz do projeto:  pyinstaller instalador/ciranda.spec --noconfirm
# Saída: dist/Ciranda/Ciranda.exe (+ _internal/ com Python, Qt, libmpv e ícones).
import os
import sys
from PyInstaller.utils.hooks import collect_all

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))
WIN = sys.platform == "win32"

binarios = []
mpv_dll = os.path.join(RAIZ, "libmpv-2.dll")
if WIN:
    if not os.path.exists(mpv_dll):
        raise SystemExit("Falta libmpv-2.dll na raiz do projeto")
    binarios.append((mpv_dll, "."))

heif_dados, heif_bin, heif_ocultos = collect_all("pillow_heif")

a = Analysis(
    [os.path.join(RAIZ, "app.py")],
    pathex=[RAIZ],
    binaries=binarios + heif_bin,
    datas=[(os.path.join(RAIZ, "ui", "ciranda.ico"), "ui"),
           (os.path.join(RAIZ, "ui", "ciranda-256.png"), "ui")] + heif_dados,
    hiddenimports=["mpv", "ciranda.autoteste", "PySide6.QtTest", "PySide6.QtSvg"] + heif_ocultos,
    excludes=["tkinter", "unittest", "pydoc", "numpy", "PySide6.QtNetwork", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.QtOpenGL", "PySide6.QtDBus", "PySide6.QtPdf"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Ciranda",
    console=False,
    icon=os.path.join(RAIZ, "ui", "ciranda.ico"),
    version=os.path.join(RAIZ, "instalador", "versao.txt") if WIN else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Ciranda", upx=False)
