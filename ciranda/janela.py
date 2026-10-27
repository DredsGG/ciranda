"""Janela principal do Ciranda (PySide6 + libmpv embutido)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time

from PySide6.QtCore import (QAbstractListModel, QByteArray, QElapsedTimer, QModelIndex,
                            QObject, QPoint, QRect, QSize, QSortFilterProxyModel, Qt,
                            QThread, QTimer, Signal)
from PySide6.QtGui import (QActionGroup, QColor, QCursor, QFont, QFontMetrics, QGuiApplication,
                           QIcon, QKeySequence, QPainter, QPixmap, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QFileDialog, QMessageBox,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QListView,
                               QMainWindow, QMenu, QPushButton, QSizePolicy, QSlider,
                               QInputDialog, QStackedWidget, QStyle, QStyledItemDelegate,
                               QToolButton, QVBoxLayout, QWidget)

from . import NOME, VERSAO, atualizacao, config, fotos, relato, textos
from .textos import t
from .biblioteca import Item, varrer_varios
from .fila import Fila
from .icones import icone

WINDOWS = sys.platform == "win32"
PASTA_APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- cores ----------
FUNDO = "#0e0f12"
BARRA = "#16171c"
PAINEL = "#121317"
LINHA = "#24262d"
TEXTO = "#ececf1"
APAGADO = "#8a8c97"
DESTAQUE = "#ff8a3d"     # laranja da Ciranda
DESTAQUE_FUNDO = "#2a1d14"

QSS = f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "DejaVu Sans", sans-serif; font-size: 13px; color: {TEXTO}; }}
QMainWindow, #raiz {{ background: {FUNDO}; }}
#barra {{ background: {BARRA}; border-top: 1px solid {LINHA}; }}
#painel {{ background: {PAINEL}; border-left: 1px solid {LINHA}; }}
#vazio {{ background: {FUNDO}; border: 2px solid transparent; border-radius: 14px; margin: 10px; }}
#vazio[arrastando="true"] {{ background: #16120f; border: 2px dashed {DESTAQUE}; }}
QLabel#tile {{ background: #1f2127; border-radius: 9px; }}
QLabel#nome {{ font-size: 13.5px; font-weight: 600; }}
QLabel#sub {{ font-size: 12px; color: {APAGADO}; }}
QLabel#tempo {{ font-size: 11.5px; color: {APAGADO}; }}
QLabel#tituloPainel {{ font-size: 16px; font-weight: 600; }}
QFrame#sep {{ background: {LINHA}; }}
QLabel#apagado {{ color: {APAGADO}; }}
QLabel#assinatura, QLabel#acoesRodape {{ color: #6f717c; font-size: 11.5px; }}
QLabel#titulo {{ font-size: 14px; font-weight: 600; }}
QLabel#grande {{ font-size: 22px; font-weight: 600; }}
QToolButton {{ background: transparent; border: none; border-radius: 8px; padding: 6px; }}
QToolButton:hover {{ background: #23252c; }}
QToolButton:pressed {{ background: #2b2e36; }}
QToolButton:checked {{ background: {DESTAQUE_FUNDO}; }}
QToolButton#play {{ background: {DESTAQUE}; border-radius: 21px; padding: 10px; }}
QToolButton#play:hover {{ background: #ff9b57; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QPushButton {{ background: #22242b; border: 1px solid {LINHA}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ background: #2a2d35; }}
QPushButton#primario {{ background: {DESTAQUE}; border: none; color: #1a0f07; font-weight: 600; }}
QPushButton#primario:hover {{ background: #ff9b57; }}
QPushButton#segmento {{ background: transparent; border: none; border-radius: 6px; padding: 6px 10px; color: {APAGADO}; }}
QPushButton#segmento:hover {{ color: {TEXTO}; }}
QPushButton#segmento:checked {{ background: #2b2e36; color: {TEXTO}; }}
QFrame#faixa {{ background: #1f1812; border-bottom: 1px solid #3a2a1d; }}
QFrame#segmentos {{ background: #1d1f25; border: 1px solid {LINHA}; border-radius: 8px; }}
QSlider {{ min-height: 18px; }}
QSlider::groove:horizontal {{ height: 4px; background: #2c2f37; border-radius: 2px; }}
QSlider::groove:horizontal:hover {{ height: 6px; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {DESTAQUE}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {TEXTO}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
QSlider::handle:horizontal:hover {{ background: #ffffff; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
QSlider:disabled::sub-page:horizontal {{ background: #6b4a33; }}
QSlider:disabled::handle:horizontal {{ background: transparent; }}
QToolButton#pilula {{ background: #1d1f25; border: 1px solid {LINHA}; border-radius: 8px; padding: 6px 12px 6px 9px; }}
QToolButton#pilula:hover {{ background: #24262d; border-color: #33363f; }}
QLineEdit {{ background: #1b1d22; border: 1px solid {LINHA}; border-radius: 8px; padding: 7px 10px; }}
QLineEdit:focus {{ border-color: #5a4232; }}
QListView {{ background: transparent; border: none; outline: 0; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #2c2f37; border-radius: 4px; min-height: 30px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QMenu {{ background: #1b1d22; border: 1px solid {LINHA}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: #2a2d35; }}
QToolTip {{ background: #1b1d22; color: {TEXTO}; border: 1px solid {LINHA}; padding: 4px 6px; }}
"""


def fmt_tempo(seg) -> str:
    if seg is None or seg != seg or seg < 0:
        return "0:00"
    seg = int(seg)
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def mostrar_no_explorer(caminho: str) -> bool:
    """Abre a pasta do arquivo no Explorer com ele já selecionado."""
    caminho = os.path.normpath(caminho)
    if not WINDOWS:
        subprocess.Popen(["xdg-open", os.path.dirname(caminho)])
        return True
    import ctypes
    from ctypes import wintypes
    try:
        ole32 = ctypes.windll.ole32
        shell32 = ctypes.windll.shell32
        ole32.CoInitialize(None)
        shell32.ILCreateFromPathW.restype = ctypes.c_void_p
        shell32.ILCreateFromPathW.argtypes = [wintypes.LPCWSTR]
        shell32.SHOpenFolderAndSelectItems.argtypes = [ctypes.c_void_p, wintypes.UINT,
                                                       ctypes.c_void_p, wintypes.DWORD]
        shell32.ILFree.argtypes = [ctypes.c_void_p]
        pidl = shell32.ILCreateFromPathW(caminho)
        if pidl:
            try:
                if shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0) == 0:
                    return True
            finally:
                shell32.ILFree(pidl)
    except Exception:
        pass
    try:  # reserva: linha de comando com as aspas do jeito que o explorer entende
        subprocess.Popen(f'explorer.exe /select,"{caminho}"')
        return True
    except Exception:
        try:
            os.startfile(os.path.dirname(caminho))
            return True
        except Exception:
            return False


def desarmar_janelas_filhas(hwnd: int):
    """No Windows, desativa a janela que o mpv cria dentro da nossa. Assim clique,
    roda do mouse e teclado continuam chegando no programa (o mpv só desenha)."""
    if not WINDOWS:
        return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        user32.EnableWindow(h, False)
        return True

    user32.EnumChildWindows(wintypes.HWND(hwnd), PROC(cb), 0)


# ---------- ponte entre a thread do mpv e a interface ----------
class Ponte(QObject):
    fim_video = Signal()
    erro_arquivo = Signal()
    tempo = Signal(float)
    duracao = Signal(float)
    pausa = Signal(bool)
    heic_pronto = Signal(int, str)


class PonteAtualizacao(QObject):
    resposta = Signal(object, str)   # (dicionário do atualizacao.procurar ou Exception, modo)


class Varredor(QThread):
    progresso = Signal(int, str)
    pronto = Signal(list, bool, object)

    def __init__(self, caminhos, adicionar: bool):
        super().__init__()
        self.caminhos = caminhos
        self.adicionar = adicionar
        self._parar = False

    def parar(self):
        self._parar = True

    def run(self):
        stats: dict = {}
        itens = varrer_varios(self.caminhos, lambda: self._parar,
                              lambda n, p: self.progresso.emit(n, p), stats)
        if not self._parar:
            self.pronto.emit(itens, self.adicionar, stats)


# ---------- lista da fila ----------
class ModeloFila(QAbstractListModel):
    ITEM = Qt.UserRole + 1
    ATUAL = Qt.UserRole + 2
    INDICE = Qt.UserRole + 3

    def __init__(self, fila: Fila):
        super().__init__()
        self.fila = fila
        self._ordem: list[int] = []

    def recarregar(self):
        self.beginResetModel()
        self._ordem = self.fila.ordem
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._ordem)

    def linha_do_atual(self) -> int:
        i = self.fila.indice_atual
        try:
            return self._ordem.index(i) if i is not None else -1
        except ValueError:
            return -1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._ordem):
            return None
        i = self._ordem[index.row()]
        if i >= len(self.fila.itens):
            return None
        item = self.fila.itens[i]
        if role == Qt.DisplayRole:
            return f"{item.nome} {item.pasta_rel}"
        if role == self.ITEM:
            return item
        if role == self.INDICE:
            return i
        if role == self.ATUAL:
            return i == self.fila.indice_atual
        if role == Qt.ToolTipRole:
            return item.caminho
        return None


