"""Gera as fixtures que provam que a heif.rs lê o HEIC como a 1.5.1, rodando o próprio código Python
da 1.5.1 (ciranda/heif.py e tests/gerar_heic.py, importados pelo caminho absoluto).

  rust/tests/fixtures/heif/*.heic   arquivos de teste (binários), cortados logo depois da caixa meta
  rust/tests/fixtures/heif.json     para cada arquivo, o filtro_de_giro e o _transformacoes_da_grade da 1.5.1

    python -I rust/ferramentas/gerar_fixtures_heif.py [raiz-do-repositório-da-1.5.1]
Sem argumento, a raiz é a pasta acima de rust/. Os HEIC de verdade (gerar_heic.CASOS, com o ffmpeg e o
libx265 do PATH) ficam em %APPDATA%\\Ciranda-rust-prova\\heic-casos; a pasta da Ciranda nunca é tocada.
O parser só lê os cabeçalhos do nível de cima e a meta, então cada fixture para uns bytes depois da
meta: o arquivo inteiro e o cortado dão o mesmo resultado (conferido aqui para os casos de verdade).
"""
import importlib.util
import json
import os
import random
import shutil
import struct
import sys

sys.dont_write_bytecode = True  # importar a 1.5.1 não deixa __pycache__ no repositório dela
RUST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(RUST)


