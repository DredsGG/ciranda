"""E2E da janela (Linux com Xvfb ou Windows). Abre a pasta de teste, passa por
todos os itens, confere que cada tipo abriu e tira prints.
    CIRANDA_VO=x11 xvfb-run -a -s "-screen 0 1400x860x24" python testes/teste_janela.py <pasta> <saida>"""

import os
os.environ.setdefault("CIRANDA_IDIOMA_SISTEMA", "pt")  # textos dos testes em português
os.environ.setdefault("CIRANDA_SEM_QUADROS", "1")  # tutorial/novidades têm teste próprio
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.makedirs(SAIDA, exist_ok=True)
os.environ.setdefault("APPDATA", os.path.join(SAIDA, "appdata"))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ciranda.janela import QSS, Janela  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
j = Janela()
j.resize(1360, 800)
j.move(0, 0)
j.show()

passos = []
log = []


def print_tela(nome):
    app.processEvents()
    os.system(f"import -window root '{os.path.join(SAIDA, nome)}.png' 2>/dev/null")


def passo(espera_ms):
    def deco(fn):
        passos.append((espera_ms, fn))
        return fn
    return deco


@passo(800)
def p_vazio():
    print_tela("01-inicio")
    j.s_foto.setValue(2)
    j.fila.aleatorio = False
    j.fila.repetir = "nao"
    j._aplicar_modos_na_tela()
    j.carregar([PASTA], adicionar=False)


@passo(1500)
def p_primeiro():
    log.append(("fila", len(j.fila), j._item.nome if j._item else None))
    assert len(j.fila) == 16, len(j.fila)
    assert j._item.nome == "abertura.mp4", j._item.nome
    print_tela("02-video-tocando")


# passa por todos: anota o que abriu (tem largura de vídeo) e o que falhou
abertos = {}


def anotar():
    it = j._item
    if it is None:
        return
    try:
        w = j.mpv.width
    except Exception:
        w = None
    abertos.setdefault(it.nome, w)


for k in range(17):
    @passo(1300 if k else 200)
    def p_avancar(k=k):
        anotar()
        j.proximo(False)


@passo(500)
def p_resultado():
    anotar()
    falhos = [i.nome for i in j.fila.itens if i.falhou]
    log.append(("abertos", abertos))
    log.append(("falhos", falhos))
    assert falhos == ["corrompido.mp4"], falhos
    for nome, w in abertos.items():
        if nome != "corrompido.mp4":
            assert w, f"{nome} não abriu (width={w})"


@passo(300)
def p_aleatorio():
    j.alternar_aleatorio()
    j.ciclar_repetir()  # nao -> tudo
    j.definir_filtro("fotos")
    assert all(j.fila.itens[i].tipo == "foto" for i in j.fila.ordem)
    j.tocar(j.fila.ir_para(j.fila.ordem[0]))


@passo(1200)
def p_print_fotos():
    print_tela("04-aleatorio-so-fotos")
    j.definir_filtro("tudo")
    j.s_foto.setValue(30)
    nome = [i for i in j.fila.ordem if j.fila.itens[i].nome == "iphone.heic"][0]
    j.tocar(j.fila.ir_para(nome))


@passo(1500)
def p_heic():
    w = j.mpv.width
    log.append(("heic width", w))
    assert w == 1200, w
    print_tela("05-heic")
    alvo = [i for i in j.fila.ordem if j.fila.itens[i].nome == "celular-deitado.jpg"][0]
    j.tocar(j.fila.ir_para(alvo))


@passo(1500)
def p_exif():
    giro = (j.mpv.video_params or {}).get("rotate", 0) + int(j.mpv["video-rotate"] or 0)
    log.append(("exif giro", giro))
    assert giro % 360 == 90, giro
    print_tela("03-foto-exif")
    j.alternar_tela_cheia()


@passo(1500)
def p_cheia():
    print_tela("06-tela-cheia-controles")


@passo(3500)
def p_cheia_limpa():
    print_tela("07-tela-cheia-sem-controles")
    j.sair_tela_cheia()


@passo(800)
def p_fim():
    j.close()
    print("\n".join(map(str, log)))
    print("E2E PASSOU")
    app.quit()


def rodar(i=0):
    if i >= len(passos):
        return
    espera, fn = passos[i]

    def executar():
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            print("LOG:", log)
            app.exit(1)
            return
        rodar(i + 1)
    QTimer.singleShot(espera, executar)


rodar()
sys.exit(app.exec())
