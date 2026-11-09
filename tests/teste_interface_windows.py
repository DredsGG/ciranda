"""Só no Windows de verdade, com a placa de vídeo: clique direito real (entrada do sistema) no
vídeo abre o menu da Ciranda, foto respeita os 5 s, aceleração de hardware nos 3 codecs e prints do OSD.
Mexe no mouse por alguns segundos e usa um APPDATA temporário.
    python testes/teste_interface_windows.py <pasta-midia> <pasta-codecs> <saida>
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

os.environ["CIRANDA_IDIOMA_SISTEMA"] = "pt"
os.environ["CIRANDA_SEM_QUADROS"] = "1"
os.environ["CIRANDA_SEM_ATUALIZACAO"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIDIA, CODECS, SAIDA = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(SAIDA, exist_ok=True)
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-interface")

from PySide6.QtCore import QPoint, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

from ciranda.janela import QSS, Janela  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
geo = QGuiApplication.primaryScreen().availableGeometry()
j = Janela()
j.resize(1280, 760)
j.move(geo.x() + 40, geo.y() + 40)
j.show()
j.raise_()
j.activateWindow()
falhas, u32 = [], ctypes.windll.user32


def ok(cond, msg):
    print(("ok     " if cond else "FALHOU ") + msg, flush=True)
    if not cond:
        falhas.append(msg)


def esperar(seg):
    fim = time.monotonic() + seg
    while time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.01)


def tirar_print(nome):
    """Só se a janela da Ciranda estiver em primeiro plano: o print nunca pode pegar outra janela."""
    if u32.GetForegroundWindow() == int(j.winId()):
        p = j.tela.mapToGlobal(QPoint(0, 0))
        QGuiApplication.primaryScreen().grabWindow(0, p.x(), p.y(), j.tela.width(), j.tela.height()).save(
            os.path.join(SAIDA, nome + ".png"))


def tocar_nome(nome):
    alvo = [i for i, it in enumerate(j.fila.itens) if it.nome == nome][0]
    j.tocar(j.fila.ir_para(alvo))


def tempo_ate_trocar(limite=9.0):
    item, t0 = j._item, time.monotonic()
    while j._item is item and time.monotonic() - t0 < limite:
        app.processEvents()
        time.sleep(0.01)
    return time.monotonic() - t0


j.carregar([MIDIA], adicionar=False)
esperar(2.0)
j.fila.aleatorio = False
j.fila.repetir = "tudo"
j._aplicar_modos_na_tela()
tocar_nome("abertura.mp4")
esperar(1.5)

# 1) botão direito de verdade no vídeo
centro = j.tela.mapToGlobal(QPoint(j.tela.width() // 2, j.tela.height() // 2))
ponto = wintypes.POINT()
u32.GetCursorPos(ctypes.byref(ponto))
u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetAncestor.restype = wintypes.HWND
u32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
SEM_MOVER = 0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE


def fixar_no_topo(sim):  # pela API: setWindowFlag recriaria a janela que o mpv usa
    u32.SetWindowPos(int(j.winId()), wintypes.HWND(-1 if sim else -2), 0, 0, 0, 0, SEM_MOVER)


fixar_no_topo(True)  # o clique só pode cair nesta janela
u32.SetForegroundWindow(int(j.winId()))
esperar(0.5)
centro = j.tela.mapToGlobal(QPoint(j.tela.width() // 2, j.tela.height() // 2))
u32.SetCursorPos(centro.x(), centro.y())
esperar(0.3)
sob = u32.WindowFromPoint(wintypes.POINT(centro.x(), centro.y()))
alvo = int(u32.GetAncestor(sob, 2) or 0)  # GA_ROOT
nome_classe = ctypes.create_unicode_buffer(128)
u32.GetClassNameW(sob, nome_classe, 128)
ok(alvo == int(j.winId()), f"a janela da Ciranda está embaixo do ponteiro (classe {nome_classe.value})")
visto = {}


def conferir_menu():
    pop = QApplication.activePopupWidget()
    visto["menu"] = isinstance(pop, QMenu)
    visto["itens"] = [a.text().split("\t")[0] for a in pop.actions()] if pop else []
    tirar_print("01-botao-direito")
    if pop:
        QGuiApplication.primaryScreen().grabWindow(0, pop.x(), pop.y(), pop.width(), pop.height()).save(
            os.path.join(SAIDA, "01-menu.png"))
        pop.close()


if alvo == int(j.winId()):
    QTimer.singleShot(900, conferir_menu)  # m.exec() roda laço próprio: quem confere é o timer
    u32.mouse_event(0x0008, 0, 0, 0, 0)  # botão direito desce
    u32.mouse_event(0x0010, 0, 0, 0, 0)  # e sobe
    esperar(1.5)
ok(visto.get("menu") is True, f"botão direito abre o menu da Ciranda: {visto.get('itens')}")
u32.SetCursorPos(ponto.x, ponto.y)
esperar(0.3)

# 2) foto de 5 s, JPEG e HEIC
j.s_foto.setValue(5)
for nome in ("capa.jpg", "iphone.heic"):
    tocar_nome(nome)
    if nome == "iphone.heic":
        esperar(1.2)
        tirar_print("02-heic-simples")
        seg = 1.2 + tempo_ate_trocar()
    else:
        seg = tempo_ate_trocar()
    ok(abs(seg - 5.0) < 0.6, f"foto {nome.split('.')[-1]}: ficou {seg:.2f} s (pedido 5)")

# 3) OSD: aviso com fundo escuro
tocar_nome("abertura.mp4")
esperar(1.2)
j.mpv.command("show-text", "Aviso de teste da Ciranda", "2500", "1")
esperar(0.6)
tirar_print("03-osd")

# 4) aceleração de hardware
j.carregar([CODECS], adicionar=False)
esperar(1.5)
j.fila.aleatorio = False
j._aplicar_modos_na_tela()
for nome in ("h264.mp4", "hevc10.mkv", "av1.mkv"):
    tocar_nome(nome)
    esperar(3.5)
    hw, pos, fmt = j.mpv.hwdec_current, j.mpv.time_pos or 0, j.mpv.video_format
    ok(pos > 1.5 and bool(hw) and hw != "no", f"{nome}: hwdec={hw}, formato={fmt}, tempo={pos:.2f}, "
                                              f"quadros perdidos={j.mpv.decoder_frame_drop_count}")
    tirar_print("04-" + nome.split(".")[0])

j.close()
print("INTERFACE " + ("FALHOU: " + "; ".join(falhas) if falhas else "PASSOU"))
QTimer.singleShot(0, lambda: app.exit(1 if falhas else 0))
sys.exit(app.exec())
