"""Botão "Apoiar ♥" (regra 16): dados oficiais e o Pix "copia e cola" (BR Code estático).

Os dados vêm de Jarvis\\02-projetos\\extensoes\\apoio.md e não mudam sem o André. O código Pix é
montado aqui, sem internet: nenhuma chamada de rede, nenhum dado de quem doa.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SPONSORS = "https://github.com/sponsors/DredsGG"
CHAVE = "fa525dad-afca-4683-845d-eee7225a53e3"   # chave aleatória
NOME = "Andre Miller Fleck"                       # sem acento, até 25
CIDADE = "Sao Paulo"                              # sem acento, até 15
VALORES = (5, 10, 25)
MINIMO, MAXIMO = Decimal("1"), Decimal("10000")


def _campo(id_: str, valor: str) -> str:
    return f"{id_}{len(valor):02d}{valor}"


def crc16(texto: str) -> str:
    """CRC16-CCITT-FALSE (poly 0x1021, início 0xFFFF), 4 dígitos hexadecimais maiúsculos."""
    crc = 0xFFFF
    for b in texto.encode("utf-8"):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def br_code(valor: Decimal | int | None = None) -> str:
    """Pix copia e cola. valor None = livre (a pessoa digita no banco)."""
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", CHAVE)
    partes = [_campo("00", "01"), _campo("26", conta), _campo("52", "0000"), _campo("53", "986")]
    if valor is not None:
        v = Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        partes.append(_campo("54", f"{v:.2f}"))
    partes += [_campo("58", "BR"), _campo("59", NOME), _campo("60", CIDADE), _campo("62", _campo("05", "***"))]
    sem_crc = "".join(partes) + "6304"
    return sem_crc + crc16(sem_crc)


def ler_valor(texto: str):
    """"Outro valor": aceita vírgula ou ponto ("12,50", "R$ 12,5", "1.000,00").
    Devolve Decimal (R$ 1 a R$ 10.000), None se vazio (livre) ou levanta ValueError."""
    s = (texto or "").strip().replace("R$", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        v = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError(texto)
    if not (MINIMO <= v <= MAXIMO):
        raise ValueError(texto)
    return v


def reais(valor) -> str:
    """R$ 10 / R$ 12,50 (para mostrar)."""
    v = Decimal(valor)
    if v == v.to_integral():
        return f"R$ {int(v)}"
    return "R$ " + f"{v:.2f}".replace(".", ",")


def qr_png(texto: str, tamanho: int = 232) -> bytes:
    """PNG do QR (correção de erro M, fundo branco com borda branca de 4 módulos), com módulos de
    tamanho inteiro (nítido) e o maior que caiba em `tamanho` pixels."""
    import io
    import segno
    q = segno.make(texto, error="m", boost_error=False, micro=False)
    escala = max(1, tamanho // q.symbol_size(scale=1, border=4)[0])
    buf = io.BytesIO()
    q.save(buf, kind="png", scale=escala, border=4, dark="#000000", light="#ffffff")
    return buf.getvalue()
