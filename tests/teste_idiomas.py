"""Regra 13 (PT · EN · ES) e regra 12/14 (tutorial na primeira vez).
Parte 1 (sem tela): todo texto nos 3 idiomas, mesmos {campos}, toda chave usada no código existe,
idioma do sistema (pt-BR, es-ES, en-US, fr-FR) e o escolhido no seletor vencendo o do sistema.
Parte 2 (tela): instalação nova com o sistema em espanhol → tela em espanhol + tutorial sozinho;
clique de verdade em EN, PT e ES no rodapé (troca na hora, fica salvo); tutorial com Próximo,
Voltar e Entendi; o ? reabre; abrir de novo com o sistema em espanhol mantém o escolhido.
    CIRANDA_VO=x11 xvfb-run -a python testes/teste_idiomas.py <pasta-de-midia> <saida>"""
import glob
import json
import os
import re
import string
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-idiomas")
os.environ["CIRANDA_SEM_ATUALIZACAO"] = "1"
os.environ.pop("CIRANDA_SEM_QUADROS", None)
dados = os.path.join(os.environ["APPDATA"], "Ciranda")
if os.path.exists(os.path.join(dados, "config.json")):
    os.remove(os.path.join(dados, "config.json"))

from ciranda import textos  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    assert cond, msg
    n += 1


# ---------- todo texto nos três, com os mesmos campos ----------
def campos(txt):
    return sorted({c[1] for c in string.Formatter().parse(txt) if c[1]})


for chave, trio in textos.T.items():
    ok(len(trio) == 3 and all(x and x.strip() for x in trio), f"'{chave}' sem os 3 idiomas")
    ok(campos(trio[0]) == campos(trio[1]) == campos(trio[2]), f"'{chave}' com campos diferentes: {trio}")
usadas = set()
for f in [x for x in glob.glob(os.path.join(RAIZ, "ciranda", "*.py")) if not x.endswith("textos.py")] + [os.path.join(RAIZ, "app.py")]:
    usadas |= set(re.findall(r'\bt\("([a-z0-9_]+)"', open(f, encoding="utf-8").read()))
for k in sorted(usadas):
    ok(k in textos.T, f"chave usada no código sem texto: {k}")
# chaves montadas (f"filtro_{chave}", f"tut{n}", f"repetir_{...}", f"osd_...")
for k in ([f"filtro_{c}{x}" for c in ("tudo", "fotos", "videos") for x in ("", "_dica")]
          + [f"tut{i}{x}" for i in range(1, 6) for x in ("", "_t")]
          + [f"{p}_{r}" for p in ("repetir", "dica_repetir", "osd_repetir") for r in ("nao", "tudo", "um")]
          + [f"osd_filtro_{c}" for c in ("tudo", "fotos", "videos")]):
    ok(k in textos.T, f"chave montada sem texto: {k}")
nov = json.load(open(os.path.join(RAIZ, "ciranda", "novidades.json"), encoding="utf-8"))
from ciranda import VERSAO  # noqa: E402
ok(VERSAO in nov and all(nov[VERSAO].get(i) for i in textos.IDIOMAS), "novidades.json sem a versão nos 3 idiomas")
ok(len(nov[VERSAO]["pt"]) == len(nov[VERSAO]["en"]) == len(nov[VERSAO]["es"]), "novidades com tamanhos diferentes")

# ---------- idioma do sistema e o escolhido ----------
for codigo, esperado in (("pt-BR", "pt"), ("pt-PT", "pt"), ("es-ES", "es"), ("es-419", "es"), ("en-US", "en"),
                         ("en-GB", "en"), ("fr-FR", "en"), ("de-DE", "en"), ("ja", "en"), ("", "en")):
    ok(textos.normalizar(codigo) == esperado, f"{codigo!r} → {textos.normalizar(codigo)}")
for sistema, esperado in (("pt-BR", "pt"), ("es-ES", "es"), ("en-US", "en"), ("fr-FR", "en")):
    os.environ["CIRANDA_IDIOMA_SISTEMA"] = sistema
    ok(textos.iniciar({}) == esperado, f"sistema {sistema} → {textos.atual()}")
    ok(textos.iniciar({"idioma": "pt"}) == "pt", "o escolhido no seletor vence o sistema")
