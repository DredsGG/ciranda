"""Gera as fixtures que provam que o núcleo em Rust faz o mesmo que a 1.5.1, rodando o próprio
código Python da 1.5.1 (ciranda/config.py e ciranda/biblioteca.py deste repositório, main 304bc21).

  rust/tests/fixtures/config/NN-nome.entrada.json  o arquivo que a 1.5.1 encontra (ausente = sem arquivo)
  rust/tests/fixtures/config/NN-nome.saida.json    o que ela grava depois de carregar() + salvar()
  rust/tests/fixtures/ordem.json                   nomes difíceis e a ordem em que a 1.5.1 os põe

    python -I rust/ferramentas/gerar_fixtures.py
O APPDATA do processo aponta para uma pasta temporária: o config real nunca é lido nem tocado.
"""
import json
import os
import random
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp(prefix="ciranda-fixtures-")
os.environ["APPDATA"] = tmp
sys.path.insert(0, RAIZ)
from ciranda import config  # noqa: E402
from ciranda.biblioteca import chave_natural  # noqa: E402

assert config.pasta_dados().startswith(tmp)
DEST = os.path.join(RAIZ, "rust", "tests", "fixtures")
DCFG = os.path.join(DEST, "config")
shutil.rmtree(DCFG, ignore_errors=True)
os.makedirs(DCFG)
arquivo = os.path.join(config.pasta_dados(), "config.json")

realista = dict(config.PADRAO)
realista.update({
    "volume": 65, "mudo": True, "aleatorio": False, "repetir": "um", "filtro": "fotos", "segundos_foto": 12,
    "painel": False,
    "ultimas_pastas": [r"C:\Users\Fulano\Fotos\Férias 2024", r'D:\Vídeos\Aniversário "da vó"', r"\\nas\mídia\São João"],
    "geometria": "AdnQywADAAAAAAB4AAAAeAAABdcAAAOrAAAAeAAAAJQAAAXXAAADqwAAAAAAAAAAB4AAAAB4AAAAlAAABdcAAAOr",
    "versao_vista": "1.5.1", "idioma": "es", "aviso_adiado_versao": "1.6.0", "aviso_adiado_ate": 1763400000.123456,
    "novidades_vista": "1.5.1", "tutorial_visto": True,
    "retomar": {"caminhos": [r"C:\Users\Fulano\Fotos\Férias 2024"], "arquivo": r"C:\Users\Fulano\Fotos\Férias 2024\v.mp4",
                "pos": 12.35, "pausado": False, "tela_cheia": True, "de": "1.5.1", "quando": 1763396400.987654},
    "apoio_escolha": "br",
})


def salvo(d):
    """O que a 1.5.1 grava para este dicionário."""
    config.salvar(d)
    return open(arquivo, "rb").read()


especiais = dict(config.PADRAO)
especiais.update({
    "versao_vista": "tab\there \"aspas\" barra\\ \x01 \x1f \x7f \u2028 ✓ 😀 \u00e9",
    "aviso_adiado_ate": 1e16, "volume": 18446744073709551615, "segundos_foto": -0.0,
    "retomar": {"a": [], "b": {}, "c": [[], [{}]], "pos": 1.5e-07, "x": 0.0001, "y": 1e22, "z": 2.5},
    "geometria": [1, 2.0, True, None, "x"],
})

CASOS = [
    ("sem-arquivo", None),
    ("padrao", salvo(dict(config.PADRAO))),
    ("realista", salvo(realista)),
    ("especiais", salvo(especiais)),
    ("ordem-trocada-e-chave-desconhecida",
     '{"filtro":"videos","nova_chave":1,"volume":30,"aleatorio":false,"idioma":"en"}'.encode()),
    ("tipos-errados",
     '{"volume":"70","aleatorio":0,"repetir":"sempre","filtro":null,"ultimas_pastas":"C:\\\\x","mudo":[]}'.encode()),
    ("json-quebrado", b'{"volume": 50,'),
    ("com-bom", b"\xef\xbb\xbf" + salvo(realista)),
    ("lista-no-topo", b"[1, 2]"),
    ("vazio", b""),
    ("chave-repetida", b'{"volume": 10, "volume": 20}'),
    ("utf8-invalido", b'{"idioma": "\xff\xfe"}'),
    ("crlf-e-recuo-4", json.dumps(realista, indent=4, ensure_ascii=True).replace("\n", "\r\n").encode()),
    ("escape-ascii", json.dumps({"idioma": "pt", "versao_vista": "S\u00e3o \ud83d\ude00"}, ensure_ascii=True).encode()),
]

