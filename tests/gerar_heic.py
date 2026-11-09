"""Gera arquivos HEIC de teste montando o contêiner à mão, do jeito que o iPhone grava:
grade de blocos 512x512 com a descrição em idat, blocos escondidos e rotação (irot).

Precisa só do ffmpeg com libx265 no PATH, usado para codificar os blocos. Isto é ferramenta
de teste: nada daqui entra no pacote da Ciranda.
    python testes/gerar_heic.py <pasta>
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys


def _box(tipo: bytes, *partes: bytes) -> bytes:
    corpo = b"".join(partes)
    return struct.pack(">I", 8 + len(corpo)) + tipo + corpo


def _fullbox(tipo: bytes, versao: int, flags: int, *partes: bytes) -> bytes:
    return _box(tipo, struct.pack(">I", (versao << 24) | flags), *partes)


def _fonte(largura: int, altura: int) -> str:
    return f"testsrc2=s={largura}x{altura}:r=1,format=rgb24"


_PARA_YUV = ",scale=in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p"


def _nals(bruto: bytes) -> list[bytes]:
    """Separa um fluxo Annex B nas suas unidades NAL."""
    pos, inicios = 0, []
    while True:
        k = bruto.find(b"\0\0\1", pos)
        if k < 0:
            break
        inicios.append(k + 3)
        pos = k + 3
    return [bruto[a:(inicios[i + 1] - 3 if i + 1 < len(inicios) else len(bruto))].rstrip(b"\0")
            for i, a in enumerate(inicios)]


def _hvcc(vps: bytes, sps: bytes, pps: bytes) -> bytes:
    rbsp, zeros = bytearray(), 0
    for b in sps[2:40]:
        if zeros >= 2 and b == 3:  # byte de prevenção do HEVC: não faz parte do dado
            zeros = 0
            continue
        rbsp.append(b)
        zeros = zeros + 1 if b == 0 else 0
    ptl = bytes(rbsp[1:13])  # profile_tier_level geral
    cfg = bytes([1]) + ptl + b"\xF0\x00\xFC\xFD\xF8\xF8\0\0\x0F\x03"
    for tipo, nal in ((32, vps), (33, sps), (34, pps)):
        cfg += bytes([0x80 | tipo]) + struct.pack(">HH", 1, len(nal)) + nal
    return _box(b"hvcC", cfg)


def _codificar(filtro: str, quadros: int) -> tuple[bytes, list[bytes]]:
    """Codifica quadros só-intra; devolve (hvcC, um bloco de amostra por quadro)."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", filtro, "-frames:v", str(quadros), "-an",
         "-c:v", "libx265", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
         "-x265-params", "keyint=1:min-keyint=1:bframes=0:log-level=error:info=0:"
                         "colorprim=bt709:transfer=bt709:colormatrix=bt709:range=limited",
         "-f", "hevc", "-"], capture_output=True, check=True)
    vps = sps = pps = None
    blocos: list[bytes] = []
    for nal in _nals(r.stdout):
        tipo = (nal[0] >> 1) & 0x3F
        if tipo == 32:
            vps = nal
        elif tipo == 33:
            sps = nal
        elif tipo == 34:
            pps = nal
        elif tipo <= 21:
            blocos.append(struct.pack(">I", len(nal)) + nal)
    if len(blocos) != quadros or not (vps and sps and pps):
        raise RuntimeError(f"esperava {quadros} quadros, vieram {len(blocos)}")
    return _hvcc(vps, sps, pps), blocos


