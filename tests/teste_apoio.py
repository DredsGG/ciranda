"""Regra 16: botão "Apoiar ♥" no rodapé.
  - Pix: o código gerado para livre, R$ 5, R$ 10 e R$ 25 é IGUAL aos 4 de referência de apoio.md;
    "Outro valor" 12,50 → 54 05 12.50; CRC16 (123456789 → 29B1); limites R$ 1 a R$ 10.000;
  - o QR de cada valor é lido de volta (OpenCV) e bate com o código;
  - quadro: abre pelo rodapé, passo "De onde você é?" com o provável destacado pelo idioma, Brasil →
    valores, QR, copiar código e chave; Outro país → GitHub Sponsors; Voltar; Esc, X e clique fora
    fecham; Tab fica dentro; Enter aciona; abre de novo no lugar escolhido; nenhuma conexão de rede;
  - prints dos dois caminhos nos 3 idiomas.
    CIRANDA_VO=x11 xvfb-run -a python testes/teste_apoio.py <pasta-de-midia> <saida>"""
import os
import socket
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
PASTA, SAIDA = sys.argv[1], sys.argv[2]
os.environ["APPDATA"] = os.path.join(SAIDA, "appdata-apoio")
os.environ.setdefault("CIRANDA_IDIOMA_SISTEMA", "pt")
os.environ["CIRANDA_SEM_QUADROS"] = "1"
os.environ["CIRANDA_SEM_ATUALIZACAO"] = "1"
dados = os.path.join(os.environ["APPDATA"], "Ciranda")
os.makedirs(dados, exist_ok=True)
for f in os.listdir(dados):
    if os.path.isfile(os.path.join(dados, f)):
        os.remove(os.path.join(dados, f))

import cv2  # noqa: E402  (só no teste, para ler o QR de volta)
from decimal import Decimal  # noqa: E402
from ciranda import pix  # noqa: E402

REF = {  # Jarvis\02-projetos\extensoes\apoio.md (conferidos em 2026-10-29; o livre foi lido pelo banco)
    None: "00020126580014br.gov.bcb.pix0136fa525dad-afca-4683-845d-eee7225a53e35204000053039865802BR"
          "5918Andre Miller Fleck6009Sao Paulo62070503***63047D61",
    5: "00020126580014br.gov.bcb.pix0136fa525dad-afca-4683-845d-eee7225a53e352040000530398654045.00"
       "5802BR5918Andre Miller Fleck6009Sao Paulo62070503***6304C8ED",
    10: "00020126580014br.gov.bcb.pix0136fa525dad-afca-4683-845d-eee7225a53e3520400005303986540510.00"
        "5802BR5918Andre Miller Fleck6009Sao Paulo62070503***6304DCD7",
    25: "00020126580014br.gov.bcb.pix0136fa525dad-afca-4683-845d-eee7225a53e3520400005303986540525.00"
        "5802BR5918Andre Miller Fleck6009Sao Paulo62070503***63044036",
}
n = 0
log = []


def ok(cond, msg):
    global n
    assert cond, msg
    n += 1


# ---------------- Pix (sem interface) ----------------
for v, ref in REF.items():
    ok(pix.br_code(v) == ref, f"código {v} diferente da referência:\n{pix.br_code(v)}\n{ref}")
ok(pix.crc16("123456789") == "29B1", "CRC16-CCITT-FALSE")
for ref in REF.values():
    ok(pix.crc16(ref[:-4]) == ref[-4:], "CRC da referência")
c = pix.br_code(pix.ler_valor("12,50"))
ok("540512.50" in c and pix.crc16(c[:-4]) == c[-4:], c)
ok(pix.ler_valor("") is None and pix.ler_valor("  ") is None, "vazio = livre")
ok(pix.ler_valor("R$ 1.000,00") == Decimal("1000.00") and pix.ler_valor("10000") == Decimal("10000.00"), "limites")
ok(pix.ler_valor("12.5") == Decimal("12.50") and pix.ler_valor("1") == Decimal("1.00"), "ponto e inteiro")
for ruim in ("0,99", "10000,01", "abc", "-5", "0"):
    try:
        pix.ler_valor(ruim)
        ok(False, f"aceitou {ruim}")
    except ValueError:
        ok(True, "")
ok(pix.reais(10) == "R$ 10" and pix.reais(Decimal("12.50")) == "R$ 12,50", "mostrar reais")
log.append("Pix: livre/R$ 5/R$ 10/R$ 25 iguais às referências; 12,50; CRC; limites")