class Delegado(QStyledItemDelegate):
    ALTURA = 46

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ALTURA)

    def paint(self, p: QPainter, option, index):
        item: Item = index.data(ModeloFila.ITEM)
        if item is None:
            return
        atual = index.data(ModeloFila.ATUAL)
        r = option.rect.adjusted(6, 2, -6, -2)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if atual:
            p.setBrush(QColor(DESTAQUE_FUNDO))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 8, 8)
            p.setBrush(QColor(DESTAQUE))
            p.drawRoundedRect(QRect(r.left(), r.top() + 10, 3, r.height() - 20), 1.5, 1.5)
        elif option.state & QStyle.State_Selected:
            p.setBrush(QColor("#22242b"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 8, 8)
        elif option.state & QStyle.State_MouseOver:
            p.setBrush(QColor("#1a1c21"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 8, 8)

        cor_ic = DESTAQUE if atual else ("#c35b5b" if item.falhou else APAGADO)
        ic = icone("foto" if item.tipo == "foto" else "video", cor_ic, 18)
        ic.paint(p, QRect(r.left() + 12, r.top() + (r.height() - 18) // 2, 18, 18))

        x = r.left() + 40
        w = r.width() - 48
        f1 = QFont(option.font)
        f1.setWeight(QFont.DemiBold if atual else QFont.Normal)
        p.setFont(f1)
        p.setPen(QColor("#c35b5b" if item.falhou else (TEXTO if atual else "#d4d5dc")))
        nome = QFontMetrics(f1).elidedText(item.nome, Qt.ElideMiddle, w)
        p.drawText(QRect(x, r.top() + 4, w, 20), Qt.AlignLeft | Qt.AlignVCenter, nome)
        f2 = QFont(option.font)
        f2.setPointSizeF(max(7.0, option.font.pointSizeF() - 1.5))
        p.setFont(f2)
        p.setPen(QColor(APAGADO))
        pasta = item.pasta_rel or os.path.basename(item.raiz) or item.raiz
        if item.falhou:
            pasta = t("nao_abriu_pasta") + pasta
        pasta = QFontMetrics(f2).elidedText(pasta, Qt.ElideLeft, w)
        p.drawText(QRect(x, r.top() + 22, w, 18), Qt.AlignLeft | Qt.AlignVCenter, pasta)
        p.restore()


# ---------- área do vídeo ----------
class TelaVideo(QWidget):
    clique = Signal()
    duplo_clique = Signal()
    roda = Signal(int)
    menu = Signal(QPoint)

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_NativeWindow)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setStyleSheet("background: black;")
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._t_clique = QTimer(self, singleShot=True, interval=230)
        self._t_clique.timeout.connect(self.clique.emit)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._t_clique.start()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._t_clique.stop()
            self.duplo_clique.emit()

    def wheelEvent(self, e):
        self.roda.emit(1 if e.angleDelta().y() > 0 else -1)

    def contextMenuEvent(self, e):
        self.menu.emit(e.globalPos())


class Vazio(QWidget):
    """Tela de início: arrastar pastas ou abrir."""

    def __init__(self, janela: "Janela"):
        super().__init__()
        self.setObjectName("vazio")
        self.setAttribute(Qt.WA_StyledBackground)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignCenter)
        png = os.path.join(PASTA_APP, "ui", "ciranda-256.png")
        if os.path.exists(png):
            self.logo.setPixmap(QPixmap(png).scaled(112, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.titulo = QLabel()
        self.titulo.setObjectName("grande")
        self.titulo.setAlignment(Qt.AlignCenter)
        self.sub = QLabel()
        self.sub.setObjectName("apagado")
        self.sub.setAlignment(Qt.AlignCenter)
        botoes = QHBoxLayout()
        botoes.setAlignment(Qt.AlignCenter)
        self.b_abrir = QPushButton(icone("pasta", "#1a0f07", 18), "")
        self.b_abrir.setObjectName("primario")
        self.b_abrir.clicked.connect(janela.abrir_pasta)
        self.b_continuar = QPushButton()
        self.b_continuar.clicked.connect(janela.continuar_ultimas)
        botoes.addWidget(self.b_abrir)
        botoes.addWidget(self.b_continuar)
        self.status = QLabel("")
        self.status.setObjectName("apagado")
        self.status.setAlignment(Qt.AlignCenter)
        self.assinatura = assinatura(self)
        self.acoes = acoes_rodape(janela, self)
        rodape = QHBoxLayout()
        rodape.setAlignment(Qt.AlignCenter)
        rodape.setSpacing(0)
        separador = QLabel(" · ")
        separador.setObjectName("assinatura")
        rodape.addWidget(self.acoes)
        rodape.addWidget(separador)
        rodape.addWidget(self.assinatura)
        self.seletor = seletor_idioma(janela, self)
        self.seletor.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.logo)
        lay.addSpacing(6)
        lay.addWidget(self.titulo)
        lay.addWidget(self.sub)
        lay.addSpacing(10)
        lay.addLayout(botoes)
        lay.addSpacing(8)
        lay.addWidget(self.status)
        lay.addSpacing(30)
        lay.addLayout(rodape)
        lay.addWidget(self.seletor)
        self._pastas = []
        self._ligado = False
        self.retraduzir()

    def retraduzir(self):
        self.titulo.setText(t("solte_para_tocar") if self._ligado else t("arraste_aqui"))
        self.sub.setText(t("vazio_sub"))
        self.b_abrir.setText("  " + t("abrir_pasta"))
        self.acoes.retraduzir()
        self.assinatura.retraduzir()
        self.seletor.retraduzir()
        self.atualizar_continuar(self._pastas)

    def destacar(self, ligado):
        self.setProperty("arrastando", bool(ligado))
        self._ligado = bool(ligado)
        self.titulo.setText(t("solte_para_tocar") if ligado else t("arraste_aqui"))
        self.style().unpolish(self)
        self.style().polish(self)

    def atualizar_continuar(self, pastas):
        self._pastas = list(pastas)
        if pastas:
            if len(pastas) == 1:
                nomes = os.path.basename(pastas[0].rstrip("\\/")) or pastas[0]
            else:
                nomes = t("n_pastas", n=len(pastas))
            self.b_continuar.setText(t("continuar_ultima", nomes=nomes))
            self.b_continuar.show()
        else:
            self.b_continuar.hide()


GITHUB = "https://github.com/DredsGG"


def acoes_rodape(janela, pai=None) -> QLabel:
    """Rodapé padrão (regra 9, itens a e b): "Relatar bug · Procurar atualização".
    Links internos: chamam a janela, não abrem navegador."""
    lab = QLabel(pai)
    lab.setObjectName("acoesRodape")
    lab.setTextFormat(Qt.RichText)
    estilo = f"color:{APAGADO}; text-decoration:none;"

    def retraduzir():
        lab.setText(f'<a href="acao:bug" style="{estilo}">{t("relatar_bug")}</a>'
                    f'<span style="color:#4a4c55"> · </span>'
                    f'<a href="acao:atualizar" style="{estilo}">{t("procurar_atualizacao")}</a>')
    lab.retraduzir = retraduzir
    retraduzir()
    lab.setOpenExternalLinks(False)
    lab.setTextInteractionFlags(Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard)
    lab.setCursor(Qt.PointingHandCursor)

    def clicou(href):
        if href == "acao:bug":
            QTimer.singleShot(0, janela.relatar_bug)
        elif href == "acao:atualizar":
            QTimer.singleShot(0, lambda: janela.procurar_atualizacao(manual=True))
    lab.linkActivated.connect(clicou)
    return lab


def seletor_idioma(janela, pai=None) -> QLabel:
    """Rodapé (regra 13): "?  ·  PT · EN · ES". O ? abre o tutorial; o idioma atual fica em laranja."""
    lab = QLabel(pai)
    lab.setObjectName("acoesRodape")
    lab.setTextFormat(Qt.RichText)
    lab.setOpenExternalLinks(False)
    lab.setTextInteractionFlags(Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard)
    lab.setCursor(Qt.PointingHandCursor)

    def retraduzir():
        partes = []
        for i in textos.IDIOMAS:
            if i == textos.atual():
                partes.append(f'<a href="idioma:{i}" style="color:{DESTAQUE}; text-decoration:none;">'
                              f'<b>{textos.NOMES[i]}</b></a>')
            else:
                partes.append(f'<a href="idioma:{i}" style="color:{APAGADO}; text-decoration:none;">'
                              f'{textos.NOMES[i]}</a>')
        sep = '<span style="color:#4a4c55"> · </span>'
        lab.setText(f'<a href="acao:tutorial" style="color:{APAGADO}; text-decoration:none;"><b>?</b></a>'
                    f'<span style="color:#4a4c55">&nbsp;&nbsp;·&nbsp;&nbsp;</span>' + sep.join(partes))
        lab.setToolTip(f"? = {t('como_usar')} · {t('idioma')}: PT · EN · ES")
    lab.retraduzir = retraduzir
    retraduzir()

    def clicou(href):
        if href.startswith("idioma:"):
            QTimer.singleShot(0, lambda: janela.mudar_idioma(href.split(":", 1)[1]))
        elif href == "acao:tutorial":
            QTimer.singleShot(0, janela.mostrar_tutorial)
    lab.linkActivated.connect(clicou)
    return lab


def assinatura(pai=None) -> QLabel:
    """Rodapé padrão de todo projeto do André (regra 9): "feito por Dreds · vX.Y.Z",
    com "Dreds" abrindo o GitHub no navegador padrão. Versão sempre da constante VERSAO."""
    lab = QLabel(pai)
    lab.setObjectName("assinatura")
    lab.setTextFormat(Qt.RichText)

    def retraduzir():
        lab.setText(f'{t("feito_por")} <a href="{GITHUB}" style="color:{DESTAQUE}; text-decoration:none;">'
                    f'<b>Dreds</b></a> · v{VERSAO}')
    lab.retraduzir = retraduzir
    retraduzir()
    lab.setOpenExternalLinks(True)  # QDesktopServices.openUrl -> navegador padrão
    lab.setTextInteractionFlags(Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard)
    lab.setToolTip(GITHUB)
    return lab


class Clicavel(QWidget):
    """Área (ou rótulo) que responde a clique."""
    clicked = Signal()

    def __init__(self, rotulo=None):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.texto = None
        if rotulo is not None:
            lay = QHBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            self.texto = QLabel(rotulo)
            lay.addWidget(self.texto)

    def setText(self, t):
        if self.texto is not None:
            self.texto.setText(t)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


# ---------- menu com título, explicação e atalho ----------
class MenuRico(QMenu):
    """Menu padrão do Qt (QAction comum). Mesma API de antes (titulo / explica / linha),
    mas sem widgets personalizados dentro do menu: na 1.1.0-1.1.2 o menu feito com
    QWidgetAction não aparecia no Windows do André (o menu padrão da 1.0.1 aparecia)."""

    def __init__(self, pai):
        super().__init__(pai)
        self.setToolTipsVisible(True)  # a explicação de cada linha aparece no hover

    def titulo(self, texto):
        if self.actions():
            self.addSeparator()
        a = self.addAction(texto.upper())
        a.setEnabled(False)
        f = a.font()
        f.setPointSizeF(max(7.5, f.pointSizeF() - 1.5))
        f.setBold(True)
        a.setFont(f)

    def explica(self, texto):
        a = self.addAction(texto)
        a.setEnabled(False)

    def linha(self, nome_icone, titulo, desc, atalho, slot, perigo=False, ativo=True):
        cor = "#ff7b72" if perigo else TEXTO
        # "\t" mostra o atalho na coluna da direita sem registrar atalho duplicado
        a = self.addAction(icone(nome_icone, cor, 16), f"{titulo}\t{atalho}" if atalho else titulo)
        if desc:
            a.setToolTip(desc)
            a.setStatusTip(desc)
        a.setEnabled(bool(ativo))
        a.triggered.connect(lambda _=False: QTimer.singleShot(0, slot))
        return a


class BotaoTempoFoto(QToolButton):
    """Botão "Foto: 5 s" com tempos prontos. Mesmo jeito de usar de um QSpinBox
    (value / setValue / valueChanged), para o resto do código não mudar."""
    valueChanged = Signal(int)
    OPCOES = (2, 3, 5, 8, 10, 15, 20, 30, 60)

    def __init__(self, valor, pai):
        super().__init__(pai)
        self.setObjectName("pilula")
        self._v = max(1, min(600, int(valor)))
        self.setIcon(icone("relogio", TEXTO, 17))
        self.setIconSize(QSize(17, 17))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setPopupMode(QToolButton.InstantPopup)
        self.setToolTip(t("dica_tempo_foto"))
        self.menu_ = MenuRico(self)
        self.menu_.aboutToShow.connect(self._montar)
        self.setMenu(self.menu_)
        self._atualizar_texto()

    def _fmt(self, v):
        return f"{v // 60} min" if v >= 60 and v % 60 == 0 else f"{v} s"

    def retraduzir(self):
        self.setToolTip(t("dica_tempo_foto"))
        self._atualizar_texto()

    def compacto(self, sim: bool):
        self._compacto = sim
        self._atualizar_texto()

    def _atualizar_texto(self):
        if getattr(self, "_compacto", False):
            self.setText(f"{self._fmt(self._v)} ▾")
        else:
            self.setText(t("foto_rotulo", tempo=self._fmt(self._v)) + "  ▾")
        # o Qt não soma o padding do estilo: largura = texto + ícone + respiro
        self.setMinimumWidth(QFontMetrics(self.font()).horizontalAdvance(self.text()) + 17 + 38)

    def _montar(self):
        m = self.menu_
        m.clear()
        m.titulo(t("tempo_de_cada_foto"))
        m.explica(t("video_nao_usa"))
        grupo = QActionGroup(m)
        for v in self.OPCOES:
            a = m.addAction(self._fmt(v))
            a.setCheckable(True)
            a.setChecked(v == self._v)
            grupo.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self.setValue(v))
        m.addSeparator()
        outro = m.addAction(t("outro_tempo"))
        if self._v not in self.OPCOES:
            outro.setText(t("outro_tempo_agora", tempo=self._fmt(self._v)))
        outro.triggered.connect(self._outro)

    def _outro(self):
        v, ok = QInputDialog.getInt(self.window(), t("tempo_de_cada_foto"), t("segundos"), self._v, 1, 600)
        if ok:
            self.setValue(v)

    def value(self):
        return self._v

    def setValue(self, v):
        v = max(1, min(600, int(v)))
        if v != self._v:
            self._v = v
            self._atualizar_texto()
            self.valueChanged.emit(v)


# ---------- janela ----------
class Janela(QMainWindow):
    def __init__(self, caminhos_iniciais=None):
        super().__init__()
        self._config_existia = config.existe()
        self.cfg = config.carregar()
        textos.iniciar(self.cfg)
        self._fixos = []  # textos fixos da tela, refeitos quando o idioma muda
        self.fila = Fila()
        self.fila.aleatorio = bool(self.cfg["aleatorio"])
        self.fila.repetir = self.cfg["repetir"] if self.cfg["repetir"] in ("nao", "tudo", "um") else "tudo"
        self.fila.filtro = self.cfg["filtro"] if self.cfg["filtro"] in ("tudo", "fotos", "videos") else "tudo"
        self.pastas_abertas: list[str] = []
        self.varredor: Varredor | None = None
        self.ponte = Ponte()
        self._token = 0
        self._item: Item | None = None
        self._carregou_em = 0.0
        self._duracao = 0.0
        self._arrastando = False
        self._erros_seguidos = 0
        self._fim_da_fila = False
        self._ignorados = 0
        self._pastas_lidas = 0
        self._foto_relogio = QElapsedTimer()
        self._foto_restante_ms = 0
        self._foto_total_ms = 0
        self._t_foto = QTimer(self, singleShot=True)
        self._t_foto.timeout.connect(self._foto_acabou)
        self._t_ui = QTimer(self, interval=100)
        self._t_ui.timeout.connect(self._tique)
        self._t_ui.start()
        self._cursor_antes = QPoint()
        self._t_esconder = QTimer(self, singleShot=True, interval=2500)
        self._t_esconder.timeout.connect(self._esconder_controles)
        self._t_cursor = QTimer(self, interval=150)
        self._t_cursor.timeout.connect(self._vigiar_cursor)
        self._painel_antes_tela_cheia = True

        self.setWindowTitle(NOME)
        ico = os.path.join(PASTA_APP, "ui", "ciranda.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))
        self.setAcceptDrops(True)
        self.setMinimumSize(880, 520)
        self._montar()
        self._criar_mpv()
        self._atalhos()
        self._aplicar_modos_na_tela()

        geo = self.cfg.get("geometria")
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))
        else:
            self.resize(1180, 720)
        self.painel.setVisible(bool(self.cfg["painel"]))
        self.b_painel.setChecked(bool(self.cfg["painel"]))
        self.vazio.atualizar_continuar([p for p in self.cfg["ultimas_pastas"] if os.path.exists(p)])
        if caminhos_iniciais:
            QTimer.singleShot(0, lambda: self.carregar(caminhos_iniciais, adicionar=False))
        QTimer.singleShot(0, self._barra_titulo_escura)

        # atualização sozinha: confere ao abrir (depois de 4 s) e a cada 6 horas
        self._info_atualizacao = None
        self._dlg_atualizacao = None
        self._ponte_atualizacao = PonteAtualizacao()
        self._ponte_atualizacao.resposta.connect(self._resposta_atualizacao)
        self._t_atualizacao = QTimer(self, interval=6 * 3600 * 1000)
        self._t_atualizacao.timeout.connect(lambda: self.procurar_atualizacao(manual=False))
        if not os.environ.get("CIRANDA_SEM_ATUALIZACAO"):
            QTimer.singleShot(4000, lambda: self.procurar_atualizacao(manual=False, abertura=True))
            self._t_atualizacao.start()

        # quadro no meio da janela: tutorial, novidades e nova versão (regras 12 e 14)
        from .quadro import Quadro
        self.quadro = Quadro(self)
        self.quadro.fechou.connect(self._quadro_fechou)
        self._quadro_render = None
        self._quadros_na_fila = []
        self._tut_passo = 0
        self._avisar_se_atualizou()

    # ----- idioma (regra 13) -----
    def _fixo(self, fn):
        """Registra um texto fixo da tela (aplica agora e de novo quando o idioma muda)."""
        self._fixos.append(fn)
        fn()

    def mudar_idioma(self, idioma):
        if idioma not in textos.IDIOMAS:
            return
        textos.definir(idioma)
        self.cfg["idioma"] = idioma
        config.salvar(self.cfg)
        self.retraduzir()
        self._log_linha(f"idioma: {idioma}")

    def retraduzir(self):
        for fn in self._fixos:
            fn()
        self.vazio.retraduzir()
        self.s_foto.retraduzir()
        self._aplicar_modos_na_tela()
        self._atualizar_lista()
        if self._item is not None:
            self._atualizar_info()
        elif self.palco.currentWidget() is self.vazio:
            self.l_nome.setText(t("nada_tocando"))
            self.l_info.setText(t("arraste_para_janela"))
        if self.faixa.isVisible() and self._faixa_render:
            self._faixa_render()
        if self.quadro.isVisible() and self._quadro_render:
            self._quadro_render()

    def _ajustar_barra(self):
        """Barra responsiva: em janela estreita o controle de volume vira só o ícone
        (a roda do mouse no vídeo e as setas continuam mudando o volume)."""
        largura = self.width()
        larga = largura >= 1080
        self.volume.setVisible(larga)
        self.s_foto.compacto(not larga)
        for w in self._lados:
            w.setMinimumWidth(330 if larga else 250)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_lados"):
            self._ajustar_barra()
        if getattr(self, "quadro", None) is not None and self.quadro.isVisible():
            self.quadro.reposicionar()

    def moveEvent(self, e):
        super().moveEvent(e)
        if getattr(self, "quadro", None) is not None and self.quadro.isVisible():
            self.quadro.reposicionar()

    def receber_de_outra_instancia(self, caminhos):
        """Outro Ciranda foi aberto (dois cliques num arquivo, botão direito numa pasta):
        mostra aqui. Vários chegando em seguida (vários arquivos selecionados) se juntam."""
        agora = time.monotonic()
        juntar = bool(self.fila.itens) and (agora - getattr(self, "_ultimo_recebido", 0.0)) < 1.5
        self._ultimo_recebido = agora
        try:
            self._log.write(f"{time.strftime('%H:%M:%S')} recebido de outra instância: "
                            f"{len(caminhos)} caminho(s){' (junta)' if juntar else ''}\n")
            self._log.flush()
        except Exception:
            pass
        if caminhos:
            self.carregar(caminhos, adicionar=juntar)
        self.trazer_para_frente()

    def trazer_para_frente(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        if WINDOWS:
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
            except Exception:
                pass

    def usar_como_padrao(self):
        """Abre a tela do Windows onde o usuário escolhe o Ciranda como padrão
        (o Windows não deixa app nenhum fazer isso sozinho)."""
        for uri in ("ms-settings:defaultapps?registeredAppUser=Ciranda", "ms-settings:defaultapps"):
            try:
                os.startfile(uri)
                return
            except Exception:
                continue

    # ----- faixa de aviso no topo (versão nova / atualizado) -----
    def _montar_faixa(self) -> QFrame:
        self.faixa = QFrame()
        self.faixa.setObjectName("faixa")
        h = QHBoxLayout(self.faixa)
        h.setContentsMargins(16, 7, 10, 7)
        h.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icone("atualizar", DESTAQUE, 16).pixmap(16, 16))
        self.l_faixa = QLabel()
        self.l_faixa.setTextFormat(Qt.RichText)
        self.b_faixa = QPushButton()
        self._fixo(lambda: self.b_faixa.setText(t("ver_e_atualizar")))
        self.b_faixa.setObjectName("primario")
        self.b_faixa.clicked.connect(self._abrir_dialogo_atualizacao)
        fechar = self._botao("fechar", "", self._fechar_faixa, tam=14)
        self._fixo(lambda: fechar.setToolTip(t("depois")))
        h.addWidget(ic)
        h.addWidget(self.l_faixa, 1)
        h.addWidget(self.b_faixa)
        h.addWidget(fechar)
        self.faixa.hide()
        self._faixa_pendente = False
        self._faixa_render = None
        self._t_faixa = QTimer(self, singleShot=True)
        self._t_faixa.timeout.connect(self._fechar_faixa)
        return self.faixa

    def _mostrar_faixa(self, texto, botao=True, some_em_ms=0):
        """`texto` pode ser uma função (refeita quando o idioma muda)."""
        if callable(texto):
            self._faixa_render = lambda: self.l_faixa.setText(texto())
            texto = texto()
        else:
            self._faixa_render = None
        self.l_faixa.setText(texto)
        self.b_faixa.setVisible(botao)
        self._faixa_pendente = True
        if not self.isFullScreen():
            self.faixa.show()
        if some_em_ms:
            self._t_faixa.start(some_em_ms)
        else:
            self._t_faixa.stop()

    def _fechar_faixa(self):
        self._faixa_pendente = False
        self.faixa.hide()

    def _log_linha(self, texto):
        try:
            self._log.write(f"{time.strftime('%H:%M:%S')} {texto}\n")
            self._log.flush()
        except Exception:
            pass

    # ----- atualização sozinha -----
    def procurar_atualizacao(self, manual=False, abertura=False):
        """manual: botão (abre a janela). abertura: ao abrir o Ciranda (quadro no meio).
        Senão é a conferida a cada 6 h (faixa discreta no topo, não cobre o vídeo)."""
        api = os.environ.get("CIRANDA_API_ATUALIZACAO") or atualizacao.API
        raw = os.environ.get("CIRANDA_RAW_NOVIDADES") or atualizacao.RAW_NOVIDADES
        ponte = self._ponte_atualizacao
        modo = "manual" if manual else ("abertura" if abertura else "periodica")
        pasta = atualizacao.pasta_teste(config.pasta_dados()) \
            if (atualizacao.instalado() or os.environ.get("CIRANDA_CANAL_TESTE_SEMPRE")) else ""

        def trabalho():
            try:
                r = atualizacao.procurar(VERSAO, api, raw)
            except Exception as e:
                r = e
            if pasta:  # canal de teste do André: setup mais novo na pasta local ganha
                try:
                    loc = atualizacao.procurar_local(pasta, VERSAO)
                except Exception:
                    loc = None
                if loc and loc["disponivel"] and (
                        isinstance(r, Exception) or not r["disponivel"]
                        or atualizacao.versao_tupla(loc["versao"]) > atualizacao.versao_tupla(r["versao"])):
                    r = loc
            ponte.resposta.emit(r, modo)
        if manual:
            self._status(t("procurando"))
        threading.Thread(target=trabalho, daemon=True).start()

    def _resposta_atualizacao(self, r, modo):
        manual = modo == "manual"
        if isinstance(r, Exception):
            self._log_linha(f"atualização: não deu para conferir ({r.__class__.__name__})")
            if manual:
                QMessageBox.information(self, t("procurar_atualizacao"), t("sem_github"))
            return
        self._log_linha(f"atualização: {'pasta de teste' if r.get('local') else 'GitHub'} tem v{r['versao']}, "
                        f"aqui v{VERSAO}{' (nova!)' if r['disponivel'] else ''}")
        if not r["disponivel"]:
            if manual:
                QMessageBox.information(self, t("procurar_atualizacao"), t("ja_mais_nova", versao=VERSAO))
            return
        self._info_atualizacao = r
        if manual:
            self._abrir_dialogo_atualizacao()
            return
        # o X do aviso esconde esta versão até sair uma mais nova
        if self.cfg.get("aviso_dispensado") == r["versao"] and not r.get("local"):
            self._log_linha(f"atualização: aviso da v{r['versao']} dispensado antes")
            return
        if modo == "abertura":
            self._mostrar_quadro(self._quadro_nova_versao)
        else:
            self._mostrar_faixa(lambda: self._texto_faixa(r))

    def _texto_faixa(self, r):
        if r.get("local"):
            return (t("faixa_teste", versao=r["versao"]) + f' <span style="color:{APAGADO}">· '
                    f'{t("da_pasta_teste")} · {t("voce_esta_na", versao=VERSAO)}</span>')
        return t("faixa_nova", versao=r["versao"]) + f' <span style="color:{APAGADO}">· ' \
            f'{t("voce_esta_na", versao=VERSAO)}</span>'

    def _abrir_dialogo_atualizacao(self, ja_atualizar=False):
        if not self._info_atualizacao:
            return
        from .dialogos import DialogoAtualizacao
        self._fechar_faixa()
        self._dlg_atualizacao = d = DialogoAtualizacao(self, self._info_atualizacao, self._sair_para_atualizar)
        d.open()
        if ja_atualizar and d.pode_instalar:
            d._atualizar()

    def _sair_para_atualizar(self):
        self._log_linha("atualização: instalador rodando, fechando o Ciranda")
        self.close()
        QApplication.instance().quit()

    # ----- quadro no meio da janela -----
    def _mostrar_quadro(self, render):
        if self.quadro.isVisible():
            self._quadros_na_fila.append(render)
            return
        self._quadro_render = render
        render()

    def _quadro_fechou(self, como):
        tipo, _, jeito = como.partition(":")
        if tipo == "nova" and jeito == "x" and self._info_atualizacao:
            self.cfg["aviso_dispensado"] = self._info_atualizacao["versao"]
            config.salvar(self.cfg)
        if tipo == "tutorial":
            self.cfg["tutorial_visto"] = True
            config.salvar(self.cfg)
        self._quadro_render = None
        if self._quadros_na_fila:
            QTimer.singleShot(300, lambda: self._mostrar_quadro(self._quadros_na_fila.pop(0)))

    @staticmethod
    def _lista_html(itens):
        esc = [str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for x in itens]
        return "<br>".join(f"• {x}" for x in esc)

    def _quadro_nova_versao(self):
        r = self._info_atualizacao
        if not r:
            return
        itens = atualizacao.notas_no_idioma(r, textos.atual())[:6]
        corpo = f'<span style="color:{APAGADO}">{t("voce_esta_na_frase", versao=VERSAO)}' \
                f'{t("veio_pasta_teste") if r.get("local") else ""}</span>'
        if itens:
            corpo += f"<br><br><b>{t('o_que_mudou')}</b><br>" + self._lista_html(itens)
        self.quadro.mostrar("nova", t("nova_versao_teste" if r.get("local") else "nova_versao", versao=r["versao"]),
                            corpo, [(t("atualizar"), self._atualizar_pelo_quadro, True)])

    def _atualizar_pelo_quadro(self):
        self.quadro.fechar("botao")
        self._abrir_dialogo_atualizacao(ja_atualizar=True)

    def _quadro_novidades(self, antes):
        itens = (atualizacao.novidades_locais().get(VERSAO) or {})
        itens = itens.get(textos.atual()) or itens.get("en") or []
        corpo = ""
        if antes:
            corpo = f'<span style="color:{APAGADO}">{t("atualizado_de", antes=antes, agora=VERSAO)}</span><br><br>'
        corpo += self._lista_html(itens)
        self.quadro.mostrar("novidades", t("novidades_da", versao=VERSAO), corpo,
                            [(t("entendi"), lambda: self.quadro.fechar("botao"), True)])

    PASSOS_TUTORIAL = 5

    def mostrar_tutorial(self):
        self._tut_passo = 0
        if self.quadro.isVisible() and self.quadro.tipo != "tutorial":
            self.quadro.fechar("botao")
        self._quadros_na_fila = [q for q in self._quadros_na_fila if q != self._quadro_tutorial]
        self._mostrar_quadro(self._quadro_tutorial)

    def _quadro_tutorial(self):
        n = self._tut_passo
        total = self.PASSOS_TUTORIAL
        botoes = [(t("pular"), lambda: self.quadro.fechar("botao"), False)]
        if n > 0:
            botoes.append((t("voltar"), lambda: self._tutorial_ir(-1), False))
        if n < total - 1:
            botoes.append((t("proximo"), lambda: self._tutorial_ir(1), True))
        else:
            botoes = [(t("voltar"), lambda: self._tutorial_ir(-1), False),
                      (t("entendi"), lambda: self.quadro.fechar("botao"), True)]
        self.quadro.mostrar("tutorial", t(f"tut{n + 1}_t"), t(f"tut{n + 1}"), botoes,
                            passos=t("passo_n", n=n + 1, total=total))

    def _tutorial_ir(self, delta):
        self._tut_passo = max(0, min(self.PASSOS_TUTORIAL - 1, self._tut_passo + delta))
        self._quadro_render = self._quadro_tutorial
        self._quadro_tutorial()

    def _avisar_se_atualizou(self):
        """Primeira abertura: tutorial. Depois de atualizar: Novidades da vX.Y.Z (uma vez por versão)."""
        arg = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--atualizado-de=")), "")
        if arg:
            self._log_linha(f"aberto pelo instalador depois de atualizar (antes v{arg.lstrip('v')}, agora v{VERSAO})")
            # o instalador baixado fica na pasta temporária: apaga quando ele já terminou
            QTimer.singleShot(60000, atualizacao.apagar_downloads)
        antes = (arg or self.cfg.get("versao_vista") or "").lstrip("v")
        sem_quadros = os.environ.get("CIRANDA_SEM_QUADROS")  # autoteste e testes antigos
        if arg and atualizacao.versao_tupla(arg) == atualizacao.versao_tupla(VERSAO):
            self._mostrar_faixa(lambda: t("reinstalado", agora=VERSAO), botao=False, some_em_ms=15000)
        elif not sem_quadros and self.cfg.get("novidades_vista") != VERSAO and self._config_existia \
                and (not antes or atualizacao.mais_nova(VERSAO, antes)):
            # quem já usava (a 1.2.0 não gravava a versão vista) e acabou de atualizar
            QTimer.singleShot(600, lambda: self._mostrar_quadro(lambda: self._quadro_novidades(antes)))
        elif not sem_quadros and not self._config_existia and not self.cfg.get("tutorial_visto"):
            QTimer.singleShot(600, self.mostrar_tutorial)
        mudou = False
        if self.cfg.get("versao_vista") != VERSAO:
            self.cfg["versao_vista"] = VERSAO
            mudou = True
        if self.cfg.get("novidades_vista") != VERSAO:
            self.cfg["novidades_vista"] = VERSAO
            mudou = True
        if not self._config_existia:
            self.cfg["tutorial_visto"] = True  # aparece uma vez; o ? do rodapé reabre
            mudou = True
        if mudou:
            config.salvar(self.cfg)

    # ----- relatar bug -----
    def info_diagnostico(self) -> dict:
        """Estado do player para o relato: só números, modos e extensões (sem nomes)."""
        info = {"instalado": atualizacao.instalado()}
        try:
            from PySide6 import __version__ as pyside
            from PySide6.QtCore import qVersion
            info["qt"] = f"{qVersion()} (PySide6 {pyside})"
        except Exception:
            pass
        try:
            info["mpv"] = str(self.mpv.mpv_version)
        except Exception:
            pass
        try:
            info["telas"] = ", ".join(f"{t.size().width()}x{t.size().height()} @{t.devicePixelRatio():g}"
                                      for t in QGuiApplication.screens())
        except Exception:
            pass
        itens = self.fila.itens
        nf = sum(1 for i in itens if i.tipo == "foto")
        info["fila"] = t("diag_fila_txt", itens=len(itens), fotos=nf, videos=len(itens) - nf,
                         abertas=len(self.pastas_abertas), lidas=self._pastas_lidas, outros=self._ignorados)
        info["modos"] = t("diag_modos_txt", aleatorio=t("sim") if self.fila.aleatorio else t("nao"),
                          repetir=self.fila.repetir, filtro=self.fila.filtro, foto=self.s_foto.value(),
                          volume=self.volume.value(), mudo=t("diag_mudo") if self.cfg.get("mudo") else "",
                          cheia=t("sim") if self.isFullScreen() else t("nao"), idioma=textos.atual())
        if self._item is not None:
            ext = os.path.splitext(self._item.caminho)[1].lower() or "?"
            pos = t("diag_em", pos=fmt_tempo(self.busca.value() * self._duracao / 1000), total=fmt_tempo(self._duracao)) \
                if self._item.tipo == "video" and self._duracao else ""
            info["atual"] = f"{self._item.tipo} {ext}{pos}{t('diag_falhou') if self._item.falhou else ''}"
        return info

    def relatar_bug(self):
        from .dialogos import DialogoBug
        diag = relato.diagnostico(self.info_diagnostico(), config.pasta_dados())
        self._dlg_bug = d = DialogoBug(self, diag)
        d.open()

    def _barra_titulo_escura(self):
        """Windows 11: barra de título escura, da cor do app (DWM)."""
        if not WINDOWS:
            return
        try:
            import ctypes
            dwm = ctypes.windll.dwmapi
            hwnd = ctypes.c_void_p(int(self.winId()))

            def attr(n, valor):
                v = ctypes.c_int(valor)
                dwm.DwmSetWindowAttribute(hwnd, n, ctypes.byref(v), ctypes.sizeof(v))
            attr(20, 1)               # DWMWA_USE_IMMERSIVE_DARK_MODE
            attr(35, 0x00120F0E)      # DWMWA_CAPTION_COLOR = #0e0f12 (fundo) em COLORREF 0x00BBGGRR
            attr(36, 0x00F1ECEC)      # DWMWA_TEXT_COLOR
            attr(34, 0x002D2624)      # DWMWA_BORDER_COLOR
        except Exception:
            pass

    # ----- montagem da interface -----
    def _botao(self, nome_icone, dica, slot=None, checavel=False, tam=20) -> QToolButton:
        b = QToolButton()
        b.setIcon(icone(nome_icone, TEXTO, tam))
        b.setIconSize(QSize(tam, tam))
        b.setToolTip(dica)
        b.setCursor(Qt.PointingHandCursor)
        b.setCheckable(checavel)
        b.setFocusPolicy(Qt.NoFocus)
        if slot:
            b.clicked.connect(slot)
        return b

    def _montar(self):
        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.setCentralWidget(raiz)
        v = QVBoxLayout(raiz)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._montar_faixa())

        meio = QHBoxLayout()
        meio.setContentsMargins(0, 0, 0, 0)
        meio.setSpacing(0)
        self.palco = QStackedWidget()
        self.vazio = Vazio(self)
        self.tela = TelaVideo()
        self.tela.clique.connect(self.alternar_pausa)
        self.tela.duplo_clique.connect(self.alternar_tela_cheia)
        self.tela.roda.connect(lambda d: self.mudar_volume(5 * d))
        self.tela.menu.connect(self._menu_video)
        self.palco.addWidget(self.vazio)
        self.palco.addWidget(self.tela)
        meio.addWidget(self.palco, 1)
        self.painel = self._montar_painel()
        meio.addWidget(self.painel)
        v.addLayout(meio, 1)

        self.barra = QFrame()
        self.barra.setObjectName("barra")
        grade = QHBoxLayout(self.barra)
        grade.setContentsMargins(16, 10, 16, 12)
        grade.setSpacing(16)

        # esquerda: o que está tocando (clique = mostra na fila)
        esq = Clicavel()
        self._fixo(lambda: esq.setToolTip(t("mostrar_na_fila")))
        esq.clicked.connect(lambda: (self._mostrar_painel(True), self._rolar_para_atual()))
        el = QHBoxLayout(esq)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(11)
        self.l_tipo = QLabel()
        self.l_tipo.setObjectName("tile")
        self.l_tipo.setFixedSize(42, 42)
        self.l_tipo.setAlignment(Qt.AlignCenter)
        self.l_tipo.setPixmap(icone("pasta", APAGADO, 20).pixmap(20, 20))
        col = QVBoxLayout()
        col.setSpacing(1)
        col.setContentsMargins(0, 2, 0, 2)
        self.l_nome = QLabel(t("nada_tocando"))
        self.l_nome.setObjectName("nome")
        self.l_nome.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.l_info = QLabel(t("arraste_para_janela"))
        self.l_info.setObjectName("sub")
        self.l_info.setTextFormat(Qt.RichText)
        self.l_info.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        col.addWidget(self.l_nome)
        col.addWidget(self.l_info)
        el.addWidget(self.l_tipo)
        el.addLayout(col, 1)

        # centro: controles e progresso
        cen = QWidget()
        cv = QVBoxLayout(cen)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(2)
        self.b_ant = self._botao("anterior", "", self.anterior)
        self.b_play = self._botao("play", "", self.alternar_pausa, tam=22)
        self.b_play.setObjectName("play")
        self.b_play.setIcon(icone("play", "#1a0f07", 22))
        self.b_prox = self._botao("proximo", "", lambda: self.proximo(False))
        self.b_alea = self._botao("aleatorio", "", self.alternar_aleatorio, checavel=True, tam=18)
        self.b_rep = self._botao("repetir", "", self.ciclar_repetir, checavel=True, tam=18)
        tr = QHBoxLayout()
        tr.setSpacing(10)
        tr.addStretch(1)
        for w in (self.b_alea, self.b_ant, self.b_play, self.b_prox, self.b_rep):
            tr.addWidget(w)
        tr.addStretch(1)
        cv.addLayout(tr)
        pr = QHBoxLayout()
        pr.setSpacing(10)
        self.l_tempo = QLabel("0:00")
        self.l_tempo.setObjectName("tempo")
        self.l_tempo.setMinimumWidth(44)
        self.l_tempo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.l_total = Clicavel(rotulo="0:00")
        self.l_total.texto.setObjectName("tempo")
        self.l_total.setMinimumWidth(44)
        self._fixo(lambda: self.l_total.setToolTip(t("dica_total")))
        self.l_total.clicked.connect(self._alternar_restante)
        self._mostrar_restante = False
        self.busca = QSlider(Qt.Horizontal)
        self.busca.setRange(0, 1000)
        self.busca.setFocusPolicy(Qt.NoFocus)
        self.busca.setCursor(Qt.PointingHandCursor)
        self.busca.sliderPressed.connect(lambda: setattr(self, "_arrastando", True))
        self.busca.sliderReleased.connect(self._soltou_busca)
        pr.addWidget(self.l_tempo)
        pr.addWidget(self.busca, 1)
        pr.addWidget(self.l_total)
        cv.addLayout(pr)

        # direita: ajustes
        dir_ = QWidget()
        dl = QHBoxLayout(dir_)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(4)
        self.s_foto = BotaoTempoFoto(int(self.cfg["segundos_foto"]), self)
        self.s_foto.valueChanged.connect(self._mudou_tempo_foto)
        self.b_vol = self._botao("volume", "", self.alternar_mudo, tam=18)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(84)
        self.volume.setFocusPolicy(Qt.NoFocus)
        self.volume.setCursor(Qt.PointingHandCursor)
        self.volume.setValue(int(self.cfg["volume"]))
        self.volume.valueChanged.connect(self._mudou_volume)
        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFixedSize(1, 22)
        self.b_abrir = self._botao("pasta", "", lambda: self._abrir_menu_pastas(self.b_abrir), tam=19)
        self.menu_abrir = MenuRico(self)
        self.b_painel = self._botao("lista", "", self.alternar_painel, checavel=True, tam=19)
        self.b_tela = self._botao("telacheia", "", self.alternar_tela_cheia, tam=19)

        def dicas_barra():
            for b, chave in ((self.b_ant, "dica_anterior"), (self.b_play, "dica_play"), (self.b_prox, "dica_proximo"),
                             (self.b_alea, "dica_aleatorio"), (self.b_vol, "dica_mudo"), (self.b_abrir, "dica_pastas"),
                             (self.b_painel, "dica_fila"), (self.b_tela, "dica_tela_cheia")):
                b.setToolTip(t(chave))
        self._fixo(dicas_barra)
        dl.addStretch(1)
        dl.addWidget(self.s_foto)
        dl.addSpacing(10)
        dl.addWidget(self.b_vol)
        dl.addWidget(self.volume)
        dl.addSpacing(10)
        dl.addWidget(sep)
        dl.addSpacing(6)
        for w in (self.b_abrir, self.b_painel, self.b_tela):
            dl.addWidget(w)

        # laterais com o mesmo peso: o centro fica sempre no meio
        self._lados = (esq, dir_)
        for w in self._lados:
            w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        cen.setMinimumWidth(300)
        cen.setMaximumWidth(720)
        grade.addWidget(esq, 2)
        grade.addWidget(cen, 3)
        grade.addWidget(dir_, 2)
        self._ajustar_barra()
        v.addWidget(self.barra)

    def _popup_acima(self, menu: QMenu, botao: QWidget, alinhar_direita=True):
        """Mostra o menu colado ao botão (acima dele se não couber embaixo)."""
        menu.adjustSize()
        tam = menu.sizeHint()
        tela = (botao.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        canto = botao.mapToGlobal(QPoint(botao.width() if alinhar_direita else 0, 0))
        x = canto.x() - tam.width() if alinhar_direita else canto.x()
        y = canto.y() - tam.height() - 6
        if y < tela.top():
            y = botao.mapToGlobal(QPoint(0, botao.height() + 6)).y()
        x = max(tela.left() + 4, min(x, tela.right() - tam.width() - 4))
        menu.popup(QPoint(x, y))
        QTimer.singleShot(400, lambda: self._log_menu(menu, x, y))

    def _log_menu(self, menu, x, y):
        try:
            self._log.write(f"{time.strftime('%H:%M:%S')} menu pedido em ({x},{y}): "
                            f"visível={menu.isVisible()} geom={menu.geometry().getRect()} "
                            f"itens={len(menu.actions())}\n")
            self._log.flush()
        except Exception:
            pass

    def _abrir_menu_pastas(self, botao):
        self._montar_menu_abrir()
        self._popup_acima(self.menu_abrir, botao, alinhar_direita=True)

    def _abrir_menu_limpar(self, botao):
        m = MenuRico(self)
        m.linha("limpar", t("limpar_fila"), t("limpar_fila_desc"), "",
                self.limpar, perigo=True, ativo=bool(self.fila.itens))
        m.linha("limpar", t("limpar_tudo"), t("limpar_tudo_desc"), "",
                self.limpar_tudo, perigo=True)
        self._menu_limpar = m  # segura a referência enquanto aberto
        self._popup_acima(m, botao, alinhar_direita=False)

    def _montar_menu_abrir(self):
        m = self.menu_abrir
        m.clear()
        m.titulo(t("m_abrir"))
        m.linha("pasta", t("abrir_pasta"), t("abrir_pasta_desc"), "Ctrl+O", self.abrir_pasta)
        m.linha("pastamais", t("juntar_outra"), t("juntar_desc"), "Ctrl+Shift+O", self.adicionar_pasta)
        m.linha("foto", t("abrir_arquivos"), t("abrir_arquivos_desc"), "", self.abrir_arquivos)
        ultimas = [p for p in self.cfg["ultimas_pastas"] if os.path.exists(p)]
        if ultimas:
            m.titulo(t("ultima_fila"))
            nomes = ", ".join(os.path.basename(p.rstrip("\\/")) or p for p in ultimas[:3])
            if len(ultimas) > 3:
                nomes += t("e_mais", n=len(ultimas) - 3)
            m.linha("repetir", t("continuar_1" if len(ultimas) == 1 else "continuar_n", n=len(ultimas)),
                    nomes, "", self.continuar_ultimas)
        m.titulo(t("arquivo_na_tela"))
        m.linha("explorer", t("mostrar_explorer"), t("mostrar_explorer_desc"), "E",
                self.mostrar_atual_no_explorer, ativo=self._item is not None)
        m.titulo(t("limpar"))
        m.linha("limpar", t("limpar_fila"), t("limpar_fila_desc"), "",
                self.limpar, perigo=True, ativo=bool(self.fila.itens))
        tem_historico = bool(self.cfg["ultimas_pastas"]) or bool(self.fila.itens)
        m.linha("limpar", t("limpar_tudo"), t("limpar_tudo_desc"), "",
                self.limpar_tudo, perigo=True, ativo=tem_historico)
        if WINDOWS and getattr(sys, "frozen", False):
            m.titulo("Windows")
            m.linha("foto", t("usar_padrao"), t("usar_padrao_desc"), "",
                    self.usar_como_padrao)
        m.titulo("Ciranda")
        m.linha("atualizar", t("procurar_atualizacao"), t("procurar_desc", versao=VERSAO), "",
                lambda: self.procurar_atualizacao(manual=True))
        m.linha("bug", t("relatar_bug") + "…", t("relatar_bug_desc"), "", self.relatar_bug)
        m.linha("buscar", t("como_usar"), t("como_usar_desc"), "", self.mostrar_tutorial)
        m.linha("repetir", t("restaurar"), t("restaurar_desc"),
                "", self.restaurar_fabrica, perigo=True)

    def _montar_painel(self) -> QFrame:
        painel = QFrame()
        painel.setObjectName("painel")
        painel.setFixedWidth(330)
        v = QVBoxLayout(painel)
        v.setContentsMargins(14, 14, 10, 12)
        v.setSpacing(10)
        topo = QHBoxLayout()
        tit = QLabel()
        tit.setObjectName("tituloPainel")
        self._fixo(lambda: tit.setText(t("fila")))
        self.l_contagem = QLabel("")
        self.l_contagem.setObjectName("apagado")
        topo.addWidget(tit)
        topo.addSpacing(6)
        topo.addWidget(self.l_contagem, 0, Qt.AlignBottom)
        topo.addStretch(1)
        v.addLayout(topo)

        acoes = QHBoxLayout()
        acoes.setSpacing(6)

        def pilula(nome_icone, chave_texto, chave_dica, slot):
            b = QToolButton()
            b.setObjectName("pilula")
            b.setIcon(icone(nome_icone, TEXTO, 16))
            b.setIconSize(QSize(16, 16))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

            def textos_pilula():
                b.setText(t(chave_texto))
                b.setToolTip(t(chave_dica))
                # o Qt não soma o padding do estilo: largura = texto + ícone + respiro
                b.setMinimumWidth(QFontMetrics(b.font()).horizontalAdvance(b.text()) + 16 + 34)
            self._fixo(textos_pilula)
            b.clicked.connect(slot)
            acoes.addWidget(b)
            return b
        self.b_p_abrir = pilula("pasta", "pil_abrir", "pil_abrir_dica", self.abrir_pasta)
        self.b_p_juntar = pilula("pastamais", "pil_juntar", "pil_juntar_dica", self.adicionar_pasta)
        self.b_p_limpar = pilula("limpar", "limpar", "pil_limpar_dica", lambda: None)
        self.b_p_limpar.clicked.disconnect()
        self.b_p_limpar.clicked.connect(lambda: self._abrir_menu_limpar(self.b_p_limpar))
        acoes.addStretch(1)
        v.addLayout(acoes)

        seg = QFrame()
        seg.setObjectName("segmentos")
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.setSpacing(2)
        self.g_filtro = QButtonGroup(self)
        for chave in ("tudo", "fotos", "videos"):
            pb = QPushButton()
            pb.setObjectName("segmento")
            pb.setCheckable(True)
            pb.setCursor(Qt.PointingHandCursor)
            pb.setFocusPolicy(Qt.NoFocus)
            self._fixo(lambda pb=pb, chave=chave: (pb.setText(t(f"filtro_{chave}")),
                                                   pb.setToolTip(t(f"filtro_{chave}_dica"))))
            pb.setProperty("filtro", chave)
            pb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.g_filtro.addButton(pb)
            sl.addWidget(pb)
        self.g_filtro.buttonClicked.connect(lambda pb: self.definir_filtro(pb.property("filtro")))
        v.addWidget(seg)

        self.filtro_txt = QLineEdit()
        self._fixo(lambda: self.filtro_txt.setPlaceholderText(t("buscar_fila")))
        self.filtro_txt.addAction(icone("buscar", APAGADO, 16), QLineEdit.LeadingPosition)
        self.filtro_txt.setClearButtonEnabled(True)
        v.addWidget(self.filtro_txt)

        self.modelo = ModeloFila(self.fila)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.modelo)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.filtro_txt.textChanged.connect(self.proxy.setFilterFixedString)
        self.lista = QListView()
        self.lista.setModel(self.proxy)
        self.lista.setItemDelegate(Delegado(self.lista))
        self.lista.setUniformItemSizes(True)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista.setMouseTracking(True)
        self.lista.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lista.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.lista.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_lista)
        self.lista.doubleClicked.connect(self._lista_duplo)
        self.lista.setFocusPolicy(Qt.ClickFocus)
        v.addWidget(self.lista, 1)

        self.l_resumo = QLabel("")
        self.l_resumo.setObjectName("apagado")
        self.l_resumo.setWordWrap(True)
        v.addWidget(self.l_resumo)
        # rodapé padrão (regra 9): Relatar bug · Procurar atualização, e a assinatura
        self.acoes_fila = acoes_rodape(self, painel)
        v.addWidget(self.acoes_fila)
        linha2 = QHBoxLayout()
        linha2.setSpacing(0)
        self.assinatura_fila = assinatura(painel)
        self.seletor_fila = seletor_idioma(self, painel)
        linha2.addWidget(self.assinatura_fila)
        linha2.addStretch(1)
        linha2.addWidget(self.seletor_fila)
        v.addLayout(linha2)
        self._fixo(lambda: (self.acoes_fila.retraduzir(), self.assinatura_fila.retraduzir(),
                            self.seletor_fila.retraduzir()))
        return painel

    def _atalhos(self):
        def a(teclas, fn):
            for t in teclas if isinstance(teclas, (list, tuple)) else [teclas]:
                QShortcut(QKeySequence(t), self, activated=fn)
        a(["Space", "K"], self.alternar_pausa)
        a(["N", "PgDown", "Media Next"], lambda: self.proximo(False))
        a(["P", "PgUp", "Media Previous"], self.anterior)
        a("Right", lambda: self.pular(5))
        a("Left", lambda: self.pular(-5))
        a("Shift+Right", lambda: self.pular(30))
        a("Shift+Left", lambda: self.pular(-30))
        a("Up", lambda: self.mudar_volume(5))
        a("Down", lambda: self.mudar_volume(-5))
        a("M", self.alternar_mudo)
        a(["F", "F11", "Return"], self.alternar_tela_cheia)
        a("Escape", lambda: self.quadro.fechar("x") if self.quadro.isVisible() else self.sair_tela_cheia())
        a("S", self.alternar_aleatorio)
        a("R", self.ciclar_repetir)
        a("L", self.alternar_painel)
        a("E", self.mostrar_atual_no_explorer)
        a(["+", "="], lambda: self.s_foto.setValue(self.s_foto.value() + 1))
        a("-", lambda: self.s_foto.setValue(self.s_foto.value() - 1))
        a("Ctrl+O", self.abrir_pasta)
        a("Ctrl+Shift+O", self.adicionar_pasta)
        a("1", lambda: self.definir_filtro("tudo"))
        a("2", lambda: self.definir_filtro("fotos"))
        a("3", lambda: self.definir_filtro("videos"))
        a("Ctrl+F", lambda: (self._mostrar_painel(True), self.filtro_txt.setFocus()))

    # ----- motor -----
    def _criar_mpv(self):
        import locale
        locale.setlocale(locale.LC_NUMERIC, "C")
        if WINDOWS:
            os.environ["PATH"] = PASTA_APP + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(PASTA_APP)
            except (AttributeError, OSError):
                pass
        import mpv  # depois do PATH, para achar o libmpv-2.dll da pasta
        self._log = open(os.path.join(config.pasta_dados(), "ciranda.log"), "w", encoding="utf-8")

        def log(nivel, prefixo, texto):
            try:
                self._log.write(f"{time.strftime('%H:%M:%S')} [{nivel}] {prefixo}: {texto.rstrip()}\n")
                self._log.flush()
            except Exception:
                pass

        opcoes = dict(
            wid=str(int(self.tela.winId())),
            hwdec="auto-safe",
            keep_open="yes",
            idle="yes",
            osc="no",
            osd_level="1",
            input_default_bindings="no",
            input_vo_keyboard="no",
            image_display_duration="inf",
            osd_on_seek="no",
            volume=str(int(self.cfg["volume"])),
            mute="yes" if self.cfg["mudo"] else "no",
            cursor_autohide="1500",
            cursor_autohide_fs_only="yes",
            log_handler=log,
            loglevel="warn",
        )
        vo = os.environ.get("CIRANDA_VO")
        if vo:
            opcoes["vo"] = vo
        self.mpv = mpv.MPV(**opcoes)
        estilo_osd = [("input-cursor-passthrough", "yes"),
                      ("osd-font", "Segoe UI Semibold" if WINDOWS else "DejaVu Sans"),
                      ("osd-font-size", "30"), ("osd-bold", "no"), ("osd-color", "#FFFFFFFF"),
                      ("osd-border-style", "background-box"),  # mpv 0.38+
                      ("osd-back-color", "#C0141519"), ("osd-border-size", "0"),
                      ("osd-shadow-offset", "0"), ("osd-margin-y", "48"),
                      ("osd-align-x", "center"), ("osd-align-y", "bottom"),
                      ("osd-playing-msg", ""), ("osd-bar", "no")]
        for chave, valor in estilo_osd:
            try:
                self.mpv[chave] = valor
            except Exception:
                pass
        log("info", "ciranda", f"{NOME} {VERSAO}, mpv {self.mpv.mpv_version}")

        ponte = self.ponte

        @self.mpv.property_observer("time-pos")
        def _t(_n, v):
            if v is not None:
                ponte.tempo.emit(float(v))

        @self.mpv.property_observer("duration")
        def _d(_n, v):
            ponte.duracao.emit(float(v or 0))

        @self.mpv.property_observer("eof-reached")
        def _e(_n, v):
            if v:
                ponte.fim_video.emit()

        @self.mpv.property_observer("pause")
        def _p(_n, v):
            ponte.pausa.emit(bool(v))

        @self.mpv.event_callback("end-file")
        def _fim(ev):
            try:
                if ev.data.reason == ev.data.ERROR:
                    ponte.erro_arquivo.emit()
            except Exception:
                pass

        ponte.tempo.connect(self._recebeu_tempo)
        ponte.duracao.connect(self._recebeu_duracao)
        ponte.fim_video.connect(self._video_acabou)
        ponte.erro_arquivo.connect(self._arquivo_falhou)
        ponte.pausa.connect(self._recebeu_pausa)
        ponte.heic_pronto.connect(self._heic_pronto)
        QTimer.singleShot(400, lambda: desarmar_janelas_filhas(int(self.tela.winId())))

    # ----- abrir pastas -----
    def abrir_pasta(self):
        self._escolher_pasta(adicionar=False)

    def adicionar_pasta(self):
        self._escolher_pasta(adicionar=True)

    def _escolher_pasta(self, adicionar: bool):
        inicio = self.pastas_abertas[-1] if self.pastas_abertas else os.path.expanduser("~")
        p = QFileDialog.getExistingDirectory(self, t("dlg_adicionar_pasta") if adicionar else t("abrir_pasta"), inicio)
        if p:
            self.carregar([p], adicionar=adicionar)

    def abrir_arquivos(self):
        arqs, _ = QFileDialog.getOpenFileNames(self, t("dlg_abrir_arquivos"), os.path.expanduser("~"))
        if arqs:
            self.carregar(arqs, adicionar=False)

    def continuar_ultimas(self):
        pastas = [p for p in self.cfg["ultimas_pastas"] if os.path.exists(p)]
        if pastas:
            self.carregar(pastas, adicionar=False)

    def carregar(self, caminhos, adicionar: bool):
        caminhos = [os.path.abspath(c) for c in caminhos if c and os.path.exists(c)]
        if not caminhos:
            return
        if self.varredor and self.varredor.isRunning():
            self.varredor.parar()
            self.varredor.wait(2000)
        if not adicionar or not self.fila.itens:
            self.pastas_abertas = list(caminhos)
        else:
            self.pastas_abertas += [c for c in caminhos if c not in self.pastas_abertas]
        self._status(t("lendo", nome=self._nome_curto(caminhos)))
        self.varredor = Varredor(caminhos, adicionar and bool(self.fila.itens))
        self.varredor.progresso.connect(
            lambda n, p: self._status(t("lendo_n", n=f"{n:,}".replace(",", ".")) + (f"  ·  {p}" if p else "")))
        self.varredor.pronto.connect(self._varredura_pronta)
        self.varredor.start()

    def _nome_curto(self, caminhos):
        n = os.path.basename(caminhos[0].rstrip("\\/")) or caminhos[0]
        return n + (f" +{len(caminhos) - 1}" if len(caminhos) > 1 else "")

    def _status(self, texto):
        if self.palco.currentWidget() is self.vazio:
            self.vazio.status.setText(texto)
        else:
            self.l_info.setText(f'<span style="color:{APAGADO}">{texto}</span>')

    def _registrar_varredura(self, itens, stats):
        ign = stats.get("ignorados", {})
        sem = stats.get("sem_acesso", [])
        pul = stats.get("puladas", [])
        self._ignorados = sum(ign.values())
        self._pastas_lidas = stats.get("pastas_lidas", 0)
        w = self._log.write
        w(f"varredura: {len(self.pastas_abertas)} pastas abertas, {self._pastas_lidas} pastas lidas, "
          f"{len(itens)} fotos/vídeos, {self._ignorados} arquivos de outros tipos\n")
        if ign:
            w("  outros tipos (não são foto/vídeo): " + ", ".join(f"{e} {n}" for e, n in ign.most_common(25)) + "\n")
        for p in sem[:200]:
            w(f"  sem acesso: {p}\n")
        for p in pul[:200]:
            w(f"  pulada: {p}\n")
        self._log.flush()

    def _varredura_pronta(self, itens, adicionar, stats=None):
        stats = stats or {}
        self._registrar_varredura(itens, stats)
        if not itens and not adicionar:
            self._status(t("nenhuma_midia"))
            return
        pastas = [p for p in self.pastas_abertas if os.path.isdir(p)]
        if pastas:  # abrir só arquivos (dois cliques numa foto) não mexe no Continuar
            self.cfg["ultimas_pastas"] = pastas[:5000]  # a fila inteira, sem corte
            config.salvar(self.cfg)
        if adicionar:
            self.fila.adicionar(itens)
            self._atualizar_lista()
            self._atualizar_info()
            return
        self._parar_motor()
        self.fila.definir_itens(itens)
        self._atualizar_lista()
        self._fim_da_fila = False
        self._erros_seguidos = 0
        item = self.fila.proximo()
        if item is None and self.fila.filtro != "tudo" and self.fila.itens:
            # filtro escondeu tudo (ex.: "Vídeos" numa pasta só de fotos)
            self.definir_filtro("tudo")
            return
        self.palco.setCurrentWidget(self.tela)
        self.vazio.status.setText("")
        self.tocar(item)

    def limpar(self):
        if self.varredor and self.varredor.isRunning():
            self.varredor.parar()
        self._parar_motor()
        self.fila.limpar()
        self._item = None
        self.b_play.setIcon(icone("play", "#1a0f07", 22))
        self.pastas_abertas = []
        self._atualizar_lista()
        self.palco.setCurrentWidget(self.vazio)
        self.vazio.atualizar_continuar([p for p in self.cfg["ultimas_pastas"] if os.path.exists(p)])
        self.l_nome.setText(t("nada_tocando"))
        self.l_info.setText(t("arraste_para_janela"))
        self.l_tipo.setPixmap(icone("pasta", APAGADO, 20).pixmap(20, 20))
        self.l_tempo.setText("0:00")
        self.l_total.setText("0:00")
        self.busca.setValue(0)
        self.setWindowTitle(NOME)

    def limpar_tudo(self, confirmar=True):
        """Limpa a fila e a "Última fila" (a lista do Continuar). Só isso:
        cache, log e ajustes ficam; nunca mexe nas fotos e vídeos do PC."""
        if confirmar and self.cfg["ultimas_pastas"]:
            r = QMessageBox.question(
                self, t("limpar_tudo"), t("limpar_tudo_confirma"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        self.cfg["ultimas_pastas"] = []
        config.salvar(self.cfg)
        self.limpar()
        self.vazio.atualizar_continuar([])
        self.vazio.status.setText(t("limpos"))

    def restaurar_fabrica(self, confirmar=True):
        """Como recém-instalado: ajustes no padrão, fila e Continuar vazios, cache apagado.
        Mantém o erro.txt (diagnóstico). Nunca mexe nas fotos e vídeos do PC."""
        if confirmar:
            r = QMessageBox.question(
                self, t("restaurar_titulo"), t("restaurar_confirma"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        if self.isFullScreen():
            self.sair_tela_cheia()
        self.limpar()
        fotos.apagar_cache()
        self.cfg = dict(config.PADRAO)
        self.cfg["ultimas_pastas"] = []
        self.cfg["versao_vista"] = VERSAO
        self.cfg["novidades_vista"] = VERSAO
        self.cfg["tutorial_visto"] = True
        textos.definir(textos.idioma_do_sistema())  # idioma volta ao do sistema
        config.salvar(self.cfg)
        # aplica o padrão na tela e no motor
        self.fila.aleatorio = bool(self.cfg["aleatorio"])
        self.fila.repetir = self.cfg["repetir"]
        self.fila.filtro = self.cfg["filtro"]
        self.volume.blockSignals(True)
        self.volume.setValue(int(self.cfg["volume"]))
        self.volume.blockSignals(False)
        self.s_foto.blockSignals(True)
        self.s_foto._v = int(self.cfg["segundos_foto"])
        self.s_foto._atualizar_texto()
        self.s_foto.blockSignals(False)
        try:
            self.mpv.volume = int(self.cfg["volume"])
            self.mpv.mute = bool(self.cfg["mudo"])
            self.mpv["loop-file"] = "no"
        except Exception:
            pass
        self._mostrar_painel(bool(self.cfg["painel"]))
        self.showNormal()
        self.resize(1180, 720)
        self._aplicar_modos_na_tela()
        self._atualizar_lista()
        self.vazio.atualizar_continuar([])
        self.retraduzir()
        self.vazio.status.setText(t("restaurado"))
        try:
            self._log.write(f"{time.strftime('%H:%M:%S')} restaurado de fábrica\n")
            self._log.flush()
        except Exception:
            pass

    # ----- tocar -----
    def _parar_motor(self):
        self._t_foto.stop()
        try:
            self.mpv.command("stop")
        except Exception:
            pass

    def tocar(self, item: Item | None):
        self._t_foto.stop()
        if item is None:
            self._fim()
            return
        self._fim_da_fila = False
        self._token += 1
        self._item = item
        self._duracao = 0.0
        self.b_play.setIcon(icone("pause", "#1a0f07", 22))
        self.palco.setCurrentWidget(self.tela)
        if item.heic:
            token = self._token
            threading.Thread(target=lambda: self.ponte.heic_pronto.emit(
                token, fotos.heic_para_jpeg(item.caminho) or ""), daemon=True).start()
        else:
            self._carregar_no_motor(item.caminho)
        self._preparar_proximo_heic()
        self._atualizar_info(carregando=item.heic)
        self.modelo.dataChanged.emit(self.modelo.index(0), self.modelo.index(self.modelo.rowCount() - 1))
        self._rolar_para_atual()

    def _heic_pronto(self, token, caminho):
        if token != self._token or self._item is None:
            return
        if not caminho:
            self._arquivo_falhou()
            return
        self._carregar_no_motor(caminho)
        self._atualizar_info()

    def _preparar_proximo_heic(self):
        prox = self.fila.espiar_proximo()
        if prox is not None and prox.heic:
            threading.Thread(target=fotos.heic_para_jpeg, args=(prox.caminho,), daemon=True).start()

    def _carregar_no_motor(self, caminho):
        item = self._item
        rep_um = self.fila.repetir == "um"
        try:
            self.mpv["loop-file"] = "inf" if (item.animada or (item.tipo == "video" and rep_um)) else "no"
            self.mpv.command("loadfile", caminho, "replace")
            self.mpv.pause = False
        except Exception as e:
            self._log.write(f"loadfile falhou: {e}\n")
            self._arquivo_falhou()
            return
        self._carregou_em = time.monotonic()
        if item.tipo == "foto":
            self._iniciar_relogio_foto()
        QTimer.singleShot(500, lambda: desarmar_janelas_filhas(int(self.tela.winId())))

    def _iniciar_relogio_foto(self, restante_ms=None):
        self._foto_total_ms = self.s_foto.value() * 1000
        self._foto_restante_ms = self._foto_total_ms if restante_ms is None else restante_ms
        self._foto_relogio.restart()
        if self.fila.repetir != "um":
            self._t_foto.start(max(1, self._foto_restante_ms))

    def _foto_acabou(self):
        if self._item and self._item.tipo == "foto" and len(self.fila) <= 1:
            # uma foto só (aberta com dois cliques): fica na tela, sem piscar
            if self.fila.repetir == "nao":
                self._fim()
            return
        if self._item and self._item.tipo == "foto":
            self._erros_seguidos = 0
            self.tocar(self.fila.proximo(automatico=True))

    def _video_acabou(self):
        if not self._item or self._item.tipo != "video":
            return
        if time.monotonic() - self._carregou_em < 0.3:
            return  # aviso atrasado do arquivo anterior
        try:
            if not self.mpv.eof_reached:
                return
        except Exception:
            pass
        self._erros_seguidos = 0
        self.tocar(self.fila.proximo(automatico=True))

    def _arquivo_falhou(self):
        if self._item is None:
            return
        self._item.falhou = True
        self._log.write(f"não abriu: {self._item.caminho}\n")
        self._erros_seguidos += 1
        if self._erros_seguidos >= max(1, len(self.fila)):
            self._fim(t("nenhum_abriu"))
            return
        QTimer.singleShot(50, lambda: self.tocar(self.fila.proximo(automatico=False)))

    def _fim(self, msg=None):
        msg = msg or t("fim_fila")
        self._t_foto.stop()
        self._fim_da_fila = True
        try:
            self.mpv.pause = True
        except Exception:
            pass
        self.l_info.setText(f'<span style="color:{APAGADO}">{msg}</span>')
        self.b_play.setIcon(icone("play", "#1a0f07", 22))

    def _aviso(self, texto):
        """Aviso rápido desenhado pelo mpv por cima do vídeo/foto."""
        if self._item is not None and self.palco.currentWidget() is self.tela:
            try:
                self.mpv.command("show-text", texto, "1300", "1")
                return
            except Exception:
                pass
        self._status(texto)

    def _menu_video(self, pos):
        m = MenuRico(self)
        pausado = bool(self.mpv.pause) if self._item else True
        m.linha("play" if pausado else "pause", t("tocar") if pausado else t("pausar"), "", t("tecla_espaco"),
                self.alternar_pausa)
        m.linha("proximo", t("proximo"), "", "N", lambda: self.proximo(False))
        m.linha("aleatorio", t("aleatorio_ligado") if self.fila.aleatorio else t("aleatorio_desligado"), "", "S",
                self.alternar_aleatorio)
        m.linha("repetir", t(f"repetir_{self.fila.repetir}"), "", "R", self.ciclar_repetir)
        m.titulo(t("m_pastas"))
        m.linha("pastamais", t("juntar_outra"), t("juntar_desc_curta"), "Ctrl+Shift+O", self.adicionar_pasta)
        m.linha("pasta", t("abrir_pasta"), t("abrir_desc_curta"), "Ctrl+O", self.abrir_pasta)
        m.titulo(t("arquivo_na_tela"))
        m.linha("explorer", t("mostrar_explorer"), t("mostrar_explorer_desc"), "E",
                self.mostrar_atual_no_explorer, ativo=self._item is not None)
        m.linha("telacheia", t("sair_tela_cheia") if self.isFullScreen() else t("tela_cheia"), "", "F",
                self.alternar_tela_cheia)
        m.exec(pos)

    # ----- controles -----
    def alternar_pausa(self):
        if not self.fila.itens:
            self.abrir_pasta()
            return
        if self._fim_da_fila:
            self.tocar(self.fila.reiniciar())
            return
        if self._item is None:
            self.tocar(self.fila.proximo())
            return
        pausar = not self.mpv.pause
        self.mpv.pause = pausar
        if self._item.tipo == "foto":
            if pausar:
                self._foto_restante_ms = max(0, self._foto_restante_ms - self._foto_relogio.elapsed())
                self._t_foto.stop()
            else:
                self._foto_relogio.restart()
                if self.fila.repetir != "um":
                    self._t_foto.start(max(1, self._foto_restante_ms))

    def proximo(self, automatico=False):
        if not self.fila.itens:
            return
        self._erros_seguidos = 0
        item = self.fila.proximo(automatico)
        if item is None:
            self._fim()
        else:
            self.tocar(item)

    def anterior(self):
        if not self.fila.itens:
            return
        # como no VLC/Spotify: vídeo com mais de 3 s volta pro começo dele
        if self._item and self._item.tipo == "video" and not self._fim_da_fila:
            try:
                if (self.mpv.time_pos or 0) > 3:
                    self.mpv.seek(0, "absolute")
                    return
            except Exception:
                pass
        self._erros_seguidos = 0
        self.tocar(self.fila.anterior())

    def pular(self, seg):
        if self._item is None:
            return
        if self._item.tipo == "foto":
            self.proximo() if seg > 0 else self.anterior()
            return
        try:
            self.mpv.seek(seg, "relative")
        except Exception:
            pass

    def _soltou_busca(self):
        self._arrastando = False
        if self._item and self._item.tipo == "video" and self._duracao > 0:
            try:
                self.mpv.seek(self.busca.value() / 10.0, "absolute-percent")
            except Exception:
                pass

    def mudar_volume(self, delta):
        self.volume.setValue(max(0, min(100, self.volume.value() + delta)))
        self._aviso(t("osd_volume", v=self.volume.value()))

    def _mudou_volume(self, v):
        try:
            self.mpv.volume = v
            if v > 0 and self.mpv.mute:
                self.alternar_mudo()
        except Exception:
            pass
        self.cfg["volume"] = v

    def alternar_mudo(self):
        try:
            self.mpv.mute = not self.mpv.mute
            self.cfg["mudo"] = bool(self.mpv.mute)
        except Exception:
            pass
        self.b_vol.setIcon(icone("mudo" if self.cfg["mudo"] else "volume", TEXTO, 18))
        self._aviso(t("osd_sem_som") if self.cfg["mudo"] else t("osd_som"))

    def alternar_aleatorio(self):
        self.fila.definir_aleatorio(not self.fila.aleatorio)
        self.cfg["aleatorio"] = self.fila.aleatorio
        self._aplicar_modos_na_tela()
        self._aviso(t("osd_aleatorio") if self.fila.aleatorio else t("osd_em_ordem"))
        self._atualizar_lista()
        self._atualizar_info()

    def ciclar_repetir(self):
        self.fila.proximo_modo_repetir()
        self.cfg["repetir"] = self.fila.repetir
        self._aplicar_modos_na_tela()
        self._aviso(t(f"osd_repetir_{self.fila.repetir}"))
        item = self._item
        if item is None:
            return
        # aplica na hora no item que está na tela
        try:
            if item.tipo == "video":
                self.mpv["loop-file"] = "inf" if self.fila.repetir == "um" else "no"
        except Exception:
            pass
        if item.tipo == "foto" and not self.mpv.pause:
            if self.fila.repetir == "um":
                self._foto_restante_ms = max(0, self._foto_restante_ms - self._foto_relogio.elapsed())
                self._foto_relogio.restart()
                self._t_foto.stop()
            elif not self._t_foto.isActive():
                self._foto_relogio.restart()
                self._t_foto.start(max(1, self._foto_restante_ms))

    def definir_filtro(self, filtro):
        if filtro == self.fila.filtro:
            self._aplicar_modos_na_tela()
            return
        continua = self.fila.definir_filtro(filtro)
        self.cfg["filtro"] = filtro
        self._aviso(t(f"osd_filtro_{filtro}"))
        self._aplicar_modos_na_tela()
        self._atualizar_lista()
        if self.fila.itens and not continua:
            item = self.fila.proximo()
            if item is None:
                self._parar_motor()
                self._item = None
                self.l_info.setText(f'<span style="color:{APAGADO}">{t("nada_com_filtro")}</span>')
            else:
                self.tocar(item)
        self._atualizar_info()

    def _aplicar_modos_na_tela(self):
        self.b_alea.setChecked(self.fila.aleatorio)
        self.b_alea.setIcon(icone("aleatorio", DESTAQUE if self.fila.aleatorio else TEXTO, 18))
        rep = self.fila.repetir
        self.b_rep.setChecked(rep != "nao")
        self.b_rep.setIcon(icone("repetir1" if rep == "um" else "repetir", DESTAQUE if rep != "nao" else TEXTO, 18))
        self.b_rep.setToolTip(t(f"dica_repetir_{rep}"))
        for pb in self.g_filtro.buttons():
            pb.setChecked(pb.property("filtro") == self.fila.filtro)
        self.b_vol.setIcon(icone("mudo" if self.cfg["mudo"] else "volume", TEXTO, 18))

    def _mudou_tempo_foto(self, v):
        self.cfg["segundos_foto"] = v
        self._aviso(t("osd_cada_foto", v=v))
        if self._item and self._item.tipo == "foto" and self._t_foto.isActive():
            passado = (self._foto_total_ms - self._foto_restante_ms) + self._foto_relogio.elapsed()
            self._iniciar_relogio_foto(max(300, v * 1000 - passado))
            self._foto_total_ms = v * 1000

    # ----- recebe do motor -----
    def _recebeu_tempo(self, t):
        if self._item and self._item.tipo == "video":
            self._t_atual = t
            self.l_tempo.setText(fmt_tempo(t))
            if self._mostrar_restante and self._duracao > 0:
                self.l_total.setText("-" + fmt_tempo(self._duracao - t))
            if self._duracao > 0 and not self._arrastando:
                self.busca.setValue(int(1000 * t / self._duracao))

    def _recebeu_duracao(self, d):
        if self._item and self._item.tipo == "video":
            self._duracao = d
            if not self._mostrar_restante:
                self.l_total.setText(fmt_tempo(d))

    def _alternar_restante(self):
        self._mostrar_restante = not self._mostrar_restante
        if self._item and self._item.tipo == "video" and self._duracao > 0:
            t = getattr(self, "_t_atual", 0.0)
            self.l_total.setText("-" + fmt_tempo(self._duracao - t) if self._mostrar_restante
                                 else fmt_tempo(self._duracao))

    def _recebeu_pausa(self, pausado):
        # sem nada tocando o mpv fica ocioso com pause=no: o botão tem que mostrar "tocar"
        tocando = not pausado and self._item is not None and not self._fim_da_fila
        self.b_play.setIcon(icone("pause" if tocando else "play", "#1a0f07", 22))

    def _tique(self):
        """Barra de progresso da foto (contagem até a próxima)."""
        item = self._item
        if not item or item.tipo != "foto":
            self.busca.setEnabled(bool(item))
            return
        self.busca.setEnabled(False)
        total = max(1, self._foto_total_ms)
        if self._t_foto.isActive():
            feito = (total - self._foto_restante_ms) + self._foto_relogio.elapsed()
        else:
            feito = total - self._foto_restante_ms
        feito = max(0, min(total, feito))
        self.busca.setValue(int(1000 * feito / total))
        self.l_tempo.setText(fmt_tempo(feito / 1000))
        if self.fila.repetir == "um":
            self.l_total.setText("∞")
        elif self._mostrar_restante:
            self.l_total.setText("-" + fmt_tempo((total - feito) / 1000))
        else:
            self.l_total.setText(fmt_tempo(total / 1000))

    # ----- lista -----
    def _atualizar_lista(self):
        self.modelo.recarregar()
        itens = self.fila.itens
        nf = sum(1 for i in itens if i.tipo == "foto")
        nv = len(itens) - nf
        n_pastas = len({os.path.dirname(i.caminho) for i in itens})
        def n(x):
            return f"{x:,}".replace(",", ".")
        txt = t("resumo", fila=n(len(self.fila)), fotos=n(nf), videos=n(nv))
        txt += "\n" + t("resumo_pastas_1" if len(self.pastas_abertas) == 1 else "resumo_pastas_n",
                        pastas=n(n_pastas), abertas=n(len(self.pastas_abertas)), lidas=n(self._pastas_lidas))
        if self._ignorados:
            txt += t("outros_tipos", n=n(self._ignorados))
        falhas = sum(1 for i in itens if i.falhou)
        if falhas:
            txt += t("um_nao_abriu") if falhas == 1 else t("n_nao_abriram", n=n(falhas))
        self.l_resumo.setText(txt if itens else t("fila_vazia"))
        self.l_contagem.setText(n(len(self.fila)) if itens else "")
        self._rolar_para_atual()

    def _rolar_para_atual(self):
        linha = self.modelo.linha_do_atual()
        if linha >= 0 and self.painel.isVisible():
            idx = self.proxy.mapFromSource(self.modelo.index(linha))
            if idx.isValid():
                self.lista.scrollTo(idx, QAbstractItemView.EnsureVisible)

    def _lista_duplo(self, idx):
        i = self.proxy.mapToSource(idx).data(ModeloFila.INDICE)
        if i is not None:
            self._erros_seguidos = 0
            self.tocar(self.fila.ir_para(i))

    def _menu_lista(self, pos):
        idx = self.lista.indexAt(pos)
        if not idx.isValid():
            return
        sel = [self.proxy.mapToSource(s).data(ModeloFila.INDICE) for s in self.lista.selectionModel().selectedIndexes()]
        alvo = self.proxy.mapToSource(idx).data(ModeloFila.INDICE)
        if alvo not in sel:
            sel = [alvo]
        item = self.fila.itens[alvo]
        m = QMenu(self)
        m.addAction(icone("play", TEXTO, 16), t("tocar_agora"), lambda: self._lista_duplo(idx))
        m.addAction(icone("explorer", TEXTO, 16), t("mostrar_explorer"), lambda: mostrar_no_explorer(item.caminho))
        m.addAction(t("copiar_caminho"), lambda: QGuiApplication.clipboard().setText(item.caminho))
        m.addSeparator()
        m.addAction(icone("limpar", TEXTO, 16),
                    t("tirar_da_fila") if len(sel) == 1 else t("tirar_n_da_fila", n=len(sel)),
                    lambda: self._tirar_da_fila(sel))
        m.exec(self.lista.viewport().mapToGlobal(pos))

    def _tirar_da_fila(self, indices):
        tocando = self.fila.indice_atual in set(indices)
        self.fila.remover(indices)
        self._atualizar_lista()
        if tocando:
            self.proximo(False) if len(self.fila) else self.limpar()
        self._atualizar_info()

    def alternar_painel(self):
        self._mostrar_painel(not self.painel.isVisible())

    def _mostrar_painel(self, ver):
        self.painel.setVisible(ver)
        self.b_painel.setChecked(ver)
        if not self.isFullScreen():
            self.cfg["painel"] = ver
        if ver:
            self._rolar_para_atual()

    def mostrar_atual_no_explorer(self):
        if not self._item:
            return
        if self.isFullScreen():
            self.sair_tela_cheia()  # senão o Explorer abre atrás da tela cheia
        mostrar_no_explorer(self._item.caminho)

    def _atualizar_info(self, carregando=False):
        item = self._item
        if not item:
            return
        n, total = self.fila.posicao()
        pasta = item.pasta_rel or (os.path.basename(item.raiz.rstrip("\\/")) or item.raiz)
        pasta = pasta.replace("&", "&amp;").replace("<", "&lt;")
        extra = t("convertendo_heic") if carregando else ""
        fm = QFontMetrics(self.l_nome.font())
        self.l_nome.setText(fm.elidedText(item.nome, Qt.ElideMiddle, max(60, self.l_nome.width())))
        self.l_nome.setToolTip(item.caminho)
        self.l_info.setText(f'{pasta} · {t("n_de_total", n=n, total=total)}{extra}')
        self.l_info.setToolTip(item.caminho)
        cor = "#c35b5b" if item.falhou else DESTAQUE
        self.l_tipo.setPixmap(icone("foto" if item.tipo == "foto" else "video", cor, 20).pixmap(20, 20))
        self.setWindowTitle(f"{item.nome} — {NOME}")

    # ----- tela cheia -----
    def alternar_tela_cheia(self):
        if self.isFullScreen():
            self.sair_tela_cheia()
        elif self.fila.itens:
            self._painel_antes_tela_cheia = self.painel.isVisible()
            self.painel.hide()
            self.faixa.hide()
            self.showFullScreen()
            self.b_tela.setIcon(icone("sairtela", TEXTO, 19))
            self._cursor_antes = QCursor.pos()
            self._t_cursor.start()
            self._t_esconder.start()

    def sair_tela_cheia(self):
        if not self.isFullScreen():
            return
        self._t_cursor.stop()
        self._t_esconder.stop()
        self.showNormal()
        self.barra.show()
        self.tela.unsetCursor()
        self.painel.setVisible(self._painel_antes_tela_cheia)
        self.b_tela.setIcon(icone("telacheia", TEXTO, 19))
        if self._faixa_pendente:
            self.faixa.show()

    def _vigiar_cursor(self):
        pos = QCursor.pos()
        if pos != self._cursor_antes:
            self._cursor_antes = pos
            self.barra.show()
            self.tela.unsetCursor()
            self._t_esconder.start()

    def _esconder_controles(self):
        if not self.isFullScreen():
            return
        if self.barra.isVisible() and self.barra.geometry().contains(self.mapFromGlobal(QCursor.pos())):
            self._t_esconder.start()
            return
        self.barra.hide()
        self.tela.setCursor(Qt.BlankCursor)

    # ----- arrastar e soltar -----
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.vazio.destacar(True)

    def dragLeaveEvent(self, e):
        self.vazio.destacar(False)

    def dropEvent(self, e):
        self.vazio.destacar(False)
        caminhos = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        juntar = bool(e.modifiers() & Qt.ControlModifier) and bool(self.fila.itens)
        if caminhos:
            self.carregar(caminhos, adicionar=juntar)
            e.acceptProposedAction()

    # ----- fechar -----
    def closeEvent(self, e):
        self.quadro.hide()
        if self.isFullScreen():
            self.showNormal()
        self.cfg["geometria"] = bytes(self.saveGeometry().toBase64()).decode()
        config.salvar(self.cfg)
        if self.varredor and self.varredor.isRunning():
            self.varredor.parar()
            self.varredor.wait(1500)
        try:
            self.mpv.terminate()
        except Exception:
            pass
        threading.Thread(target=fotos.limpar_cache, daemon=True).start()
        super().closeEvent(e)
