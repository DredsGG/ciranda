"""Atualização sozinha e Relatar bug.
Parte 1 (sem tela): versões, notas, limpeza de dados pessoais, endereço do relato,
download com conferência do SHA-256 (servidor local).
Parte 2 (tela): GitHub falso com versão nova -> faixa aparece; clicar abre a janela de
atualização; menu tem "Procurar atualização" e "Relatar bug…"; o relato não leva nomes
de pastas/arquivos; "atualizado: vX -> vY" aparece depois de atualizar.
    CIRANDA_VO=x11 xvfb-run -a python testes/teste_atualizacao.py <pasta-de-midia> <saida>"""
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading
import urllib.parse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-atualizacao")
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.makedirs(os.path.join(os.environ["APPDATA"], "Ciranda"), exist_ok=True)

from ciranda import VERSAO, atualizacao as A, relato as R  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    assert cond, msg
    n += 1


# ---------- versões e notas ----------
ok(A.mais_nova("1.10.0", "1.9.9"), "1.10 > 1.9")
ok(not A.mais_nova("v1.2.0", "1.2.0"), "v1.2.0 == 1.2.0")
ok(not A.mais_nova("1.2.0", "1.3.0"), "mais velha")
ok(A.versao_tupla("lixo") == (0, 0, 0), "versão inválida")
corpo = ("### Install\nDownload **Ciranda-Setup-1.4.0.exe** and run it.\n\nPortable alternative: zip\n\n"
         "## What's new\n- **Auto update**: checks GitHub\n- Bug report with `diagnostics`\n* third\n1. fourth\n")
it = A.itens_das_notas(corpo)
ok(it == ["Auto update: checks GitHub", "Bug report with diagnostics", "third", "fourth"], f"notas {it}")
ok(len(A.itens_das_notas("\n".join(f"- {k}" for k in range(20)))) == 6, "máximo 6 notas")

# ---------- limpeza de dados pessoais ----------
amostra = "\n".join([
    r"não abriu: C:\Users\Fulano\Fotos\Ana Clara\2024 Praia\praia geral.png",
    r'  File "C:\Users\Fulano\AppData\Local\Programs\Ciranda\_internal\ciranda\janela.py", line 12, in tocar',
    r"[cplayer] Playing: D:\Família\Natal 2023\VID_0001.MOV",
    r"  sem acesso: E:\Coisas da Maria\Privado",
    r"rede: \\SERVIDOR\fotos\joão\a.jpg",
    "linux: /home/fulano/Fotos/Ana/x.heic fim",
])
limpo = R.limpar_texto(amostra)
for proibido in ("Fulano", "Ana Clara", "Praia", "praia geral", "Família", "Natal", "VID_0001",
                 "Maria", "Privado", "SERVIDOR", "joão", "fulano", "/home"):
    ok(proibido not in limpo, f"sobrou '{proibido}' em:\n{limpo}")
for esperado in ("<arquivo>.png", "<app>\\janela.py\", line 12", "<arquivo>.mov", "<arquivo>.heic", "<pasta>"):
    ok(esperado in limpo, f"faltou '{esperado}' em:\n{limpo}")

# ---------- endereço do relato ----------
titulo, corpo = R.montar("A tela ficou preta\nao abrir .mov", "Ciranda: v1.3.0\n\nFim do log (ciranda.log):\n"
                         + "\n".join(f"linha {k} " + "x" * 80 for k in range(300)))
ok(titulo == "[Bug] A tela ficou preta", titulo)
url, cortado = R.url_github(titulo, corpo)
ok(len(url) <= R.LIMITE_URL and cortado, f"url {len(url)} cortado={cortado}")
q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
ok(q["title"] == [titulo] and "linha 299" in q["body"][0] and "linha 0 " not in q["body"][0],
   "corta o começo do log, mantém o fim")
url2, c2 = R.url_github(*R.montar("curto", "Ciranda: v1.3.0"))
ok(not c2 and url2.startswith("https://github.com/DredsGG/ciranda/issues/new?title="), url2)
ok("labels" not in url2, "sem labels (quem não tem permissão não pode usar)")

# ---------- download com SHA-256 (servidor local) ----------
servir = tempfile.mkdtemp(prefix="ciranda-srv-")
conteudo = os.urandom(700_000)
with open(os.path.join(servir, "Ciranda-Setup-9.9.9.exe"), "wb") as f:
    f.write(conteudo)
