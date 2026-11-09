"""Monta a pasta de mídia dos testes de janela (16 itens: 7 vídeos, um deles corrompido, e 9 fotos).
Precisa do ffmpeg com libx264, libx265, libvpx e libsvtav1 no PATH.
    python testes/gerar_midia.py <pasta>
A pasta extra `codecs` traz H.264, HEVC 10 bits e AV1 para conferir a aceleração de hardware.
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gerar_heic  # noqa: E402


def _ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def _video(destino: str, *codec, tamanho="640x360", segundos="6"):
    _ff("-f", "lavfi", "-i", f"testsrc2=s={tamanho}:r=30:d={segundos}", "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={segundos}", *codec, "-shortest", destino)


def _foto(destino: str, cor: str, *extra):
    _ff("-f", "lavfi", "-i", f"color=c={cor}:s=800x600:d=1", "-frames:v", "1", "-update", "1", *extra, destino)


def _exif_deitado(origem: str, destino: str):
    """Insere um EXIF com Orientation=6 (girar 90 graus no sentido horário) num JPEG."""
    tiff = b"II*\0\x08\0\0\0\x01\0\x12\x01\x03\0\x01\0\0\0\x06\0\0\0\0\0\0\0"
    app1 = b"Exif\0\0" + tiff
    dados = open(origem, "rb").read()
    with open(destino, "wb") as f:
        f.write(dados[:2] + b"\xFF\xE1" + struct.pack(">H", len(app1) + 2) + app1 + dados[2:])


def gerar(pasta: str):
    praia, dia1, aniv, oculta = (os.path.join(pasta, "2024 Praia"), os.path.join(pasta, "2024 Praia", "Dia 1"),
                                 os.path.join(pasta, "Aniversário"), os.path.join(pasta, ".oculta"))
    for d in (dia1, aniv, oculta):
        os.makedirs(d, exist_ok=True)
    h264 = ("-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac")
    _video(os.path.join(pasta, "abertura.mp4"), *h264)
    _video(os.path.join(pasta, "clipe.mov"), *h264)
    _video(os.path.join(pasta, "clipe.mkv"), *h264)
    _video(os.path.join(pasta, "clipe.avi"), "-c:v", "mpeg4", "-c:a", "mp3")
    _video(os.path.join(pasta, "clipe.webm"), "-c:v", "libvpx-vp9", "-b:v", "400k", "-c:a", "libopus")
    _video(os.path.join(oculta, "nao-deve-aparecer.mp4"), *h264)
    with open(os.path.join(pasta, "corrompido.mp4"), "wb") as f:
        f.write(b"isto nao e um video " * 500)
    _foto(os.path.join(pasta, "capa.jpg"), "steelblue")
    _exif_deitado(os.path.join(pasta, "capa.jpg"), os.path.join(pasta, "celular-deitado.jpg"))
    gerar_heic.simples(os.path.join(pasta, "iphone.heic"), 1200, 900)
    _foto(os.path.join(praia, "praia geral.png"), "orange")
    _foto(os.path.join(dia1, "foto2.jpg"), "gold")
    _foto(os.path.join(dia1, "foto10.jpg"), "teal")
    _ff("-f", "lavfi", "-i", "testsrc2=s=320x240:r=5:d=1", os.path.join(aniv, "anim.gif"))
    _foto(os.path.join(aniv, "foto.bmp"), "seagreen")
    _foto(os.path.join(aniv, "foto.webp"), "purple")


def gerar_codecs(pasta: str):
    os.makedirs(pasta, exist_ok=True)
    grande = {"tamanho": "1920x1080", "segundos": "8"}
    _video(os.path.join(pasta, "h264.mp4"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", **grande)
    _video(os.path.join(pasta, "hevc10.mkv"), "-c:v", "libx265", "-pix_fmt", "yuv420p10le", "-x265-params",
           "log-level=error", "-c:a", "aac", **grande)
    _video(os.path.join(pasta, "av1.mkv"), "-c:v", "libsvtav1", "-preset", "10", "-pix_fmt", "yuv420p", "-c:a",
           "libopus", **grande)


if __name__ == "__main__":
    gerar(sys.argv[1])
    if not os.path.isdir(sys.argv[1] + "-codecs"):
        gerar_codecs(sys.argv[1] + "-codecs")
    print("mídia de teste gerada em", sys.argv[1])
