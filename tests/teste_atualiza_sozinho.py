"""1.4.0: o Ciranda instalado se atualiza sozinho, sem clique, e volta de onde parou.
GitHub falso com o setup de verdade (bytes + SHA-256). O instalador e a saída do app são trocados
por registros (no Linux não há instalador do Windows); o resto é o código do app.
  1. tocando: sai versão nova → baixa e confere sozinho, NÃO fecha; quadro "baixada" no meio;
  2. o vídeo acaba e vai para o próximo → instala (com reabrir) e guarda "voltar no próximo, do começo";
  3. pausado → instala depois de 1 s pausado; guarda arquivo, ponto do vídeo e "pausado";
  4. URGENTE → baixa e instala na hora;
  5. fechar o Ciranda com versão baixada → instala sem reabrir;
  6. (outro processo) abriu pelo instalador → mesma fila, mesmo arquivo, mesmo ponto, pausado;
     depois, nada tocando + versão nova → instala na hora.
    CIRANDA_VO=x11 xvfb-run -a python testes/teste_atualiza_sozinho.py <pasta-de-midia> <saida>"""
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
PASTA_ORIG, SAIDA = sys.argv[1], sys.argv[2]
FASE = sys.argv[3] if len(sys.argv) > 3 else "principal"
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-sozinho")
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ.setdefault("CIRANDA_IDIOMA_SISTEMA", "pt")
os.environ["CIRANDA_SEM_QUADROS"] = "1"
os.environ["CIRANDA_INTERVALO_ATUALIZACAO_S"] = "3600"
os.environ["CIRANDA_PAUSA_INSTALA_S"] = "1"
os.environ["CIRANDA_ESPERA_SAIR_MS"] = "100"
os.environ.pop("CIRANDA_SEM_ATUALIZACAO", None)
dados = os.path.join(os.environ["APPDATA"], "Ciranda")
os.makedirs(dados, exist_ok=True)

# pasta com 3 vídeos de 20 s (ordem fixa: aleatório desligado)
PASTA = os.path.join(SAIDA, "videos-sozinho")
if FASE == "principal":
    for f in os.listdir(dados):
        if os.path.isfile(os.path.join(dados, f)):
            os.remove(os.path.join(dados, f))
    shutil.rmtree(PASTA, ignore_errors=True)
    os.makedirs(PASTA)
    for n, cor in (("a", "red"), ("b", "green"), ("c", "blue")):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={cor}:s=320x240:d=20:r=25",
                        "-pix_fmt", "yuv420p", os.path.join(PASTA, f"{n}.mp4")], check=True)
    with open(os.path.join(dados, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"aleatorio": False, "repetir": "tudo", "tutorial_visto": True, "versao_vista": "x"}, f)

from ciranda import VERSAO  # noqa: E402
import ciranda.atualizacao as A  # noqa: E402

SETUPS = {}
for v in ("9.9.9", "9.9.10", "9.9.11"):
    b = os.urandom(300_000)
    SETUPS[v] = (b, hashlib.sha256(b).hexdigest())
GITHUB = {"versao": VERSAO, "nome": "v" + VERSAO}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/raw/"):
            d = json.dumps({GITHUB["versao"]: {"pt": ["Novidade"], "en": ["News"], "es": ["Novedad"]}}).encode()
        elif self.path.startswith("/dl/"):
            v = self.path.split("Ciranda-Setup-")[1][:-4]
            d = SETUPS[v][0]
        else:
            v = GITHUB["versao"]
            assets = []
            if v in SETUPS:
                assets = [{"name": f"Ciranda-Setup-{v}.exe", "size": len(SETUPS[v][0]),
                           "browser_download_url": BASE + f"dl/Ciranda-Setup-{v}.exe",
                           "digest": "sha256:" + SETUPS[v][1]}]
            d = json.dumps({"tag_name": "v" + v, "name": GITHUB["nome"],
                            "html_url": "https://github.com/DredsGG/ciranda/releases/tag/v" + v,
                            "body": "- nota", "assets": assets}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(d)))
        self.end_headers()
        self.wfile.write(d)


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/"
os.environ["CIRANDA_API_ATUALIZACAO"] = BASE + "latest"
os.environ["CIRANDA_RAW_NOVIDADES"] = BASE + "raw/{tag}/novidades.json"
A.BASE_DOWNLOAD = BASE + "dl/"
A.instalado = lambda: True  # como o Ciranda instalado pelo Setup
INSTALADOR = []  # (caminho, versão de onde sai, reabrir)
A.rodar_instalador = lambda caminho, versao, relancar=True: INSTALADOR.append((caminho, versao, relancar))

