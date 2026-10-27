"""Atualização sozinha (igual aos outros projetos do André, adaptado para app):

- procura versão nova nos Releases do GitHub (ao abrir, a cada 6 h e no botão
  "Procurar atualização");
- mostra o que mudou e os botões Atualizar / Depois;
- Atualizar: baixa o Ciranda-Setup-X.Y.Z.exe do Release, confere o SHA-256 com o que o
  GitHub informa (`digest`) e roda o instalador em silêncio; o app fecha, o instalador
  troca os arquivos e reabre o Ciranda já na versão nova.
Sem conta, sem token, sem mandar nada do usuário: é só uma leitura pública do GitHub.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request

REPO = "DredsGG/ciranda"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA = f"https://github.com/{REPO}/releases/latest"
BASE_DOWNLOAD = f"https://github.com/{REPO}/releases/download/"


def versao_tupla(v: str) -> tuple:
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", (v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def mais_nova(remota: str, local: str) -> bool:
    return versao_tupla(remota) > versao_tupla(local)


def instalado() -> bool:
    """True no app que veio do instalador (PyInstaller); False rodando pelo código/zip."""
    return bool(getattr(sys, "frozen", False))


def itens_das_notas(corpo: str, maximo: int = 6) -> list[str]:
    """Tira o bloco de instalação que o workflow põe no topo e devolve até `maximo` itens."""
    linhas = (corpo or "").replace("\r", "").split("\n")
    if linhas and linhas[0].startswith("### Install"):
        for i, l in enumerate(linhas):
            if l.startswith("Portable alternative"):
                linhas = linhas[i + 1:]
                break
    itens = []
    for l in linhas:
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        l = re.sub(r"^[-*+]\s+|^\d+\.\s+", "", l)
        l = re.sub(r"\*\*(.+?)\*\*", r"\1", l).replace("`", "")
        itens.append(l if len(l) <= 160 else l[:157] + "…")
        if len(itens) >= maximo:
            break
    return itens


def _contexto_ssl():
    # No Windows o Python usa os certificados do próprio Windows (mesmos do navegador).
    return ssl.create_default_context()


def _abrir(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Ciranda-atualizador",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout, context=_contexto_ssl())


def procurar(versao_local: str, api: str = API) -> dict:
    """Consulta o último Release. Devolve um dicionário com o que a tela precisa."""
    with _abrir(api) as r:
        d = json.loads(r.read().decode("utf-8"))
    tag = d.get("tag_name", "")
    remota = tag.lstrip("v")
    setup = None
    for a in d.get("assets", []):
        if re.fullmatch(r"Ciranda-Setup-\d+\.\d+\.\d+\.exe", a.get("name", "")):
            setup = {"nome": a["name"], "url": a.get("browser_download_url", ""),
                     "tamanho": a.get("size", 0), "digest": a.get("digest") or ""}
    return {
        "versao": remota,
        "disponivel": mais_nova(remota, versao_local),
        "notas": itens_das_notas(d.get("body", "")),
        "pagina": d.get("html_url") or PAGINA,
        "setup": setup,
    }


def pasta_downloads() -> str:
    return os.path.join(tempfile.gettempdir(), "Ciranda-atualizacao")


def apagar_downloads():
    import shutil
    shutil.rmtree(pasta_downloads(), ignore_errors=True)


def baixar_setup(setup: dict, progresso=None, cancelado=lambda: False) -> str:
    """Baixa o instalador para a pasta temporária e confere o SHA-256. Devolve o caminho."""
    url = setup["url"]
    if not url.startswith(BASE_DOWNLOAD):
        raise ValueError("endereço do instalador fora do repositório do Ciranda")
    esperado = setup.get("digest", "")
    if not esperado.startswith("sha256:"):
        raise ValueError("o GitHub não informou o SHA-256 do instalador")
    destino = os.path.join(pasta_downloads(), setup["nome"])
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    h = hashlib.sha256()
    feito = 0
    with _abrir(url, timeout=60) as r, open(destino + ".part", "wb") as f:
        total = int(r.headers.get("Content-Length") or setup.get("tamanho") or 0)
        while True:
            if cancelado():
                raise InterruptedError("download cancelado")
            bloco = r.read(256 * 1024)
            if not bloco:
                break
            f.write(bloco)
            h.update(bloco)
            feito += len(bloco)
            if progresso:
                progresso(feito, total)
    if h.hexdigest() != esperado.split(":", 1)[1].lower():
        os.remove(destino + ".part")
        raise ValueError("o instalador baixado não confere com o SHA-256 do GitHub")
    os.replace(destino + ".part", destino)
    return destino


def rodar_instalador(caminho: str, versao_atual: str):
    """Roda o instalador em silêncio e reabre o Ciranda no fim (o app deve sair logo depois).
    /RELANCAR=1 faz o instalador abrir o Ciranda no fim (seção [Run] do ciranda.iss)."""
    args = [caminho, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
            "/RELANCAR=1", f"/DE={versao_atual}"]
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if instalado():
            # o PyInstaller muda a busca de DLL deste processo para a pasta _internal;
            # o instalador (e o Ciranda novo que ele abre) não pode herdar isso
            try:
                import ctypes
                ctypes.windll.kernel32.SetDllDirectoryW(None)
            except Exception:
                pass
    # o Ciranda novo, aberto pelo instalador, tem que começar do zero (não como "filho" deste)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("_PYI_", "_MEIPASS"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(args, close_fds=True, creationflags=flags, env=env)
