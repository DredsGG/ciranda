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
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QFileDialog, QMessageBox,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QListView,
                               QMainWindow, QMenu, QPushButton, QSizePolicy, QSlider,
                               QInputDialog, QStackedWidget, QStyle, QStyledItemDelegate,
                               QToolButton, QVBoxLayout, QWidget)

from . import NOME, VERSAO, config, fotos
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
QLabel#assinatura {{ color: #6f717c; font-size: 11.5px; }}
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
            pasta = "não abriu · " + pasta
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
        self.titulo = QLabel("Arraste pastas aqui")
        self.titulo.setObjectName("grande")
        self.titulo.setAlignment(Qt.AlignCenter)
        self.sub = QLabel("Fotos e vídeos da pasta e de todas as subpastas entram numa fila só.\n"
                          "Segure Ctrl ao soltar para juntar à fila atual.")
        self.sub.setObjectName("apagado")
        self.sub.setAlignment(Qt.AlignCenter)
        botoes = QHBoxLayout()
        botoes.setAlignment(Qt.AlignCenter)
        self.b_abrir = QPushButton(icone("pasta", "#1a0f07", 18), "  Abrir pasta")
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
        self.assinatura.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.logo)
        lay.addSpacing(6)
        lay.addWidget(self.titulo)
        lay.addWidget(self.sub)
        lay.addSpacing(10)
        lay.addLayout(botoes)
        lay.addSpacing(8)
        lay.addWidget(self.status)
        lay.addSpacing(30)
        lay.addWidget(self.assinatura)

    def destacar(self, ligado):
        self.setProperty("arrastando", bool(ligado))
        self.titulo.setText("Solte para tocar" if ligado else "Arraste pastas aqui")
        self.style().unpolish(self)
        self.style().polish(self)

    def atualizar_continuar(self, pastas):
        if pastas:
            if len(pastas) == 1:
                nomes = os.path.basename(pastas[0].rstrip("\\/")) or pastas[0]
            else:
                nomes = f"{len(pastas)} pastas"
            self.b_continuar.setText(f"Continuar a última fila ({nomes})")
            self.b_continuar.show()
        else:
            self.b_continuar.hide()


GITHUB = "https://github.com/DredsGG"


