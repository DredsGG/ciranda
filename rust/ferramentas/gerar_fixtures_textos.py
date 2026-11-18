"""Gera rust/tests/fixtures/textos.json: o que a textos.py da 1.5.1 devolve, rodando o próprio
código dela (importado pelo caminho absoluto do arquivo), para o Rust provar que faz igual.

  t            toda chave × idioma: t(chave) cru e t(chave, **valores) com um valor diferente por
               campo (inteiros e textos com acento; um deles com chaves dentro, que não podem ser
               expandidas de novo) e mais um valor que o modelo não usa
  formato      modelos inventados com {{, }} e campos repetidos, pelo str.format(**kw)
  escolha      trios com tradução vazia: o `trio[idx] or trio[1]`
  normalizar   códigos de idioma tortos (inclusive todo espaço que o str.strip() tira)
  sistema      idioma_do_sistema() com CIRANDA_IDIOMA_SISTEMA em vários valores
  iniciar      iniciar({"idioma": salvo}) com o sistema simulado
  definir      definir(x) e o atual() que fica

    python -I rust/ferramentas/gerar_fixtures_textos.py [caminho/do/textos.py]
Sem argumento, usa o ciranda/textos.py deste repositório.
"""
import importlib.util
import json
import os
import string
import sys

RUST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEM = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(RUST), "ciranda", "textos.py"))
DEST = os.path.join(RUST, "tests", "fixtures", "textos.json")

spec = importlib.util.spec_from_file_location("textos_151", ORIGEM)
textos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(textos)
os.environ.pop("CIRANDA_IDIOMA_SISTEMA", None)


def campos(modelo):
    return sorted({c for _, c, _, _ in string.Formatter().parse(modelo) if c is not None})


# Um valor diferente por nome de campo: trocar dois campos de lugar muda o resultado.
TODOS = sorted({c for trio in textos.T.values() for s in trio for c in campos(s)})
TEXTOS = {"nome": "Férias {n} {{x}} 2024", "nomes": "São João, Ação", "versao": "1.6.0-ç", "tempo": "7 s",
          "valor": "R$ 12,50", "erro": "[WinError 5] Acesso negado: 'C:\\\\Instalação'", "msg": "rede caiu — “ops”",
          "antes": "1.5.1", "agora": "1.6.0", "aleatorio": "sim", "repetir": "não", "filtro": "vídeos",
          "cheia": "não", "idioma": "es", "mudo": " (mudo)"}
VALORES = {}
for i, c in enumerate(TODOS):
    VALORES[c] = TEXTOS[c] if c in TEXTOS else 1000 + 37 * i  # os outros são números (n, total, fotos...)
SOBRA = ("campo_que_nenhum_modelo_usa", "ñ")

casos_t = []
for chave, trio in textos.T.items():
    for idioma in textos.IDIOMAS:
        textos.definir(idioma)
        kw = {c: VALORES[c] for c in campos(trio[textos.IDIOMAS.index(idioma)])}
        kw[SOBRA[0]] = SOBRA[1]
        casos_t.append({"chave": chave, "idioma": idioma, "cru": textos.t(chave), "args": kw,
                        "formatado": textos.t(chave, **kw)})

MODELOS = [
    ("{{", {}), ("}}", {}), ("{{n}}", {}), ("{{n}}", {"n": 1}), ("{{{n}}}", {"n": 7}), ("a{{b}}c{n}d", {"n": "é"}),
    ("}}{{", {"x": 1}), ("{n}{n}{total}", {"n": 2, "total": 30}), ("100%", {"v": 1}), ("%APPDATA%\\x {v}%", {"v": 55}),
    ("", {"n": 1}), ("sem campo", {"n": 1}), ("ç{nome}ç", {"nome": "{n}"}), ("{n}}}", {"n": 4}), ("{{{{", {}),
    ("{nome}", {"nome": ""}), ("início {a}, meio {b}, fim {a}", {"a": "α", "b": -3}), ("{x}{{}}{y}", {"x": 0, "y": "😀"}),
]
formato = [{"modelo": m, "args": a, "esperado": m.format(**a)} for m, a in MODELOS]

TRIOS = [("", "en", "es"), ("pt", "", "es"), ("pt", "en", ""), ("", "", ""), ("", "en", ""), ("pt", "", "")]
escolha = []
for trio in TRIOS:
    textos.T["__teste__"] = trio
    for idioma in textos.IDIOMAS:
        textos.definir(idioma)
        escolha.append({"trio": list(trio), "idioma": idioma, "esperado": textos.t("__teste__")})
del textos.T["__teste__"]

ESPACOS = [chr(c) for c in range(0x110000) if chr(c).isspace()]
CODIGOS = ["pt-BR", "es-419", "en-US", "PT", "pt_BR", "", "fr", "ptx", " es ", "pt-", "zh-Hant-TW", "pt", "en", "es",
           "EN-gb", "Es-Es", "es_MX.UTF-8", "pt_", "-pt", "p", "pt--BR", "en-pt", "esp", "ES419", "\tpt-PT\n",
           "\u200bpt", "\ufeffes", "\u180ees", "pt\x00", "  ", "PT-BR ", "İt", "ΡΤ", "ｐｔ", "pt\u0301", "de-DE", "ja"]
CODIGOS += [f"{e}pt-BR{e}" for e in ESPACOS] + [f"{e}{e}ES" for e in ESPACOS]
normalizar = [[c, textos.normalizar(c)] for c in CODIGOS]

sistema = []
for v in ["pt-BR", "es-419", "en-US", "fr-FR", "PT", " es ", "ptx", "de", "zh-Hant-TW", "pt_PT", "es", "\u3000pt"]:
    os.environ["CIRANDA_IDIOMA_SISTEMA"] = v
    sistema.append([v, textos.idioma_do_sistema()])

iniciar = []
for simulado in ["pt-BR", "es-ES", "fr"]:
    os.environ["CIRANDA_IDIOMA_SISTEMA"] = simulado
    for salvo in [None, "", "pt", "en", "es", "PT", "fr", "pt-BR", " es"]:
        cfg = {} if salvo is None else {"idioma": salvo}
        r = textos.iniciar(cfg)
        assert r == textos.atual()
        iniciar.append({"sistema": simulado, "salvo": salvo, "esperado": r})
os.environ.pop("CIRANDA_IDIOMA_SISTEMA", None)

definir = []
for x in ["pt", "en", "es", "PT", "pt-BR", "", "xx", " es"]:
    textos.definir(x)
    definir.append([x, textos.atual()])

with open(DEST, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"python": sys.version.split()[0], "idiomas": list(textos.IDIOMAS), "nomes": textos.NOMES,
               "quantas": len(textos.T), "chaves": list(textos.T), "t": casos_t, "formato": formato,
               "escolha": escolha, "normalizar": normalizar, "sistema": sistema, "iniciar": iniciar,
               "definir": definir}, f, ensure_ascii=False, indent=0)
    f.write("\n")
print(f"{len(textos.T)} chaves, {len(casos_t)} casos de t, {len(formato)} de formato, {len(escolha)} de escolha, "
      f"{len(normalizar)} de normalizar, {len(sistema)} de sistema, {len(iniciar)} de iniciar, {len(definir)} de definir")