def ler_qr(png_ou_pixmap, nome):
    caminho = os.path.join(SAIDA, nome)
    if isinstance(png_ou_pixmap, bytes):
        with open(caminho, "wb") as f:
            f.write(png_ou_pixmap)
    else:
        png_ou_pixmap.save(caminho, "PNG")
    txt, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(caminho))
    return txt


for v, ref in REF.items():
    ok(ler_qr(pix.qr_png(ref), f"qr-{v or 'livre'}.png") == ref, f"QR {v} não lê de volta")
log.append("QR (correção M) lido de volta = código, nos 4 valores")

# ---------------- quadro ----------------
from PySide6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
import ciranda.apoio as AP  # noqa: E402
from ciranda import config, textos  # noqa: E402
from ciranda.janela import QSS, Janela  # noqa: E402

ABRIU = []
AP._abrir_url = lambda url: ABRIU.append(url)
REDE = []


def _sem_rede(*a, **k):
    REDE.append(a)
    raise OSError("rede proibida no teste do Apoiar")


socket.socket.connect = _sem_rede
socket.create_connection = _sem_rede

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
j = Janela([])
j.resize(1280, 760)
j.move(0, 0)
j.show()


def foto(nome):
    q = j._apoio
    q.grab().save(os.path.join(SAIDA, nome), "PNG")


def rodape_tem_apoiar():
    for lab in (j.acoes_fila, j.vazio.acoes):
        h = lab.text()
        ok("acao:apoiar" in h and t_apoiar_sem_coracao() in h and "♥" in h, h)
        i_atu, i_apo = h.index("acao:atualizar"), h.index("acao:apoiar")
        ok(i_atu < i_apo, "Apoiar fica depois de Procurar atualização")


def t_apoiar_sem_coracao():
    return textos.t("apoiar").replace("♥", "").strip()


