"""Testes da varredura e da fila (sem interface). Rodar:
    python testes/teste_logica.py [pasta-de-midia-de-teste]
A pasta é opcional; sem ela, só os testes da fila rodam."""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ciranda.biblioteca import Item, chave_natural, varrer, varrer_varios  # noqa: E402
from ciranda.fila import Fila  # noqa: E402

ok = 0


def check(cond, msg):
    global ok
    if not cond:
        raise AssertionError(msg)
    ok += 1


def itens_falsos(nf=6, nv=4):
    its = [Item(f"/x/f{i}.jpg", "foto", "/x", "", f"f{i}.jpg", ".jpg") for i in range(nf)]
    its += [Item(f"/x/v{i}.mp4", "video", "/x", "sub", f"v{i}.mp4", ".mp4") for i in range(nv)]
    return its


def teste_ordem_natural():
    nomes = ["foto10.jpg", "foto2.jpg", "Foto1.jpg", "a.jpg"]
    check(sorted(nomes, key=chave_natural) == ["a.jpg", "Foto1.jpg", "foto2.jpg", "foto10.jpg"], "ordem natural")


def teste_em_ordem_repetir_nada():
    f = Fila()
    f.repetir = "nao"
    f.definir_itens(itens_falsos())
    vistos = []
    it = f.proximo()
    while it:
        vistos.append(it.nome)
        it = f.proximo(automatico=True)
    check(len(vistos) == 10, "em ordem toca os 10")
    check(vistos[0] == "f0.jpg" and vistos[-1] == "v3.mp4", "em ordem começa e termina certo")
    check(f.proximo() is None, "fim sem repetir")


def teste_baralho_sem_repetir():
    f = Fila(semente=1)
    f.repetir = "tudo"
    f.aleatorio = True
    f.definir_itens(itens_falsos())
    for rodada in range(50):
        vistos = [f.proximo(automatico=True).caminho for _ in range(10)]
        check(len(set(vistos)) == 10, f"rodada {rodada}: cada item uma vez por rodada")
    # o último de uma rodada não abre a próxima
    f2 = Fila(semente=7)
    f2.aleatorio = True
    f2.definir_itens(itens_falsos(3, 0))
    anterior = None
    for _ in range(300):
        it = f2.proximo(automatico=True)
        check(it.caminho != anterior, "nunca o mesmo item duas vezes seguidas")
        anterior = it.caminho


def teste_aleatorio_distribui():
    c = Counter()
    for s in range(400):
        f = Fila(semente=s)
        f.aleatorio = True
        f.definir_itens(itens_falsos())
        c[f.proximo().nome] += 1
    check(len(c) == 10 and min(c.values()) > 15, f"primeiro item varia: {c}")


def teste_repetir_um():
    f = Fila()
    f.repetir = "um"
    f.definir_itens(itens_falsos())
    a = f.proximo()
    check(f.proximo(automatico=True) is a, "repetir um repete no automático")
    check(f.proximo(automatico=False) is not a, "botão próximo sai do repetir um")


def teste_filtro():
    f = Fila()
    f.definir_itens(itens_falsos())
    f.proximo()  # f0
    check(f.definir_filtro("videos") is False, "foto atual sai com filtro vídeos")
    check(len(f) == 4, "só vídeos")
    check(f.proximo().tipo == "video", "próximo é vídeo")
    check(f.definir_filtro("tudo") is True, "vídeo atual fica com filtro tudo")
    check(len(f) == 10, "volta tudo")


def teste_alternar_aleatorio_mantem_atual():
    f = Fila(semente=3)
    f.definir_itens(itens_falsos())
    for _ in range(4):
        atual = f.proximo()
    f.definir_aleatorio(True)
    check(f.atual is atual and f.posicao()[0] == 1, "ligar aleatório mantém o atual no topo")
    f.definir_aleatorio(False)
    check(f.atual is atual and f.posicao()[0] == 4, "desligar volta para a posição dele")


def teste_anterior_e_ir_para():
    f = Fila()
    f.repetir = "tudo"
    f.definir_itens(itens_falsos())
    f.proximo()
    check(f.anterior().nome == "v3.mp4", "anterior no começo com repetir tudo vai pro fim")
    check(f.ir_para(2).nome == "f2.jpg", "ir para")
    check(f.proximo().nome == "f3.jpg", "segue do escolhido")


