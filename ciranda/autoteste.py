"""Autoteste do app empacotado: `Ciranda.exe --autoteste=<resultado.json>`.

Roda no Windows do GitHub (e em qualquer PC) sem ninguém olhando:
gera fotos de exemplo numa pasta temporária, abre a pasta, CLICA de verdade na
pastinha da barra e no "Limpar" da fila, confere se os menus aparecem, confere a
assinatura (regra 9) e grava tudo num JSON. Código de saída 0 = passou.
Não mexe nos ajustes do usuário: usa um APPDATA temporário.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback


def _gerar_midia(pasta: str) -> int:
    from PIL import Image
    n = 0
    for sub, cor in (("", (40, 90, 160)), ("viagem", (200, 120, 40)), ("viagem/dia 2", (60, 140, 60))):
        d = os.path.join(pasta, sub)
        os.makedirs(d, exist_ok=True)
        for k in range(2):
            Image.new("RGB", (640, 400), cor).save(os.path.join(d, f"foto{k}.jpg"))
            n += 1
    return n


def rodar(saida: str) -> int:
    base = tempfile.mkdtemp(prefix="ciranda-autoteste-")
    os.environ["APPDATA"] = os.path.join(base, "appdata")  # ajustes do usuário intocados
    midia = os.path.join(base, "midia")
    total = _gerar_midia(midia)

    from PySide6.QtCore import QPoint, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from . import NOME, VERSAO
    from .janela import GITHUB, QSS, Janela

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(NOME)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    res = {"versao": VERSAO, "plataforma": app.platformName(), "checagens": {}, "erro": None}
    ok = res["checagens"]
    j = Janela([midia])
    j.resize(1280, 760)
    j.show()

    def clique(w):
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(w.width() // 2, w.height() // 2))

    def etapa1():
        ok["fila_carregada"] = len(j.fila) == total
        ok["motor"] = str(getattr(j.mpv, "mpv_version", ""))
        clique(j.b_abrir)
        QTimer.singleShot(700, etapa2)

    def etapa2():
        m = j.menu_abrir
        ok["menu_pastinha_visivel"] = m.isVisible()
        ok["menu_pastinha_itens"] = len(m.actions())
        m.close()
        clique(j.b_p_limpar)
        QTimer.singleShot(700, etapa3)

    def etapa3():
        m = getattr(j, "_menu_limpar", None)
        ok["menu_limpar_visivel"] = bool(m and m.isVisible())
        if m and m.isVisible():
            alvo = [a for a in m.actions() if a.text().startswith("Limpar fila")][0]
            QTest.mouseClick(m, Qt.LeftButton, Qt.NoModifier, m.actionGeometry(alvo).center())
        QTimer.singleShot(700, etapa4)

    def etapa4():
        ok["limpar_fila_funcionou"] = len(j.fila) == 0
        txt = j.assinatura_fila.text()
        ok["assinatura"] = (f"· v{VERSAO}" in txt and GITHUB in txt and j.assinatura_fila.openExternalLinks())
        terminar()

    def terminar():
        res["passou"] = all(v for k, v in ok.items() if k not in ("motor", "menu_pastinha_itens"))
        with open(saida, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        app.exit(0 if res["passou"] else 1)

    def falhou(e):
        res["erro"] = "".join(traceback.format_exception(e))
        res["passou"] = False
        with open(saida, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        app.exit(1)

    def protegido(fn):
        def w():
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                falhou(e)
        return w

    etapa1, etapa2, etapa3, etapa4 = map(protegido, (etapa1, etapa2, etapa3, etapa4))
    QTimer.singleShot(3000, etapa1)
    QTimer.singleShot(60000, lambda: falhou(TimeoutError("autoteste passou de 60 s")))
    t0 = time.monotonic()
    codigo = app.exec()
    res["segundos"] = round(time.monotonic() - t0, 1)
    try:
        j.close()
    except Exception:
        pass
    return codigo
