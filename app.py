"""Ciranda: abre a janela. Aceita pastas/arquivos na linha de comando
(é assim que o "Abrir com" e o menu do botão direito passam a pasta)."""

import os
import sys
import traceback

# Empacotado (instalador): os arquivos ficam em sys._MEIPASS (a pasta _internal do PyInstaller).
PASTA = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
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


def _testar_atualizacao(saida: str) -> int:
    import json
    from ciranda import VERSAO, atualizacao
    res = {"versao_app": VERSAO, "passou": False}
    try:
        r = atualizacao.procurar("0.0.1", os.environ.get("CIRANDA_API_ATUALIZACAO") or atualizacao.API)
        res.update(versao_github=r["versao"], setup=r["setup"], notas=r["notas"])
        caminho = atualizacao.baixar_setup(r["setup"])  # confere o SHA-256 do GitHub
        res["baixado"] = os.path.getsize(caminho)
        res["passou"] = res["baixado"] == r["setup"]["tamanho"]
        os.remove(caminho)
    except Exception as e:
        res["erro"] = f"{e.__class__.__name__}: {e}"
    # canal de teste (só existe se houver %APPDATA%\\Ciranda\\pasta-de-teste.txt)
    from ciranda.config import pasta_dados
    pasta = atualizacao.pasta_teste(pasta_dados())
    if pasta:
        try:
            loc = atualizacao.procurar_local(pasta, VERSAO)
            res["canal_teste"] = {k: loc[k] for k in ("versao", "disponivel", "notas")} if loc else None
            if loc:
                copia = atualizacao.copiar_setup_local(loc["setup"])
                res["canal_teste"]["copiado"] = os.path.getsize(copia) == loc["setup"]["tamanho"]
                os.remove(copia)
            res["passou"] = res["passou"] and bool(loc and loc["disponivel"] and res["canal_teste"]["copiado"])
        except Exception as e:
            res["canal_teste"] = {"erro": f"{e.__class__.__name__}: {e}"}
            res["passou"] = False
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    return 0 if res["passou"] else 1


def main():
    autoteste = next((a.split("=", 1)[1] if "=" in a else "autoteste.json"
                      for a in sys.argv[1:] if a.startswith("--autoteste")), None)
    if autoteste:
        from ciranda.autoteste import rodar
        sys.exit(rodar(os.path.abspath(autoteste)))
    teste = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--testar-atualizacao=")), None)
    if teste:  # usado pelo teste no Windows do GitHub: procura e baixa o Release de verdade
        sys.exit(_testar_atualizacao(os.path.abspath(teste)))
    aplicar = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--aplicar-atualizacao=")), None)
    if aplicar:  # mesmo caminho do botão "Atualizar agora", sem a parte do download
        import re
        from ciranda import VERSAO
        from ciranda.atualizacao import rodar_instalador
        if not re.fullmatch(r"Ciranda-Setup-\d+\.\d+\.\d+\.exe", os.path.basename(aplicar)):
            sys.exit(2)
        rodar_instalador(os.path.abspath(aplicar), VERSAO)
        sys.exit(0)
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
    caminhos = [os.path.abspath(a) for a in sys.argv[1:] if not a.startswith("-")]

    # janela única: se já tem um Ciranda aberto, entrega os caminhos para ele e sai
    from ciranda.instancia import Servidor, enviar_para_aberta
    if enviar_para_aberta(caminhos):
        sys.exit(0)
    servidor = Servidor()
    if not servidor.escutar() and enviar_para_aberta(caminhos, 1500):
        sys.exit(0)  # outra instância abriu no mesmo instante e ganhou

    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    j = Janela(caminhos)
    servidor.recebeu.connect(j.receber_de_outra_instancia)
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
