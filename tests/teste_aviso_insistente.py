"""Regra 14 (27/10, 20h): aviso de versão nova automático e insistente, com o Ciranda já aberto.
GitHub falso que muda durante o teste. Tempos encurtados por variável (30 min → 3 s, 10 min → 2 s,
1 h de adiamento → 4 s); a lógica é a mesma do app de verdade.
  1. abre sem versão nova: nada aparece;
  2. sai um Release novo: o quadro "Nova versão" aparece sozinho, sem reabrir, por cima do que toca;
  3. X adia: some, a conferida seguinte não mostra, e volta sozinho depois do adiamento;
  4. voltar para a janela confere de novo (no máximo 1 vez por intervalo mínimo);
  5. Release "URGENTE": quadro sem X (Esc não fecha), player pausado e Tocar/Próximo bloqueados.
    CIRANDA_VO=x11 xvfb-run -a python testes/teste_aviso_insistente.py <pasta-de-midia> <saida>"""
import http.server
import json
import os
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-aviso")
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ.setdefault("CIRANDA_IDIOMA_SISTEMA", "pt")
os.environ["CIRANDA_SEM_QUADROS"] = "1"
os.environ["CIRANDA_INTERVALO_ATUALIZACAO_S"] = "3"
os.environ["CIRANDA_FOCO_MIN_S"] = "2"
os.environ["CIRANDA_ADIAMENTO_S"] = "4"
os.environ.pop("CIRANDA_SEM_ATUALIZACAO", None)
dados = os.path.join(os.environ["APPDATA"], "Ciranda")
os.makedirs(dados, exist_ok=True)
for f in os.listdir(dados):
    if os.path.isfile(os.path.join(dados, f)):
        os.remove(os.path.join(dados, f))

from ciranda import VERSAO  # noqa: E402

GITHUB = {"tag": "v" + VERSAO, "nome": "v" + VERSAO}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/raw/"):
            d = json.dumps({GITHUB["tag"][1:]: {"pt": ["Novidade em português"], "en": ["News"], "es": ["Novedad"]}})
        else:
            d = json.dumps({"tag_name": GITHUB["tag"], "name": GITHUB["nome"],
                            "html_url": "https://github.com/DredsGG/ciranda/releases/tag/" + GITHUB["tag"],
                            "body": "- nota", "assets": []})
        b = d.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/"
os.environ["CIRANDA_API_ATUALIZACAO"] = BASE + "latest"
os.environ["CIRANDA_RAW_NOVIDADES"] = BASE + "raw/{tag}/novidades.json"

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from ciranda import config  # noqa: E402
import ciranda.dialogos as D  # noqa: E402
from ciranda.janela import QSS, Janela  # noqa: E402

D._abrir_url = lambda url: None  # não abre navegador
app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
j = Janela([PASTA])
j.resize(1280, 760)
j.move(0, 0)
j.show()
n = 0
log = []
estado = {}


def ok(cond, msg):
    global n
    assert cond, msg
    n += 1


def foto(nome):
    os.system(f"import -window root -crop 1280x760+0+0 +repage '{os.path.join(SAIDA, nome)}'")


def passo_sem_novidade():
    ok(j._conferidas >= 1, "não conferiu ao abrir")
    ok(not j.quadro.isVisible(), "quadro sem versão nova")
    ok(j._item is not None, "não está tocando")
    estado["conferidas"] = j._conferidas
    GITHUB.update(tag="v9.9.9", nome="v9.9.9")  # sai um Release novo com o Ciranda aberto
    log.append("abre sem novidade: nada aparece")


