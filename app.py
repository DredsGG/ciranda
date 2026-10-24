"""Ciranda: abre a janela. Aceita pastas/arquivos na linha de comando
(é assim que o "Abrir com" e o menu do botão direito passam a pasta)."""

import os
import sys
import traceback

PASTA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PASTA)


def _registrar_erros():
    """Erro dentro de um botão não derruba o app, mas some calado no pythonw.
    Aqui ele vai para %APPDATA%\\Ciranda\\erro.txt (com data e hora)."""
    import time
    from ciranda.config import pasta_dados
    caminho = os.path.join(pasta_dados(), "erro.txt")

    def gancho(tipo, valor, tb):
        try:
            with open(caminho, "a", encoding="utf-8") as f:
                f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                traceback.print_exception(tipo, valor, tb, file=f)
        except Exception:
            pass
    sys.excepthook = gancho


def main():
    _registrar_erros()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dreds.Ciranda")
        except Exception:
            pass
    from PySide6.QtWidgets import QApplication
    from ciranda import NOME
    from ciranda.janela import QSS, Janela

    app = QApplication(sys.argv)
    app.setApplicationName(NOME)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    caminhos = [a for a in sys.argv[1:] if not a.startswith("-")]
    j = Janela(caminhos)
    j.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # pythonw não tem console: grava o erro num arquivo para dar para ler depois
        from ciranda.config import pasta_dados
        with open(os.path.join(pasta_dados(), "erro.txt"), "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "O Ciranda não conseguiu abrir.\nDetalhes em %APPDATA%\\Ciranda\\erro.txt", "Ciranda", 0x10)
        except Exception:
            pass
        raise