def clicar(w):
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(w.width() // 2, w.height() // 2))


def qr_atual():
    return ler_qr(j._apoio.qr.pixmap(), "qr-tela.png")


def p_abrir():
    rodape_tem_apoiar()
    ok(j._apoio is None, "o quadro não pode existir antes do clique (nunca abre sozinho)")
    j.vazio.acoes.linkActivated.emit("acao:apoiar")  # o mesmo sinal do clique no link do rodapé


def p_escolha():
    q = j._apoio
    ok(q is not None and q.isVisible() and q.pilha.currentIndex() == 0, "não abriu no passo 1")
    ok(q.l_titulo.text() == "De onde você é?", q.l_titulo.text())
    ok(q.c_br.property("provavel") is True and q.c_fora.property("provavel") is False, "PT destaca Brasil")
    ok("não muda nada no Ciranda" in q.l_opcional.text(), q.l_opcional.text())
    ok(q.c_br.isEnabled() and q.c_fora.isEnabled(), "os dois cartões clicáveis")
    foto("apoio-pt-1-escolha.png")
    # Tab fica dentro do quadro
    q.activateWindow()
    q.c_br.setFocus()
    for _ in range(12):
        QTest.keyClick(QApplication.focusWidget() or q, Qt.Key_Tab)
        fw = QApplication.focusWidget()
        ok(fw is not None and fw.window() is q, f"Tab saiu do quadro: {fw}")
    q.c_br.setFocus()
    QTest.keyClick(q.c_br, Qt.Key_Return)  # Enter no cartão escolhe


def p_pix():
    q = j._apoio
    ok(q.pilha.currentIndex() == 1 and q.l_titulo.text() == "Apoiar com Pix", "Enter no cartão Brasil")
    ok(not j.isFullScreen(), "Enter no quadro virou atalho do player (tela cheia)")
    filtro = j.fila.filtro
    q.campo.show()
    q.campo.setFocus()
    QTest.keyClick(q.campo, Qt.Key_2)
    ok(j.fila.filtro == filtro and q.campo.text() == "2", "tecla 2 no campo virou atalho do player (filtro)")
    q.campo.clear()
    q.escolher_valor(10)
    ok(config.carregar()["apoio_escolha"] == "br", "escolha salva")
    ok(q.codigo == REF[10] and qr_atual() == REF[10], "padrão R$ 10")
    ok(q.qr.accessibleName() == "QR Code Pix de R$ 10", q.qr.accessibleName())
    ok(q.qr.pixmap().width() >= 200, "QR grande")
    foto("apoio-pt-2-pix.png")
    for v in (5, 25):
        clicar(q.b_valores[v])
        ok(q.codigo == REF[v] and qr_atual() == REF[v], f"R$ {v}")
    clicar(q.b_outro)
    ok(q.campo.isVisible() and q.codigo == REF[None] and qr_atual() == REF[None], "outro valor vazio = livre")
    ok(q.qr.accessibleName() == "QR Code Pix de valor livre", q.qr.accessibleName())
    QTest.keyClicks(q.campo, "12,50")
    ok("540512.50" in q.codigo and qr_atual() == q.codigo, f"12,50: {q.codigo}")
    q.campo.clear()
    QTest.keyClicks(q.campo, "0,50")
    ok(not q.b_copiar.isEnabled() and "R$ 1" in q.l_campo.text(), "valor abaixo de R$ 1 recusado")
    q.campo.clear()
    QTest.keyClicks(q.campo, "10")
    ok(q.b_copiar.isEnabled() and q.codigo == REF[10], "10 digitado = R$ 10")
    clicar(q.b_valores[10])
    clicar(q.b_copiar)
    ok(QGuiApplication.clipboard().text() == REF[10] and q.l_copiado.text() == "Copiado!", "copiar código")
    clicar(q.b_chave)
    ok(QGuiApplication.clipboard().text() == pix.CHAVE, "copiar chave")
    ok(pix.CHAVE in q.l_chave.text() and "Andre Miller Fleck" in q.l_instr.text(), "chave e nome na tela")
    log.append("Brasil: R$ 10 padrão, R$ 5/R$ 25/livre/12,50 com QR lido de volta, 0,50 recusado, "
               "copiar código e chave")
    clicar(q.b_voltar_br)


def p_fora():
    q = j._apoio
    ok(q.pilha.currentIndex() == 0, "Voltar")
    clicar(q.c_fora)
    ok(q.pilha.currentIndex() == 2 and "US$ 1" in q.l_fora.text(), "outro país")
    foto("apoio-pt-3-fora.png")
    clicar(q.b_sponsors)
    ok(ABRIU == ["https://github.com/sponsors/DredsGG"], ABRIU)
    log.append("Outro país: abre https://github.com/sponsors/DredsGG; Voltar troca de opção")
    QTest.keyClick(q, Qt.Key_Escape)
    ok(not q.isVisible(), "Esc não fechou")


def p_reabre_lugar():
    j.apoiar()
    q = j._apoio
    ok(q.isVisible() and q.pilha.currentIndex() == 2, "não reabriu no lugar escolhido")
    clicar(q.b_x)
    ok(not q.isVisible(), "X não fechou")
    j.apoiar()
    QTest.mouseClick(j.palco, Qt.LeftButton, Qt.NoModifier, QPoint(40, 40))  # clique fora


def p_clique_fora():
    ok(not j._apoio.isVisible(), "clique fora não fechou")
    log.append("Esc, X e clique fora fecham; Tab fica dentro; Enter aciona; reabre no lugar escolhido")
    estado["idiomas"] = ["en", "es"]


estado = {}


def p_idioma():
    if not estado["idiomas"]:
        return
    lang = estado["idiomas"].pop(0)
    j.mudar_idioma(lang)
    rodape_tem_apoiar()
    q = j._apoio
    q.ir("", salvar=False)
    j.apoiar()
    q.ir("")
    ok(q.c_fora.property("provavel") is True and q.c_br.property("provavel") is False, f"{lang}: destaca outro país")
    foto(f"apoio-{lang}-1-escolha.png")
    q.ir("br")
    ok(qr_atual() == q.codigo, f"{lang}: QR")
    foto(f"apoio-{lang}-2-pix.png")
    q.ir("fora")
    foto(f"apoio-{lang}-3-fora.png")
    esperado = {"en": "One-time or monthly, from US$ 1. Card payments through GitHub, no fee for me.",
                "es": "Una vez o cada mes, desde US$ 1."}[lang]
    ok(esperado in q.l_fora.text(), q.l_fora.text())
    q.close()
    log.append(f"{lang}: textos, destaque em outro país, prints")


def p_fim():
    ok(not REDE, f"o Apoiar tentou usar a rede: {REDE}")
    log.append("nenhuma conexão de rede")
    print("\n".join(log))
    print(f"APOIO PASSOU ({n} checagens)")
    app.quit()


passos = [(1500, p_abrir), (800, p_escolha), (800, p_pix), (600, p_fora), (600, p_reabre_lugar),
          (600, p_clique_fora), (900, p_idioma), (900, p_idioma), (600, p_fim)]


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
QTimer.singleShot(60000, lambda: (print("tempo esgotado"), app.exit(1)))
sys.exit(app.exec())
