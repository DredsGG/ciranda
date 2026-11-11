"""1.5.1: grade HEIC que não aparecia. Na janela real (Windows):
  1. grade de 2 blocos, 40 aberturas sem a correção (motor direto) e 40 pela Ciranda;
  2. grade de 48 blocos e HEIC simples: nenhuma recarga a mais;
  3. HEIC corrompido: desiste em 5 tentativas e pula, sem travar a fila;
  4. foto em pé (irot) que só aparece depois de recarregar continua em pé;
  5. o tempo da foto só começa a contar quando a imagem aparece.
    python testes/teste_heic_recarga.py <saida>        (precisa do ffmpeg com libx265 no PATH)
"""
import os

import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = sys.argv[1]
os.makedirs(SAIDA, exist_ok=True)
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-recarga")
os.environ["CIRANDA_IDIOMA_SISTEMA"] = "pt"
os.environ["CIRANDA_SEM_QUADROS"] = "1"
os.environ["CIRANDA_SEM_ATUALIZACAO"] = "1"

from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import gerar_heic  # noqa: E402
from ciranda.janela import QSS, Janela  # noqa: E402

PASTA = os.path.join(SAIDA, "midia-recarga")
os.makedirs(PASTA, exist_ok=True)
arq = {n: os.path.join(PASTA, n) for n in ("foto.jpg", "g2x1.heic", "g8x6.heic", "simples.heic", "giro.heic", "corrompido.heic",
                                           "vermelha.heic", "azul.heic")}
gerar_heic.grade(arq["vermelha.heic"], 2, 1, 1024, 512, cor="red")  # mesmo tamanho, cores diferentes:
gerar_heic.grade(arq["azul.heic"], 2, 1, 1024, 512, cor="blue")     # só a cor diz qual está na tela
img = QImage(800, 600, QImage.Format_RGB32)
img.fill(QColor(70, 130, 180))
img.save(arq["foto.jpg"])
gerar_heic.grade(arq["g2x1.heic"], 2, 1, 1024, 512)
gerar_heic.grade(arq["g8x6.heic"], 8, 6, 4032, 3024)
gerar_heic.simples(arq["simples.heic"], 1200, 900)
gerar_heic.grade(arq["giro.heic"], 8, 6, 4032, 3024, irot=3)
dados = open(arq["g2x1.heic"], "rb").read()
inicio = dados.rindex(b"mdat") + 4
bloco1 = int.from_bytes(dados[inicio:inicio + 4], "big") + 4
# arquivo cortado depois do 1o bloco: o contêiner abre, o motor não acusa erro e nenhum quadro sai
open(arq["corrompido.heic"], "wb").write(dados[:inicio + bloco1])

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
geo = QGuiApplication.primaryScreen().availableGeometry()
j = Janela([PASTA])
j.resize(1100, 700)
j.move(geo.x() + 40, geo.y() + 40)
j.show()
LOG = os.path.join(os.environ["APPDATA"], "Ciranda", "ciranda.log")
n_ok, falhas = 0, []


def ok(cond, msg):
    global n_ok
    print(("ok     " if cond else "FALHOU ") + msg, flush=True)
    if cond:
        n_ok += 1
    else:
        falhas.append(msg)


def esperar(s, ate=None):
    fim = time.monotonic() + s
    while time.monotonic() < fim:
        if ate and ate():
            return True
        app.processEvents()
        time.sleep(0.004)
    return bool(ate and ate())


def log_desde(pos):
    with open(LOG, encoding="utf-8", errors="replace") as f:
        f.seek(pos)
        return f.read()


def tamanho_log():
    return os.path.getsize(LOG) if os.path.exists(LOG) else 0


esperar(2.5)
j.s_foto.setValue(30)
j.fila.aleatorio = False
j.fila.repetir = "tudo"
j._aplicar_modos_na_tela()
idx = {it.nome: i for i, it in enumerate(j.fila.itens)}
ev = {}
j.mpv.event_callback("playback-restart")(lambda _e: ev.__setitem__("ok", time.monotonic()))


TAMANHO = {"g2x1.heic": (1024, 512), "g8x6.heic": (4032, 3024), "simples.heic": (1200, 900), "giro.heic": (3024, 4032)}


def na_tela(nome):
    """A verdade: o que a saída de vídeo mostra (a foto anterior é 800 x 600)."""
    return (j.mpv.dwidth, j.mpv.dheight) == TAMANHO[nome]