def passo_apareceu():
    q = j.quadro
    ok(j._conferidas > estado["conferidas"], "não conferiu de novo sozinho")
    ok(q.isVisible() and q.tipo == "nova" and "9.9.9" in q.l_titulo.text(), f"quadro não apareceu: {q.l_titulo.text()!r}")
    ok(q.b_x.isVisible() and j._item is not None, "quadro normal tem X e o player segue")
    foto("aviso-nova-versao-tocando.png")
    QTest.mouseClick(q.b_x, Qt.LeftButton)
    ok(not q.isVisible(), "X não fechou")
    c = config.carregar()
    ok(c["aviso_adiado_versao"] == "9.9.9" and c["aviso_adiado_ate"] > time.time() + 2, "X não adiou")
    estado["adiou"] = time.monotonic()
    log.append("Release novo com o app aberto: quadro aparece sozinho (sem reabrir); X adia")


def passo_ainda_adiado():
    # passou uma conferida de 30 min (3 s) dentro do adiamento: não pode voltar
    ok(time.monotonic() - estado["adiou"] < 4, "teste atrasou")
    ok(not j.quadro.isVisible(), "aviso voltou antes do fim do adiamento")


def passo_voltou():
    ok(j.quadro.isVisible() and j.quadro.tipo == "nova", "aviso não voltou depois do adiamento")
    log.append("X só adia: não volta antes, volta sozinho depois de 1 h (4 s no teste)")
    j.quadro.hide()
    j._quadro_render = None
    # voltar para a janela: confere se já passou o mínimo; senão, não
    antes = j._conferidas
    j._ultima_conferida = time.monotonic()
    j.isActiveWindow = lambda: True  # Xvfb sem gerenciador de janelas: simula a janela ativa
    QApplication.sendEvent(j, QEvent(QEvent.ActivationChange))  # o mesmo evento de quando a pessoa volta
    ok(j._conferidas == antes, "conferiu ao voltar para a janela antes do mínimo")
    j._ultima_conferida = time.monotonic() - 2.5
    QApplication.sendEvent(j, QEvent(QEvent.ActivationChange))
    ok(j._conferidas == antes + 1, "não conferiu ao voltar para a janela")
    log.append("voltar para a janela confere (no máximo 1 vez a cada 10 min; 2 s no teste)")
    GITHUB.update(tag="v9.9.10", nome="v9.9.10 URGENTE")


def passo_urgente():
    q = j.quadro
    ok(j._urgente and q.isVisible() and q.tipo == "nova", "quadro urgente não apareceu")
    ok(not q.b_x.isVisible(), "urgente com X")
    ok("urgente" in q.l_titulo.text().lower(), q.l_titulo.text())
    ok(bool(j.mpv.pause), "player não pausou")
    QTest.keyClick(q, Qt.Key_Escape)
    ok(q.isVisible(), "Esc fechou o urgente")
    j.alternar_pausa()
    ok(bool(j.mpv.pause) and q.isVisible(), "Tocar destravou o urgente")
    item = j._item
    j.proximo()
    ok(j._item is item and bool(j.mpv.pause), "Próximo passou de arquivo no urgente")
    foto("aviso-urgente.png")
    log.append("URGENTE: sem X, Esc não fecha, player pausado, Tocar/Próximo bloqueados")
    QTest.mouseClick(q.botoes()[-1], Qt.LeftButton)  # Atualizar: abre a janela de atualizar
    estado["dlg"] = j._dlg_atualizacao


def passo_urgente_continua():
    ok(estado["dlg"] is not None, "Atualizar não abriu a janela de atualização")
    ok(j.quadro.isVisible() and bool(j.mpv.pause), "urgente sumiu sem atualizar")
    log.append("Atualizar leva para a atualização; o quadro urgente fica até atualizar")
    print("\n".join(log))
    print(f"AVISO INSISTENTE PASSOU ({n} checagens)")
    app.quit()


passos = [(5000, passo_sem_novidade), (3600, passo_apareceu), (2600, passo_ainda_adiado), (2600, passo_voltou),
          (3600, passo_urgente), (1500, passo_urgente_continua)]


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
QTimer.singleShot(60000, lambda: (print("tempo esgotado"), app.exit(1)))
sys.exit(app.exec())