def teste_falhou_pula():
    f = Fila()
    its = itens_falsos(3, 0)
    its[1].falhou = True
    f.definir_itens(its)
    check([f.proximo().nome, f.proximo().nome] == ["f0.jpg", "f2.jpg"], "pula o que falhou")
    for i in its:
        i.falhou = True
    check(f.proximo() is None, "tudo falhou -> None, sem laço infinito")


def teste_adicionar_e_remover():
    f = Fila(semente=2)
    f.aleatorio = True
    f.definir_itens(itens_falsos(4, 0))
    a = f.proximo()
    novos = [Item(f"/y/n{i}.jpg", "foto", "/y", "", f"n{i}.jpg", ".jpg") for i in range(5)]
    f.adicionar(novos)
    check(f.atual is a and len(f) == 9, "adicionar não troca o atual")
    resto = [f.proximo(automatico=True).nome for _ in range(8)]
    check(len(set(resto)) == 8 and a.nome not in resto, "novos entram no resto da rodada")
    f.remover([f.indice_atual])
    check(len(f) == 8 and f.proximo() is not None, "remover o atual segue a fila")


def teste_varredura(pasta):
    its = varrer(pasta)
    nomes = [os.path.join(i.pasta_rel, i.nome).replace("\\", "/") for i in its]
    check(".oculta/nao-deve-aparecer.mp4" in nomes, "pasta oculta também entra (abre tudo)")
    check(nomes[:2] == ["abertura.mp4", "capa.jpg"], f"arquivos da raiz primeiro: {nomes[:3]}")
    i2 = nomes.index("2024 Praia/Dia 1/foto2.jpg")
    i10 = nomes.index("2024 Praia/Dia 1/foto10.jpg")
    check(i2 < i10, "foto2 antes de foto10")
    check(len(its) == 16, f"16 arquivos de mídia achados, achou {len(its)}: {nomes}")
    check(sum(i.tipo == "video" for i in its) == 7, "7 vídeos (inclui o corrompido e o da pasta oculta)")
    dup = varrer_varios([pasta, os.path.join(pasta, "Aniversário")])
    check(len(dup) == 16, "pasta dentro de pasta não duplica")
    um = varrer(os.path.join(pasta, "capa.jpg"))
    check(len(um) == 1 and um[0].tipo == "foto", "arquivo solto")


def teste_muitas_pastas():
    """84 pastas soltas (como arrastar 84 pastas de uma vez), cada uma com
    arquivos na raiz e 3 níveis de subpasta, mais lixo de outros tipos."""
    import tempfile
    base = tempfile.mkdtemp(prefix="ciranda-84-")
    raizes = []
    for k in range(84):
        r = os.path.join(base, f"Pasta {k:02d}")
        fundo = os.path.join(r, "a", "b", "c")
        os.makedirs(fundo)
        for nome in ("x.jpg", "y.MP4", "z.HEIC", "leia.txt", "desktop.ini"):
            open(os.path.join(r, nome), "w").close()
        open(os.path.join(fundo, "fundo.mov"), "w").close()
        raizes.append(r)
    stats = {}
    its = varrer_varios(raizes, stats=stats)
    check(len(its) == 84 * 4, f"84 pastas: esperado {84 * 4}, achou {len(its)}")
    check(len({os.path.dirname(i.caminho) for i in its}) == 84 * 2, "pastas com mídia contadas")
    check(stats["pastas_lidas"] == 84 * 4, f"pastas lidas {stats['pastas_lidas']}")
    check(stats["ignorados"][".txt"] == 84 and stats["ignorados"][".ini"] == 84, "outros tipos contados")
    # profundidade grande, sem estourar recursão
    fundo = os.path.join(base, "fundo")
    p = fundo
    for k in range(400):
        p = os.path.join(p, "d")
    try:
        os.makedirs(p)
        open(os.path.join(p, "lá-no-fundo.jpg"), "w").close()
        check(len(varrer(fundo)) == 1, "400 níveis de subpasta")
    except (OSError, RecursionError):
        pass  # caminho longo demais para o sistema de arquivos: ok
    import shutil
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("teste_") and nome != "teste_varredura":
            fn()
    if len(sys.argv) > 1:
        teste_varredura(sys.argv[1])
    print(f"TUDO PASSOU ({ok} verificações)")
