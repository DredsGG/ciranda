"""Preparo de fotos que o motor não mostra direito sozinho.

- HEIC/HEIF (foto de iPhone): convertida uma vez para JPEG num cache, com
  pillow-heif. O resultado fica guardado; a segunda vez abre na hora.
- Orientação EXIF (foto de celular "deitada"): o mpv já gira sozinho; o HEIC
  sai do conversor já em pé.
"""

from __future__ import annotations

import hashlib
import os

from .config import pasta_dados


def pasta_cache() -> str:
    p = os.path.join(pasta_dados(), "cache-heic")
    os.makedirs(p, exist_ok=True)
    return p


def heic_para_jpeg(caminho: str) -> str | None:
    """Converte HEIC/HEIF para JPEG no cache. Devolve o caminho do JPEG, ou None."""
    try:
        st = os.stat(caminho)
    except OSError:
        return None
    chave = hashlib.sha1(f"{caminho}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()
    destino = os.path.join(pasta_cache(), chave + ".jpg")
    if os.path.exists(destino):
        return destino
    try:
        from pillow_heif import register_heif_opener
        from PIL import Image, ImageOps
        register_heif_opener()
        with Image.open(caminho) as im:
            im = ImageOps.exif_transpose(im)  # já sai em pé
            im.convert("RGB").save(destino + ".tmp", "JPEG", quality=92)
        os.replace(destino + ".tmp", destino)
        return destino
    except Exception:
        try:
            os.remove(destino + ".tmp")
        except OSError:
            pass
        return None


def limpar_cache(limite_mb: int = 1024):
    """Apaga os JPEGs mais antigos do cache quando passa do limite."""
    try:
        arquivos = [os.path.join(pasta_cache(), n) for n in os.listdir(pasta_cache())]
        arquivos = [(os.path.getatime(a), os.path.getsize(a), a) for a in arquivos if a.endswith(".jpg")]
    except OSError:
        return
    total = sum(t for _, t, _ in arquivos)
    for _, tam, a in sorted(arquivos):
        if total <= limite_mb * 1024 * 1024:
            break
        try:
            os.remove(a)
            total -= tam
        except OSError:
            pass


def tem_cache() -> bool:
    try:
        return any(n.endswith(".jpg") for n in os.listdir(pasta_cache()))
    except OSError:
        return False


def apagar_cache():
    """Apaga todos os JPEGs convertidos (só o cache do Ciranda, nunca o original)."""
    pasta = pasta_cache()
    for n in os.listdir(pasta):
        if n.endswith((".jpg", ".tmp")):
            try:
                os.remove(os.path.join(pasta, n))
            except OSError:
                pass