def _montar(hvcc: bytes, blocos: list[bytes], ispe_bloco: tuple[int, int], primario_grade: dict | None,
            irot: int | None) -> bytes:
    ftyp = _box(b"ftyp", b"heic", struct.pack(">I", 0), b"mif1", b"heic")
    mdat_corpo = b"".join(blocos)
    idat = b""
    if primario_grade:
        idat = struct.pack(">BBBBHH", 0, 0, primario_grade["linhas"] - 1, primario_grade["colunas"] - 1,
                           primario_grade["largura"], primario_grade["altura"])
    n = len(blocos)
    id_prim = 1 if not primario_grade else n + 1
    ispe = lambda w, h: _fullbox(b"ispe", 0, 0, struct.pack(">II", w, h))  # noqa: E731

    def meta(inicio_mdat: int) -> bytes:
        itens = [_fullbox(b"infe", 2, 1 if primario_grade else 0,
                          struct.pack(">HH", i + 1, 0), b"hvc1", b"\0") for i in range(n)]
        if primario_grade:
            itens.append(_fullbox(b"infe", 2, 0, struct.pack(">HH", id_prim, 0), b"grid", b"\0"))
        iinf = _fullbox(b"iinf", 0, 0, struct.pack(">H", len(itens)), *itens)
        locs = []
        pos = inicio_mdat
        for i, b in enumerate(blocos):
            locs.append(struct.pack(">HHHHII", i + 1, 0, 0, 1, pos, len(b)))
            pos += len(b)
        if primario_grade:
            locs.append(struct.pack(">HHHHII", id_prim, 1, 0, 1, 0, len(idat)))
        iloc = _fullbox(b"iloc", 1, 0, b"\x44\x00", struct.pack(">H", len(locs)), *locs)
        partes = [_fullbox(b"hdlr", 0, 0, b"\0\0\0\0pict", b"\0" * 12, b"\0"),
                  _fullbox(b"pitm", 0, 0, struct.pack(">H", id_prim)), iloc, iinf]
        if primario_grade:
            partes.append(_fullbox(b"iref", 0, 0, _box(b"dimg", struct.pack(">HH", id_prim, n),
                                                       *[struct.pack(">H", i + 1) for i in range(n)])))
        props = [hvcc, ispe(*ispe_bloco)]
        assoc = []
        if primario_grade:
            props.append(ispe(primario_grade["largura"], primario_grade["altura"]))
            do_prim = [3]
            for i in range(n):
                assoc.append(struct.pack(">HB", i + 1, 2) + bytes([0x81, 0x02]))
        else:
            do_prim = [0x81, 2]
        if irot is not None:
            props.append(_box(b"irot", bytes([irot & 3])))
            do_prim.append(0x80 | len(props))
        assoc.append(struct.pack(">HB", id_prim, len(do_prim)) + bytes(do_prim))
        ipma = _fullbox(b"ipma", 0, 0, struct.pack(">I", len(assoc)), *assoc)
        partes.append(_box(b"iprp", _box(b"ipco", *props), ipma))
        if idat:
            partes.append(_box(b"idat", idat))
        return _fullbox(b"meta", 0, 0, *partes)

    tam_meta = len(meta(0))
    return ftyp + meta(len(ftyp) + tam_meta + 8) + _box(b"mdat", mdat_corpo)


def simples(destino: str, largura: int, altura: int, irot: int | None = None):
    hvcc, blocos = _codificar(_fonte(largura, altura) + _PARA_YUV, 1)
    with open(destino, "wb") as f:
        f.write(_montar(hvcc, blocos, (largura, altura), None, irot))


def grade(destino: str, colunas: int, linhas: int, largura: int, altura: int, irot: int | None = None,
          bloco: int = 512):
    """Grade colunas x linhas de blocos quadrados. largura/altura são o tamanho final (o iPhone corta a sobra)."""
    filtro = (f"{_fonte(colunas * bloco, linhas * bloco)},trim=end_frame=1,loop=loop={colunas * linhas - 1}:size=1,"
              f"crop={bloco}:{bloco}:x='mod(n,{colunas})*{bloco}':y='floor(n/{colunas})*{bloco}'{_PARA_YUV}")
    hvcc, blocos = _codificar(filtro, colunas * linhas)
    with open(destino, "wb") as f:
        f.write(_montar(hvcc, blocos, (bloco, bloco),
                        {"linhas": linhas, "colunas": colunas, "largura": largura, "altura": altura}, irot))


def referencia(destino: str, largura_total: int, altura_total: int, largura: int, altura: int):
    """PNG do que a foto deve mostrar (antes de girar)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"{_fonte(largura_total, altura_total)},crop={largura}:{altura}:0:0",
                    "-frames:v", "1", "-update", "1", destino], check=True)


# nome: função, argumentos, (largura, altura) como aparece na tela, giro horário em graus, tamanho da fonte
CASOS = {
    "simples-1200x900.heic": (simples, (1200, 900), (1200, 900), 0, (1200, 900)),
    "grade-48-4032x3024.heic": (grade, (8, 6, 4032, 3024), (4032, 3024), 0, (4096, 3072)),
    "grade-2-1024x512.heic": (grade, (2, 1, 1024, 512), (1024, 512), 0, (1024, 512)),
    "giro-simples-640x480.heic": (simples, (640, 480, 3), (480, 640), 90, (640, 480)),
    "giro-grade-48-4032x3024.heic": (grade, (8, 6, 4032, 3024, 3), (3024, 4032), 90, (4096, 3072)),
}


def gerar(pasta: str) -> dict:
    os.makedirs(pasta, exist_ok=True)
    for nome, caso in CASOS.items():
        fn, args = caso[0], caso[1]
        fn(os.path.join(pasta, nome), *args)
    return CASOS


if __name__ == "__main__":
    gerar(sys.argv[1])
    print("HEIC de teste gerados em", sys.argv[1])
