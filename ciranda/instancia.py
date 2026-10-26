"""Janela única: se o Ciranda já está aberto, abrir outra foto/vídeo/pasta manda o
caminho para a janela aberta (em vez de abrir uma segunda) e esta instância sai.

Funciona com QLocalServer (pipe nomeado no Windows, socket local no Linux).
"""

from __future__ import annotations

import getpass
import json
import re
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def _nome_servidor() -> str:
    try:
        usuario = getpass.getuser()
    except Exception:
        usuario = "usuario"
    return "Dreds.Ciranda." + re.sub(r"[^A-Za-z0-9_.-]", "_", usuario)


def enviar_para_aberta(caminhos: list[str], espera_ms: int = 400) -> bool:
    """Tenta entregar os caminhos à janela já aberta. True = entregou (pode sair)."""
    s = QLocalSocket()
    s.connectToServer(_nome_servidor())
    if not s.waitForConnected(espera_ms):
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
        except Exception:
            pass
    s.write(json.dumps({"caminhos": caminhos}).encode("utf-8"))
    s.flush()
    s.waitForBytesWritten(1500)
    s.disconnectFromServer()
    if s.state() != QLocalSocket.UnconnectedState:
        s.waitForDisconnected(1000)
    return True


class Servidor(QObject):
    """Fica escutando na janela aberta. Emite `recebeu(lista de caminhos)`."""
    recebeu = Signal(list)

    def __init__(self):
        super().__init__()
        self._srv = QLocalServer(self)
        self._buffers: dict = {}
        self._srv.newConnection.connect(self._nova)

    def escutar(self) -> bool:
        nome = _nome_servidor()
        if self._srv.listen(nome):
            return True
        # no Linux sobra o arquivo do socket se o app caiu; no Windows o nome está em uso
        QLocalServer.removeServer(nome)
        return self._srv.listen(nome)

    def _nova(self):
        while self._srv.hasPendingConnections():
            c = self._srv.nextPendingConnection()
            self._buffers[c] = b""
            c.readyRead.connect(lambda c=c: self._ler(c))
            c.disconnected.connect(lambda c=c: self._fim(c))

    def _ler(self, c):
        self._buffers[c] = self._buffers.get(c, b"") + bytes(c.readAll())

    def _fim(self, c):
        self._ler(c)
        dados = self._buffers.pop(c, b"")
        c.deleteLater()
        try:
            caminhos = json.loads(dados.decode("utf-8")).get("caminhos", [])
        except Exception:
            caminhos = []
        self.recebeu.emit([p for p in caminhos if isinstance(p, str)])
