"""Rotação da foto HEIC em grade (é assim que o iPhone grava).

O mpv 0.42 monta a grade de blocos, mas não aplica o `irot` dela: a foto tirada em pé
apareceria deitada. Foto HEIC sem grade ele gira sozinho, então aqui só a grade conta.
Lê apenas o cabeçalho do contêiner (ISO/IEC 23008-12) e nunca falha: na dúvida, devolve 0.
"""

from __future__ import annotations

import struct

EXTENSOES = {".heic", ".heif"}
_LIMITE_META = 8 * 1024 * 1024


def _caixas(dados: bytes, ini: int, fim: int):
    while ini + 8 <= fim:
        tam, tipo = struct.unpack_from(">I4s", dados, ini)
        cab = 8
        if tam == 1:
            tam = struct.unpack_from(">Q", dados, ini + 8)[0]
            cab = 16
        elif tam == 0:
            tam = fim - ini
        if tam < cab or ini + tam > fim:
            return
        yield tipo, ini + cab, ini + tam
        ini += tam


def _ler_meta(f) -> bytes | None:
    """Os bytes da caixa meta, que fica no nível de cima do arquivo."""
    pos = 0
    for _ in range(64):
        f.seek(pos)
        cab = f.read(16)
        if len(cab) < 8:
            return None
        tam, tipo = struct.unpack_from(">I4s", cab, 0)
        ini = 8
        if tam == 1:
            tam = struct.unpack_from(">Q", cab, 8)[0]
            ini = 16
        if tipo == b"meta":
            if tam == 0 or tam > _LIMITE_META:
                return None
            f.seek(pos + ini)
            return f.read(tam - ini)
        if tam < ini:
            return None
        pos += tam
    return None


def _tipo_do_item(dados: bytes, ini: int, fim: int, alvo: int) -> bytes | None:
    versao = dados[ini]
    pos = ini + 4 + (2 if versao == 0 else 4)
    for tipo, a, _b in _caixas(dados, pos, fim):
        if tipo != b"infe":
            continue
        v = dados[a]
        if v < 2:
            continue
        if v == 2:
            item = struct.unpack_from(">H", dados, a + 4)[0]
            salto = a + 8
        else:
            item = struct.unpack_from(">I", dados, a + 4)[0]
            salto = a + 10
        if item == alvo:
            return dados[salto:salto + 4]
    return None


def _propriedades_do_item(dados: bytes, ini: int, fim: int, alvo: int) -> list[int]:
    """Índices (a partir de 1) das propriedades ligadas ao item, conforme a caixa ipma."""
    versao, flags = dados[ini], int.from_bytes(dados[ini + 1:ini + 4], "big")
    n = struct.unpack_from(">I", dados, ini + 4)[0]
    pos = ini + 8
    achou: list[int] = []
    for _ in range(n):
        if versao < 1:
            item = struct.unpack_from(">H", dados, pos)[0]
            pos += 2
        else:
            item = struct.unpack_from(">I", dados, pos)[0]
            pos += 4
        qtd = dados[pos]
        pos += 1
        for _k in range(qtd):
            if flags & 1:
                idx = struct.unpack_from(">H", dados, pos)[0] & 0x7FFF
                pos += 2
            else:
                idx = dados[pos] & 0x7F
                pos += 1
            if item == alvo:
                achou.append(idx)
    return achou


def filtro_de_giro(caminho: str) -> str:
    """O filtro de vídeo que põe a grade em pé, ou "" se não precisa.
    Tem que ser filtro: o video-rotate do mpv não chega na grade já montada."""
    return {90: "lavfi=[transpose=clock]", 180: "lavfi=[hflip,vflip]",
            270: "lavfi=[transpose=cclock]"}.get(giro_da_grade(caminho), "")


def giro_da_grade(caminho: str) -> int:
    """Graus no sentido horário que a foto em grade precisa girar (0, 90, 180 ou 270)."""
    try:
        with open(caminho, "rb") as f:
            meta = _ler_meta(f)
        if not meta:
            return 0
        primario = iinf = iprp = None
        for tipo, a, b in _caixas(meta, 4, len(meta)):
            if tipo == b"pitm":
                if meta[a] == 0:
                    primario = struct.unpack_from(">H", meta, a + 4)[0]
                else:
                    primario = struct.unpack_from(">I", meta, a + 4)[0]
            elif tipo == b"iinf":
                iinf = (a, b)
            elif tipo == b"iprp":
                iprp = (a, b)
        if primario is None or not iinf or not iprp:
            return 0
        if _tipo_do_item(meta, iinf[0], iinf[1], primario) != b"grid":
            return 0
        props: list[tuple[bytes, int]] = []
        ipma = None
        for tipo, a, b in _caixas(meta, iprp[0], iprp[1]):
            if tipo == b"ipco":
                props = [(t, x) for t, x, _y in _caixas(meta, a, b)]
            elif tipo == b"ipma":
                ipma = (a, b)
        if not ipma:
            return 0
        for idx in _propriedades_do_item(meta, ipma[0], ipma[1], primario):
            if 1 <= idx <= len(props) and props[idx - 1][0] == b"irot":
                return (360 - (meta[props[idx - 1][1]] & 3) * 90) % 360  # irot é anti-horário
        return 0
    except (OSError, struct.error, IndexError, ValueError):
        return 0