def assinatura(pai=None) -> QLabel:
    """Rodapé padrão de todo projeto do André (regra 9): "feito por Dreds · vX.Y.Z",
    com "Dreds" abrindo o GitHub no navegador padrão. Versão sempre da constante VERSAO."""
    lab = QLabel(pai)
    lab.setObjectName("assinatura")
    lab.setTextFormat(Qt.RichText)
    lab.setText(f'feito por <a href="{GITHUB}" style="color:{DESTAQUE}; text-decoration:none;">'
                f'<b>Dreds</b></a> · v{VERSAO}')
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
        self.setToolTip("Tempo de cada foto na tela antes de passar para a próxima.\n"
                        "Vídeo sempre toca até o fim. Atalho: + e −")
        self.menu_ = MenuRico(self)
        self.menu_.aboutToShow.connect(self._montar)
        self.setMenu(self.menu_)
        self._atualizar_texto()

    def _fmt(self, v):
        return f"{v // 60} min" if v >= 60 and v % 60 == 0 else f"{v} s"

    def compacto(self, sim: bool):
        self._compacto = sim
        self._atualizar_texto()

    def _atualizar_texto(self):
        if getattr(self, "_compacto", False):
            self.setText(f"{self._fmt(self._v)} ▾")
        else:
            self.setText(f"Foto: {self._fmt(self._v)}  ▾")
        # o Qt não soma o padding do estilo: largura = texto + ícone + respiro
        self.setMinimumWidth(QFontMetrics(self.font()).horizontalAdvance(self.text()) + 17 + 38)

    def _montar(self):
        m = self.menu_
        m.clear()
        m.titulo("Tempo de cada foto")
        m.explica("Vídeo não usa: sempre toca até o fim")
        grupo = QActionGroup(m)
        for v in self.OPCOES:
            a = m.addAction(self._fmt(v))
            a.setCheckable(True)
            a.setChecked(v == self._v)
            grupo.addAction(a)
            a.triggered.connect(lambda _=False, v=v: self.setValue(v))
        m.addSeparator()
        outro = m.addAction("Outro tempo…")
        if self._v not in self.OPCOES:
            outro.setText(f"Outro tempo… (agora {self._fmt(self._v)})")
        outro.triggered.connect(self._outro)

    def _outro(self):
        v, ok = QInputDialog.getInt(self.window(), "Tempo de cada foto", "Segundos:", self._v, 1, 600)
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
        self.cfg = config.carregar()
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
        esq.setToolTip("Mostrar na fila")
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
        self.l_nome = QLabel("Nada tocando")
        self.l_nome.setObjectName("nome")
        self.l_nome.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.l_info = QLabel("Arraste pastas para a janela")
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
        self.b_ant = self._botao("anterior", "Anterior (P)", self.anterior)
        self.b_play = self._botao("play", "Tocar / pausar (Espaço)", self.alternar_pausa, tam=22)
        self.b_play.setObjectName("play")
        self.b_play.setIcon(icone("play", "#1a0f07", 22))
        self.b_prox = self._botao("proximo", "Próximo (N)", lambda: self.proximo(False))
        self.b_alea = self._botao("aleatorio", "Aleatório (S)", self.alternar_aleatorio, checavel=True, tam=18)
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
        self.l_total.setToolTip("Clique: tempo total / tempo que falta")
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
        self.b_vol = self._botao("volume", "Mudo (M)", self.alternar_mudo, tam=18)
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
        self.b_abrir = self._botao("pasta", "Pastas: abrir, juntar, limpar (Ctrl+O abre direto)",
                                   lambda: self._abrir_menu_pastas(self.b_abrir), tam=19)
        self.menu_abrir = MenuRico(self)
        self.b_painel = self._botao("lista", "Fila (L)", self.alternar_painel, checavel=True, tam=19)
        self.b_tela = self._botao("telacheia", "Tela cheia (F / duplo clique)", self.alternar_tela_cheia, tam=19)
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
        m.linha("limpar", "Limpar fila", "Esvazia a fila. O Continuar fica guardado", "",
                self.limpar, perigo=True, ativo=bool(self.fila.itens))
        m.linha("limpar", "Limpar tudo", "Fila e a lista do Continuar. Não apaga nada do PC", "",
                self.limpar_tudo, perigo=True)
        self._menu_limpar = m  # segura a referência enquanto aberto
        self._popup_acima(m, botao, alinhar_direita=False)

    def _montar_menu_abrir(self):
        m = self.menu_abrir
        m.clear()
        m.titulo("Abrir")
        m.linha("pasta", "Abrir pasta", "Toca a pasta e todas as subpastas (troca a fila)",
                "Ctrl+O", self.abrir_pasta)
        m.linha("pastamais", "Juntar outra pasta", "Soma mais uma pasta à fila, sem parar o que toca",
                "Ctrl+Shift+O", self.adicionar_pasta)
        m.linha("foto", "Abrir arquivos", "Escolher fotos ou vídeos soltos", "", self.abrir_arquivos)
        ultimas = [p for p in self.cfg["ultimas_pastas"] if os.path.exists(p)]
        if ultimas:
            m.titulo("Última fila")
            nomes = ", ".join(os.path.basename(p.rstrip("\\/")) or p for p in ultimas[:3])
            if len(ultimas) > 3:
                nomes += f" e mais {len(ultimas) - 3}"
            m.linha("repetir", f"Continuar ({len(ultimas)} pasta{'s' if len(ultimas) > 1 else ''})",
                    nomes, "", self.continuar_ultimas)
        m.titulo("Arquivo na tela")
        m.linha("explorer", "Mostrar no Explorer", "Abre a pasta onde ele está", "E",
                self.mostrar_atual_no_explorer, ativo=self._item is not None)
        m.titulo("Limpar")
        m.linha("limpar", "Limpar fila", "Esvazia a fila. O Continuar fica guardado", "",
                self.limpar, perigo=True, ativo=bool(self.fila.itens))
        tem_historico = bool(self.cfg["ultimas_pastas"]) or bool(self.fila.itens)
        m.linha("limpar", "Limpar tudo", "Fila e a lista do Continuar. Não apaga nada do PC", "",
                self.limpar_tudo, perigo=True, ativo=tem_historico)
        m.titulo("Problemas")
        m.linha("repetir", "Restaurar de fábrica…",
                "Volta todos os ajustes ao padrão e limpa fila, Continuar e cache. Não apaga nada do PC",
                "", self.restaurar_fabrica, perigo=True)

    def _montar_painel(self) -> QFrame:
        painel = QFrame()
        painel.setObjectName("painel")
        painel.setFixedWidth(330)
        v = QVBoxLayout(painel)
        v.setContentsMargins(14, 14, 10, 12)
        v.setSpacing(10)
        topo = QHBoxLayout()
        t = QLabel("Fila")
        t.setObjectName("tituloPainel")
        self.l_contagem = QLabel("")
        self.l_contagem.setObjectName("apagado")
        topo.addWidget(t)
        topo.addSpacing(6)
        topo.addWidget(self.l_contagem, 0, Qt.AlignBottom)
        topo.addStretch(1)
        v.addLayout(topo)

        acoes = QHBoxLayout()
        acoes.setSpacing(6)

        def pilula(nome_icone, texto, dica, slot):
            b = QToolButton()
            b.setObjectName("pilula")
            b.setText(texto)
            b.setIcon(icone(nome_icone, TEXTO, 16))
            b.setIconSize(QSize(16, 16))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(dica)
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            # o Qt não soma o padding do estilo: largura = texto + ícone + respiro
            b.setMinimumWidth(QFontMetrics(b.font()).horizontalAdvance(texto) + 16 + 34)
            b.clicked.connect(slot)
            acoes.addWidget(b)
            return b
        self.b_p_abrir = pilula("pasta", "Abrir", "Abrir pasta: troca a fila (Ctrl+O)", self.abrir_pasta)
        self.b_p_juntar = pilula("pastamais", "Juntar pasta",
                                 "Soma mais uma pasta à fila, sem parar o que toca (Ctrl+Shift+O)",
                                 self.adicionar_pasta)
        self.b_p_limpar = pilula("limpar", "Limpar", "Limpar fila ou limpar tudo", lambda: None)
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
        for chave, texto, dica in (("tudo", "Tudo", "Fotos e vídeos (1)"), ("fotos", "Fotos", "Só fotos (2)"),
                                   ("videos", "Vídeos", "Só vídeos (3)")):
            pb = QPushButton(texto)
            pb.setObjectName("segmento")
            pb.setCheckable(True)
            pb.setCursor(Qt.PointingHandCursor)
            pb.setFocusPolicy(Qt.NoFocus)
            pb.setToolTip(dica)
            pb.setProperty("filtro", chave)
            pb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.g_filtro.addButton(pb)
            sl.addWidget(pb)
        self.g_filtro.buttonClicked.connect(lambda pb: self.definir_filtro(pb.property("filtro")))
        v.addWidget(seg)

        self.filtro_txt = QLineEdit()
        self.filtro_txt.setPlaceholderText("Buscar na fila (nome ou pasta)")
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
        self.assinatura_fila = assinatura(painel)
        v.addWidget(self.assinatura_fila)
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
        a("Escape", self.sair_tela_cheia)
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
        p = QFileDialog.getExistingDirectory(self, "Adicionar pasta à fila" if adicionar else "Abrir pasta", inicio)
        if p:
            self.carregar([p], adicionar=adicionar)

    def abrir_arquivos(self):
        arqs, _ = QFileDialog.getOpenFileNames(self, "Abrir fotos e vídeos", os.path.expanduser("~"))
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
        self._status(f"Lendo {self._nome_curto(caminhos)}…")
        self.varredor = Varredor(caminhos, adicionar and bool(self.fila.itens))
        self.varredor.progresso.connect(
            lambda n, p: self._status(f"Lendo… {n:,} arquivos".replace(",", ".") + (f"  ·  {p}" if p else "")))
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
            self._status("Nenhuma foto ou vídeo nessa pasta nem nas subpastas.")
            return
        pastas = [p for p in self.pastas_abertas if os.path.exists(p)]
        if pastas:
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
        self.pastas_abertas = []
        self._atualizar_lista()
        self.palco.setCurrentWidget(self.vazio)
        self.vazio.atualizar_continuar([p for p in self.cfg["ultimas_pastas"] if os.path.exists(p)])
        self.l_nome.setText("Nada tocando")
        self.l_info.setText("Arraste pastas para a janela")
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
                self, "Limpar tudo",
                "Limpar a fila e a lista do \"Continuar\"?\n\nNenhuma foto ou vídeo do PC é apagado.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        self.cfg["ultimas_pastas"] = []
        config.salvar(self.cfg)
        self.limpar()
        self.vazio.atualizar_continuar([])
        self.vazio.status.setText("Fila e Continuar limpos. Arraste pastas para começar.")

    def restaurar_fabrica(self, confirmar=True):
        """Como recém-instalado: ajustes no padrão, fila e Continuar vazios, cache apagado.
        Mantém o erro.txt (diagnóstico). Nunca mexe nas fotos e vídeos do PC."""
        if confirmar:
            r = QMessageBox.question(
                self, "Restaurar de fábrica",
                "Voltar o Ciranda ao estado de recém-instalado?\n\n"
                "• Ajustes voltam ao padrão (volume, aleatório, repetir, tempo da foto, filtro, janela)\n"
                "• Fila, Continuar e cache das fotos HEIC são limpos\n\n"
                "Nenhuma foto ou vídeo do PC é apagado.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        if self.isFullScreen():
            self.sair_tela_cheia()
        self.limpar()
        fotos.apagar_cache()
        self.cfg = dict(config.PADRAO)
        self.cfg["ultimas_pastas"] = []
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
        self.vazio.status.setText("Ciranda restaurado de fábrica. Arraste pastas para começar.")
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
            self._fim("Nenhum arquivo da fila abriu.")
            return
        QTimer.singleShot(50, lambda: self.tocar(self.fila.proximo(automatico=False)))

    def _fim(self, msg="Fim da fila. Aperte ▶ para começar de novo."):
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
        m.linha("play" if pausado else "pause", "Tocar" if pausado else "Pausar", "", "Espaço", self.alternar_pausa)
        m.linha("proximo", "Próximo", "", "N", lambda: self.proximo(False))
        m.linha("aleatorio", "Aleatório: " + ("ligado" if self.fila.aleatorio else "desligado"), "", "S",
                self.alternar_aleatorio)
        rep = {"nao": "desligado", "tudo": "a fila toda", "um": "só este"}[self.fila.repetir]
        m.linha("repetir", f"Repetir: {rep}", "", "R", self.ciclar_repetir)
        m.titulo("Pastas")
        m.linha("pastamais", "Juntar outra pasta", "Soma à fila sem parar o que toca", "Ctrl+Shift+O",
                self.adicionar_pasta)
        m.linha("pasta", "Abrir pasta", "Troca a fila", "Ctrl+O", self.abrir_pasta)
        m.titulo("Arquivo na tela")
        m.linha("explorer", "Mostrar no Explorer", "Abre a pasta onde ele está", "E",
                self.mostrar_atual_no_explorer, ativo=self._item is not None)
        m.linha("telacheia", "Sair da tela cheia" if self.isFullScreen() else "Tela cheia", "", "F",
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
        self._aviso(f"Volume {self.volume.value()}%")

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
        self._aviso("Sem som" if self.cfg["mudo"] else "Som ligado")

    def alternar_aleatorio(self):
        self.fila.definir_aleatorio(not self.fila.aleatorio)
        self.cfg["aleatorio"] = self.fila.aleatorio
        self._aplicar_modos_na_tela()
        self._aviso("Aleatório ligado" if self.fila.aleatorio else "Em ordem")
        self._atualizar_lista()
        self._atualizar_info()

    def ciclar_repetir(self):
        self.fila.proximo_modo_repetir()
        self.cfg["repetir"] = self.fila.repetir
        self._aplicar_modos_na_tela()
        self._aviso({"nao": "Repetir desligado", "tudo": "Repetir a fila toda",
                     "um": "Repetir só este"}[self.fila.repetir])
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
        self._aviso({"tudo": "Mostrando fotos e vídeos", "fotos": "Só fotos", "videos": "Só vídeos"}[filtro])
        self._aplicar_modos_na_tela()
        self._atualizar_lista()
        if self.fila.itens and not continua:
            item = self.fila.proximo()
            if item is None:
                self._parar_motor()
                self._item = None
                self.l_info.setText(f'<span style="color:{APAGADO}">Nada na fila com esse filtro.</span>')
            else:
                self.tocar(item)
        self._atualizar_info()

    def _aplicar_modos_na_tela(self):
        self.b_alea.setChecked(self.fila.aleatorio)
        self.b_alea.setIcon(icone("aleatorio", DESTAQUE if self.fila.aleatorio else TEXTO, 18))
        rep = self.fila.repetir
        self.b_rep.setChecked(rep != "nao")
        self.b_rep.setIcon(icone("repetir1" if rep == "um" else "repetir", DESTAQUE if rep != "nao" else TEXTO, 18))
        self.b_rep.setToolTip({"nao": "Repetir: desligado (R)", "tudo": "Repetir: a fila toda (R)",
                               "um": "Repetir: só este (R)"}[rep])
        for pb in self.g_filtro.buttons():
            pb.setChecked(pb.property("filtro") == self.fila.filtro)
        self.b_vol.setIcon(icone("mudo" if self.cfg["mudo"] else "volume", TEXTO, 18))

    def _mudou_tempo_foto(self, v):
        self.cfg["segundos_foto"] = v
        self._aviso(f"Cada foto: {v} s")
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
        self.b_play.setIcon(icone("play" if pausado else "pause", "#1a0f07", 22))

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
        txt = f"{n(len(self.fila))} na fila · {n(nf)} fotos · {n(nv)} vídeos"
        txt += f"\nde {n(n_pastas)} pastas com mídia ({n(len(self.pastas_abertas))} aberta{'s' if len(self.pastas_abertas) != 1 else ''}, {n(self._pastas_lidas)} lidas)"
        if self._ignorados:
            txt += f" · {n(self._ignorados)} arquivos de outros tipos"
        falhas = sum(1 for i in itens if i.falhou)
        if falhas:
            txt += " · 1 não abriu" if falhas == 1 else f" · {n(falhas)} não abriram"
        self.l_resumo.setText(txt if itens else "Fila vazia. Arraste pastas para a janela.")
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
        m.addAction(icone("play", TEXTO, 16), "Tocar agora", lambda: self._lista_duplo(idx))
        m.addAction(icone("explorer", TEXTO, 16), "Mostrar no Explorer", lambda: mostrar_no_explorer(item.caminho))
        m.addAction("Copiar caminho", lambda: QGuiApplication.clipboard().setText(item.caminho))
        m.addSeparator()
        m.addAction(icone("limpar", TEXTO, 16),
                    "Tirar da fila" if len(sel) == 1 else f"Tirar {len(sel)} da fila",
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
        extra = " · convertendo HEIC…" if carregando else ""
        fm = QFontMetrics(self.l_nome.font())
        self.l_nome.setText(fm.elidedText(item.nome, Qt.ElideMiddle, max(60, self.l_nome.width())))
        self.l_nome.setToolTip(item.caminho)
        self.l_info.setText(f'{pasta} · {n} de {total}{extra}')
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
