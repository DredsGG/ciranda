"""Restaurar de fábrica: clique de verdade no item do menu da pastinha, confirma,
e confere ajustes no padrão, fila/Continuar vazios, cache apagado, erro.txt mantido.
    xvfb-run -a python testes/teste_restaurar.py <pasta> <saida>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-restaurar")
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from ciranda import config, fotos
from ciranda.janela import QSS, Janela
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(QSS)
j = Janela([PASTA]); j.resize(1360, 800); j.show()
erro = os.path.join(config.pasta_dados(), "erro.txt")

def baguncar():
    j.volume.setValue(30); j.s_foto.setValue(30)
    j.alternar_aleatorio(); j.ciclar_repetir(); j.definir_filtro("fotos")
    alvo = [i for i in j.fila.ordem if j.fila.itens[i].nome.endswith(".heic")]
    if not alvo:
        j.definir_filtro("tudo"); alvo = [i for i in j.fila.ordem if j.fila.itens[i].nome.endswith(".heic")]
    j.tocar(j.fila.ir_para(alvo[0]))
    open(erro, "w").write("erro de teste")

def clicar_menu():
    assert fotos.tem_cache(), "antes: cache existe"
    QTest.mouseClick(j.b_abrir, Qt.LeftButton, Qt.NoModifier, QPoint(10, 10))
    QTimer.singleShot(600, clicar_item)

def clicar_item():
    m = j.menu_abrir
    assert m.isVisible(), "menu da pastinha não abriu"
    a = [a for a in m.actions() if a.text().startswith("Restaurar de fábrica")][0]
    QTest.mouseClick(m, Qt.LeftButton, Qt.NoModifier, m.actionGeometry(a).center())
    QTimer.singleShot(800, conferir)

def conferir():
    cfg = json.load(open(os.path.join(config.pasta_dados(), "config.json")))
    for k in ("volume", "mudo", "aleatorio", "repetir", "filtro", "segundos_foto", "painel"):
        assert cfg[k] == config.PADRAO[k], f"{k}: {cfg[k]} != {config.PADRAO[k]}"
    assert cfg["ultimas_pastas"] == []
    assert j.volume.value() == config.PADRAO["volume"] and j.s_foto.value() == config.PADRAO["segundos_foto"]
    assert j.fila.aleatorio == config.PADRAO["aleatorio"] and j.fila.repetir == config.PADRAO["repetir"]
    assert j.fila.filtro == "tudo" and len(j.fila) == 0 and j._item is None
    assert not fotos.tem_cache(), "cache não foi apagado"
    assert os.path.exists(erro), "erro.txt deveria ficar"
    print("RESTAURAR PASSOU"); app.quit()

QTimer.singleShot(2500, baguncar)
QTimer.singleShot(5000, clicar_menu)
QTimer.singleShot(20000, lambda: (print("tempo esgotado"), app.exit(1)))
sys.exit(app.exec())
