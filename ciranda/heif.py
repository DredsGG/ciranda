"""Rotação e espelho da foto HEIC em grade (é assim que o iPhone grava).

O mpv 0.42 monta a grade de blocos, mas não aplica `irot` nem `imir` dela: a foto tirada em pé
apareceria deitada. Foto HEIC sem grade ele gira sozinho, então aqui só a grade conta.
Lê apenas o cabeçalho do contêiner (ISO/IEC 23008-12) e nunca falha: na dúvida, não muda nada.
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
            if tam <= ini or tam > _LIMITE_META:
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


_GIRO = {1: "transpose=cclock", 2: "hflip,vflip", 3: "transpose=clock"}  # irot: 90 graus anti-horários x valor
_ESPELHO = {0: "vflip", 1: "hflip"}  # imir, conferido contra o libheif


def filtro_de_giro(caminho: str) -> str:
    """O filtro de vídeo que põe a grade em pé (giro e espelho, na ordem do arquivo), ou "" se não precisa.
    Tem que ser filtro: o video-rotate do mpv não chega na grade já montada."""
    partes = _transformacoes_da_grade(caminho)
    return f"lavfi=[{','.join(partes)}]" if partes else ""


def _transformacoes_da_grade(caminho: str) -> list[str]:
    try:
        with open(caminho, "rb") as f:
            meta = _ler_meta(f)
        if not meta:
            return []
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
            return []
        if _tipo_do_item(meta, iinf[0], iinf[1], primario) != b"grid":
            return []
        props: list[tuple[bytes, int]] = []
        ipma = None
        for tipo, a, b in _caixas(meta, iprp[0], iprp[1]):
            if tipo == b"ipco":
                props = [(t, x) for t, x, _y in _caixas(meta, a, b)]
            elif tipo == b"ipma":
                ipma = (a, b)
        if not ipma:
            return []
        partes = []
        for idx in _propriedades_do_item(meta, ipma[0], ipma[1], primario):
            if not 1 <= idx <= len(props):
                continue
            tipo, pos = props[idx - 1]
            if tipo == b"irot" and meta[pos] & 3:
                partes.append(_GIRO[meta[pos] & 3])
            elif tipo == b"imir":
                partes.append(_ESPELHO[meta[pos] & 1])
        return partes
    except (OSError, struct.error, IndexError, ValueError):
        return []
