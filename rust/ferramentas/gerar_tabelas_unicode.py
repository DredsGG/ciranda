"""Gera rust/src/unicode_py.rs: as tabelas que a ordem natural da 1.5.1 usa sem dizer.

A 1.5.1 ordena com `re.split(r"(\\d+)", nome.casefold())` e `int(...)` (biblioteca.chave_natural).
Para a versão Rust dar exatamente a mesma ordem, as duas tabelas saem do próprio Python:
  - DOBRA: todo caractere em que `str.casefold()` muda alguma coisa (ß → ss, Σ → σ, ...);
  - DIGITOS: as faixas de caracteres que o `\\d` do `re` aceita, com o valor de cada um.
A 1.5.1 instalada roda o Python 3.12 (python312.dll), que usa o Unicode 15.0.0.

    python -I rust/ferramentas/gerar_tabelas_unicode.py rust/src/unicode_py.rs
"""
import re
import sys
import unicodedata

assert sys.version_info[:2] == (3, 12), "use o Python 3.12, o mesmo da 1.5.1"
saida = sys.argv[1]
d = re.compile(r"\d")

dobra = []
faixas = []
inicio = fim = None
for cp in range(0x110000):
    if 0xD800 <= cp <= 0xDFFF:
        continue
    c = chr(cp)
    f = c.casefold()
    if f != c:
        dobra.append((cp, f))
    if d.fullmatch(c):
        v = int(c)
        if inicio is None or v != cp - inicio:
            assert v == 0, f"faixa de dígitos que não começa no 0: U+{cp:04X}"
            if inicio is not None:
                faixas.append((inicio, fim))
            inicio = cp
        fim = cp
    elif inicio is not None:
        faixas.append((inicio, fim))
        inicio = None
if inicio is not None:
    faixas.append((inicio, fim))

# Nenhuma dobra cria ou apaga dígito: dá para dobrar antes de separar os números (como o Python faz).
for cp, f in dobra:
    assert bool(d.search(chr(cp))) == bool(d.search(f)), hex(cp)


def lit(s):
    return '"' + "".join(c if 0x20 <= ord(c) < 0x7F and c not in '"\\' else f"\\u{{{ord(c):x}}}" for c in s) + '"'


with open(saida, "w", encoding="utf-8", newline="\n") as o:
    o.write("//! Gerado por ferramentas/gerar_tabelas_unicode.py: não editar à mão.\n")
    o.write(f"//! Python {sys.version.split()[0]}, Unicode {unicodedata.unidata_version}.\n")
    o.write("//! Dados derivados do Unicode Character Database (licença Unicode-3.0).\n\n")
    o.write(f"pub const VERSAO_UNICODE: &str = \"{unicodedata.unidata_version}\";\n\n")
    o.write("/// `str.casefold()` do Python para os caracteres que mudam, em ordem de código.\n")
    o.write(f"pub static DOBRA: [(u32, &str); {len(dobra)}] = [\n")
    for cp, f in dobra:
        o.write(f"    (0x{cp:X}, {lit(f)}),\n")
    o.write("];\n\n")
    o.write("/// Faixas (primeiro, último) do `\\d` do `re` do Python; o valor é a distância ao primeiro.\n")
    o.write(f"pub static DIGITOS: [(u32, u32); {len(faixas)}] = [\n")
    for a, b in faixas:
        o.write(f"    (0x{a:X}, 0x{b:X}),\n")
    o.write("];\n")
print(f"{len(dobra)} dobras, {len(faixas)} faixas de dígitos, Unicode {unicodedata.unidata_version}")
