"""Atualização sozinha (igual aos outros projetos do André, adaptado para app):

- procura versão nova nos Releases do GitHub (ao abrir, a cada 6 h e no botão
  "Procurar atualização");
- mostra o que mudou e os botões Atualizar / Depois;
- Atualizar: baixa o Ciranda-Setup-X.Y.Z.exe do Release, confere o SHA-256 com o que o
  GitHub informa (`digest`) e roda o instalador em silêncio; o app fecha, o instalador
  troca os arquivos e reabre o Ciranda já na versão nova.
Sem conta, sem token, sem mandar nada do usuário: é só uma leitura pública do GitHub.

Canal de teste (só no PC do André): se existir %APPDATA%\\Ciranda\\pasta-de-teste.txt com o
caminho de uma pasta, o Ciranda instalado também olha essa pasta. Um Ciranda-Setup-X.Y.Z.exe
mais novo do que o instalado aparece na mesma faixa, com o mesmo Atualizar agora. No PC de
quem baixou do GitHub esse arquivo não existe e nada muda.
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

from .textos import t

REPO = "DredsGG/ciranda"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA = f"https://github.com/{REPO}/releases/latest"
BASE_DOWNLOAD = f"https://github.com/{REPO}/releases/download/"
# arquivo de novidades (PT/EN/ES) da versão publicada, lido da tag do Release
RAW_NOVIDADES = f"https://raw.githubusercontent.com/{REPO}/{{tag}}/ciranda/novidades.json"
ARQ_NOVIDADES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "novidades.json")


def novidades_locais() -> dict:
    """Changelog que vem dentro do app: {"1.3.0": {"pt": [...], "en": [...], "es": [...]}}."""
    try:
        with open(ARQ_NOVIDADES, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def notas_no_idioma(info: dict, idioma: str) -> list:
    """Notas da versão no idioma da interface; sem tradução, as notas do Release."""
    nov = info.get("novidades") or {}
    itens = nov.get(idioma) or nov.get("en")
    return list(itens) if itens else list(info.get("notas") or [])


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


def procurar(versao_local: str, api: str = API, raw: str = RAW_NOVIDADES) -> dict:
    """Consulta o último Release. Devolve um dicionário com o que a tela precisa."""
    with _abrir(api) as r:
        d = json.loads(r.read().decode("utf-8"))
    tag = d.get("tag_name", "")
    remota = tag.lstrip("v")
    novidades = None
    if mais_nova(remota, versao_local):
        try:  # novidades nos três idiomas (versões publicadas a partir da 1.3.0)
            with _abrir(raw.format(tag=tag), timeout=10) as r:
                novidades = (json.loads(r.read().decode("utf-8")) or {}).get(remota)
        except Exception:
            novidades = None
    setup = None
    for a in d.get("assets", []):
        if re.fullmatch(r"Ciranda-Setup-\d+\.\d+\.\d+\.exe", a.get("name", "")):
            setup = {"nome": a["name"], "url": a.get("browser_download_url", ""),
                     "tamanho": a.get("size", 0), "digest": a.get("digest") or ""}
    return {
        "versao": remota,
        "disponivel": mais_nova(remota, versao_local),
        "notas": itens_das_notas(d.get("body", "")),
        "novidades": novidades if isinstance(novidades, dict) else None,
        # Release com "URGENTE" no título (o André marca para bug grave): quadro sem X, player pausado
        "urgente": "URGENTE" in (d.get("name") or "").upper(),
        "pagina": d.get("html_url") or PAGINA,
        "setup": setup,
    }


def pasta_downloads() -> str:
    return os.path.join(tempfile.gettempdir(), "Ciranda-atualizacao")


def apagar_downloads():
    import shutil
    shutil.rmtree(pasta_downloads(), ignore_errors=True)


# ---------- canal de teste (pasta local) ----------
ARQ_PASTA_TESTE = "pasta-de-teste.txt"
_NOME_SETUP = re.compile(r"Ciranda-Setup-(\d+\.\d+\.\d+)\.exe", re.IGNORECASE)


def pasta_teste(pasta_dados: str) -> str:
    """Pasta do canal de teste, ou "" se não houver (o normal)."""
    try:
        with open(os.path.join(pasta_dados, ARQ_PASTA_TESTE), encoding="utf-8-sig") as f:
            p = f.readline().strip().strip('"')
    except OSError:
        return ""
    return p if p and os.path.isdir(p) else ""


def instalado_em() -> float:
    """Quando o Ciranda foi instalado pela última vez (o instalador regrava o unins000.dat)."""
    try:
        return os.path.getmtime(os.path.join(os.path.dirname(sys.executable), "unins000.dat"))
    except OSError:
        return 0.0


def procurar_local(pasta: str, versao_local: str, quando_instalou: float | None = None) -> dict | None:
    """Setup mais novo da pasta de teste. Versão maior = disponível; mesma versão = disponível
    só se o arquivo é mais novo que a última instalação (uma versão de teste refeita)."""
    melhor = None
    try:
        nomes = os.listdir(pasta)
    except OSError:
        return None
    for nome in nomes:
        m = _NOME_SETUP.fullmatch(nome)
        caminho = os.path.join(pasta, nome)
        if not m or not os.path.isfile(caminho):
            continue
        chave = (versao_tupla(m.group(1)), os.path.getmtime(caminho))
        if melhor is None or chave > melhor[0]:
            melhor = (chave, m.group(1), nome, caminho)
    if melhor is None:
        return None
    (_, mtime), versao, nome, caminho = melhor
    if quando_instalou is None:
        quando_instalou = instalado_em()
    disponivel = mais_nova(versao, versao_local) or (
        versao_tupla(versao) == versao_tupla(versao_local) and mtime > quando_instalou + 60)
    notas = []
    try:
        with open(caminho[:-4] + ".txt", encoding="utf-8-sig") as f:
            notas = itens_das_notas(f.read())
    except OSError:
        pass
    # versão de teste: as novidades dela vêm do novidades.json gravado ao lado, se houver
    novidades = None
    try:
        with open(os.path.join(pasta, "novidades.json"), encoding="utf-8") as f:
            novidades = (json.load(f) or {}).get(versao)
    except (OSError, ValueError):
        pass
    return {
        "versao": versao,
        "disponivel": disponivel,
        "notas": notas or [t("notas_teste")],
        "novidades": novidades if isinstance(novidades, dict) else None,
        "pagina": "",
        "local": True,
        "setup": {"nome": nome, "caminho": caminho, "tamanho": os.path.getsize(caminho), "local": True},
    }


def copiar_setup_local(setup: dict, progresso=None, cancelado=lambda: False) -> str:
    """Copia o setup da pasta de teste para a pasta temporária (o original fica na pasta).
    Se houver <setup>.sha256 ao lado, confere."""
    origem = setup["caminho"]
    destino = os.path.join(pasta_downloads(), setup["nome"])
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    h = hashlib.sha256()
    total = os.path.getsize(origem)
    feito = 0
    with open(origem, "rb") as r, open(destino + ".part", "wb") as f:
        while True:
            if cancelado():
                raise InterruptedError("cópia cancelada")
            bloco = r.read(1024 * 1024)
            if not bloco:
                break
            f.write(bloco)
            h.update(bloco)
            feito += len(bloco)
            if progresso:
                progresso(feito, total)
    try:
        with open(origem + ".sha256", encoding="utf-8") as f:
            esperado = f.read().split()[0].lower()
    except (OSError, IndexError):
        esperado = ""
    if feito != total or (esperado and h.hexdigest() != esperado):
        os.remove(destino + ".part")
        raise ValueError(t("erro_local"))
    os.replace(destino + ".part", destino)
    return destino


def baixar_setup(setup: dict, progresso=None, cancelado=lambda: False) -> str:
    """Baixa o instalador para a pasta temporária e confere o SHA-256. Devolve o caminho."""
    url = setup["url"]
    if not url.startswith(BASE_DOWNLOAD):
        raise ValueError(t("erro_endereco"))
    esperado = setup.get("digest", "")
    if not esperado.startswith("sha256:"):
        raise ValueError(t("erro_sem_sha"))
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
        raise ValueError(t("erro_sha"))
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
