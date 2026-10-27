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
    from .textos import idioma_do_sistema
    sistema = idioma_do_sistema()  # o de verdade (Windows: GetUserPreferredUILanguages), antes de forçar pt
    base = tempfile.mkdtemp(prefix="ciranda-autoteste-")
    os.environ["APPDATA"] = os.path.join(base, "appdata")  # ajustes do usuário intocados
    os.environ["CIRANDA_SEM_ATUALIZACAO"] = "1"  # a atualização tem teste próprio
    os.environ["CIRANDA_IDIOMA_SISTEMA"] = "pt"  # o autoteste procura os textos em português
    os.environ["CIRANDA_SEM_QUADROS"] = "1"  # o tutorial é aberto de propósito no fim
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
    res = {"versao": VERSAO, "plataforma": app.platformName(), "idioma_do_sistema": sistema,
           "checagens": {}, "erro": None}
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
        nomes = [a.text().split("\t")[0] for a in m.actions()]
        ok["menu_tem_atualizacao_e_bug"] = "Procurar atualização" in nomes and "Relatar bug…" in nomes
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
        acoes = j.acoes_fila.text()
        ok["rodape_bug_e_atualizacao"] = ("acao:bug" in acoes and "acao:atualizar" in acoes
                                          and j.acoes_fila.isVisible())
        clique(j.b_abrir)
        QTimer.singleShot(700, etapa5)

    def etapa5():
        m = j.menu_abrir
        alvo = [a for a in m.actions() if a.text().startswith("Relatar bug")][0]
        QTest.mouseClick(m, Qt.LeftButton, Qt.NoModifier, m.actionGeometry(alvo).center())
        QTimer.singleShot(900, etapa6)

    def etapa6():
        d = getattr(j, "_dlg_bug", None)
        ok["relatar_bug_abriu"] = bool(d and d.isVisible())
        diag = d.previa.toPlainText() if d else ""
        res["diagnostico"] = diag[:600]
        ok["relatar_bug_sem_nomes"] = bool(diag) and not any(
            x.lower() in diag.lower() for x in (base, "ciranda-autoteste", "viagem", os.environ.get("USERNAME") or "\0"))
        if d:
            d.reject()
        # idioma (regra 13): clique de verdade no EN do rodapé da fila
        import re
        lab = j.seletor_fila
        plano = re.sub("<[^>]+>", "", lab.text()).replace("&nbsp;", " ")
        x = lab.fontMetrics().horizontalAdvance(plano[:plano.index("EN")]) + 6
        QTest.mouseClick(lab, Qt.LeftButton, Qt.NoModifier, QPoint(x, lab.height() // 2))
        QTimer.singleShot(500, etapa7)

    def etapa7():
        ok["idioma_en_no_clique"] = (j.b_p_juntar.text() == "Add folder" and "Report a bug" in j.acoes_fila.text()
                                     and "made by" in j.assinatura_fila.text())
        j.mudar_idioma("pt")
        ok["idioma_pt_de_novo"] = j.b_p_juntar.text() == "Juntar pasta"
        # tutorial (regras 12 e 14): quadro no meio da janela, por cima, fecha no Esc
        j.mostrar_tutorial()
        QTimer.singleShot(500, etapa8)

    def etapa8():
        q = j.quadro
        g, jg = q.frameGeometry(), j.frameGeometry()
        ok["tutorial_no_meio"] = (q.isVisible() and q.isWindow() and jg.contains(g.center())
                                  and abs(g.center().x() - jg.center().x()) < 40)
        res["quadro_geometria"] = [g.x(), g.y(), g.width(), g.height(), jg.x(), jg.y(), jg.width(), jg.height()]
        QTest.keyClick(q, Qt.Key_Escape)
        ok["tutorial_fecha_no_esc"] = not q.isVisible()
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

    etapa1, etapa2, etapa3, etapa4, etapa5, etapa6, etapa7, etapa8 = map(
        protegido, (etapa1, etapa2, etapa3, etapa4, etapa5, etapa6, etapa7, etapa8))
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
