"""Gera rust/src/textos_tabela.rs: a tabela T da ciranda/textos.py da 1.5.1, nas mesmas ordem e grafia.

O textos.py é importado pelo caminho absoluto do arquivo (não pelo pacote `ciranda`, que puxaria o
resto do app). A saída só depende do conteúdo da tabela: rodar de novo dá os mesmos bytes.

    python -I rust/ferramentas/gerar_textos.py [caminho/do/textos.py]
Sem argumento, usa o ciranda/textos.py deste repositório.

Também confere que os modelos só usam o que o `formatar` do Rust sabe fazer: campos `{nome}` com
nome de identificador, `{{` e `}}`; nada de `{0}`, `{x:>5}`, `{x!r}` ou `{x.y}`.
"""
import importlib.util
import os
import string
import sys
import unicodedata

RUST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEM = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(RUST), "ciranda", "textos.py"))
SAIDA = os.path.join(RUST, "src", "textos_tabela.rs")


def carregar(caminho):
    spec = importlib.util.spec_from_file_location("textos_151", caminho)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def lit(s):
    """Literal de string do Rust. Acentos e símbolos ficam em UTF-8; aspas, barra, quebras de linha
    e tudo o que é invisível (controle, formatação, espaços que não são o espaço comum, bidi) vira
    escape, para o fonte não esconder nada (e o rustc não recusar caracteres bidi)."""
    fora = []
    for c in s:
        if c == "\\":
            fora.append("\\\\")
        elif c == '"':
            fora.append('\\"')
        elif c == "\n":
            fora.append("\\n")
        elif c == "\r":
            fora.append("\\r")
        elif c == "\t":
            fora.append("\\t")
        elif c == " " or (0x20 < ord(c) < 0x7F):
            fora.append(c)
        elif ord(c) < 0x80 or unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zs", "Zl", "Zp", "Mn", "Me"):
            fora.append(f"\\u{{{ord(c):x}}}")
        else:
            fora.append(c)
    return '"' + "".join(fora) + '"'


def conferir_modelo(chave, s):
    for _, campo, espec, conv in string.Formatter().parse(s):  # levanta ValueError se o modelo estiver torto
        if campo is None:
            continue
        assert campo.isidentifier(), f"{chave}: campo {campo!r} não é um nome simples"
        assert not espec and conv is None, f"{chave}: {{{campo}}} usa especificação ou conversão"


m = carregar(ORIGEM)
assert tuple(m.IDIOMAS) == ("pt", "en", "es"), m.IDIOMAS
linhas = []
for chave, trio in m.T.items():
    assert isinstance(chave, str) and isinstance(trio, tuple) and len(trio) == 3, chave
    assert all(isinstance(s, str) for s in trio), chave
    for s in trio:
        conferir_modelo(chave, s)
    linhas.append(f"    ({lit(chave)}, [{lit(trio[0])}, {lit(trio[1])}, {lit(trio[2])}]),\n")

with open(SAIDA, "w", encoding="utf-8", newline="\n") as o:
    o.write("//! Gerado por ferramentas/gerar_textos.py a partir da ciranda/textos.py da 1.5.1: não editar à mão.\n")
    o.write("//! Para mudar um texto, mude o textos.py e gere de novo:\n")
    o.write("//!     python -I rust/ferramentas/gerar_textos.py [caminho/do/textos.py]\n\n")
    o.write(f"/// A tabela `T` da 1.5.1 ({len(linhas)} chaves, na mesma ordem): chave → (português, inglês, espanhol).\n")
    o.write("pub(crate) static TABELA: &[(&str, [&str; 3])] = &[\n")
    o.writelines(linhas)
    o.write("];\n")
print(f"{len(linhas)} chaves -> {SAIDA}")