def abrir_pela_ciranda(nome, limite=25.0):
    """Abre pela Ciranda depois de uma foto JPEG; devolve (apareceu na tela, segundos, texto do log).
    Também confere que a Ciranda percebeu (o tempo da foto só começa quando aparece)."""
    j.tocar(j.fila.ir_para(idx["foto.jpg"]))
    esperar(1.0, lambda: (j.mpv.dwidth, j.mpv.dheight) == (800, 600))
    esperar(0.15)
    pos = tamanho_log()
    t0 = time.monotonic()
    j.tocar(j.fila.ir_para(idx[nome]))
    esperar(limite, lambda: (na_tela(nome) and j._heic_apareceu) or j._item.falhou or j._item.nome != nome)
    seg = time.monotonic() - t0
    apareceu = na_tela(nome) and j._item.nome == nome
    if apareceu and not j._heic_apareceu:
        print(f"       {nome}: na tela, mas a Ciranda não percebeu", flush=True)
    esperar(0.2)
    return apareceu and j._heic_apareceu, seg, log_desde(pos)


# 1a. sem a correção: o motor direto, como na 1.5.0
antes = 0
for _ in range(40):
    j.mpv.command("loadfile", arq["foto.jpg"], "replace")
    esperar(1.0, lambda: (j.mpv.dwidth, j.mpv.dheight) == (800, 600))
    esperar(0.15)
    j.mpv.command("loadfile", arq["g2x1.heic"], "replace")
    antes += esperar(2.0, lambda: na_tela("g2x1.heic"))
j.tocar(j.fila.ir_para(idx["foto.jpg"]))
esperar(0.5)
print(f"       antes (1.5.0, motor direto): apareceu {antes} de 40", flush=True)

# 1b. pela Ciranda 1.5.1
depois, recargas, tempos = 0, 0, []
for _ in range(40):
    a, seg, texto = abrir_pela_ciranda("g2x1.heic")
    depois += a
    recargas += texto.count("recarregando")
    tempos.append(seg)
ok(depois >= 39, f"grade de 2 blocos pela Ciranda: apareceu {depois} de 40 (antes {antes} de 40), "
                 f"{recargas} recargas, até aparecer no máximo {max(tempos):.2f} s")

# 2. grade de 48 blocos e HEIC simples: nenhuma recarga a mais
for nome in ("g8x6.heic", "simples.heic"):
    vezes, rec = 0, 0
    for _ in range(10):
        a, _seg, texto = abrir_pela_ciranda(nome)
        vezes += a
        rec += texto.count("recarregando")
    ok(vezes == 10 and rec == 0, f"{nome}: apareceu {vezes} de 10, {rec} recargas")

# 3. corrompido: desiste em até 5 tentativas e pula
j._erros_seguidos = 0  # as cargas diretas da etapa 1a contam como falhas seguidas e encerrariam a fila
pos = tamanho_log()
t_corr = time.monotonic()
j.tocar(j.fila.ir_para(idx["corrompido.heic"]))
esperar(30.0, lambda: j._item.nome != "corrompido.heic")
esperar(0.5)
print(f"       corrompido: pulou em {time.monotonic() - t_corr:.1f} s", flush=True)
texto = log_desde(pos)
corr = j.fila.itens[idx["corrompido.heic"]]
tentativas = 1 + texto.count("recarregando")
print("       log do corrompido:", " | ".join(l.split(" ", 1)[-1][:70] for l in texto.splitlines() if "HEIC" in l or "não abriu" in l), flush=True)
ok(corr.falhou and tentativas <= 5 and j._item is not None and j._item.nome != "corrompido.heic",
   f"corrompido: marcado como falho depois de {tentativas} tentativa(s), a fila seguiu para {j._item.nome if j._item else None}")

# 4. em pé depois de recarregar: força a 1a conferência antes de dar tempo de aparecer
j.HEIC_ESPERA_S, j.HEIC_PASSO_S = 0.02, 2.0
a, _seg, texto = abrir_pela_ciranda("giro.heic")
j.HEIC_ESPERA_S, j.HEIC_PASSO_S = Janela.HEIC_ESPERA_S, Janela.HEIC_PASSO_S
ok(a and "tentativa 2" in texto and na_tela("giro.heic") and "transpose=clock" in str(j.mpv["vf"]),
   f"em pé depois de recarregar: apareceu={a}, {(j.mpv.dwidth, j.mpv.dheight)}, vf={j.mpv['vf']}, "
   f"log={[l.split(' ', 1)[-1] for l in texto.splitlines() if 'HEIC' in l]}")

# 5. o tempo da foto conta a partir de quando aparece
j.s_foto.setValue(2)
j.HEIC_ESPERA_S, j.HEIC_PASSO_S = 0.02, 2.0  # 1a tentativa "perdida": aparece só na 2a, ~2 s depois
t0 = time.monotonic()
j.tocar(j.fila.ir_para(idx["giro.heic"]))
esperar(10, lambda: j._heic_apareceu)
t_apareceu = time.monotonic()
esperar(10, lambda: j._item.nome != "giro.heic")
j.HEIC_ESPERA_S, j.HEIC_PASSO_S = Janela.HEIC_ESPERA_S, Janela.HEIC_PASSO_S
tela_s = time.monotonic() - t_apareceu
ok(abs(tela_s - 2.0) < 0.4 and t_apareceu - t0 > 0.3,
   f"foto de 2 s: ficou {tela_s:.2f} s na tela depois de aparecer (apareceu {t_apareceu - t0:.2f} s após abrir, "
   f"na 2a tentativa); se contasse desde o carregamento, ficaria uns {2.0 - (t_apareceu - t0):.2f} s")


