"""Limpar tudo: some a fila e a lista do Continuar; ficam cache, ajustes e os arquivos originais.
    CIRANDA_VO=x11 xvfb-run -a python testes/teste_limpar.py <pasta> <saida>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-limpar")
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from ciranda import fotos
from ciranda.janela import QSS, Janela
from ciranda.biblioteca import varrer

antes = len(varrer(PASTA))
app = QApplication(sys.argv); app.setStyleSheet(QSS)
j = Janela([PASTA]); j.show()

def heic():
    alvo = [i for i in j.fila.ordem if j.fila.itens[i].nome.endswith(".heic")][0]
    j.s_foto.setValue(7)
    j.tocar(j.fila.ir_para(alvo))

def conferir():
    cfgf = os.path.join(os.environ["APPDATA"], "Ciranda", "config.json")
    assert json.load(open(cfgf))["ultimas_pastas"], "antes: última fila guardada"
    assert fotos.tem_cache(), "antes: cache HEIC existe"
    j._montar_menu_abrir()
    j.limpar_tudo(confirmar=False)
    cfg = json.load(open(cfgf))
    assert cfg["ultimas_pastas"] == [], cfg["ultimas_pastas"]
    assert cfg["segundos_foto"] == 7, "ajuste mantido"
    assert fotos.tem_cache(), "cache NÃO deve ser apagado (só fila + Continuar)"
    assert len(j.fila) == 0 and j._item is None, "fila vazia"
    assert j.vazio.b_continuar.isHidden(), "botão Continuar sumiu"
    assert len(varrer(PASTA)) == antes, "nenhum arquivo original mexido"
    os.system(f"import -window root '{os.path.join(SAIDA, 'limpo.png')}' 2>/dev/null")
    print("LIMPAR TUDO PASSOU"); app.quit()

QTimer.singleShot(2000, heic)
QTimer.singleShot(4000, conferir)
QTimer.singleShot(9000, lambda: (print("tempo esgotado"), app.exit(1)))
sys.exit(app.exec())