if FASE == "retomar":
    sys.argv.append("--atualizado-de=1.3.1")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from ciranda import config  # noqa: E402
from ciranda.janela import QSS, Janela  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setQuitOnLastWindowClosed(False)
app.setStyleSheet(QSS)
j = Janela([PASTA] if FASE == "principal" else [])
j.resize(1280, 760)
j.move(0, 0)
j.show()
SAIU = []
j._sair_para_atualizar = lambda: SAIU.append(time.monotonic())  # no app de verdade: fecha e o instalador reabre
n = 0
log = []
estado = {}


def ok(cond, msg):
    global n
    assert cond, msg
    n += 1


def foto(nome):
    os.system(f"import -window root -crop 1280x760+0+0 +repage '{os.path.join(SAIDA, nome)}'")


def nome_atual():
    return os.path.basename(j._item.caminho) if j._item else None


def zerar():
    """Depois de cada 'instalação' de mentira: o app continua aberto para o próximo caso."""
    INSTALADOR.clear()
    SAIU.clear()
    j._instalando = False
    j._setup_pronto = None
    j._info_atualizacao = None
    j.cfg["retomar"] = {}
    j.cfg["aviso_adiado_versao"] = ""
    j.quadro.hide()
    j._quadro_render = None


# ------------------------------------------------------------------ fase principal
def p_tocando():
    ok(nome_atual() == "a.mp4" and not j.mpv.pause, f"não está tocando a.mp4: {nome_atual()}")
    GITHUB.update(versao="9.9.9", nome="v9.9.9")
    j.procurar_atualizacao()  # a mesma conferida dos 30 min / da volta para a janela
    log.append("tocando a.mp4; sai a v9.9.9 no GitHub")


def p_baixou_nao_fechou():
    ok(j._setup_pronto and j._setup_pronto[0] == "9.9.9", f"não baixou sozinho: {j._setup_pronto}")
    caminho = j._setup_pronto[1]
    ok(A.sha256_arquivo(caminho) == SETUPS["9.9.9"][1], "setup baixado diferente do publicado")
    ok(not INSTALADOR and not SAIU, "instalou no meio do vídeo")
    ok(not j.mpv.pause and nome_atual() == "a.mp4", "parou o vídeo")
    q = j.quadro
    ok(q.isVisible() and q.tipo == "pronta" and "9.9.9" in q.l_titulo.text(), f"quadro 'baixada' não apareceu: {q.tipo}")
    foto("sozinho-baixada-tocando.png")
    log.append("baixou e conferiu o SHA-256 sozinho, sem clique; continuou tocando; quadro 'baixada' no meio")
    j.mpv.command("seek", "18.5", "absolute")  # leva o vídeo para perto do fim


def p_fim_do_arquivo():
    ok(INSTALADOR and INSTALADOR[-1][2] is True and INSTALADOR[-1][1] == VERSAO,
       f"não instalou na troca de arquivo: {INSTALADOR}")
    ok(INSTALADOR[-1][0] == j._setup_pronto[1], "instalou outro arquivo")
    ok(SAIU, "não fechou para instalar")
    r = config.carregar()["retomar"]
    ok(os.path.basename(r.get("arquivo", "")) == "b.mp4" and r["pos"] == 0 and not r["pausado"],
       f"retomar errado no fim do arquivo: {r}")
    ok(r["caminhos"] == [PASTA], r)
    log.append("a.mp4 acabou → instalou na troca e guardou 'voltar em b.mp4, do começo'")
    zerar()
    # caso 3: pausado
    j.tocar(j.fila.itens[1])
    estado["t"] = time.monotonic()


def p_pausa_prepara():
    j.mpv.command("seek", "7", "absolute")
    GITHUB.update(versao="9.9.10", nome="v9.9.10")
    j.procurar_atualizacao()


def p_pausa_baixou():
    ok(j._setup_pronto and j._setup_pronto[0] == "9.9.10" and not INSTALADOR, f"{j._setup_pronto} {INSTALADOR}")
    j.alternar_pausa()  # a pessoa pausa
    ok(j.mpv.pause, "não pausou")
    estado["pos_pausa"] = float(j.mpv.time_pos or 0)