dig = hashlib.sha256(conteudo).hexdigest()


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=servir, **k)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/latest"):
            d = json.dumps({"tag_name": "v9.9.9", "html_url": "https://github.com/DredsGG/ciranda/releases/tag/v9.9.9",
                            "body": "### Install\nx\nPortable alternative: y\n\n- Novidade A\n- Novidade B",
                            "assets": [{"name": "Ciranda-Setup-9.9.9.exe", "size": len(conteudo),
                                        "browser_download_url": BASE + "Ciranda-Setup-9.9.9.exe",
                                        "digest": "sha256:" + dig}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(d)))
            self.end_headers()
            self.wfile.write(d)
            return
        super().do_GET()


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/"
A.BASE_DOWNLOAD = BASE  # o teste baixa do servidor local

info = A.procurar(VERSAO, BASE + "latest")
ok(info["disponivel"] and info["versao"] == "9.9.9" and info["notas"] == ["Novidade A", "Novidade B"], info)
prog = []
caminho = A.baixar_setup(info["setup"], lambda f, t: prog.append((f, t)))
ok(open(caminho, "rb").read() == conteudo and prog[-1] == (len(conteudo), len(conteudo)), "download")
ruim = dict(info["setup"], digest="sha256:" + "0" * 64)
os.remove(caminho)
try:
    A.baixar_setup(ruim)
    ok(False, "SHA errado passou")
except ValueError:
    ok(not os.path.exists(caminho) and not os.path.exists(caminho + ".part"), "SHA errado deixou arquivo")
try:
    A.baixar_setup(dict(info["setup"], url="https://exemplo.com/Ciranda-Setup-9.9.9.exe"))
    ok(False, "endereço de fora passou")
except ValueError:
    ok(True, "")
try:
    A.baixar_setup(dict(info["setup"], digest=""))
    ok(False, "sem SHA passou")
except ValueError:
    ok(True, "")
print(f"ok: parte 1 ({n} checagens)")

# ---------- parte 2: tela ----------
# config de quem atualizou da 1.2.0 (para o aviso "atualizado")
with open(os.path.join(os.environ["APPDATA"], "Ciranda", "config.json"), "w", encoding="utf-8") as f:
    json.dump({"versao_vista": "1.2.0"}, f)
os.environ["CIRANDA_API_ATUALIZACAO"] = BASE + "latest"
os.environ.pop("CIRANDA_SEM_ATUALIZACAO", None)

from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from ciranda.janela import QSS, Janela  # noqa: E402
from ciranda import config  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
abertos = []
import ciranda.dialogos as D  # noqa: E402
D._abrir_url = abertos.append  # não abre navegador no teste
j = Janela([PASTA])
j.resize(1280, 760)
j.show()
log = []


def clique(w):
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(w.width() // 2, w.height() // 2))


def etapa_aviso():
    ok(j.faixa.isVisible() and "1.2.0" in j.l_faixa.text() and VERSAO in j.l_faixa.text(),
       f"aviso de atualizado: {j.l_faixa.text()!r}")
    ok(config.carregar()["versao_vista"] == VERSAO, "versao_vista salva")
    log.append("aviso 'atualizado v1.2.0 → v" + VERSAO + "' ok")


def etapa_faixa():
    ok(j.faixa.isVisible() and "9.9.9" in j.l_faixa.text() and j.b_faixa.isVisible(),
       f"faixa de versão nova: {j.l_faixa.text()!r}")
    os.system(f"import -window root '{os.path.join(SAIDA, 'faixa-atualizacao.png')}'")
    clique(j.b_faixa)


def etapa_dialogo():
    d = j._dlg_atualizacao
    ok(d is not None and d.isVisible(), "janela de atualização não abriu")
    ok(not j.faixa.isVisible(), "faixa continuou")
    ok(d.b_ok.text() == "Baixar no GitHub", f"rodando pelo código: {d.b_ok.text()}")
    os.system(f"import -window root '{os.path.join(SAIDA, 'dialogo-atualizacao.png')}'")
    clique(d.b_ok)
    ok(abertos and abertos[-1].endswith("v9.9.9") and not d.isVisible(), f"página: {abertos}")
    log.append("faixa → janela → Baixar no GitHub ok")
    j._montar_menu_abrir()
    nomes = [a.text().split("\t")[0] for a in j.menu_abrir.actions()]
    ok("Procurar atualização" in nomes and "Relatar bug…" in nomes, f"menu: {nomes}")
    clique(j.b_abrir)  # pastinha da barra, como o usuário

    def no_menu():
        ok(j.menu_abrir.isVisible(), "menu da pastinha não abriu")
        os.system(f"import -window root '{os.path.join(SAIDA, 'menu-ajuda.png')}'")
        alvo = [a for a in j.menu_abrir.actions() if a.text().startswith("Relatar bug")][0]
        QTest.mouseClick(j.menu_abrir, Qt.LeftButton, Qt.NoModifier, j.menu_abrir.actionGeometry(alvo).center())
    QTimer.singleShot(600, no_menu)


def etapa_bug():
    d = getattr(j, "_dlg_bug", None)
    ok(d is not None and d.isVisible(), "Relatar bug não abriu pelo menu")
    diag = d.previa.toPlainText()
    for proibido in ("Aniversário", "Viagem", os.path.basename(PASTA), "claude", "/home"):
        ok(proibido not in diag, f"diagnóstico tem '{proibido}'")
    ok(f"v{VERSAO}" in diag and "Fila:" in diag and "Modos:" in diag, diag[:400])
    d.texto.setPlainText("Teste: a foto não passou")
    os.system(f"import -window root '{os.path.join(SAIDA, 'dialogo-bug.png')}'")
    clique(d.b_git)
    ok(abertos[-1].startswith(R.NOVO) and len(abertos[-1]) <= R.LIMITE_URL, abertos[-1][:120])
    corpo = urllib.parse.parse_qs(urllib.parse.urlparse(abertos[-1]).query)["body"][0]
    ok("Teste: a foto não passou" in corpo and "Diagnóstico" in corpo, corpo[:300])
    clique(d.b_copiar)
    ok("Teste: a foto não passou" in QApplication.clipboard().text(), "copiar")
    d.reject()
    log.append(f"Relatar bug pelo menu ok (url {len(abertos[-1])} caracteres, sem nomes)")
    print("\n".join(log))
    print(f"ATUALIZACAO PASSOU ({n} checagens)")
    app.quit()


passos = [(1500, etapa_aviso), (4500, etapa_faixa), (1000, etapa_dialogo), (1500, etapa_bug)]


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
QTimer.singleShot(40000, lambda: (print("tempo esgotado"), app.exit(1)))
sys.exit(app.exec())