def cor_na_tela():
    """A verdade quando o tamanho não muda: a cor do quadro que a saída de vídeo mostra."""
    f = os.path.join(SAIDA, "quadro.png")
    j.mpv.command("screenshot-to-file", f, "video")
    esperar(0.2)
    c = QImage(f).pixelColor(512, 256)
    return "azul" if c.blue() > 150 and c.red() < 100 else ("vermelha" if c.red() > 150 and c.blue() < 100 else "outra")


# 6. foto anterior do mesmo tamanho (pasta de iPhone): a grade nova tem que aparecer de verdade
j.s_foto.setValue(30)
certo, percebeu = 0, 0
for _ in range(20):
    j.tocar(j.fila.ir_para(idx["vermelha.heic"]))
    esperar(5, lambda: j._heic_apareceu)
    esperar(0.3)
    j.tocar(j.fila.ir_para(idx["azul.heic"]))
    esperar(8, lambda: j._heic_apareceu or j._item.falhou)
    esperar(0.3)
    certo += cor_na_tela() == "azul"
    percebeu += j._heic_apareceu
ok(certo == 20 and percebeu == 20, f"foto anterior do mesmo tamanho: a nova na tela {certo} de 20, a Ciranda percebeu {percebeu} de 20")

# 7. o mesmo arquivo de novo
j.tocar(j.fila.ir_para(idx["azul.heic"]))
a1 = esperar(5, lambda: j._heic_apareceu)
j.tocar(j.fila.ir_para(idx["azul.heic"]))
a2 = esperar(8, lambda: j._heic_apareceu or j._item.falhou)
ok(a1 and a2 and not j._item.falhou and cor_na_tela() == "azul", "o mesmo HEIC duas vezes seguidas aparece e não é marcado como falho")

# 8. pausado antes de aparecer: aparece, o relógio não anda; ao despausar, conta o tempo inteiro
j.s_foto.setValue(2)
j.tocar(j.fila.ir_para(idx["foto.jpg"]))
esperar(0.8)
j.tocar(j.fila.ir_para(idx["g8x6.heic"]))
j.alternar_pausa()  # pausa antes de a grade aparecer
pausou = bool(j.mpv.pause)
esperar(6, lambda: j._heic_apareceu)
esperar(3.0)  # mais que os 2 s da foto
parada = j._item.nome == "g8x6.heic" and not j._t_foto.isActive() and bool(j.mpv.pause)
apareceu_pausado = j._heic_apareceu  # lido antes de despausar: a troca de arquivo zera
t_desp = time.monotonic()
j.alternar_pausa()
esperar(6, lambda: j._item.nome != "g8x6.heic")
depois = time.monotonic() - t_desp
ok(pausou and apareceu_pausado and parada and abs(depois - 2.0) < 0.4,
   f"pausado antes de aparecer: ficou parado (relógio parado={parada}); despausado, ficou {depois:.2f} s (pedido 2)")

# 9. a recarga mantém a pausa
j.s_foto.setValue(30)
j.HEIC_ESPERA_S, j.HEIC_PASSO_S = 0.02, 2.0
pos = tamanho_log()
j.tocar(j.fila.ir_para(idx["giro.heic"]))
j.alternar_pausa()
esperar(8, lambda: j._heic_apareceu)
texto = log_desde(pos)
j.HEIC_ESPERA_S, j.HEIC_PASSO_S = Janela.HEIC_ESPERA_S, Janela.HEIC_PASSO_S
ok("recarregando" in texto and bool(j.mpv.pause) and not j._t_foto.isActive(),
   f"recarga com o player pausado: recarregou={'recarregando' in texto}, continua pausado={bool(j.mpv.pause)}")
j.alternar_pausa()

# 10. pausar e despausar antes de aparecer não pula o HEIC
j.s_foto.setValue(2)
j.tocar(j.fila.ir_para(idx["foto.jpg"]))
esperar(3.0, lambda: j._item.nome != "foto.jpg")  # a foto anterior roda o tempo inteiro
j.tocar(j.fila.ir_para(idx["g8x6.heic"]))
j.alternar_pausa()
j.alternar_pausa()
esperar(0.3)
ainda = j._item.nome == "g8x6.heic" and not j._item.falhou
esperar(5, lambda: j._heic_apareceu)
ok(ainda and j._heic_apareceu and j._item.nome == "g8x6.heic",
   "pausar e despausar antes de aparecer: o HEIC não foi pulado e apareceu")

j.close()
print("HEIC RECARGA " + (f"FALHOU: {falhas}" if falhas else f"PASSOU ({n_ok} checagens)"))
sys.exit(1 if falhas else 0)
