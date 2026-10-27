"""Canal de teste (só no PC do André): um Ciranda-Setup mais novo na pasta de teste aparece
na faixa e o "Atualizar agora" copia e instala, sem apagar o original da pasta.
    CIRANDA_VO=x11 xvfb-run -a python testes/teste_canal_teste.py <pasta-de-midia> <saida>"""
import json
import os
os.environ.setdefault("CIRANDA_IDIOMA_SISTEMA", "pt")  # textos dos testes em português
os.environ.setdefault("CIRANDA_SEM_QUADROS", "1")  # tutorial/novidades têm teste próprio
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-canal")
os.environ["TMPDIR"] = os.path.join(SAIDA, "tmp-canal")
os.makedirs(os.environ["TMPDIR"], exist_ok=True)
tempfile.tempdir = None
dados = os.path.join(os.environ["APPDATA"], "Ciranda")
os.makedirs(dados, exist_ok=True)

from ciranda import VERSAO, atualizacao as A  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    assert cond, msg
    n += 1


def setup(pasta, versao, idade_s=0, conteudo=b"MZ setup de teste"):
    c = os.path.join(pasta, f"Ciranda-Setup-{versao}.exe")
    with open(c, "wb") as f:
        f.write(conteudo)
    t = time.time() - idade_s
    os.utime(c, (t, t))
    return c


# ---------- sem o arquivo de configuração: nada muda (PC de quem baixou do GitHub) ----------
import shutil  # noqa: E402
for velho in os.listdir(dados):  # saída reaproveitada de outra rodada
    caminho_velho = os.path.join(dados, velho)
    shutil.rmtree(caminho_velho) if os.path.isdir(caminho_velho) else os.remove(caminho_velho)
ok(A.pasta_teste(dados) == "", "sem pasta-de-teste.txt tem que dar vazio")
with open(os.path.join(dados, A.ARQ_PASTA_TESTE), "w", encoding="utf-8") as f:
    f.write(r"C:\não\existe" + "\n")
ok(A.pasta_teste(dados) == "", "pasta que não existe tem que dar vazio")

teste = tempfile.mkdtemp(prefix="ciranda-versoes-", dir=SAIDA)
with open(os.path.join(dados, A.ARQ_PASTA_TESTE), "w", encoding="utf-8-sig") as f:
    f.write(f'"{teste}"\n')
ok(A.pasta_teste(dados) == teste, "lê a pasta (com BOM e aspas)")

# ---------- escolha do setup ----------
ok(A.procurar_local(teste, VERSAO, 0) is None, "pasta vazia")
setup(teste, "1.0.0")
setup(teste, VERSAO, idade_s=7200)
with open(os.path.join(teste, "Ciranda-Setup-velho.exe"), "wb") as f:
    f.write(b"x")
r = A.procurar_local(teste, VERSAO, quando_instalou=time.time() - 3600)
ok(r["versao"] == VERSAO and not r["disponivel"], f"mesma versão, arquivo mais velho que a instalação: {r}")
r = A.procurar_local(teste, VERSAO, quando_instalou=time.time() - 3 * 86400)
ok(r["disponivel"], "mesma versão refeita depois da instalação: disponível")
ok(r["notas"] == ["Versão de teste: ainda não publicada no GitHub."], r["notas"])
nova = setup(teste, "9.9.8", conteudo=os.urandom(3_000_000))
with open(nova[:-4] + ".txt", "w", encoding="utf-8") as f:
    f.write("- Canal de teste\n- Rodapé padrão\n")
r = A.procurar_local(teste, VERSAO, quando_instalou=time.time())
ok(r["versao"] == "9.9.8" and r["disponivel"] and r["local"], r)
ok(r["notas"] == ["Canal de teste", "Rodapé padrão"], r["notas"])

# ---------- cópia ----------
prog = []
copia = A.copiar_setup_local(r["setup"], lambda f, t: prog.append((f, t)))
ok(open(copia, "rb").read() == open(nova, "rb").read() and os.path.exists(nova), "copiou e manteve o original")
ok(prog[-1] == (3_000_000, 3_000_000), prog[-1:])
with open(nova + ".sha256", "w") as f:
    f.write("0" * 64 + "  Ciranda-Setup-9.9.8.exe\n")
try:
    A.copiar_setup_local(r["setup"])
    ok(False, ".sha256 errado passou")
except ValueError:
    ok(not os.path.exists(copia + ".part"), "sobrou .part")
import hashlib  # noqa: E402
with open(nova + ".sha256", "w") as f:
    f.write(hashlib.sha256(open(nova, "rb").read()).hexdigest() + "\n")
ok(os.path.exists(A.copiar_setup_local(r["setup"])), ".sha256 certo passa")
print(f"ok: parte 1 ({n} checagens)")

# ---------- tela: GitHub sem novidade, pasta de teste com 9.9.8 ----------
os.environ["CIRANDA_CANAL_TESTE_SEMPRE"] = "1"
os.environ["CIRANDA_API_ATUALIZACAO"] = "http://127.0.0.1:9/fora-do-ar"  # GitHub inacessível
from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from ciranda.janela import QSS, Janela  # noqa: E402

rodou = []
A.rodar_instalador = lambda caminho, versao: rodou.append((caminho, versao))  # não roda .exe no teste
app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
j = Janela([PASTA])
j.resize(1280, 760)
j.show()
log = []


def clique(w):
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(w.width() // 2, w.height() // 2))


def etapa_faixa():
    q = j.quadro
    ok(q.isVisible() and q.tipo == "nova" and "9.9.8" in q.l_titulo.text(), f"quadro: {q.l_titulo.text()!r}")
    ok("Canal de teste" in q.l_corpo.text(), q.l_corpo.text())
    os.system(f"import -window root '{os.path.join(SAIDA, 'canal-teste-quadro.png')}'")
    clique(q.botoes()[-1])  # Atualizar: abre a janela e já começa


def etapa_dialogo():
    d = j._dlg_atualizacao
    ok(d is not None, "janela do canal de teste")


def conferir_depois():
    ok(rodou and rodou[-1][0].endswith("Ciranda-Setup-9.9.8.exe") and rodou[-1][1] == VERSAO, rodou)
    ok(os.path.dirname(rodou[-1][0]) == A.pasta_downloads(), "roda a cópia da pasta temporária")
    ok(os.path.exists(nova), "o setup da pasta de teste continua lá")
    log.append("faixa (teste) → janela → Atualizar agora → copiou e chamou o instalador")
    print("\n".join(log))
    print(f"CANAL TESTE PASSOU ({n} checagens)")


passos = [(5500, etapa_faixa), (1000, etapa_dialogo)]


def rodar(i=0):
    if i >= len(passos):
        return
    ms, fn = passos[i]

    def ex():
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            app.exit(1)
            return
        rodar(i + 1)
    QTimer.singleShot(ms, ex)


rodar()
QTimer.singleShot(30000, lambda: (print("tempo esgotado"), app.exit(1)))
codigo = app.exec()  # o "Atualizar agora" fecha o Ciranda (como no Windows)
if codigo == 0:
    conferir_depois()
sys.exit(codigo)
