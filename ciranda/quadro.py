"""Quadro no meio da janela (regras 12 e 14): nova versão, novidades e tutorial.

Janela própria sem borda, presa à janela do Ciranda (fica por cima até do vídeo, que é uma
janela nativa do mpv) e centralizada nela. Não é modal: o player continua tocando.
Fecha no X ou no Esc.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from .icones import icone
from .textos import t

QSS_QUADRO = """
QFrame#quadro { background: #17181d; border: 1px solid #33363f; }
QLabel#quadroTitulo { font-size: 17px; font-weight: 600; }
QLabel#quadroCorpo { color: #c9cad2; font-size: 13px; }
QLabel#quadroPassos { color: #6f717c; font-size: 11.5px; }
"""


class Quadro(QFrame):
    fechou = Signal(str)  # "x" (X ou Esc) ou "botao"

    def __init__(self, janela: QWidget):
        super().__init__(janela, Qt.Tool | Qt.FramelessWindowHint)
        self.setObjectName("quadro")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(QSS_QUADRO)
        self.setFixedWidth(480)
        self._janela = janela
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 16, 14, 18)
        v.setSpacing(10)
        topo = QHBoxLayout()
        self.l_titulo = QLabel()
        self.l_titulo.setObjectName("quadroTitulo")
        self.l_titulo.setWordWrap(True)
        self.b_x = QToolButton()
        self.b_x.setIcon(icone("fechar", "#c9cad2", 14))
        self.b_x.setCursor(Qt.PointingHandCursor)
        self.b_x.setFocusPolicy(Qt.NoFocus)
        self.b_x.clicked.connect(lambda: self.fechar("x"))
        topo.addWidget(self.l_titulo, 1)
        topo.addWidget(self.b_x, 0, Qt.AlignTop)
        v.addLayout(topo)
        self.l_corpo = QLabel()
        self.l_corpo.setObjectName("quadroCorpo")
        self.l_corpo.setWordWrap(True)
        self.l_corpo.setTextFormat(Qt.RichText)
        v.addWidget(self.l_corpo)
        v.addSpacing(4)
        self.rodape = QHBoxLayout()
        self.l_passos = QLabel()
        self.l_passos.setObjectName("quadroPassos")
        self.rodape.addWidget(self.l_passos)
        self.rodape.addStretch(1)
        self._botoes: list[QPushButton] = []
        v.addLayout(self.rodape)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.tipo = ""

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.fechar("x")
            return
        super().keyPressEvent(e)

    def mostrar(self, tipo, titulo, corpo_html, botoes, passos=""):
        """botoes: lista de (texto, função, primário). A função recebe nada; para fechar o
        quadro ela mesma chama fechar("botao") (ou troca o conteúdo, como no tutorial)."""
        self.tipo = tipo
        self.l_titulo.setText(titulo)
        self.l_corpo.setText(corpo_html)
        self.l_passos.setText(passos)
        self.b_x.setToolTip(t("fechar_esc"))
        for b in self._botoes:
            self.rodape.removeWidget(b)
            b.deleteLater()
        self._botoes = []
        for texto, fn, primario in botoes:
            b = QPushButton(texto)
            if primario:
                b.setObjectName("primario")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            self.rodape.addWidget(b)
            self._botoes.append(b)
        if self._botoes:
            self._botoes[-1].setDefault(True)
        self.adjustSize()
        self.reposicionar()
        self.show()  # sem roubar o teclado: Espaço, setas etc. continuam no player; Esc fecha
        self.raise_()

    def reposicionar(self):
        j = self._janela
        if not j.isVisible():
            return
        centro = j.mapToGlobal(QPoint(j.width() // 2, j.height() // 2))
        self.move(centro.x() - self.width() // 2, centro.y() - self.height() // 2 - 30)

    def botoes(self):
        return list(self._botoes)

    def fechar(self, como="x"):
        if not self.isVisible():
            return
        tipo = self.tipo
        self.hide()
        self.tipo = ""
        self.fechou.emit(f"{tipo}:{como}")
