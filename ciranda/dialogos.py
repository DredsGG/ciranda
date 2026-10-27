"""Janelas de "Atualização" e "Relatar bug"."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QProgressBar, QPushButton, QVBoxLayout)

from . import VERSAO, atualizacao, relato

QSS_DIALOGO = """
QDialog { background: #16171c; }
QPlainTextEdit { background: #1b1d22; border: 1px solid #24262d; border-radius: 8px; padding: 6px; }
QPlainTextEdit[readOnly="true"] { color: #8a8c97; font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 11.5px; }
QProgressBar { background: #22242b; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #ff8a3d; border-radius: 4px; }
QCheckBox { spacing: 8px; }
"""


def _abrir_url(url: str):
    QDesktopServices.openUrl(QUrl(url))


class _Sinais(QObject):
    progresso = Signal(int, int)
    pronto = Signal(str)
    falhou = Signal(str)


class DialogoAtualizacao(QDialog):
    """Mostra a versão nova e o que mudou. Atualizar = baixar, conferir, instalar, reabrir.
    `sair` é chamado quando o instalador já está rodando (a janela principal fecha)."""

    def __init__(self, pai, info: dict, sair):
        super().__init__(pai)
        self.info = info
        self._sair = sair
        self._cancelar = False
        self._baixando = False
        self.setWindowTitle("Atualização do Ciranda")
        self.setStyleSheet(QSS_DIALOGO)
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(10)

        self.local = bool(info.get("local"))
        t = QLabel(f"Ciranda v{info['versao']} (teste) disponível" if self.local
                   else f"Ciranda v{info['versao']} disponível")
        t.setObjectName("grande")
        v.addWidget(t)
        sub = QLabel(f"Você está na v{VERSAO}." + (" Esta versão veio da sua pasta de teste e ainda não "
                                                    "está no GitHub." if self.local else ""))
        sub.setWordWrap(True)
        sub.setObjectName("apagado")
        v.addWidget(sub)
        if info.get("notas"):
            v.addSpacing(4)
            v.addWidget(QLabel("<b>O que mudou</b>"))
            notas = QLabel("<br>".join(f"• {self._esc(n)}" for n in info["notas"]))
            notas.setWordWrap(True)
            notas.setTextFormat(Qt.RichText)
            v.addWidget(notas)
        link = QLabel(f'<a href="{info["pagina"]}" style="color:#ff8a3d; text-decoration:none;">'
                      f'Ver tudo no GitHub</a>')
        link.setOpenExternalLinks(True)
        if not self.local:
            v.addWidget(link)

        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.hide()
        v.addWidget(self.barra)
        self.estado = QLabel("")
        self.estado.setObjectName("apagado")
        self.estado.setWordWrap(True)
        self.estado.hide()
        v.addWidget(self.estado)

        v.addSpacing(6)
        bot = QHBoxLayout()
        bot.addStretch(1)
        self.b_depois = QPushButton("Depois")
        self.b_depois.clicked.connect(self.reject)
        self.pode_instalar = bool(info.get("setup")) and (atualizacao.instalado() or self.local)
        self.b_ok = QPushButton("Atualizar agora" if self.pode_instalar else "Baixar no GitHub")
        self.b_ok.setObjectName("primario")
        self.b_ok.setDefault(True)
        self.b_ok.clicked.connect(self._atualizar)
        bot.addWidget(self.b_depois)
        bot.addWidget(self.b_ok)
        v.addLayout(bot)
        if self.pode_instalar:
            dica = QLabel("O Ciranda fecha, instala sozinho e abre de novo. Seus ajustes ficam.")
        else:
            dica = QLabel("Este Ciranda não veio do instalador: baixe a versão nova na página.")
        dica.setObjectName("apagado")
        dica.setWordWrap(True)
        v.addWidget(dica)

    @staticmethod
    def _esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _atualizar(self):
        if not self.pode_instalar:
            _abrir_url(self.info["pagina"])
            self.accept()
            return
        self._baixando = True
        self.b_ok.setEnabled(False)
        self.b_depois.setText("Cancelar")
        self.barra.setRange(0, 0)
        self.barra.show()
        self.estado.setText("Copiando…" if self.local else "Baixando…")
        self.estado.show()
        s = self._sinais = _Sinais()
        s.progresso.connect(self._progresso)
        s.pronto.connect(self._baixou)
        s.falhou.connect(self._falhou)

        def trabalho():
            try:
                fn = atualizacao.copiar_setup_local if self.local else atualizacao.baixar_setup
                caminho = fn(self.info["setup"], s.progresso.emit, lambda: self._cancelar)
                s.pronto.emit(caminho)
            except InterruptedError:
                s.falhou.emit("")
            except Exception as e:
                s.falhou.emit(str(e) or e.__class__.__name__)
        threading.Thread(target=trabalho, daemon=True).start()

    def _progresso(self, feito, total):
        if total:
            self.barra.setRange(0, 1000)
            self.barra.setValue(int(feito * 1000 / total))
            self.estado.setText(f"{'Copiando' if self.local else 'Baixando'}… "
                                f"{feito / 1048576:.0f} de {total / 1048576:.0f} MB")

    def _baixou(self, caminho):
        self.barra.setRange(0, 0)
        self.estado.setText("Instalando…" if self.local else "Conferido (SHA-256 igual ao do GitHub). Instalando…")
        try:
            atualizacao.rodar_instalador(caminho, VERSAO)
        except Exception as e:
            self._falhou(f"não consegui abrir o instalador ({e})")
            return
        self._baixando = False
        QTimer.singleShot(600, self._sair)

    def _falhou(self, msg):
        self._baixando = False
        self.barra.hide()
        self.b_ok.setEnabled(True)
        self.b_ok.setText("Tentar de novo")
        self.b_depois.setText("Depois")
        self.estado.setText("Download cancelado." if not msg else
                            f"Não deu para atualizar: {msg}. Tente de novo ou baixe na página.")

    def reject(self):
        if self._baixando:
            self._cancelar = True
            return
        super().reject()


class DialogoBug(QDialog):
    """Relatar bug: a pessoa escreve o que aconteceu, vê o diagnóstico (sem nomes de
    pastas/arquivos) e abre o relato no GitHub já preenchido, ou copia o texto."""

    def __init__(self, pai, diag: str):
        super().__init__(pai)
        self.diag = diag
        self.setWindowTitle("Relatar bug")
        self.setStyleSheet(QSS_DIALOGO)
        self.resize(560, 560)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(8)
        t = QLabel("Relatar bug")
        t.setObjectName("grande")
        v.addWidget(t)
        v.addWidget(QLabel("O que aconteceu? O que você estava fazendo?"))
        self.texto = QPlainTextEdit()
        self.texto.setPlaceholderText("Ex.: abri uma pasta com vídeos .mov e a tela ficou preta")
        self.texto.setFixedHeight(110)
        v.addWidget(self.texto)
        self.incluir = QCheckBox("Incluir diagnóstico (versões, ajustes, fim do log)")
        self.incluir.setChecked(True)
        v.addWidget(self.incluir)
        self.previa = QPlainTextEdit(diag)
        self.previa.setReadOnly(True)
        self.previa.setProperty("readOnly", True)
        v.addWidget(self.previa, 1)
        self.incluir.toggled.connect(self.previa.setVisible)
        aviso = QLabel("Nomes de pastas, arquivos, do usuário e do PC são tirados: fica só a extensão. "
                       "Nada é enviado sozinho: o GitHub abre no navegador e você confere antes de enviar "
                       "(precisa de conta no GitHub; sem conta, use Copiar relatório).")
        aviso.setObjectName("apagado")
        aviso.setWordWrap(True)
        v.addWidget(aviso)
        self.estado = QLabel("")
        self.estado.setObjectName("apagado")
        self.estado.setWordWrap(True)
        v.addWidget(self.estado)
        bot = QHBoxLayout()
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(self.reject)
        self.b_copiar = QPushButton("Copiar relatório")
        self.b_copiar.clicked.connect(self.copiar)
        self.b_git = QPushButton("Abrir no GitHub")
        self.b_git.setObjectName("primario")
        self.b_git.clicked.connect(self.abrir_github)
        bot.addWidget(b_cancel)
        bot.addStretch(1)
        bot.addWidget(self.b_copiar)
        bot.addWidget(self.b_git)
        v.addLayout(bot)
        self.ultima_url = ""

    def _partes(self):
        return relato.montar(self.texto.toPlainText(), self.diag if self.incluir.isChecked() else "")

    def copiar(self):
        titulo, corpo = self._partes()
        QGuiApplication.clipboard().setText(f"{titulo}\n\n{corpo}")
        self.estado.setText("Copiado. Cole em github.com/DredsGG/ciranda/issues ou mande para o Dreds.")

    def abrir_github(self):
        titulo, corpo = self._partes()
        url, cortado = relato.url_github(titulo, corpo)
        self.ultima_url = url
        if cortado:
            QGuiApplication.clipboard().setText(f"{titulo}\n\n{corpo}")
        _abrir_url(url)
        self.estado.setText("Abri o GitHub no navegador. Confira o texto e envie lá."
                            + (" O log era grande: o relatório completo foi copiado (Ctrl+V para colar)."
                               if cortado else ""))
