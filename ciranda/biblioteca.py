"""Varredura de pastas: acha todas as fotos e vídeos de uma pasta e de todas as
subpastas, em qualquer profundidade, e devolve uma lista achatada.

Ordem "natural" (a mesma do Explorer para nomes como foto2 < foto10): em cada
pasta, primeiro os arquivos dela, depois cada subpasta em ordem de nome.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field

FOTOS = {
    ".jpg", ".jpeg", ".jfif", ".jpe", ".png", ".gif", ".webp", ".bmp", ".dib",
    ".tif", ".tiff", ".heic", ".heif", ".avif", ".jxl", ".tga", ".ico", ".apng", ".mpo",
}
VIDEOS = {
    ".mp4", ".m4v", ".mov", ".qt", ".mkv", ".webm", ".avi", ".wmv", ".asf",
    ".flv", ".f4v", ".mpg", ".mpeg", ".mpe", ".m2v", ".ts", ".mts", ".m2ts",
    ".vob", ".3gp", ".3g2", ".ogv", ".divx", ".xvid", ".rm", ".rmvb", ".mxf",
    ".dv", ".y4m", ".hevc", ".h264", ".264", ".265", ".mod", ".tod",
    ".mp4v", ".ogm", ".wtv", ".dvr-ms", ".m2t", ".trp", ".nsv", ".amv",
}
# Pastas de sistema e de lixeira que nunca têm mídia do usuário.
PASTAS_IGNORADAS = {
    "$recycle.bin", "system volume information", "recycler", "$windows.~bt",
    "$windows.~ws", "windows.old", "__pycache__", "node_modules", ".git",
    ".thumbnails", ".trash", ".trashes", ".spotlight-v100", ".fseventsd",
}
FOTOS_ANIMADAS = {".gif"}  # tratadas como foto, mas animando em loop
HEIC = {".heic", ".heif"}


@dataclass(slots=True)
class Item:
    caminho: str          # caminho absoluto do arquivo
    tipo: str             # "foto" ou "video"
    raiz: str             # pasta que o usuário abriu
    pasta_rel: str        # subpasta relativa à raiz ("" = a própria raiz)
    nome: str             # nome do arquivo
    ext: str = field(default="")
    falhou: bool = field(default=False)  # o motor não conseguiu abrir

    @property
    def animada(self) -> bool:
        return self.ext in FOTOS_ANIMADAS

    @property
    def heic(self) -> bool:
        return self.ext in HEIC


def tipo_do_arquivo(nome: str) -> str | None:
    ext = os.path.splitext(nome)[1].lower()
    if ext in FOTOS:
        return "foto"
    if ext in VIDEOS:
        return "video"
    return None


_NUM = re.compile(r"(\d+)")


def chave_natural(texto: str):
    """foto2 vem antes de foto10; ignora maiúsculas e acentos comuns no começo."""
    partes = _NUM.split(texto.casefold())
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in partes]


def _eh_link(e: os.DirEntry) -> bool:
    try:
        if e.is_symlink():
            return True
        junc = getattr(e, "is_junction", None)  # Python 3.12+
        return bool(junc and junc())
    except OSError:
        return False


def varrer(raiz: str, cancelado=lambda: False, progresso=None, stats: dict | None = None) -> list[Item]:
    """Varre `raiz` recursivamente, sem limite de quantidade nem de profundidade.
    `cancelado()` interrompe; `progresso(n, pasta)` é chamado de tempos em tempos;
    `stats` (opcional) recebe o que foi lido e o que ficou de fora, para o log."""
    if stats is None:
        stats = {}
    stats.setdefault("pastas_lidas", 0)
    stats.setdefault("ignorados", Counter())
    stats.setdefault("sem_acesso", [])
    stats.setdefault("puladas", [])
    raiz = os.path.abspath(raiz)
    if os.path.isfile(raiz):
        tipo = tipo_do_arquivo(raiz)
        nome = os.path.basename(raiz)
        if not tipo:
            stats["ignorados"][os.path.splitext(nome)[1].lower() or "(sem extensão)"] += 1
            return []
        return [Item(raiz, tipo, os.path.dirname(raiz), "", nome, os.path.splitext(nome)[1].lower())]

    achados: list[Item] = []
    # Só atalhos/junções podem fazer laço; pasta comum nunca. Guarda o destino real deles.
    links_vistos: set[str] = {os.path.normcase(os.path.realpath(raiz))}
    ultimo_aviso = [0]
    pilha = [raiz]  # sem recursão: aguenta qualquer profundidade

    while pilha:
        if cancelado():
            break
        pasta = pilha.pop()
        try:
            with os.scandir(pasta) as it:
                entradas = list(it)
        except OSError as erro:
            stats["sem_acesso"].append(f"{pasta} ({erro.__class__.__name__})")
            continue
        stats["pastas_lidas"] += 1

        arquivos, subpastas = [], []
        for e in entradas:
            try:
                if e.is_dir(follow_symlinks=True):
                    if e.name.casefold() in PASTAS_IGNORADAS:
                        stats["puladas"].append(e.path)
                        continue
                    if _eh_link(e):
                        destino = os.path.normcase(os.path.realpath(e.path))
                        if destino in links_vistos:
                            stats["puladas"].append(e.path + " (atalho repetido)")
                            continue
                        links_vistos.add(destino)
                    subpastas.append(e)
                elif e.is_file(follow_symlinks=True):
                    tipo = tipo_do_arquivo(e.name)
                    if tipo and not e.name.startswith("._"):
                        arquivos.append((e, tipo))
                    else:
                        ext = os.path.splitext(e.name)[1].lower() or "(sem extensão)"
                        stats["ignorados"][ext] += 1
            except OSError:
                stats["sem_acesso"].append(e.path)
                continue

        rel = os.path.relpath(pasta, raiz)
        rel = "" if rel == "." else rel
        for e, tipo in sorted(arquivos, key=lambda x: chave_natural(x[0].name)):
            achados.append(Item(e.path, tipo, raiz, rel, e.name,
                                os.path.splitext(e.name)[1].lower()))
        if progresso and len(achados) - ultimo_aviso[0] >= 200:
            ultimo_aviso[0] = len(achados)
            progresso(len(achados), rel)
        # pilha: empilha ao contrário para sair na ordem natural (A antes de B)
        for e in sorted(subpastas, key=lambda x: chave_natural(x.name), reverse=True):
            pilha.append(e.path)

    if progresso:
        progresso(len(achados), "")
    return achados


def varrer_varios(caminhos, cancelado=lambda: False, progresso=None, stats: dict | None = None) -> list[Item]:
    """Varre várias pastas/arquivos e junta tudo, sem repetir o mesmo arquivo."""
    vistos: set[str] = set()
    total: list[Item] = []
    for c in caminhos:
        if cancelado():
            break
        base = len(total)

        def prog(n, pasta, _base=base):
            if progresso:
                progresso(_base + n, pasta)

        for item in varrer(c, cancelado, prog, stats):
            chave = os.path.normcase(item.caminho)
            if chave not in vistos:
                vistos.add(chave)
                total.append(item)
    return total
