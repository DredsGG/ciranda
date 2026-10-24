"""Gera instalador/versao.txt (informações de versão do Ciranda.exe) a partir de VERSAO.
Assim a versão nunca é escrita à mão: vem de ciranda/__init__.py (regra 9)."""
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
texto = open(os.path.join(RAIZ, "ciranda", "__init__.py"), encoding="utf-8").read()
versao = re.search(r'VERSAO = "(\d+)\.(\d+)\.(\d+)"', texto)
a, b, c = (int(x) for x in versao.groups())
v = f"{a}.{b}.{c}"
conteudo = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({a}, {b}, {c}, 0), prodvers=({a}, {b}, {c}, 0),
                    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', 'Dreds'),
      StringStruct('FileDescription', 'Ciranda - player de fotos e videos'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'Ciranda'),
      StringStruct('LegalCopyright', 'feito por Dreds - github.com/DredsGG'),
      StringStruct('OriginalFilename', 'Ciranda.exe'),
      StringStruct('ProductName', 'Ciranda'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
"""
with open(os.path.join(RAIZ, "instalador", "versao.txt"), "w", encoding="utf-8") as f:
    f.write(conteudo)
print(v)
