"""Quadro "Apoiar ♥" (regra 16): doação opcional, Brasil (Pix) ou outro país (GitHub Sponsors).

Abre só pelo rodapé, nunca sozinho; não trava nada e não muda nenhum recurso. Nada vai para a
internet: o Pix e o QR são feitos aqui (ciranda/pix.py); o Sponsors abre no navegador padrão.
Fecha no X, no Esc ou clicando fora. Enquanto aberto, o Tab fica dentro dele.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from . import config, pix, textos
from .icones import icone
from .textos import t

DESTAQUE = "#ff8a3d"
APAGADO = "#8a8c97"

QSS_APOIO = f"""
QFrame#apoio {{ background: #17181d; border: 1px solid #33363f; }}
QLabel#apoioTitulo {{ font-size: 17px; font-weight: 600; }}
QLabel#apoioTexto {{ color: #c9cad2; font-size: 13px; }}
QLabel#apoioPeq {{ color: {APAGADO}; font-size: 11.5px; }}
QPushButton#cartao {{ background: #1d1f25; border: 1px solid #2c2f37; border-radius: 12px; padding: 14px;
                      text-align: left; }}
QPushButton#cartao:hover {{ background: #23252c; border-color: #4a4c55; }}
QPushButton#cartao:focus {{ border-color: #6f717c; }}
QPushButton#cartao[provavel="true"] {{ border: 2px solid {DESTAQUE}; background: #21180f; }}
QPushButton#valor {{ background: #1d1f25; border: 1px solid #2c2f37; border-radius: 8px; padding: 7px 4px; }}
QPushButton#valor:checked {{ background: #2a1d14; border: 1px solid {DESTAQUE}; color: #ffffff; font-weight: 600; }}
QPushButton#voltar {{ background: transparent; border: none; color: {APAGADO}; padding: 6px 2px; }}
QPushButton#voltar:hover, QPushButton#voltar:focus {{ color: #ececf1; }}
QLineEdit {{ background: #1b1d22; border: 1px solid #2c2f37; border-radius: 8px; padding: 6px 8px; }}
QLineEdit:focus {{ border-color: {DESTAQUE}; }}
QLabel#qr {{ background: #ffffff; border-radius: 10px; }}
"""


def _abrir_url(url: str):  # trocado nos testes
    QDesktopServices.openUrl(QUrl(url))


class _Cartao(QPushButton):
    """Cartão grande: ícone + título + linha pequena."""

    def __init__(self, nome_icone, pai=None):
        super().__init__(pai)
        self.setObjectName("cartao")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(118)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(6)
        self.ic = QLabel()
        self.ic.setPixmap(icone(nome_icone, "#ececf1", 30).pixmap(30, 30))
        self.ic.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.l_titulo = QLabel()
        self.l_titulo.setStyleSheet("font-size: 15px; font-weight: 600; background: transparent;")
        self.l_sub = QLabel()
        self.l_sub.setWordWrap(True)
        self.l_sub.setStyleSheet(f"color: {APAGADO}; font-size: 12px; background: transparent;")
        for w in (self.ic, self.l_titulo, self.l_sub):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            v.addWidget(w)
        v.addStretch(1)

    def textos(self, titulo, sub):
        self.l_titulo.setText(titulo)
        self.l_sub.setText(sub)
        self.setAccessibleName(f"{titulo}. {sub}")


class _Pilha(QWidget):
    """Os três passos um sobre o outro; só o atual aparece e o quadro fica com a altura dele
    (o QStackedWidget usaria a altura do maior)."""

    def __init__(self):
        super().__init__()
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._paginas = []
        self._i = 0

    def addWidget(self, w):
        self._paginas.append(w)
        self._v.addWidget(w)
        w.setVisible(len(self._paginas) - 1 == self._i)

    def setCurrentIndex(self, i):
        self._i = i
        for k, w in enumerate(self._paginas):
            w.setVisible(k == i)

    def currentIndex(self):
        return self._i

    def count(self):
        return len(self._paginas)

    def widget(self, i):
        return self._paginas[i]


class QuadroApoio(QFrame):
    LARGURA = 470

    def __init__(self, janela: QWidget, cfg: dict):
        super().__init__(janela, Qt.Tool | Qt.FramelessWindowHint)
        self.setObjectName("apoio")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(QSS_APOIO)
        self.setFixedWidth(self.LARGURA)
        self._janela = janela
        self._cfg = cfg
        self._valor = 10           # int, Decimal ou None (livre)
        self._codigo = ""
        self._filtro = False

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(22, 16, 14, 18)
        raiz.setSpacing(10)
        topo = QHBoxLayout()
        self.l_titulo = QLabel()
        self.l_titulo.setObjectName("apoioTitulo")
        self.b_x = QToolButton()
        self.b_x.setIcon(icone("fechar", "#c9cad2", 14))
        self.b_x.setCursor(Qt.PointingHandCursor)
        self.b_x.clicked.connect(self.close)
        topo.addWidget(self.l_titulo, 1)
        topo.addWidget(self.b_x, 0, Qt.AlignTop)
        raiz.addLayout(topo)
        self.pilha = _Pilha()
        raiz.addWidget(self.pilha)
        self._montar_escolha()
        self._montar_pix()
        self._montar_fora()
        self.retraduzir()

    # ---------- montagem ----------
    def _montar_escolha(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 4, 8, 0)
        v.setSpacing(12)
        h = QHBoxLayout()
        h.setSpacing(10)
        self.c_br = _Cartao("bandeira_br")
        self.c_fora = _Cartao("globo")
        self.c_br.clicked.connect(lambda: self.ir("br"))
        self.c_fora.clicked.connect(lambda: self.ir("fora"))
        h.addWidget(self.c_br, 1)
        h.addWidget(self.c_fora, 1)
        v.addLayout(h)
        self.l_opcional = QLabel()
        self.l_opcional.setObjectName("apoioPeq")
        self.l_opcional.setWordWrap(True)
        self.l_opcional.setAlignment(Qt.AlignCenter)
        v.addWidget(self.l_opcional)
        self.pilha.addWidget(p)

    def _montar_pix(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(10)
        h = QHBoxLayout()
        h.setSpacing(6)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.b_valores = {}
        for val in pix.VALORES:
            b = QPushButton(pix.reais(val))
            b.setObjectName("valor")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, x=val: self.escolher_valor(x))
            self.grupo.addButton(b)
            self.b_valores[val] = b
            h.addWidget(b, 1)
        self.b_outro = QPushButton()
        self.b_outro.setObjectName("valor")
        self.b_outro.setCheckable(True)
        self.b_outro.setCursor(Qt.PointingHandCursor)
        self.b_outro.clicked.connect(self._outro_valor)
        self.grupo.addButton(self.b_outro)
        h.addWidget(self.b_outro, 2)
        v.addLayout(h)
        self.campo = QLineEdit()
        self.campo.setMaxLength(12)
        self.campo.textEdited.connect(lambda _: self._campo_mudou())
        self.campo.returnPressed.connect(self._campo_mudou)
        self.campo.hide()
        v.addWidget(self.campo)
        self.l_campo = QLabel()
        self.l_campo.setObjectName("apoioPeq")
        self.l_campo.setWordWrap(True)
        self.l_campo.hide()
        v.addWidget(self.l_campo)
        self.qr = QLabel()
        self.qr.setObjectName("qr")
        self.qr.setAlignment(Qt.AlignCenter)
        self.qr.setFixedSize(236, 236)
        v.addWidget(self.qr, 0, Qt.AlignHCenter)
        h2 = QHBoxLayout()
        self.b_copiar = QPushButton()
        self.b_copiar.setObjectName("primario")
        self.b_copiar.setCursor(Qt.PointingHandCursor)
        self.b_copiar.setIcon(icone("copiar", "#1a0f07", 16))
        self.b_copiar.clicked.connect(self.copiar_codigo)
        self.l_copiado = QLabel()
        self.l_copiado.setStyleSheet(f"color: {DESTAQUE}; font-weight: 600;")
        h2.addStretch(1)
        h2.addWidget(self.b_copiar)
        h2.addWidget(self.l_copiado)
        h2.addStretch(1)
        v.addLayout(h2)
        h3 = QHBoxLayout()
        h3.setSpacing(4)
        self.l_chave = QLabel()
        self.l_chave.setObjectName("apoioPeq")
        self.l_chave.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.b_chave = QToolButton()
        self.b_chave.setIcon(icone("copiar", "#c9cad2", 14))
        self.b_chave.setCursor(Qt.PointingHandCursor)
        self.b_chave.clicked.connect(self.copiar_chave)
        h3.addStretch(1)
        h3.addWidget(self.l_chave)
        h3.addWidget(self.b_chave)
        h3.addStretch(1)
        v.addLayout(h3)
        self.l_instr = QLabel()
        self.l_instr.setObjectName("apoioTexto")
        self.l_instr.setWordWrap(True)
        self.l_instr.setAlignment(Qt.AlignCenter)
        v.addWidget(self.l_instr)
        self.b_voltar_br = self._botao_voltar(v)
        self.pilha.addWidget(p)

    def _montar_fora(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 4, 8, 0)
        v.setSpacing(14)
        self.l_fora = QLabel()
        self.l_fora.setObjectName("apoioTexto")
        self.l_fora.setWordWrap(True)
        v.addWidget(self.l_fora)
        self.b_sponsors = QPushButton()
        self.b_sponsors.setObjectName("primario")
        self.b_sponsors.setCursor(Qt.PointingHandCursor)
        self.b_sponsors.setIcon(icone("explorer", "#1a0f07", 16))
        self.b_sponsors.clicked.connect(lambda: _abrir_url(pix.SPONSORS))
        v.addWidget(self.b_sponsors, 0, Qt.AlignLeft)
        self.l_url = QLabel(pix.SPONSORS)
        self.l_url.setObjectName("apoioPeq")
        v.addWidget(self.l_url)
        self.b_voltar_fora = self._botao_voltar(v)
        self.pilha.addWidget(p)

    def _botao_voltar(self, v):
        b = QPushButton()
        b.setObjectName("voltar")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.ir(""))
        v.addWidget(b, 0, Qt.AlignLeft)
        return b

    # ---------- textos ----------
    def retraduzir(self):
        self.c_br.textos(t("apoio_brasil"), t("apoio_brasil_sub"))
        self.c_fora.textos(t("apoio_fora"), t("apoio_fora_sub"))
        provavel_br = textos.atual() == "pt"
        for c, sim in ((self.c_br, provavel_br), (self.c_fora, not provavel_br)):
            c.setProperty("provavel", sim)
            c.style().unpolish(c)
            c.style().polish(c)
        self.l_opcional.setText(t("apoio_opcional"))
        self.b_outro.setText(t("apoio_outro_valor"))
        self.campo.setPlaceholderText("R$ 12,50")
        self.l_campo.setText(t("apoio_valor_dica"))
        self.b_copiar.setText(" " + t("apoio_copiar_codigo"))
        self.l_chave.setText(f"{t('apoio_chave')}: {pix.CHAVE}")
        self.b_chave.setToolTip(t("apoio_copiar_chave"))
        self.b_chave.setAccessibleName(t("apoio_copiar_chave"))
        self.l_instr.setText(t("apoio_instrucoes"))
        self.l_fora.setText(t("apoio_fora_texto"))
        self.b_sponsors.setText(" " + t("apoio_abrir_sponsors"))
        self.b_voltar_br.setText(t("apoio_voltar"))
        self.b_voltar_fora.setText(t("apoio_voltar"))
        self.b_x.setToolTip(t("fechar_esc"))
        self.b_x.setAccessibleName(t("fechar_esc"))
        self._titulo()
        if self.pilha.currentIndex() == 1:
            self._atualizar_qr()

    def _titulo(self):
        i = self.pilha.currentIndex()
        self.l_titulo.setText([t("apoio_onde"), t("apoio_pix_titulo"), t("apoio_fora_titulo")][i])

    # ---------- navegação ----------
    def abrir(self):
        """Pelo rodapé. Abre onde a pessoa parou da última vez (a escolha fica salva só para isso)."""
        self.retraduzir()
        self.ir(self._cfg.get("apoio_escolha") or "", salvar=False)
        self.adjustSize()
        self.reposicionar()
        self.show()
        self.raise_()
        self.activateWindow()
        self._focar()
        if not self._filtro:
            QApplication.instance().installEventFilter(self)
            self._filtro = True

    def ir(self, destino, salvar=True):
        i = {"": 0, "br": 1, "fora": 2}.get(destino, 0)
        self.pilha.setCurrentIndex(i)
        if i == 1:
            self._marcar_valor()
            self._atualizar_qr()
        self._titulo()
        if salvar and destino:
            self._cfg["apoio_escolha"] = destino
            config.salvar(self._cfg)
        self._ajustar()
        if self.isVisible():
            self._focar()

    def _ajustar(self):
        """Altura do passo atual (campo de valor aparece/some) e centro da janela."""
        for w in (self.pilha.widget(self.pilha.currentIndex()), self.pilha):
            if w.layout() is not None:
                w.layout().activate()
        self.layout().activate()
        self.adjustSize()
        if self.isVisible():
            self.reposicionar()

    def _focar(self):
        i = self.pilha.currentIndex()
        alvo = {0: self.c_br if textos.atual() == "pt" else self.c_fora,
                1: self.b_copiar, 2: self.b_sponsors}[i]
        QTimer.singleShot(0, lambda: alvo.setFocus(Qt.TabFocusReason))

    def reposicionar(self):
        j = self._janela
        if not j.isVisible():
            return
        centro = j.mapToGlobal(QPoint(j.width() // 2, j.height() // 2))
        self.move(centro.x() - self.width() // 2, max(j.mapToGlobal(QPoint(0, 0)).y() + 8,
                                                      centro.y() - self.height() // 2 - 20))

    # ---------- valor e QR ----------
    def _marcar_valor(self):
        if self._valor in self.b_valores:
            self.b_valores[self._valor].setChecked(True)
            self.campo.hide()
            self.l_campo.hide()
            self._ajustar()
        else:
            self.b_outro.setChecked(True)
            self.campo.show()
            self.l_campo.show()

    def escolher_valor(self, valor):
        self._valor = valor
        self._marcar_valor()
        self._atualizar_qr()
        self._ajustar()

    def _outro_valor(self):
        self.b_outro.setChecked(True)
        self.campo.show()
        self.l_campo.show()
        self._ajustar()
        self.campo.setFocus()
        self._campo_mudou()

    def _campo_mudou(self):
        try:
            v = pix.ler_valor(self.campo.text())
        except ValueError:
            self.l_campo.setText(t("apoio_valor_ruim"))
            self.l_campo.setStyleSheet("color: #e07a6a;")
            self.b_copiar.setEnabled(False)
            self.qr.setEnabled(False)
            return
        self.l_campo.setText(t("apoio_valor_dica"))
        self.l_campo.setStyleSheet("")
        self.b_copiar.setEnabled(True)
        self.qr.setEnabled(True)
        self._valor = v
        self._atualizar_qr()

    def valor_texto(self):
        return t("apoio_valor_livre") if self._valor is None else pix.reais(self._valor)

    def _atualizar_qr(self):
        self._codigo = pix.br_code(self._valor)
        pm = QPixmap()
        pm.loadFromData(pix.qr_png(self._codigo, tamanho=232))
        self.qr.setPixmap(pm)
        alt = t("apoio_qr_alt", valor=self.valor_texto())
        self.qr.setAccessibleName(alt)
        self.qr.setToolTip(alt)
        self.l_copiado.setText("")

    @property
    def codigo(self):
        return self._codigo

    # ---------- copiar ----------
    def _copiar(self, texto):
        try:
            QGuiApplication.clipboard().setText(texto)
            ok = QGuiApplication.clipboard().text() == texto
        except Exception:
            ok = False
        self.l_copiado.setText(t("apoio_copiado") if ok else "")
        if not ok:  # alternativa: deixa o texto selecionado no campo para Ctrl+C
            self.campo.show()
            self.campo.setText(texto)
            self.campo.selectAll()
            self.campo.setFocus()
        QTimer.singleShot(2500, lambda: self.l_copiado.setText(""))
        return ok

    def copiar_codigo(self):
        return self._copiar(self._codigo)

    def copiar_chave(self):
        return self._copiar(pix.CHAVE)

    # ---------- teclado e fechar ----------
    def event(self, e):
        # o quadro é janela-filha da principal: sem isto, Enter/Espaço/1/2/3/F… virariam atalhos do
        # player (tela cheia, pausa, filtro). Aqui dentro o teclado é só do quadro.
        if e.type() == QEvent.ShortcutOverride:
            e.accept()
            return True
        return super().event(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            w = self.focusWidget()
            if isinstance(w, (QPushButton, QToolButton)) and w.isEnabled():
                w.animateClick()
                return
        super().keyPressEvent(e)

    def eventFilter(self, obj, ev):
        # clique fora do quadro fecha (dentro, segue normal)
        if ev.type() == QEvent.MouseButtonPress and self.isVisible() and isinstance(obj, QWidget):
            if obj.window() is not self:
                QTimer.singleShot(0, self.close)
        return False

    def closeEvent(self, e):
        if self._filtro:
            QApplication.instance().removeEventFilter(self)
            self._filtro = False
        super().closeEvent(e)
        try:
            self._janela.activateWindow()
        except Exception:
            pass