os.environ["CIRANDA_IDIOMA_SISTEMA"] = "es-ES"
textos.iniciar({})
ok(textos.t("fila") == "Cola" and textos.t("n_de_total", n=2, total=9) == "2 de 9", "t() em espanhol")
print(f"ok: parte 1 ({n} checagens, {len(textos.T)} textos)")

# ---------- tela ----------
from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from ciranda import config  # noqa: E402
from ciranda.janela import QSS, Janela  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
estado = {"j": Janela()}
j = estado["j"]
j.resize(1280, 760)
j.move(0, 0)
j.show()
log = []


def foto(nome):
    os.system(f"import -window root -crop 1280x760+0+0 +repage '{os.path.join(SAIDA, nome)}'")


def clicar_idioma(codigo):
    """Clique de verdade no PT/EN/ES do rodapé da fila."""
    lab = j.seletor_fila
    plano = re.sub("<[^>]+>", "", lab.text()).replace("&nbsp;", " ")
    i = plano.index(textos.NOMES[codigo])
    x = lab.fontMetrics().horizontalAdvance(plano[:i]) + 6
    x += max(0, (lab.width() - lab.sizeHint().width()) if lab.alignment() & Qt.AlignRight else 0)
    QTest.mouseClick(lab, Qt.LeftButton, Qt.NoModifier, QPoint(x, lab.height() // 2))


def pilulas_cabem():
    """Os botões Abrir / Juntar / Limpar não podem se sobrepor nem sair da fila."""
    a, b, c = (x.geometry() for x in (j.b_p_abrir, j.b_p_juntar, j.b_p_limpar))
    largura = j.painel.width()
    ok(a.right() < b.left() and b.right() < c.left() and c.right() < largura - 4,
       f"botões da fila não cabem em {textos.atual()}: {a.getRect()} {b.getRect()} {c.getRect()} / {largura}")


def textos_da_tela():
    return {"fila": j.findChild(type(j.l_nome), "tituloPainel").text(), "juntar": j.b_p_juntar.text(),
            "acoes": re.sub("<[^>]+>", "", j.acoes_fila.text()), "assinatura": re.sub("<[^>]+>", "", j.assinatura_fila.text()),
            "inicio": j.vazio.titulo.text(), "busca": j.filtro_txt.placeholderText(), "nada": j.l_nome.text()}


def passo_espanhol():
    q = j.quadro
    ok(q.isVisible() and q.tipo == "tutorial", "tutorial não apareceu sozinho na instalação nova")
    ok(q.l_titulo.text() == "Te damos la bienvenida a Ciranda" and q.l_passos.text() == "1 de 5", q.l_titulo.text())
    tt = textos_da_tela()
    ok(tt["fila"] == "Cola" and tt["juntar"] == "Añadir" and "Reportar un error" in tt["acoes"]
       and "hecho por" in tt["assinatura"] and tt["inicio"] == "Suelta carpetas aquí", tt)
    pilulas_cabem()
    foto("idioma-es-inicio.png")
    log.append("sistema em espanhol: tela e tutorial em espanhol")
    clicar_idioma("en")


def passo_ingles():
    q = j.quadro
    tt = textos_da_tela()
    ok(tt["fila"] == "Queue" and tt["juntar"] == "Add folder" and "Report a bug" in tt["acoes"]
       and "made by" in tt["assinatura"] and tt["busca"].startswith("Search"), tt)
    ok(q.isVisible() and q.l_titulo.text() == "Welcome to Ciranda", f"tutorial não trocou: {q.l_titulo.text()}")
    ok(config.carregar()["idioma"] == "en", "escolha não foi salva")
    j._montar_menu_abrir()
    nomes = [a.text().split("\t")[0] for a in j.menu_abrir.actions()]
    ok("Open folder" in nomes and "Check for updates" in nomes and "Factory reset…" in nomes, nomes)
    pilulas_cabem()
    foto("idioma-en-inicio.png")
    # tutorial: Próximo até o fim, Voltar, Entendi
    QTest.mouseClick(q.botoes()[-1], Qt.LeftButton)
    ok(q.l_passos.text() == "2 of 5" and q.l_titulo.text() == "Play it your way", q.l_passos.text())
    for _ in range(3):
        QTest.mouseClick(q.botoes()[-1], Qt.LeftButton)
    ok(q.l_passos.text() == "5 of 5" and q.botoes()[-1].text() == "Got it", [b.text() for b in q.botoes()])
    QTest.mouseClick(q.botoes()[0], Qt.LeftButton)  # Back
    ok(q.l_passos.text() == "4 of 5", q.l_passos.text())
    QTest.mouseClick(q.botoes()[-1], Qt.LeftButton)
    QTest.mouseClick(q.botoes()[-1], Qt.LeftButton)  # Got it
    ok(not q.isVisible() and config.carregar()["tutorial_visto"], "Entendi não fechou / não salvou")
    log.append("EN: troca na hora, salva; tutorial Next/Back/Got it")
    clicar_idioma("pt")


def passo_portugues():
    tt = textos_da_tela()
    ok(tt["fila"] == "Fila" and tt["juntar"] == "Juntar pasta" and "Relatar bug" in tt["acoes"]
       and tt["nada"] == "Nada tocando", tt)
    pilulas_cabem()
    # o ? do rodapé reabre o tutorial
    lab = j.seletor_fila
    QTest.mouseClick(lab, Qt.LeftButton, Qt.NoModifier, QPoint(3, lab.height() // 2))


def passo_interrogacao():
    q = j.quadro
    ok(q.isVisible() and q.tipo == "tutorial" and q.l_titulo.text() == "Bem-vindo ao Ciranda", "o ? não reabriu")
    foto("idioma-pt-tutorial.png")
    QTest.keyClick(q, Qt.Key_Escape)
    ok(not q.isVisible(), "Esc não fechou")
    j.carregar([PASTA], adicionar=False)
    log.append("PT: troca na hora; o ? reabre o tutorial; Esc fecha")


def passo_tocando():
    ok(j._item is not None and re.search(r" · \d+ de \d+", j.l_info.text()), j.l_info.text())
    clicar_idioma("es")


def passo_tocando_es():
    ok(re.search(r" · \d+ de \d+", j.l_info.text()) and "en la cola" in j.l_resumo.text(), j.l_resumo.text())
    foto("idioma-es-tocando.png")
    ok(config.carregar()["idioma"] == "es", "es não salvo")
    log.append("ES com fila tocando: barra e resumo da fila em espanhol")
    j.close()
    # abre de novo: sistema em inglês, escolhido espanhol → espanhol, e sem tutorial
    os.environ["CIRANDA_IDIOMA_SISTEMA"] = "en-US"
    j2 = Janela()
    j2.show()
    estado["j2"] = j2


def passo_reabrir():
    j2 = estado["j2"]
    ok(j2.b_p_juntar.text() == "Añadir", f"não manteve o escolhido: {j2.b_p_juntar.text()}")
    ok(not j2.quadro.isVisible(), "tutorial apareceu de novo")
    log.append("reabrir: mantém o idioma escolhido e não repete o tutorial")
    print("\n".join(log))
    print(f"IDIOMAS PASSOU ({n} checagens)")
    j2.close()
    app.quit()


passos = [(1800, passo_espanhol), (900, passo_ingles), (900, passo_portugues), (900, passo_interrogacao),
          (3000, passo_tocando), (900, passo_tocando_es), (2000, passo_reabrir)]


def rodar(i=0):
    if i >= len(passos):
        return
    ms, fn = passos[i]

    def ex():
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            app.exit(1)
            return
        rodar(i + 1)
    QTimer.singleShot(ms, ex)


rodar()
QTimer.singleShot(40000, lambda: (print("tempo esgotado"), app.exit(1)))
sys.exit(app.exec())
