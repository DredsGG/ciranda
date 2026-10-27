"""Regra 9: "feito por Dreds · vX.Y.Z" na tela inicial e no rodapé da fila,
versão igual à constante VERSAO e clique em "Dreds" abrindo o GitHub.
    xvfb-run -a python testes/teste_assinatura.py <saida>"""
import os, sys
os.environ.setdefault("CIRANDA_IDIOMA_SISTEMA", "pt")  # textos dos testes em português
os.environ.setdefault("CIRANDA_SEM_QUADROS", "1")  # tutorial/novidades têm teste próprio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["APPDATA"] = os.path.join(sys.argv[1], "appdata-assinatura")
from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from ciranda import VERSAO
from ciranda.janela import GITHUB, QSS, Janela

class Captura(QObject):
    urls = []
    @Slot(QUrl)
    def abrir(self, url):
        Captura.urls.append(url.toString())

app = QApplication(sys.argv); app.setStyleSheet(QSS)
cap = Captura()
QDesktopServices.setUrlHandler("https", cap, "abrir")
j = Janela(); j.resize(1360, 800); j.show()

def clicar_em_dreds(lab):
    """Varre a linha do rótulo até o clique cair no link."""
    antes = len(Captura.urls)
    y = lab.height() // 2
    for x in range(2, lab.width(), 3):
        QTest.mouseClick(lab, Qt.LeftButton, Qt.NoModifier, QPoint(x, y))
        app.processEvents()
        if len(Captura.urls) > antes:
            return Captura.urls[-1]
    return None

def conferir():
    for nome, lab in (("tela inicial", j.vazio.assinatura), ("rodapé da fila", j.assinatura_fila)):
        assert lab.isVisible(), f"{nome}: assinatura não aparece"
        txt = lab.text()
        assert "feito por" in txt and ">Dreds<" in txt.replace("<b>", "").replace("</b>", ""), txt
        assert f"· v{VERSAO}" in txt, f"{nome}: versão errada: {txt}"
        assert lab.openExternalLinks(), f"{nome}: link não abre"
        url = clicar_em_dreds(lab)
        assert url and url.rstrip("/") == GITHUB, f"{nome}: clique abriu {url}"
        print(f"ok {nome}: v{VERSAO}, clique -> {url}")
    print("ASSINATURA PASSOU"); app.quit()

QTimer.singleShot(1200, conferir)
QTimer.singleShot(15000, lambda: (print("tempo esgotado"), app.exit(1)))
sys.exit(app.exec())