for n, (nome, entrada) in enumerate(CASOS, 1):
    base = os.path.join(DCFG, f"{n:02d}-{nome}")
    if os.path.exists(arquivo):
        os.remove(arquivo)
    if entrada is not None:
        with open(arquivo, "wb") as f:
            f.write(entrada)
        with open(base + ".entrada.json", "wb") as f:
            f.write(entrada)
    cfg = config.carregar()
    config.salvar(cfg)
    with open(arquivo, "rb") as f, open(base + ".saida.json", "wb") as g:
        g.write(f.read())

# ---------- ordem natural ----------
dificeis = [
    "foto01.jpg", "foto1.jpg", "Foto1.jpg", "foto001.jpg", "foto10.jpg", "foto2.jpg", "foto", "foto.jpg",
    "ß", "ss", "SS", "Straße", "strasse", "Ärger", "arger", "árvore", "arvore", "a b", "a_b", "a-b", "a.b",
    "٣", "३", "3", "10", "9", "00", "0", "", ".", "x²", "①", "IMG_0001.JPG", "img_1.jpg", "IMG_0001 (2).JPG",
    "Ǆ", "ǅ", "ǆ", "ﬁle", "file", "Σίσυφος", "σίσυφος", "ΣΊΣΥΦΟΣ", "Ꭰ", "ꭰ", "😀", "İ", "ı", "i", "I",
    "１２", "12", "a１２b3", "a12b3", "a12b03", "18446744073709551616", "18446744073709551615x", "x99999999999999999999999",
    "Ω", "ω", "Ω", "K", "k", "K", "Å", "å", "Å", "ﬀ", "ff", "ŉ", "ʼn",
]
alfabeto = list("aAbBzZ09 _-.()[]ßẞſÄäΣσςΩωİıﬁﬀ٣३１２①²éÉçÇ😀Ꭰꭰ") + ["0", "1", "5", "9", "00"]
rng = random.Random(20261117)
nomes = list(dificeis)
for _ in range(3000):
    nomes.append("".join(rng.choice(alfabeto) for _ in range(rng.randint(1, 12))))
validos = []
for s in nomes:
    try:
        chave_natural(s)  # a 1.5.1 quebra com "1²" (int('²')): esses ficam de fora
        validos.append(s)
    except ValueError:
        pass
ordem = sorted(range(len(validos)), key=lambda i: chave_natural(validos[i]))
# As subpastas vão para a pilha com sorted(reverse=True), que também é estável nos empates.
decrescente = sorted(range(len(validos)), key=lambda i: chave_natural(validos[i]), reverse=True)
with open(os.path.join(DEST, "ordem.json"), "w", encoding="utf-8") as f:
    json.dump({"python": sys.version.split()[0], "nomes": validos, "ordem": ordem, "ordem_decrescente": decrescente,
               "fora": len(nomes) - len(validos)}, f, ensure_ascii=False, indent=0)

# ---------- caminhos: normcase, abspath e a classe de erro de cada código do Windows ----------
import ntpath  # noqa: E402

B = "\\"
normcase = [s.replace("/", B) for s in [
    "C:/Fotos/K.jpg", "C:/Fotos/k.jpg", "D:/ΦΩΤΟΣ", "D:/φωτοσ", "D:/Ωmega", "E:/Straße/ẞ", "E:/İstanbul/I",
    "F:/ΣΊΣΥΦΟΣ/σίσυφος", "G:/ǄǅǆĲ", "H:/Ꭰꭰ/Å", "C:/a/b/../c", "//nas/Mídia/São João/ÁÉÍÓÚ", "//?/C:/X/Y",
    "C:/mixed/Separators\\here", "ÀÉÎÕÜÇÑ ẞ ꞵ Ꞵ", "",
]]
abspath = [s.replace("/", B) for s in [
    "C:/Windows/", "C:/Windows//Fonts/", "C:/Windows/./Fonts/../", "C:/", "//server/share/", "//server/share/x/",
    "//?/C:/Windows/", "//?/C:/", "C:/Windows/a. ", "C:/Windows/b...", "C:/Fotos/Férias/",
]]
erros = {}
for w in range(20000):
    nome = type(OSError(0, "x", None, w)).__name__
    if nome != "OSError":
        erros[str(w)] = nome
with open(os.path.join(DEST, "caminhos.json"), "w", encoding="utf-8") as f:
    json.dump({"python": sys.version.split()[0],
               "normcase": [[s, ntpath.normcase(s)] for s in normcase],
               "abspath": [[s, ntpath.abspath(s)] for s in abspath],
               "erros_nao_oserror": erros}, f, ensure_ascii=False, indent=1)
shutil.rmtree(tmp, ignore_errors=True)
print(f"{len(CASOS)} casos de config, {len(validos)} nomes ({len(nomes) - len(validos)} quebram a 1.5.1 e ficaram de fora)")
