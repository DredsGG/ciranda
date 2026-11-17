"""Varredura da 1.5.1 (ciranda/biblioteca.py, main 304bc21) contra a do núcleo em Rust, nas
mesmas pastas: o resultado tem que ser idêntico (item por item, na mesma ordem, e as contas de
pastas lidas, outros tipos, sem acesso e puladas) e o tempo é medido nas duas.

    python -I rust/ferramentas/comparar_varredura.py <exe-do-exemplo-varrer> <saida.json> [pastas...]
Sem pastas: monta a árvore de teste (montar_arvore) em %APPDATA%\\Ciranda-rust-prova\\arvore.
Só lê as pastas. A árvore de teste é a única coisa que ele cria (e recria a cada vez).
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
from ciranda.biblioteca import varrer_varios  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
RODADAS = 3


def montar_arvore(base):
    """~60 mil arquivos em ~2.600 pastas, com tudo que a varredura trata de jeito especial."""
    if os.path.isdir(base):
        # Junções primeiro (rmdir tira só a junção, nunca o destino).
        for raiz, pastas, _ in os.walk(base):
            for p in list(pastas):
                c = os.path.join(raiz, p)
                if os.path.isjunction(c) or os.path.islink(c):
                    os.rmdir(c)
                    pastas.remove(p)  # não desce pelo link
        shutil.rmtree(base)
    nomes = ["IMG_{:04d}.JPG", "foto{}.jpg", "Foto {} (cópia).png", "vídeo{}.mp4", "clipe_{:03d}.MKV", "ß{}.heic",
             "Σ{}.gif", "leia{}.txt", "desktop{}.ini", "._foto{}.jpg", "semext{}", ".jpg{}", "a..b{}.webp", "٣{}.mov",
             "１２x{}.avif", "x{}.dvr-ms"]
    n = 0
    for a in range(40):
        for b in range(16):
            for c in range(4):
                d = os.path.join(base, f"Ano {2000 + a}", f"Mês {b + 1}", f"Dia {c * 7 + 1:02d}")
                os.makedirs(d, exist_ok=True)
                for k in range(6):
                    nome = nomes[(a + b + c + k) % len(nomes)].format(k * 37 + c)
                    with open(os.path.join(d, nome), "wb"):
                        pass
                    n += 1
    for esp in ["$RECYCLE.BIN", "System Volume Information", "node_modules", ".git", "Windows.old", ".oculta",
                "Vazia", "__pycache__", ".thumbnails"]:
        d = os.path.join(base, esp)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "dentro.jpg"), "wb"):
            pass
    fundo = os.path.join(base, "fundo")
    p = fundo
    for _ in range(400):
        p = os.path.join(p, "d")
    os.makedirs(p)
    with open(os.path.join(p, "lá-no-fundo.jpg"), "wb"):
        pass
    # Junções (não pedem administrador): laço para a raiz, atalho para uma irmã, duas para o
    # mesmo lugar, e uma quebrada.
    ok = []

    # O destino vai pelo caminho real: rodando de dentro do app Claude (pacote MSIX), o
    # %APPDATA% é redirecionado e uma junção para o caminho "de fora" fica quebrada.
    real = os.path.realpath(base)

    def juncao(link, *alvo):
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link, os.path.join(real, *alvo)], capture_output=True)
        ok.append(r.returncode == 0)

    juncao(os.path.join(base, "Ano 2001", "laço para a raiz"))
    juncao(os.path.join(base, "atalho Ano 2003"), "Ano 2003")
    juncao(os.path.join(base, "atalho A"), "Ano 2005", "Mês 2")
    juncao(os.path.join(base, "atalho B"), "Ano 2005", "Mês 2")
    os.makedirs(os.path.join(base, "some"))
    juncao(os.path.join(base, "quebrada 1"), "some")
    juncao(os.path.join(base, "quebrada 2"), "some")
    os.rmdir(os.path.join(base, "some"))
    links = 0
    try:  # link simbólico pede o modo de desenvolvedor ou administrador
        os.symlink(os.path.join(real, "Ano 2007"), os.path.join(base, "link Ano 2007"), target_is_directory=True)
        os.symlink(os.path.join(real, "Ano 2008", "Mês 1", "Dia 01", "nao-existe.jpg"), os.path.join(base, "link quebrado.jpg"))
        os.symlink(os.path.join(real, "Ano 2009", "Mês 1", "Dia 01"), os.path.join(base, "Ano 2010", "link relativo"),
                   target_is_directory=True)
        links = 3
    except OSError:
        pass
    return n + 10, sum(ok), links


def rodar_python(caminhos):
    stats = {}
    t0 = time.perf_counter()
    itens = varrer_varios(caminhos, stats=stats)
    dt = time.perf_counter() - t0
    return dt, {
        "itens": [[i.caminho, i.tipo, i.raiz, i.pasta_rel, i.nome, i.ext] for i in itens],
        "pastas_lidas": stats["pastas_lidas"],
        # Lista de pares, não dict: a ordem de inserção do Counter também tem de ser a mesma.
        "ignorados": [[k, n] for k, n in stats["ignorados"].items()],
        "sem_acesso": stats["sem_acesso"],
        "puladas": stats["puladas"],
    }


def rodar_rust(exe, caminhos, tmp):
    subprocess.run([exe, tmp, *caminhos], check=True, capture_output=True)
    with open(tmp, encoding="utf-8") as f:
        r = json.load(f)
    r["ignorados"] = [[k, n] for k, n in r["ignorados"].items()]  # o json.load guarda a ordem do arquivo
    return r.pop("segundos"), r


def comparar(a, b):
    difs = []
    for k in ("pastas_lidas", "ignorados", "sem_acesso", "puladas"):
        if a[k] != b[k]:
            difs.append(k)
    if a["itens"] != b["itens"]:
        i = next((i for i, (x, y) in enumerate(zip(a["itens"], b["itens"])) if x != y), min(len(a["itens"]), len(b["itens"])))
        difs.append(f"itens (1.5.1 {len(a['itens'])}, Rust {len(b['itens'])}; primeira diferença na posição {i})")
    return difs


def main():
    exe, saida, *pastas = sys.argv[1:]
    resultado = {"rodadas": RODADAS, "casos": []}
    if not pastas:
        base = os.path.join(os.environ["APPDATA"], "Ciranda-rust-prova", "arvore")
        arquivos, juncoes, links = montar_arvore(base)
        resultado["arvore"] = {"arquivos": arquivos, "juncoes": juncoes, "links_simbolicos": links}
        print(f"árvore: {arquivos} arquivos, {juncoes} junções, {links} links simbólicos")
        casos = [("árvore de teste", [base]), ("árvore de teste, com barra no fim", [base + "\\"])]
    else:
        casos = [(p, [p]) for p in pastas]
    tmp = saida + ".rust.json"
    for nome, caminhos in casos:
        py, rs = [], []
        ref = res = None
        for _ in range(RODADAS):  # alterna para nenhum dos dois ganhar só pelo cache do disco
            dt, ref = rodar_python(caminhos)
            py.append(dt)
            dt, res = rodar_rust(exe, caminhos, tmp)
            rs.append(dt)
        difs = comparar(ref, res)
        caso = {
            "pasta": nome, "itens": len(ref["itens"]), "pastas_lidas": ref["pastas_lidas"],
            "outros_tipos": sum(n for _, n in ref["ignorados"]), "sem_acesso": len(ref["sem_acesso"]),
            "puladas": len(ref["puladas"]), "python_s": [round(x, 3) for x in py], "rust_s": [round(x, 3) for x in rs],
            "python_mediana_s": round(statistics.median(py), 3), "rust_mediana_s": round(statistics.median(rs), 3),
            "igual": not difs, "diferencas": difs,
        }
        caso["vezes_mais_rapido"] = round(caso["python_mediana_s"] / max(caso["rust_mediana_s"], 1e-6), 1)
        resultado["casos"].append(caso)
        print(json.dumps(caso, ensure_ascii=False))
        if difs:
            with open(saida + ".diferenca.json", "w", encoding="utf-8") as f:
                json.dump({"python": ref, "rust": res}, f, ensure_ascii=False)
    os.remove(tmp)
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)


main()
