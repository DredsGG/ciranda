"""Relatar bug (igual aos outros projetos do André, adaptado para app):
monta o relato com um diagnóstico SEM dados pessoais e abre a página de novo relato
(Issue) do GitHub já preenchida. Nada é enviado sozinho: a pessoa confere e envia lá.

Os nomes de pastas e arquivos são pessoais (as pastas do André têm nome de gente),
então todo caminho vira <pasta>\\…\\<arquivo>.ext: fica só a extensão.
"""

from __future__ import annotations

import getpass
import os
import platform
import re
import urllib.parse

from . import VERSAO
from .textos import t

REPO = "DredsGG/ciranda"
NOVO = f"https://github.com/{REPO}/issues/new"
LIMITE_URL = 7500  # GitHub dá erro 414 acima de ~8180 caracteres (medido no Midas)

# caminhos do Windows (C:\..., \\servidor\...) e do Linux/mac (/home/..., /Users/..., /tmp/...)
_WIN = re.compile(r'(?:[A-Za-z]:|\\\\[^\\\s"\'<>|]+)\\[^"\'<>|\r\n\t]*')
_UNIX = re.compile(r'(?<![\w.])/(?:home|Users|tmp|mnt|media|run|var|root|private)/[^"\'<>|\r\n\t]*')


_CONHECIDAS = None


def _exts():
    global _CONHECIDAS
    if _CONHECIDAS is None:
        from .biblioteca import FOTOS, VIDEOS
        _CONHECIDAS = {e.lstrip(".") for e in FOTOS | VIDEOS} | {"py", "pyd", "dll", "exe", "txt", "log", "json"}
    return _CONHECIDAS


def _troca_caminho(m: re.Match) -> str:
    txt = m.group(0)
    # o caminho pode ter espaços: termina na 1ª extensão conhecida seguida de fim/espaço/pontuação
    fim = None
    for e in re.finditer(r"\.([A-Za-z0-9]{1,5})(?=$|[\s,;:)\]])", txt):
        if e.group(1).lower() in _exts():
            fim = e
            break
    if fim is None:
        corpo = txt.rstrip(" .,;:)]")
        return "<pasta>" + txt[len(corpo):]
    caminho, resto, ext = txt[:fim.end()], txt[fim.end():], fim.group(1).lower()
    nome = re.split(r"[\\/]", caminho)[-1]
    # traceback: File "C:\...\ciranda\janela.py", line 12 → <app>\janela.py (arquivo do próprio app)
    if ext in ("py", "pyd", "dll", "exe") and re.fullmatch(r"[\w.-]+", nome):
        return f"<app>\\{nome}{resto}"
    return f"<pasta>\\…\\<arquivo>.{ext}{resto}"


def limpar_texto(texto: str) -> str:
    """Tira caminhos, nome do usuário e nome do PC. Mantém extensões e números."""
    if not texto:
        return ""
    t = _WIN.sub(_troca_caminho, texto)
    t = _UNIX.sub(_troca_caminho, t)
    for segredo, troca in ((_usuario(), "<usuario>"), (platform.node(), "<pc>")):
        if segredo and len(segredo) >= 3:
            t = re.sub(re.escape(segredo), troca, t, flags=re.IGNORECASE)
    return t


def _usuario() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME", "")


def _ultimas_linhas(caminho: str, n: int) -> list[str]:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return []


def _ultimo_erro(caminho: str) -> str:
    """Último bloco do erro.txt (o traceback mais recente)."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError:
        return ""
    blocos = txt.split("\n===== ")
    ultimo = blocos[-1].strip()
    if len(blocos) > 1:
        ultimo = "===== " + ultimo
    return "\n".join(ultimo.splitlines()[-40:])


def diagnostico(info: dict, pasta_dados: str, linhas_log: int = 60) -> str:
    """Texto do diagnóstico. `info` vem da janela (estado do player, sem nomes)."""
    linhas = [
        f"Ciranda: v{VERSAO} ({t('diag_instalado') if info.get('instalado') else t('diag_codigo')})",
        f"{t('diag_sistema')}: {platform.platform()}",
    ]
    for chave, rotulo in (("qt", "Qt"), ("mpv", "mpv"), ("telas", t("diag_telas")),
                          ("fila", t("diag_fila")), ("modos", t("diag_modos")), ("atual", t("diag_atual"))):
        if info.get(chave):
            linhas.append(f"{rotulo}: {info[chave]}")
    erro = _ultimo_erro(os.path.join(pasta_dados, "erro.txt"))
    log = _ultimas_linhas(os.path.join(pasta_dados, "ciranda.log"), linhas_log)
    corpo = "\n".join(linhas)
    if erro:
        corpo += "\n\n" + t("diag_ultimo_erro") + "\n" + erro
    if log:
        corpo += "\n\n" + t("diag_fim_log") + "\n" + "\n".join(log)
    return limpar_texto(corpo)


def montar(oque: str, diag: str) -> tuple[str, str]:
    """Devolve (título, corpo em Markdown)."""
    oque = (oque or "").strip()
    primeira = limpar_texto(oque.splitlines()[0] if oque else "")
    titulo = f"[Bug] {primeira[:70]}" if primeira else f"[Bug] Ciranda v{VERSAO}"
    corpo = t("bug_o_que") + "\n" + (limpar_texto(oque) or t("bug_nao_escrito"))
    if diag:
        corpo += "\n\n" + t("bug_diag") + "\n```\n" + diag + "\n```"
    corpo += "\n\n" + t("bug_enviado", versao=VERSAO)
    return titulo, corpo


def url_github(titulo: str, corpo: str, limite: int = LIMITE_URL) -> tuple[str, bool]:
    """Endereço do novo relato. Se ficar grande demais, corta o começo do log
    (o mais antigo) até caber e devolve cortado=True (o completo vai no Copiar)."""
    def url(c):
        return NOVO + "?" + urllib.parse.urlencode({"title": titulo, "body": c},
                                                    quote_via=urllib.parse.quote)
    u = url(corpo)
    if len(u) <= limite:
        return u, False
    marca = t("diag_fim_log") + "\n"
    if marca in corpo:
        antes, depois = corpo.split(marca, 1)
        log, _, fim = depois.partition("\n```")
        linhas = log.splitlines()
        while linhas:
            linhas.pop(0)
            c = antes + marca + t("log_cortado") + "\n" \
                + "\n".join(linhas) + "\n```" + fim
            u = url(c)
            if len(u) <= limite:
                return u, True
    # ainda grande (erro enorme): manda só o texto e pede para colar o resto
    c = corpo.split(t("bug_diag"), 1)[0] + t("bug_diag") + "\n" + t("diag_grande")
    return url(c)[:limite], True
