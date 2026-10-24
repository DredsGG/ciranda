"""Clica de verdade (QTest) em cada botão de pasta/fila e confere o efeito:
Abrir, Juntar pasta, Limpar (menu) e o botão de pasta da barra (menu).
    xvfb-run -a python testes/teste_botoes.py <pasta> <saida>"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-botoes")
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
from ciranda.janela import QSS, Janela

app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(QSS)
escolhida = {"p": PASTA}
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: escolhida["p"])
j = Janela(); j.resize(1360, 800); j.move(0, 0); j.show()
passos, log = [], []

def clique(w):
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(w.width() // 2, w.height() // 2))


def p(ms):
    def d(fn):
        passos.append((ms, fn)); return fn
    return d

@p(800)
def abrir():
    clique(j.b_p_abrir)               # botão "Abrir" da fila

@p(2500)
def conferir_abrir():
    assert len(j.fila) == 16, f"Abrir: fila {len(j.fila)}"
    log.append("Abrir ok (16)")
    escolhida["p"] = os.path.join(PASTA, "Aniversário")  # pasta já está na fila: não duplica
    escolhida["p2"] = True
    import tempfile, shutil
    extra = tempfile.mkdtemp(prefix="ciranda-extra-")
    shutil.copy(os.path.join(PASTA, "capa.jpg"), os.path.join(extra, "nova.jpg"))
    escolhida["p"] = extra
    j.s_foto.setValue(120)            # nada passa sozinho durante o teste
    if j._item.tipo == "video":
        j.mpv["loop-file"] = "inf"
    j._tocando_antes = j._item.caminho
    clique(j.b_p_juntar)              # botão "Juntar pasta"

@p(2000)
def conferir_juntar():
    assert len(j.fila) == 17, f"Juntar: fila {len(j.fila)}"
    assert j._item.caminho == j._tocando_antes, "Juntar parou o que tocava"
    log.append("Juntar pasta ok (17, sem parar o atual)")
    clique(j.b_abrir)                 # botão de pasta da barra

@p(800)
def conferir_menu_barra():
    assert j.menu_abrir.isVisible(), "menu do botão de pasta não abriu"
    log.append("Botão de pasta da barra abre o menu")
    os.system(f"import -window root '{os.path.join(SAIDA, 'menu-barra.png')}'")
    j.menu_abrir.close()
    clique(j.b_p_limpar)              # botão "Limpar"

@p(800)
def conferir_menu_limpar():
    m = j._menu_limpar
    assert m.isVisible(), "menu Limpar não abriu"
    os.system(f"import -window root '{os.path.join(SAIDA, 'menu-limpar.png')}'")
    alvo = [a for a in m.actions() if a.text().startswith("Limpar fila")][0]
    QTest.mouseClick(m, Qt.LeftButton, Qt.NoModifier, m.actionGeometry(alvo).center())  # clique no item

@p(800)
def conferir_limpo():
    assert len(j.fila) == 0, f"Limpar fila: {len(j.fila)}"
    log.append("Limpar > Limpar fila ok")
    print("\n".join(log)); print("BOTOES PASSOU"); app.quit()

def rodar(i=0):
    if i >= len(passos): return
    ms, fn = passos[i]
    def ex():
        try:
            fn()
        except Exception:
            import traceback; traceback.print_exc(); print(log); app.exit(1); return
        rodar(i + 1)
    QTimer.singleShot(ms, ex)
rodar()
QTimer.singleShot(30000, lambda: (print("tempo esgotado"), app.exit(1)))
sys.exit(app.exec())