def modulo(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


heif = modulo("heif_151", os.path.join(RAIZ, "ciranda", "heif.py"))
gerar_heic = modulo("gerar_heic_151", os.path.join(RAIZ, "tests", "gerar_heic.py"))

CASOS_DIR = os.path.join(os.environ["APPDATA"], "Ciranda-rust-prova", "heic-casos")
DEST = os.path.join(RUST, "tests", "fixtures", "heif")
JSON = os.path.join(RUST, "tests", "fixtures", "heif.json")
shutil.rmtree(DEST, ignore_errors=True)
os.makedirs(DEST)
resultados = {}


def fixture(nome, dados):
    """Grava o arquivo e anota o que a 1.5.1 responde para ele."""
    assert nome not in resultados, nome
    p = os.path.join(DEST, nome)
    with open(p, "wb") as f:
        f.write(dados)
    try:
        partes = heif._transformacoes_da_grade(p)
        filtro = heif.filtro_de_giro(p)
    except BaseException as e:  # a 1.5.1 deixaria escapar: a Rust não tem como imitar, então não vale
        raise SystemExit(f"{nome}: a 1.5.1 levantou {type(e).__name__}: {e}")
    resultados[nome] = {"filtro": filtro, "partes": partes}
    return partes


# ---------- caixas ----------

def caixa(tipo, corpo, modo="normal"):
    """modo: "normal", "zero" (até o fim), "longo" (tamanho de 64 bits), ("tam", n) ou ("longo", n)."""
    if modo == "normal":
        return struct.pack(">I", 8 + len(corpo)) + tipo + corpo
    if modo == "zero":
        return struct.pack(">I", 0) + tipo + corpo
    if modo == "longo":
        return struct.pack(">I", 1) + tipo + struct.pack(">Q", 16 + len(corpo)) + corpo
    if modo[0] == "tam":
        return struct.pack(">I", modo[1]) + tipo + corpo
    if modo[0] == "longo":
        return struct.pack(">I", 1) + tipo + struct.pack(">Q", modo[1]) + corpo
    raise ValueError(modo)


def cheia(tipo, versao, flags, corpo, modo="normal"):
    return caixa(tipo, struct.pack(">I", (versao << 24) | flags) + corpo, modo)


MDAT = struct.pack(">I", 4096) + b"mdat" + b"\0" * 8  # os "poucos bytes" depois da meta
FTYP = caixa(b"ftyp", b"heic" + struct.pack(">I", 0) + b"mif1heic")


def nivel(d, ini, fim):
    """Caixas bem formadas (só para os arquivos que o gerar_heic monta)."""
    while ini + 8 <= fim:
        tam, tipo = struct.unpack_from(">I4s", d, ini)
        assert 8 <= tam <= fim - ini, (tipo, tam)
        yield tipo, ini, ini + 8, ini + tam
        ini += tam


def arvore(d, ini, fim, pai=""):
    """Nós da meta: {"tipo", "rotulo", "pos", "fim", "pre"+"filhos" | "corpo"}; rotulo = "meta/iprp/ipco/irot#0"."""
    nos, vistos = [], {}
    for tipo, i, c, f in nivel(d, ini, fim):
        k = vistos.get(tipo, 0)
        vistos[tipo] = k + 1
        rotulo = f"{pai}{tipo.decode()}#{k}"
        pre = {b"meta": 4, b"iprp": 0, b"ipco": 0}.get(tipo)
        if tipo == b"iinf":
            pre = 4 + (2 if d[c] == 0 else 4)
        no = {"tipo": tipo, "rotulo": rotulo, "pos": i, "fim": f}
        if pre is None:
            no["corpo"] = d[c:f]
        else:
            no["pre"] = d[c:c + pre]
            no["filhos"] = arvore(d, c + pre, f, rotulo + "/")
        nos.append(no)
    return nos


def todos(nos):
    for n in nos:
        yield n
        yield from todos(n.get("filhos", []))


def montar(no, modos):
    corpo = no["pre"] + b"".join(montar(f, modos) for f in no["filhos"]) if "filhos" in no else no["corpo"]
    return caixa(no["tipo"], corpo, modos.get(no["rotulo"], "normal"))


# ---------- os HEIC de verdade (gerar_heic.CASOS) ----------

os.makedirs(CASOS_DIR, exist_ok=True)
gerar_heic.gerar(CASOS_DIR)
ESPERADO = {"giro-grade-48-4032x3024.heic": ["transpose=clock"], "espelho-grade-12-2048x1536.heic": ["hflip"]}
rng = random.Random(20261117)
reais = []
for nome in gerar_heic.CASOS:
    p = os.path.join(CASOS_DIR, nome)
    cheio = open(p, "rb").read()
    inteiro = heif._transformacoes_da_grade(p)
    assert inteiro == ESPERADO.get(nome, []), (nome, inteiro)
    base = nome[:-5]
    tam_ftyp = struct.unpack_from(">I", cheio, 0)[0]
    tam_meta, tipo = struct.unpack_from(">I4s", cheio, tam_ftyp)
    assert tipo == b"meta"
    ini_meta, fim_meta = tam_ftyp, tam_ftyp + tam_meta
    dados = cheio[:fim_meta + 16]
    assert fixture(f"real-{base}.heic", dados) == inteiro, nome
    meta = arvore(cheio, ini_meta, fim_meta)[0]
    assert montar(meta, {}) == cheio[ini_meta:fim_meta], nome  # a árvore remonta os mesmos bytes
    reais.append((base, dados, ini_meta, fim_meta, meta))

    # Cortes: no ftyp, no cabeçalho da meta, nas bordas de cada caixa e byte a byte nas que decidem.
    cortes = set(range(0, ini_meta + 17)) if base == "grade-2-1024x512" else \
        {0, 1, 4, 7, 8, 9, 12, 15, 16, ini_meta - 1} | {ini_meta + k for k in (0, 1, 4, 7, 8, 11, 12, 13, 15, 16)}
    por_tipo = {}
    for n in todos([meta]):
        por_tipo.setdefault(n["tipo"], []).append(n)
    for tipo, ns in por_tipo.items():
        for n in ns[:1] + ns[-1:]:  # das repetidas (infe, ispe...), só a primeira e a última
            a, b = n["pos"], n["fim"]
            cortes |= {a, a + 1, a + 7, a + 8, a + 9, (a + b) // 2, b - 1, b}
            # Byte a byte nas que decidem (a grade de 48 sem giro tem a mesma forma da com giro: só as bordas).
            denso = base != "grade-48-4032x3024" and (
                tipo in (b"ipma", b"irot", b"imir", b"pitm", b"ispe") or (tipo == b"infe" and n["corpo"][8:12] == b"grid"))
            if denso:
                cortes |= set(range(a, b + 1, 1 if b - a <= 64 else 4))
            if tipo == b"ipco":
                cortes |= set(range(a, a + 17))
    cortes |= {fim_meta - 1, fim_meta, fim_meta + 1, fim_meta + 8}
    for k in sorted(c for c in cortes if 0 <= c <= len(dados)):
        fixture(f"corte-{base}-{k:05d}.heic", dados[:k])

    # Bytes trocados dentro da meta (sorteio com semente), metade em qualquer lugar e metade na iprp.
    iprp = next(n for n in todos([meta]) if n["tipo"] == b"iprp")
    for k in range(40):
        a, b = (ini_meta, fim_meta) if k < 20 else (iprp["pos"], iprp["fim"])
        v = bytearray(dados)
        for _ in range(rng.randint(1, 3)):
            v[rng.randrange(a, b)] ^= rng.randrange(1, 256)
        fixture(f"troca-{base}-{k:02d}.heic", bytes(v))

    # Tamanho 0 (até o fim) e 1 (64 bits) em cada caixa que conta, e tamanhos tortos.
    resto = dados[fim_meta:]
    ftyp = dados[:ini_meta]
    variantes = {
        "ftyp-zero": caixa(b"ftyp", ftyp[8:], "zero") + montar(meta, {}) + resto,
        "ftyp-longo": caixa(b"ftyp", ftyp[8:], "longo") + montar(meta, {}) + resto,
        "ftyp-tam-4": caixa(b"ftyp", ftyp[8:], ("tam", 4)) + montar(meta, {}) + resto,
        "ftyp-longo-15": caixa(b"ftyp", ftyp[8:], ("longo", 15)) + montar(meta, {}) + resto,
        "meta-tam-8": ftyp + caixa(b"meta", montar(meta, {})[8:], ("tam", 8)) + resto,
        "meta-tam-mais-100": ftyp + caixa(b"meta", montar(meta, {})[8:], ("tam", tam_meta + 100)) + resto,
        "meta-tam-limite": ftyp + caixa(b"meta", montar(meta, {})[8:], ("tam", 8 * 1024 * 1024)) + resto,
        "meta-tam-limite-mais-1": ftyp + caixa(b"meta", montar(meta, {})[8:], ("tam", 8 * 1024 * 1024 + 1)) + resto,
        "meta-longo-16": ftyp + caixa(b"meta", montar(meta, {})[8:], ("longo", 16)) + resto,
        "meta-longo-limite": ftyp + caixa(b"meta", montar(meta, {})[8:], ("longo", 8 * 1024 * 1024)) + resto,
        "meta-longo-2a40": ftyp + caixa(b"meta", montar(meta, {})[8:], ("longo", 2 ** 40)) + resto,
    }
    for n in todos([meta]):
        t = n["tipo"]
        conta = t in (b"meta", b"hdlr", b"pitm", b"iloc", b"iinf", b"iref", b"iprp", b"ipco", b"ipma", b"irot",
                      b"imir", b"idat", b"hvcC") or (t == b"ispe" and n["rotulo"].endswith("#0")) or \
            (t == b"infe" and n["corpo"][8:12] == b"grid")
        if not conta:
            continue
        rot = n["rotulo"].replace("#", "").replace("/", "_")
        for modo in ("zero", "longo"):
            variantes[f"{rot}-{modo}"] = ftyp + montar(meta, {n["rotulo"]: modo}) + resto
        if t in (b"ipco", b"ipma", b"pitm", b"irot", b"imir", b"iinf", b"infe"):
            tam = n["fim"] - n["pos"]
            variantes[f"{rot}-tam-7"] = ftyp + montar(meta, {n["rotulo"]: ("tam", 7)}) + resto
            variantes[f"{rot}-tam-mais-1"] = ftyp + montar(meta, {n["rotulo"]: ("tam", tam + 1)}) + resto
            variantes[f"{rot}-longo-grande"] = ftyp + montar(meta, {n["rotulo"]: ("longo", 2 ** 64 - 1)}) + resto
    for chave, v in variantes.items():
        fixture(f"caixa-{base}-{chave}.heic", v)


# ---------- sintéticos: só o contêiner, sem imagem (o parser não decodifica nada) ----------

def irot(v):
    return caixa(b"irot", bytes([v]))


def imir(v):
    return caixa(b"imir", bytes([v]))


ISPE = cheia(b"ispe", 0, 0, struct.pack(">II", 1024, 512))
HVCC = caixa(b"hvcC", bytes([1]) + b"\x01\x60\0\0\0\x90\0\0\0\0\0\x5d\xf0\0\xfc\xfd\xf8\xf8\0\0\x0f\0")
HDLR = cheia(b"hdlr", 0, 0, b"\0\0\0\0pict" + b"\0" * 12 + b"\0")


def infe(item, tipo, versao=2):
    if versao < 2:
        return cheia(b"infe", versao, 0, struct.pack(">HH", item, 0) + b"\0")
    if versao == 2:
        return cheia(b"infe", 2, 0, struct.pack(">HH", item, 0) + tipo + b"\0")
    return cheia(b"infe", versao, 0, struct.pack(">IH", item, 0) + tipo + b"\0")


def entrada(item, indices, versao, flags):
    s = struct.pack(">H" if versao < 1 else ">I", item) + bytes([len(indices)])
    return s + b"".join(struct.pack(">H", i) if flags & 1 else bytes([i]) for i in indices)


def sintetico(primario=10, pitm_v=0, itens=None, props=None, assoc=None, ipma_v=0, ipma_flags=0, n_ipma=None,
              ipma_extra=b"", ipma_antes=False, iinf_v=0, pitm=None, iinf=None, iprp=None, ipco=None, ipma=None,
              meta_extra=b"", meta_antes=b"", topo_antes=FTYP, depois=MDAT, iprp_extra=b""):
    """Monta ftyp + meta + começo da mdat. Os parâmetros de caixa pronta (pitm, iinf...) trocam a montada;
    b"" tira a caixa."""
    if itens is None:
        itens = [(1, b"hvc1", 2), (2, b"hvc1", 2), (10, b"grid", 2)]
    if props is None:
        props = [HVCC, ISPE, irot(3)]
    if assoc is None:
        assoc = [(1, [0x81, 0x02]), (2, [0x81, 0x02]), (10, [0x02, 0x83])]
    if pitm is None:
        pitm = cheia(b"pitm", pitm_v, 0, struct.pack(">H" if pitm_v == 0 else ">I", primario))
    if iinf is None:
        corpo = b"".join(infe(*i) for i in itens)
        iinf = cheia(b"iinf", iinf_v, 0, struct.pack(">H" if iinf_v == 0 else ">I", len(itens)) + corpo)
    if ipco is None:
        ipco = caixa(b"ipco", b"".join(props))
    if ipma is None:
        n = len(assoc) if n_ipma is None else n_ipma
        corpo = struct.pack(">I", n) + b"".join(entrada(i, x, ipma_v, ipma_flags) for i, x in assoc) + ipma_extra
        ipma = cheia(b"ipma", ipma_v, ipma_flags, corpo)
    if iprp is None:
        iprp = caixa(b"iprp", (ipma + ipco if ipma_antes else ipco + ipma) + iprp_extra)
    meta = cheia(b"meta", 0, 0, meta_antes + HDLR + pitm + iinf + iprp + meta_extra)
    return topo_antes + meta + depois


# Giro 0-3 x espelho 0/1 (e sem um ou outro), com e sem grade, nas duas ordens, nas duas larguras de índice.
for largura in (0, 1):
    for grade in (True, False):
        if largura and not grade:
            continue
        for r in (None, 0, 1, 2, 3):
            for m in (None, 0, 1):
                for ordem in (("rot", "mir"), ("mir", "rot")) if r is not None and m is not None else (("rot", "mir"),):
                    props, idx = [HVCC, ISPE], [0x81, 0x02]
                    for o in ordem:
                        if o == "rot" and r is not None:
                            props.append(irot(r))
                            idx.append(0x80 | len(props))
                        if o == "mir" and m is not None:
                            props.append(imir(m))
                            idx.append(len(props))  # sem o bit de essencial: tanto faz para a 1.5.1
                    if largura:
                        idx = [(i & 0x7F) | (0x8000 if i & 0x80 else 0) for i in idx]
                    itens = [(1, b"hvc1", 2), (2, b"hvc1", 2), (10, b"grid" if grade else b"hvc1", 2)]
                    nome = f"sint-{'grade' if grade else 'sem-grade'}-larg{8 << largura}-rot{r}-mir{m}-{'-'.join(ordem)}"
                    fixture(nome + ".heic", sintetico(itens=itens, props=props, ipma_flags=largura,
                                                      assoc=[(1, [0x81]), (2, [0x81]), (10, idx)]))

MUITAS = [cheia(b"colr", 0, 0, bytes([k])) for k in range(200)]  # 200 propriedades de enchimento
casos = {
    # índice de 15 bits (flags & 1): irot e imir depois da 127ª propriedade
    "indice-alto-flags1": dict(props=MUITAS + [irot(1), imir(0)], ipma_flags=1,
                               assoc=[(10, [0x8000 | 201, 202, 0x00C9])]),
    "indice-alto-flags1-v1": dict(props=MUITAS + [irot(2), imir(1)], ipma_flags=1, ipma_v=1,
                                  assoc=[(10, [0x8000 | 201, 202])]),
    "flags-0x100-indice-8bits": dict(ipma_flags=0x100, assoc=[(10, [0x83])]),
    "flags-0xffffff": dict(ipma_flags=0xFFFFFF, assoc=[(10, [0x8003, 0x0003])]),
    "flags0-mas-indices-de-16bits": dict(ipma=cheia(b"ipma", 0, 0, struct.pack(">IHB", 1, 10, 2) + b"\x80\x03\x00\x03")),
    "flags1-mas-indices-de-8bits": dict(ipma=cheia(b"ipma", 0, 1, struct.pack(">IHB", 1, 10, 2) + b"\x83\x03")),
    "indice-0": dict(assoc=[(10, [0x80, 0x83])]),
    "indice-alem-do-fim": dict(assoc=[(10, [0x84, 0x83, 0xFF])]),
    "indice-127": dict(assoc=[(10, [0x7F, 0x83])]),
    "indice-16bits-alem": dict(ipma_flags=1, assoc=[(10, [0x7FFF, 0x0004, 0x0003])]),
    "sem-ipco": dict(ipco=b""),
    "ipco-vazia": dict(props=[]),
    "sem-ipma": dict(ipma=b""),
    "sem-pitm": dict(pitm=b""),
    "sem-iinf": dict(iinf=b""),
    "sem-iprp": dict(iprp=b""),
    "duas-pitm-ultima-vale": dict(meta_extra=cheia(b"pitm", 0, 0, struct.pack(">H", 1))),
    "duas-pitm-ultima-grade": dict(primario=1, meta_extra=cheia(b"pitm", 0, 0, struct.pack(">H", 10))),
    "duas-ipco-ultima-vale": dict(iprp_extra=caixa(b"ipco", HVCC + ISPE + imir(1))),
    "duas-ipma-ultima-vale": dict(iprp_extra=cheia(b"ipma", 0, 0, struct.pack(">IHB", 1, 10, 1) + b"\x02")),
    "duas-iinf-ultima-vale": dict(meta_extra=cheia(b"iinf", 0, 0, struct.pack(">H", 1) + infe(10, b"hvc1"))),
    "duas-iprp-ultima-vale": dict(meta_extra=caixa(b"iprp", caixa(b"ipco", imir(0)) +
                                                   cheia(b"ipma", 0, 0, struct.pack(">IHB", 1, 10, 1) + b"\x01"))),
    "ipma-antes-da-ipco": dict(ipma_antes=True, props=[HVCC, ISPE, irot(1), imir(1)], assoc=[(10, [3, 4])]),
    "irot-bits-altos": dict(props=[HVCC, ISPE, irot(0xFD), imir(0xFE)], assoc=[(10, [3, 4])]),
    "irot-4-vira-0": dict(props=[HVCC, ISPE, irot(4), imir(0x03)], assoc=[(10, [3, 4])]),
    "giro-repetido": dict(props=[HVCC, ISPE, irot(1), imir(1)], assoc=[(10, [3, 4, 3, 3, 4])]),
    "duas-entradas-do-primario": dict(props=[HVCC, ISPE, irot(1), imir(0)], assoc=[(10, [3]), (1, [4]), (10, [4])]),
    "giro-so-nos-blocos": dict(assoc=[(1, [0x83]), (2, [0x83]), (10, [0x81])]),
    "item-0": dict(primario=0, itens=[(0, b"grid", 2)], assoc=[(0, [0x83])]),
    "ids-32bits": dict(primario=70000, pitm_v=1, ipma_v=1, itens=[(70000, b"grid", 3)], assoc=[(70000, [0x83])]),
    "ids-32bits-ipma-v0": dict(primario=70000, pitm_v=1, itens=[(70000, b"grid", 3)],
                               ipma=cheia(b"ipma", 0, 0, struct.pack(">IHB", 1, 70000 & 0xFFFF, 1) + b"\x83")),
    "pitm-v1-id-curto": dict(pitm_v=1, ipma_v=1),
    "pitm-v2": dict(pitm=cheia(b"pitm", 2, 0, struct.pack(">I", 10))),
    "infe-v3-grade": dict(itens=[(1, b"hvc1", 2), (10, b"grid", 3)]),
    "infe-v4-grade": dict(itens=[(1, b"hvc1", 2), (10, b"grid", 4)]),
    "infe-v0-grade": dict(itens=[(1, b"hvc1", 2), (10, b"grid", 0)]),
    "infe-v1-grade": dict(itens=[(1, b"hvc1", 2), (10, b"grid", 1)]),
    "infe-repetida-hvc1-antes": dict(itens=[(10, b"hvc1", 2), (10, b"grid", 2)]),
    "infe-repetida-grid-antes": dict(itens=[(10, b"grid", 2), (10, b"hvc1", 2)]),
    "primario-e-bloco": dict(primario=1),
    "primario-sem-infe": dict(primario=99),
    "iinf-v1": dict(iinf_v=1),
    "tipo-grid-maiusculo": dict(itens=[(10, b"GRID", 2)]),
    "ipma-n-0": dict(n_ipma=0),
    "ipma-n-enorme": dict(n_ipma=0xFFFFFFFF, props=[HVCC, ISPE, irot(1)], assoc=[(10, [0x83])]),
    "ipma-n-mais-1": dict(n_ipma=4),
    # a 1.5.1 lê a ipma além do fim da caixa: a entrada a mais vem dos bytes depois da iprp (que, como
    # caixa, têm tamanho 0x000a0184 e só param a varredura da meta)
    "ipma-le-alem-da-caixa": dict(n_ipma=4, props=[HVCC, ISPE, irot(1), imir(1)],
                                  meta_extra=struct.pack(">HB", 10, 1) + b"\x84free"),
    "ipma-le-alem-da-caixa-idat": dict(n_ipma=4, props=[HVCC, ISPE, irot(1), imir(1)],
                                       meta_extra=caixa(b"idat", struct.pack(">HB", 10, 1) + b"\x84")),
    "ipma-qtd-alem-da-caixa": dict(ipma=cheia(b"ipma", 0, 0, struct.pack(">IHB", 1, 10, 3) + b"\x83"),
                                   props=[HVCC, ISPE, irot(1)], meta_extra=b"\x00\x00\x00\x09free\x03"),
    "ipma-curta-no-fim": dict(ipma=cheia(b"ipma", 0, 0, struct.pack(">I", 1)), iprp_extra=b""),
    "ipma-so-cabecalho": dict(ipma=caixa(b"ipma", b"")),
    "ipma-sem-n": dict(ipma=caixa(b"ipma", b"\0\0\0\0")),
    "pitm-curta-le-a-proxima": dict(pitm=caixa(b"pitm", b"\0\0\0\0")),
    "pitm-v1-curta": dict(pitm=caixa(b"pitm", b"\x01\0\0\0\0\0")),
    "pitm-vazia": dict(pitm=caixa(b"pitm", b"")),
    # pitm e infe curtas que a 1.5.1 completa com os bytes da caixa seguinte, e que dão certo assim:
    # o id sai do tamanho da próxima caixa (0x0000...) e o tipo da infe sai do tipo dela ("grid")
    "pitm-curta-id-da-proxima-casa": dict(pitm=caixa(b"pitm", b"\0\0\0\0"), itens=[(0, b"grid", 2)],
                                          assoc=[(0, [0x83])]),
    "pitm-v1-curta-id-da-proxima-casa": dict(pitm=caixa(b"pitm", b"\x01\0\0\0\0\0"), itens=[(0, b"grid", 2)],
                                             ipma_v=1, assoc=[(0, [0x83])]),
    "infe-curta-tipo-da-proxima": dict(primario=0, assoc=[(0, [0x83])], iinf=cheia(
        b"iinf", 0, 0, struct.pack(">H", 2) + caixa(b"infe", b"\x02\0\0\0") + caixa(b"grid", b"\0" * 8))),
    # propriedade só com cabeçalho: lê o primeiro byte da caixa seguinte (aqui, o tamanho da ipma: 0)
    "imir-sem-corpo-no-meio": dict(props=[HVCC, ISPE, caixa(b"imir", b"")], assoc=[(10, [0x83])]),
    "irot-sem-corpo-no-meio": dict(props=[HVCC, ISPE, caixa(b"irot", b""), irot(1)], assoc=[(10, [0x83, 0x84])]),
    # e no fim da meta: IndexError, a função inteira dá vazio (nada da lista pela metade)
    "imir-ok-irot-sem-corpo-no-fim": dict(ipma_antes=True, props=[HVCC, ISPE, imir(1), caixa(b"irot", b"")],
                                          assoc=[(10, [3, 4])]),
    "irot-ok-imir-sem-corpo-no-fim": dict(ipma_antes=True, props=[HVCC, ISPE, irot(3), caixa(b"imir", b"")],
                                          assoc=[(10, [3, 4])]),
    "imir-sem-corpo-no-fim-nao-usado": dict(ipma_antes=True, props=[HVCC, ISPE, imir(1), caixa(b"irot", b"")],
                                            assoc=[(10, [3])]),
    # caixa de 64 bits sem os 8 bytes do tamanho: no fim dos bytes é erro; antes do fim só para a varredura
    "ipco-filho-longo-ipma-depois": dict(props=[HVCC, ISPE, irot(1), b"\0\0\0\x01free"], assoc=[(10, [3])]),
    "meta-longo-sem-tamanho-no-fim": dict(meta_extra=b"\0\0\0\x01free\0\0\0\0"),
    "meta-longo-sem-tamanho-8-no-fim": dict(meta_extra=b"\0\0\0\x01free"),
    "meta-tam-2-no-fim": dict(meta_extra=b"\0\0\0\x02free\0\0\0\0"),
    "meta-filho-longo-ok": dict(meta_extra=caixa(b"free", b"xyz", "longo")),
    "ipco-filho-tam-3": dict(props=[HVCC, ISPE, irot(1), b"\0\0\0\x03free", imir(1)], assoc=[(10, [3, 4])]),
    "ipco-filho-alem-do-pai": dict(props=[HVCC, ISPE, irot(1), b"\0\0\x01\x00free"], assoc=[(10, [3])]),
    "ipco-filho-zero": dict(props=[HVCC, ISPE, irot(1), caixa(b"imir", b"\x01", "zero")], assoc=[(10, [3, 4])]),
    "iprp-filho-zero-ipco": dict(iprp=caixa(b"iprp", caixa(b"ipco", HVCC + ISPE + irot(1), "zero") +
                                            cheia(b"ipma", 0, 0, struct.pack(">IHB", 1, 10, 1) + b"\x83"))),
    "infe-zero-no-fim-da-iinf": dict(iinf=cheia(b"iinf", 0, 0, struct.pack(">H", 2) + infe(1, b"hvc1") +
                                                caixa(b"infe", infe(10, b"grid")[8:], "zero"))),
    "iinf-depois-da-iprp-grid-curto": dict(iinf=b"", meta_extra=cheia(b"iinf", 0, 0, struct.pack(">H", 1) +
                                                                       caixa(b"infe", b"\x02\0\0\0\0\x0a\0\0gr"))),
    "infe-grid-sem-nada-depois": dict(iinf=b"", meta_extra=cheia(b"iinf", 0, 0, struct.pack(">H", 1) +
                                                                  caixa(b"infe", b"\x02\0\0\0\0\x0a\0\0grid"))),
    "infe-sem-id-no-fim": dict(iinf=b"", meta_extra=cheia(b"iinf", 0, 0, struct.pack(">H", 1) +
                                                           caixa(b"infe", b"\x02\0\0\0\0"))),
    "infe-vazia-no-fim": dict(iinf=b"", meta_extra=cheia(b"iinf", 0, 0, struct.pack(">H", 1) + caixa(b"infe", b""))),
    "iinf-vazia-no-fim": dict(iinf=b"", meta_extra=caixa(b"iinf", b"")),
    "iprp-vazia": dict(iprp=caixa(b"iprp", b"")),
    "meta-antes-hdlr-zero": dict(meta_antes=caixa(b"hdlr", b"", "zero")),
    "meta-primeira-sem-ftyp": dict(topo_antes=b""),
    "62-free-antes-da-meta": dict(topo_antes=FTYP + caixa(b"free", b"") * 62),
    "63-free-antes-da-meta": dict(topo_antes=FTYP + caixa(b"free", b"") * 63),
    "free-longo-antes-da-meta": dict(topo_antes=FTYP + caixa(b"free", b"abc", "longo")),
    "free-zero-antes-da-meta": dict(topo_antes=FTYP + caixa(b"free", b"", "zero")),
    "free-tam-7-antes-da-meta": dict(topo_antes=FTYP + caixa(b"free", b"", ("tam", 7))),
    "mdat-antes-da-meta": dict(topo_antes=FTYP + caixa(b"mdat", b"\0" * 300)),
    "sem-mdat-depois": dict(depois=b""),
}
for k in (2 ** 32, 2 ** 40, 2 ** 62, 2 ** 63 - 1 - len(FTYP), 2 ** 63 - len(FTYP), 2 ** 63, 2 ** 64 - 1):
    casos[f"free-longo-{k:x}-antes-da-meta"] = dict(topo_antes=FTYP + caixa(b"free", b"", ("longo", k)))
for nome, kw in casos.items():
    fixture(f"sint-{nome}.heic", sintetico(**kw))

# Arquivos que não são HEIC, e os que acabam cedo.
fora = {
    "vazio": b"",
    "7-bytes": b"\0\0\0\x08fre",
    "so-cabecalho-free": b"\0\0\0\x08free",
    "so-ftyp": FTYP,
    "longo-sem-tamanho": b"\0\0\0\x01free\0\0\0",
    "png": b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR\0\0\x04\0\0\0\x03\0\x08\x02\0\0\0" + b"\0" * 16,
    "jpeg": b"\xff\xd8\xff\xe1\0\x18Exif\0\0MM\0*\0\0\0\x08\0\0\0\0\0\0\xff\xd9",
    "texto": "olá, isto não é uma foto\r\n".encode() * 4,
    "mp4-com-meta-dentro-da-moov": caixa(b"ftyp", b"isom\0\0\x02\0isomiso2") +
    caixa(b"moov", cheia(b"meta", 0, 0, HDLR) + caixa(b"mvhd", b"\0" * 100)) + MDAT,
    "meta-so-cabecalho-cheio": FTYP + caixa(b"meta", b"\0\0\0\0") + MDAT,
    "meta-1-byte": FTYP + caixa(b"meta", b"\0") + MDAT,
    "meta-zero": FTYP + caixa(b"meta", b"\0\0\0\0", "zero"),
    "meta-muito-grande": FTYP + caixa(b"meta", b"\0\0\0\0", ("longo", 2 ** 63)),
    "meta-sem-versao-com-caixas": FTYP + caixa(b"meta", HDLR + cheia(b"pitm", 0, 0, b"\0\x0a")) + MDAT,
    "zeros": b"\0" * 64,
    "uns": b"\xff" * 64,
}
for nome, v in fora.items():
    fixture(f"fora-{nome}.heic", v)

# Bytes trocados também em três sintéticos que mexem em tudo (índice de 16 bits, ids de 32, ipma além do fim).
for base in ("indice-alto-flags1", "ids-32bits", "ipma-le-alem-da-caixa", "ipma-antes-da-ipco"):
    dados = sintetico(**casos[base])
    ini = len(FTYP)
    for k in range(30):
        v = bytearray(dados)
        for _ in range(rng.randint(1, 3)):
            v[rng.randrange(ini, len(dados) - len(MDAT))] ^= rng.randrange(1, 256)
        fixture(f"troca-sint-{base}-{k:02d}.heic", bytes(v))

with open(JSON, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"python": sys.version.split()[0], "casos": resultados}, f, ensure_ascii=False, indent=0, sort_keys=True)
com = sum(1 for r in resultados.values() if r["partes"])
tamanho = sum(os.path.getsize(os.path.join(DEST, n)) for n in resultados)
contagem = {}
for r in resultados.values():
    contagem[r["filtro"]] = contagem.get(r["filtro"], 0) + 1
print(f"{len(resultados)} fixtures ({tamanho // 1024} KiB), {com} com giro ou espelho")
for filtro, n in sorted(contagem.items(), key=lambda x: -x[1]):
    print(f"  {n:5d}  {filtro or '(vazio)'}")