def p_pausa_instalou():
    ok(INSTALADOR and INSTALADOR[-1][2] is True, f"não instalou pausado: {INSTALADOR}")
    r = config.carregar()["retomar"]
    ok(os.path.basename(r["arquivo"]) == "b.mp4" and r["pausado"] and r["pos"] > 6
       and abs(r["pos"] - estado["pos_pausa"]) < 0.5, f"retomar pausado: {r} (pausou em {estado['pos_pausa']})")
    estado["retomar_pausado"] = r
    log.append(f"pausou em b.mp4 ({r['pos']:.1f} s) → instalou depois de 1 s pausado e guardou o ponto")
    zerar()
    j.alternar_pausa()  # volta a tocar
    GITHUB.update(versao="9.9.11", nome="v9.9.11 URGENTE")
    j.procurar_atualizacao()


def p_urgente():
    ok(j._urgente, "urgente não travou")
    ok(INSTALADOR and j._setup_pronto[0] == "9.9.11", f"urgente não instalou na hora: {INSTALADOR}")
    log.append("URGENTE tocando → baixou e instalou na hora")
    INSTALADOR.clear()
    SAIU.clear()
    j._instalando = False  # simula a pessoa ainda com o app aberto (o instalador falhou, por ex.)
    j._urgente = False
    j.quadro.hide()
    j.close()  # fechar com versão baixada


def p_fechar():
    ok(INSTALADOR and INSTALADOR[-1][2] is False and INSTALADOR[-1][0] == j._setup_pronto[1],
       f"não instalou ao fechar (ou reabriu): {INSTALADOR}")
    log.append("fechou o Ciranda com versão baixada → instalou sem reabrir")
    with open(os.path.join(SAIDA, "retomar.json"), "w", encoding="utf-8") as f:
        json.dump(estado["retomar_pausado"], f)
    print("\n".join(log))
    print(f"PRINCIPAL PASSOU ({n} checagens)")
    app.quit()


# ------------------------------------------------------------------ fase retomar (outro processo)
def r_voltou():
    ok(nome_atual() == "b.mp4", f"não voltou em b.mp4: {nome_atual()}")
    pos = float(j.mpv.time_pos or 0)
    ok(abs(pos - estado["pos"]) < 0.3, f"não voltou no ponto: {pos} (esperado {estado['pos']})")
    ok(j.mpv.pause, "não voltou pausado")
    ok(len(j.fila.itens) == 3, "fila incompleta")
    ok(config.carregar()["retomar"] == {}, "retomar não foi limpo")
    foto("sozinho-voltou.png")
    log.append(f"abriu pelo instalador → mesma fila, b.mp4 em {pos:.1f} s, pausado")
    j.limpar()  # nada tocando
    GITHUB.update(versao="9.9.9", nome="v9.9.9")
    j.procurar_atualizacao()


def r_livre():
    ok(INSTALADOR and INSTALADOR[-1][2] is True, f"nada tocando e não instalou na hora: {INSTALADOR}")
    ok(config.carregar()["retomar"] == {}, "sem fila não guarda retomar")
    log.append("nada tocando + versão nova → baixou e instalou na hora")
    print("\n".join(log))
    print(f"RETOMAR PASSOU ({n} checagens)")
    app.quit()


if FASE == "principal":
    passos = [(4000, p_tocando), (2500, p_baixou_nao_fechou), (3500, p_fim_do_arquivo), (1500, p_pausa_prepara),
              (2500, p_pausa_baixou), (2500, p_pausa_instalou), (2500, p_urgente), (1000, p_fechar)]
else:
    with open(os.path.join(SAIDA, "retomar.json"), encoding="utf-8") as f:
        r = json.load(f)
    estado["pos"] = r["pos"]
    cfg = config.carregar()
    cfg["retomar"] = dict(r, quando=time.time())
    config.salvar(cfg)
    j.cfg["retomar"] = cfg["retomar"]
    passos = [(5000, r_voltou), (2500, r_livre)]


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
codigo = app.exec()
if codigo == 0 and FASE == "principal":
    codigo = subprocess.call([sys.executable, os.path.abspath(__file__), PASTA_ORIG, SAIDA, "retomar"])
sys.exit(codigo)
