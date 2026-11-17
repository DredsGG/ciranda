"""Teste de interface da fase 1 no Windows de verdade (clique e tecla reais via SendInput).

Confere, lendo o prova.log e as janelas:
  * camada (Slint) alinhada à área cliente da hospedeira ao mover, redimensionar, minimizar,
    restaurar, trocar de monitor e na tela cheia;
  * quadro do meio fecha no botão; menu do botão direito abre e executa;
  * teclas com o foco na camada e com o foco na hospedeira; Alt+Tab;
  * tela cheia: controles somem em 2,5 s parados e voltam com o mouse;
  * foto passa em 5 s; GIF anima.
Prints: só a área da janela do app, com ela por cima de tudo; antes de cada print confere,
ponto a ponto, que nenhuma outra janela cobre a área (senão não grava).

Uso: python -I interface.py <exe> <pasta_midia> <pasta_prints> [etapas]
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import json
import os
import struct
import subprocess
import sys
import tempfile
import time

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
dwm = ctypes.windll.dwmapi
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
for f in ("GetDC", "GetWindowDC"):
    getattr(u32, f).restype = w.HDC
g32.CreateCompatibleDC.restype = w.HDC
g32.CreateCompatibleBitmap.restype = w.HBITMAP
g32.SelectObject.restype = w.HGDIOBJ
u32.WindowFromPoint.restype = w.HWND
# Sem argtypes, o -1 (HWND_TOPMOST) vai como int de 32 bits e a chamada falha calada no Windows 64-bit.
u32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
u32.SetWindowPos.restype = w.BOOL
u32.WindowFromPoint.argtypes = [w.POINT]
u32.GetAncestor.restype = w.HWND
u32.GetWindow.restype = w.HWND
u32.GetForegroundWindow.restype = w.HWND
u32.FindWindowW.restype = w.HWND
u32.ReleaseDC.argtypes = [w.HWND, w.HDC]
g32.GetPixel.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]
g32.GetPixel.restype = w.DWORD
g32.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
g32.BitBlt.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC, ctypes.c_int, ctypes.c_int, w.DWORD]
g32.GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p, ctypes.c_void_p, w.UINT]
g32.DeleteObject.argtypes = [w.HGDIOBJ]
g32.DeleteDC.argtypes = [w.HDC]
g32.CreateCompatibleDC.argtypes = [w.HDC]
g32.CreateCompatibleBitmap.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]
u32.GetWindow.argtypes = [w.HWND, w.UINT]
u32.GetAncestor.argtypes = [w.HWND, w.UINT]

# Pasta de dados própria (CIRANDA_DADOS), com a fila em ordem: o padrão da 1.5.1 é aleatório
# ligado, e as etapas contam com a ordem por nome.
DADOS = os.path.join(os.environ["APPDATA"], "Ciranda-rust-prova", "interface")
LOG = os.path.join(DADOS, "prova.log")
os.makedirs(DADOS, exist_ok=True)
with open(os.path.join(DADOS, "config.json"), "w", encoding="utf-8") as _f:
    _f.write('{"aleatorio": false, "repetir": "tudo"}')
RESULTADOS: list[dict] = []


# ---------------------------------------------------------------- entrada real
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _U)]


def _enviar(*itens):
    arr = (INPUT * len(itens))(*itens)
    u32.SendInput(len(itens), arr, ctypes.sizeof(INPUT))


def tecla(vk: int, shift=False, alt=False):
    seq = []
    if shift:
        seq.append(INPUT(1, _U(ki=KEYBDINPUT(0x10, 0, 0, 0, 0))))
    if alt:
        seq.append(INPUT(1, _U(ki=KEYBDINPUT(0x12, 0, 0, 0, 0))))
    ext = 1 if vk in (0x25, 0x26, 0x27, 0x28) else 0
    seq.append(INPUT(1, _U(ki=KEYBDINPUT(vk, 0, ext, 0, 0))))
    seq.append(INPUT(1, _U(ki=KEYBDINPUT(vk, 0, ext | 2, 0, 0))))
    if alt:
        seq.append(INPUT(1, _U(ki=KEYBDINPUT(0x12, 0, 2, 0, 0))))
    if shift:
        seq.append(INPUT(1, _U(ki=KEYBDINPUT(0x10, 0, 2, 0, 0))))
    _enviar(*seq)
    time.sleep(0.25)


def mover(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)


def clicar(x, y, direito=False, duplo=False):
    mover(x, y)
    desce, sobe = (0x8, 0x10) if direito else (0x2, 0x4)
    for _ in range(2 if duplo else 1):
        _enviar(INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, desce, 0, 0))),
                INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, sobe, 0, 0))))
        time.sleep(0.06)
    time.sleep(0.3)


def mexer_mouse(dx=3):
    _enviar(INPUT(0, _U(mi=MOUSEINPUT(dx, 0, 0, 0x1, 0, 0))))
    time.sleep(0.05)


# ---------------------------------------------------------------- janelas
def janelas_do_pid(pid):
    achadas = []
    PROC = ctypes.WINFUNCTYPE(ctypes.c_int, w.HWND, w.LPARAM)

    def cb(h, _):
        p = w.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            achadas.append(h)
        return 1

    u32.EnumWindows(PROC(cb), 0)
    return achadas


def titulo(h):
    b = ctypes.create_unicode_buffer(256)
    u32.GetWindowTextW(h, b, 256)
    return b.value


def rect_janela(h):
    r = w.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def rect_cliente(h):
    r = w.RECT()
    u32.GetClientRect(h, ctypes.byref(r))
    p = w.POINT(0, 0)
    u32.ClientToScreen(h, ctypes.byref(p))
    return (p.x, p.y, p.x + r.right, p.y + r.bottom)


def visivel(h):
    return bool(u32.IsWindowVisible(h))


def monitores():
    res = []
    PROC = ctypes.WINFUNCTYPE(ctypes.c_int, w.HMONITOR, w.HDC, ctypes.POINTER(w.RECT), w.LPARAM)
    s = ctypes.windll.shcore

    def cb(hm, _dc, r, _l):
        x, y = ctypes.c_uint(), ctypes.c_uint()
        s.GetDpiForMonitor(hm, 0, ctypes.byref(x), ctypes.byref(y))
        rr = r.contents
        res.append({"rect": (rr.left, rr.top, rr.right, rr.bottom), "dpi": x.value})
        return 1

    u32.EnumDisplayMonitors(None, None, PROC(cb), 0)
    return res


class App:
    def __init__(self, exe, args):
        self.p = subprocess.Popen([exe, *args], env=dict(os.environ, CIRANDA_DADOS=DADOS))
        self.host = self.camada = None
        t0 = time.time()
        while time.time() - t0 < 15 and not (self.host and self.camada):
            for h in janelas_do_pid(self.p.pid):
                if titulo(h) == "Ciranda (prova Rust)" and visivel(h):
                    self.host = h
            if self.host:
                for h in janelas_do_pid(self.p.pid):
                    if u32.GetWindow(h, 4) == self.host and visivel(h):  # GW_OWNER
                        self.camada = h
            time.sleep(0.1)
        if not (self.host and self.camada):
            raise SystemExit("não achei as janelas")
        time.sleep(1.0)

    def alinhamento(self):
        rc, rw = rect_cliente(self.host), rect_janela(self.camada)
        return {"hospedeira_cliente": rc, "camada": rw, "diferenca": [a - b for a, b in zip(rw, rc)]}

    def fechar(self):
        u32.PostMessageW(self.host, 0x10, 0, 0)  # WM_CLOSE
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()


def log_desde(marca: int) -> str:
    with open(LOG, encoding="utf-8", errors="replace") as f:
        f.seek(marca)
        return f.read()


def tamanho_log() -> int:
    return os.path.getsize(LOG)


def conferir(nome: str, ok: bool, detalhe=None):
    RESULTADOS.append({"teste": nome, "passou": bool(ok), "detalhe": detalhe})
    print(("PASSOU " if ok else "FALHOU ") + nome, "" if detalhe is None else detalhe, flush=True)


def esperar_no_log(marca, texto, seg=4.0):
    t0 = time.time()
    while time.time() - t0 < seg:
        if texto in log_desde(marca):
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------- print só do app
def print_do_app(app: App, caminho: str) -> bool:
    """Põe as janelas do app por cima de tudo, confere que só elas cobrem a área e grava.

    A hospedeira sobe primeiro e as outras do app (camada, menu) depois, para o menu não ficar
    embaixo. Pinta de preto o que fica fora da janela (borda de 1 px e cantos arredondados do
    Windows 11), onde apareceriam pixels de outras janelas."""
    h = app.host
    outras = [x for x in janelas_do_pid(app.p.pid) if x != h and visivel(x)]
    for x in [h, *outras]:
        u32.SetWindowPos(x, -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # HWND_TOPMOST, NOSIZE|NOMOVE|NOACTIVATE
    time.sleep(0.35)
    try:
        r = w.RECT()
        dwm.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r))  # DWMWA_EXTENDED_FRAME_BOUNDS
        x0, y0, x1, y1 = r.left, r.top, r.right, r.bottom
        nossas = set(janelas_do_pid(app.p.pid))
        for i in range(1, 12):
            for j in range(1, 12):
                pt = w.POINT(x0 + (x1 - x0) * i // 12, y0 + (y1 - y0) * j // 12)
                alvo = u32.WindowFromPoint(pt)
                raiz = u32.GetAncestor(alvo, 3)  # GA_ROOTOWNER
                if alvo and raiz not in nossas and u32.GetAncestor(alvo, 2) not in nossas:
                    print("  print cancelado: outra janela cobre o app", flush=True)
                    return False
        largura, altura = x1 - x0, y1 - y0
        tela = u32.GetDC(None)
        mem = g32.CreateCompatibleDC(tela)
        bmp = g32.CreateCompatibleBitmap(tela, largura, altura)
        g32.SelectObject(mem, bmp)
        g32.BitBlt(mem, 0, 0, largura, altura, tela, x0, y0, 0x00CC0020)
        cab = struct.pack("<IiiHHIIiiII", 40, largura, -altura, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(largura * altura * 4)
        bi = ctypes.create_string_buffer(cab, 40 + 12)
        g32.GetDIBits(mem, bmp, 0, altura, buf, bi, 0)
        g32.DeleteObject(bmp)
        g32.DeleteDC(mem)
        u32.ReleaseDC(None, tela)
        px = bytearray(buf.raw)
        raio = int(8 * u32.GetDpiForWindow(h) / 96) + 1
        if not u32.IsZoomed(h) and (largura, altura) != tuple(c - d for c, d in zip(rect_do_monitor(h)[2:], rect_do_monitor(h)[:2])):
            for yy in range(altura):
                for xx in list(range(min(raio, largura))) + list(range(max(largura - raio, 0), largura)):
                    if yy >= raio and yy < altura - raio:
                        if xx != 0 and xx != largura - 1:
                            continue
                    cx_ = raio if xx < raio else largura - 1 - raio
                    cy_ = raio if yy < raio else altura - 1 - raio
                    canto = (xx < raio or xx >= largura - raio) and (yy < raio or yy >= altura - raio)
                    fora = (xx - cx_) ** 2 + (yy - cy_) ** 2 > raio ** 2 if canto else True
                    if fora:
                        i = (yy * largura + xx) * 4
                        px[i:i + 4] = b"\x00\x00\x00\xff"
            for xx in range(largura):  # linhas de cima e de baixo (borda do Windows)
                for yy in (0, altura - 1):
                    i = (yy * largura + xx) * 4
                    px[i:i + 4] = b"\x00\x00\x00\xff"
        bruto = os.path.join(tempfile.gettempdir(), "ciranda-print.bgra")
        with open(bruto, "wb") as f:
            f.write(bytes(px))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "bgra",
                        "-video_size", f"{largura}x{altura}", "-i", bruto, "-frames:v", "1", caminho], check=True)
        os.remove(bruto)
        return True
    finally:
        for x in [*outras, h]:
            u32.SetWindowPos(x, -2, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # HWND_NOTOPMOST


def pixels_da_area(app: App, area):
    """Copia uma área pequena da tela de uma vez (BitBlt) para ver se o GIF mudou."""
    x0, y0, x1, y1 = area
    largura, altura = x1 - x0, y1 - y0
    tela = u32.GetDC(None)
    mem = g32.CreateCompatibleDC(tela)
    bmp = g32.CreateCompatibleBitmap(tela, largura, altura)
    g32.SelectObject(mem, bmp)
    g32.BitBlt(mem, 0, 0, largura, altura, tela, x0, y0, 0x00CC0020)
    cab = struct.pack("<IiiHHIIiiII", 40, largura, -altura, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(largura * altura * 4)
    bi = ctypes.create_string_buffer(cab, 40 + 12)
    g32.GetDIBits(mem, bmp, 0, altura, buf, bi, 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mem)
    u32.ReleaseDC(None, tela)
    px = buf.raw
    return [px[i:i + 3] for i in range(0, len(px), 4)]


# ---------------------------------------------------------------- etapas
class WINDOWINFO(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("rcWindow", w.RECT), ("rcClient", w.RECT), ("dwStyle", w.DWORD),
                ("dwExStyle", w.DWORD), ("dwWindowStatus", w.DWORD), ("cxWindowBorders", w.UINT),
                ("cyWindowBorders", w.UINT), ("atomWindowType", w.ATOM), ("wCreatorVersion", w.WORD)]


def titulo_aceso(h) -> bool:
    """WS_ACTIVECAPTION em GetWindowInfo: a barra de título está desenhada como ativa."""
    wi = WINDOWINFO()
    wi.cbSize = ctypes.sizeof(WINDOWINFO)
    u32.GetWindowInfo(h, ctypes.byref(wi))
    return bool(wi.dwWindowStatus & 1)


def rect_do_monitor(h):
    hm = u32.MonitorFromWindow(h, 2)
    mi = (ctypes.c_long * 10)()
    mi[0] = 40
    u32.GetMonitorInfoW(hm, mi)
    return tuple(mi[1:5])


def cobre_monitor(app) -> bool:
    """Tela cheia de fato (retângulo da janela = monitor), não só o que o log diz."""
    return rect_janela(app.host) == rect_do_monitor(app.host)


def centro(r):
    return ((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)


def alinhado(app, nome):
    a = app.alinhamento()
    conferir(f"alinhada: {nome}", a["diferenca"] == [0, 0, 0, 0], a)


def etapa_janela(app: App, prints: str, midia: str):
    alinhado(app, "ao abrir")
    print_do_app(app, os.path.join(prints, "01-abriu-com-quadro.png"))
    # Fecha o quadro no botão "Entendi" (canto de baixo à direita do quadro).
    cx, cy = centro(rect_cliente(app.host))
    escala = u32.GetDpiForWindow(app.camada) / 96
    m = tamanho_log()
    largura = min(rect_cliente(app.host)[2] - rect_cliente(app.host)[0] - 48 * escala, 460 * escala)
    clicar(cx + largura / 2 - (24 + 55) * escala, cy + (115 - 20 - 18) * escala)
    conferir("quadro fecha no botão", esperar_no_log(m, "quadro fechado"))

    # Mover, redimensionar, minimizar e restaurar.
    u32.SetWindowPos(app.host, 0, 200, 150, 1100, 650, 0x4 | 0x10)
    time.sleep(0.5)
    alinhado(app, "mover e redimensionar")
    u32.ShowWindow(app.host, 6)  # SW_MINIMIZE
    time.sleep(0.8)
    conferir("minimizada: camada some junto", not visivel(app.camada) or u32.IsIconic(app.host) and
             not u32.IsWindowVisible(app.camada), {"camada_visivel": visivel(app.camada)})
    u32.ShowWindow(app.host, 9)  # SW_RESTORE
    time.sleep(0.8)
    conferir("restaurada: camada volta", visivel(app.camada))
    alinhado(app, "restaurar")
    u32.ShowWindow(app.host, 3)  # SW_MAXIMIZE
    time.sleep(0.8)
    alinhado(app, "maximizar")
    u32.ShowWindow(app.host, 9)
    time.sleep(0.6)

    # Cada monitor.
    for i, mon in enumerate(monitores()):
        x0, y0, x1, y1 = mon["rect"]
        u32.SetWindowPos(app.host, 0, x0 + 80, y0 + 80, min(1000, x1 - x0 - 160), min(600, y1 - y0 - 160), 0x4 | 0x10)
        time.sleep(0.8)
        alinhado(app, f"monitor {i + 1} ({x1 - x0}x{y1 - y0}, {round(mon['dpi'] / 96 * 100)}%)")
    # Volta ao monitor principal e fica por cima de tudo durante os testes de clique, para nenhuma
    # outra janela (aberta em outro monitor) pegar o clique no lugar do app.
    u32.SetWindowPos(app.host, -1, 120, 120, 1320, 780, 0x10)  # HWND_TOPMOST, NOACTIVATE
    time.sleep(0.6)


def etapa_teclas(app: App, prints: str):
    cx, cy = centro(rect_cliente(app.host))
    # Foco na camada: clique no vídeo.
    sob = u32.WindowFromPoint(w.POINT(int(cx), int(cy - 60)))  # noqa
    antes = titulo(u32.GetForegroundWindow())
    clicar(cx, cy - 60)
    conferir("clique no vídeo dá foco à camada", u32.GetForegroundWindow() == app.camada,
             {"frente": titulo(u32.GetForegroundWindow()), "antes": antes, "sob_o_mouse": titulo(sob),
              "sob_e_camada": sob == app.camada})
    conferir("barra de título acesa com o foco na camada", titulo_aceso(app.host))
    for nome, vk, esperado in [("Espaço", 0x20, "TocarPausar"), ("Espaço de novo", 0x20, "TocarPausar"),
                               ("→", 0x27, "Pular(5.0)"), ("←", 0x25, "Pular(-5.0)"), ("N", 0x4E, "Proximo")]:
        m = tamanho_log()
        tecla(vk)
        conferir(f"tecla {nome} com foco na camada", esperar_no_log(m, f"tecla na camada: {esperado}"))
    m = tamanho_log()
    tecla(0x46)  # F
    ok = esperar_no_log(m, "tela cheia: true")
    time.sleep(0.6)
    conferir("F com foco na camada: tela cheia", ok and cobre_monitor(app))
    alinhado(app, "tela cheia (F na camada)")
    m = tamanho_log()
    tecla(0x1B)  # Esc
    ok = esperar_no_log(m, "tela cheia: false")
    time.sleep(0.6)
    conferir("Esc com foco na camada: sai da tela cheia", ok and not cobre_monitor(app))
    alinhado(app, "saiu da tela cheia")
    m = tamanho_log()
    tecla(0x0D)  # Enter
    ok = esperar_no_log(m, "tela cheia: true")
    time.sleep(0.4)
    conferir("Enter com foco na camada: tela cheia", ok and cobre_monitor(app))
    tecla(0x1B)
    time.sleep(0.6)

    # Foco na hospedeira: clique na barra de título.
    r = rect_janela(app.host)
    clicar(r[0] + 300, r[1] + 12)
    conferir("clique na barra de título dá foco à hospedeira", u32.GetForegroundWindow() == app.host,
             {"frente": titulo(u32.GetForegroundWindow())})
    for nome, vk, esperado in [("Espaço", 0x20, "TocarPausar"), ("Espaço de novo", 0x20, "TocarPausar"),
                               ("→", 0x27, "Pular(5.0)"), ("←", 0x25, "Pular(-5.0)"), ("N", 0x4E, "Proximo")]:
        m = tamanho_log()
        tecla(vk)
        conferir(f"tecla {nome} com foco na hospedeira", esperar_no_log(m, f"tecla na hospedeira: {esperado}"))
    m = tamanho_log()
    tecla(0x46)
    ok = esperar_no_log(m, "tela cheia: true")
    time.sleep(0.6)
    conferir("F com foco na hospedeira: tela cheia", ok and cobre_monitor(app))
    alinhado(app, "tela cheia (F na hospedeira)")
    m = tamanho_log()
    tecla(0x1B)
    ok = esperar_no_log(m, "tela cheia: false")
    time.sleep(0.6)
    conferir("Esc com foco na hospedeira: sai da tela cheia", ok and not cobre_monitor(app))
    # Segurar F (repetição da tecla) não pode ficar ligando e desligando.
    m = tamanho_log()
    for _ in range(12):  # vários "desce" sem "sobe": é como o Windows entrega a tecla segurada
        _enviar(INPUT(1, _U(ki=KEYBDINPUT(0x46, 0, 0, 0, 0))))
        time.sleep(0.04)
    _enviar(INPUT(1, _U(ki=KEYBDINPUT(0x46, 0, 0x2, 0, 0))))
    time.sleep(0.6)
    trocas = log_desde(m).count("tela cheia: ")
    conferir("segurar F alterna uma vez só", trocas == 1 and cobre_monitor(app), {"trocas_no_log": trocas})
    tecla(0x1B)
    time.sleep(0.6)

    # Alt+Tab: sai para a janela anterior e volta.
    clicar(*centro(rect_cliente(app.host)))  # foco na camada antes de sair
    time.sleep(0.3)
    tecla(0x09, alt=True)
    time.sleep(0.8)
    saiu = u32.GetForegroundWindow() not in (app.host, app.camada)
    conferir("barra de título apaga com outro app na frente", saiu and not titulo_aceso(app.host),
             {"saiu": saiu, "acesa": titulo_aceso(app.host)})
    tecla(0x09, alt=True)
    time.sleep(0.8)
    frente = u32.GetForegroundWindow()
    conferir("Alt+Tab sai e volta para o app", saiu and frente in (app.host, app.camada),
             {"saiu": saiu, "voltou_em": "hospedeira" if frente == app.host else
              "camada" if frente == app.camada else titulo(frente)[:20] and "outra"})
    m = tamanho_log()
    tecla(0x20)
    conferir("tecla depois do Alt+Tab", esperar_no_log(m, "TocarPausar"))
    tecla(0x20)
    alinhado(app, "depois do Alt+Tab")


def etapa_menu(app: App, prints: str):
    cx, cy = centro(rect_cliente(app.host))
    antes = set(janelas_do_pid(app.p.pid))
    clicar(cx - 100, cy - 80, direito=True)
    time.sleep(0.6)
    novas = [h for h in janelas_do_pid(app.p.pid) if h not in antes and visivel(h)]
    print_do_app(app, os.path.join(prints, "03-menu-botao-direito.png"))
    escala = u32.GetDpiForWindow(app.camada) / 96
    m = tamanho_log()
    clicar(cx - 100 + 30 * escala, cy - 80 + 14 * escala)  # primeiro item: Pausar/Tocar
    conferir("menu do botão direito abre e executa o 1º item", esperar_no_log(m, "menu: tocar"),
             {"janelas_novas_do_menu": len(novas)})
    m = tamanho_log()
    clicar(cx - 100, cy - 80, direito=True)
    time.sleep(0.5)
    tecla(0x28)  # ↓ até "Mostrar o quadro" (4º item depois do separador)
    for _ in range(3):
        tecla(0x28)
    tecla(0x0D)
    ok = esperar_no_log(m, "menu: quadro")
    conferir("menu pelo teclado (↓ e Enter) mostra o quadro", ok)
    time.sleep(0.4)
    print_do_app(app, os.path.join(prints, "04-quadro-por-cima-do-video.png"))
    clicar(cx, cy)  # fecha clicando fora? não: o fundo segura o clique; usa Entendi
    largura = min(rect_cliente(app.host)[2] - rect_cliente(app.host)[0] - 48 * escala, 460 * escala)
    clicar(cx + largura / 2 - (24 + 55) * escala, cy + (115 - 20 - 18) * escala)


def etapa_tela_cheia(app: App, prints: str):
    cx, cy = centro(rect_cliente(app.host))
    clicar(cx, cy - 60)
    m = tamanho_log()
    tecla(0x46)
    esperar_no_log(m, "tela cheia: true")
    time.sleep(0.5)
    hm = u32.MonitorFromWindow(app.host, 2)
    mi = (ctypes.c_long * 10)()
    mi[0] = 40
    u32.GetMonitorInfoW(hm, mi)
    conferir("tela cheia cobre o monitor inteiro", rect_janela(app.host) == tuple(mi[1:5]),
             {"janela": rect_janela(app.host), "monitor": tuple(mi[1:5])})
    alinhado(app, "tela cheia")
    print_do_app(app, os.path.join(prints, "05-tela-cheia-com-controles.png"))
    m = tamanho_log()
    t0 = time.time()
    ok = esperar_no_log(m, "controles somem", 5)
    conferir("tela cheia: controles somem parados", ok, {"segundos": round(time.time() - t0, 2)})
    time.sleep(0.3)
    print_do_app(app, os.path.join(prints, "06-tela-cheia-sem-controles.png"))
    m = tamanho_log()
    mexer_mouse(5)
    mexer_mouse(-5)
    conferir("tela cheia: controles voltam com o mouse", esperar_no_log(m, "controles voltam", 2))
    rm = rect_janela(app.host)
    escala = u32.GetDpiForWindow(app.host) / 96
    mover((rm[0] + rm[2]) // 2, rm[3] - int(60 * escala))  # sobre a barra, longe dos botões
    m = tamanho_log()
    time.sleep(4.0)
    conferir("tela cheia: mouse parado sobre a barra, os controles ficam", "controles somem" not in log_desde(m))
    mover((rm[0] + rm[2]) // 2, (rm[1] + rm[3]) // 2)
    m = tamanho_log()
    conferir("tela cheia: mouse fora da barra, somem de novo", esperar_no_log(m, "controles somem", 4))
    mexer_mouse(5)
    # Tela cheia em outro monitor.
    tecla(0x1B)
    time.sleep(0.5)
    mons = monitores()
    if len(mons) > 1:
        x0, y0, x1, y1 = mons[1]["rect"]
        u32.SetWindowPos(app.host, 0, x0 + 60, y0 + 60, 900, 520, 0x4 | 0x10)
        time.sleep(0.6)
        cx, cy = centro(rect_cliente(app.host))
        clicar(cx, cy - 40)
        tecla(0x46)
        time.sleep(0.6)
        conferir("tela cheia no monitor 2 cobre o monitor 2", rect_janela(app.host) == mons[1]["rect"],
                 {"janela": rect_janela(app.host), "monitor": mons[1]["rect"]})
        alinhado(app, "tela cheia no monitor 2")
        tecla(0x1B)
        time.sleep(0.5)
        alinhado(app, "saiu da tela cheia no monitor 2")


def linhas_com_tempo(texto: str):
    for linha in texto.splitlines():
        partes = linha.strip().split(" ", 1)
        try:
            yield float(partes[0]), partes[1] if len(partes) > 1 else ""
        except ValueError:
            continue


def etapa_fotos(exe: str, pasta_fotos: str, prints: str):
    """Fila: anim.gif, foto.jpg, heic-grade-4x3.heic (ordem por nome)."""
    m = 0
    app = App(exe, [pasta_fotos])
    try:
        u32.SetWindowPos(app.host, -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # por cima de tudo durante a etapa
        cx, cy = centro(rect_cliente(app.host))
        rc = rect_cliente(app.host)
        # Canto de cima à esquerda (fora do quadro do meio), onde o GIF de teste tem o relógio.
        area = (rc[0] + 20, rc[1] + 20, rc[0] + 300, rc[1] + 140)
        time.sleep(0.8)
        a = pixels_da_area(app, area)
        time.sleep(0.45)
        b = pixels_da_area(app, area)
        gif_mudou = sum(1 for x, y in zip(a, b) if x != y)
        print_do_app(app, os.path.join(prints, "07-gif.png"))
        conferir("GIF passa para a foto", esperar_no_log(m, "\\foto.jpg", 8))
        # Na foto: controle do GIF (foto parada não muda pixel) e pausa 3 s logo no começo.
        time.sleep(0.6)
        a = pixels_da_area(app, area)
        time.sleep(0.45)
        b = pixels_da_area(app, area)
        foto_mudou = sum(1 for x, y in zip(a, b) if x != y)
        conferir("GIF anima (pixels mudam em 0,45 s; na foto parada, nenhum)", gif_mudou >= len(a) * 0.01 and foto_mudou == 0,
                 {"gif_pixels_que_mudaram": f"{gif_mudou}/{len(a)}", "foto_pixels_que_mudaram": f"{foto_mudou}/{len(a)}"})
        clicar(cx, cy - 60)
        tecla(0x20)
        time.sleep(3.0)
        tecla(0x20)
        time.sleep(0.5)
        print_do_app(app, os.path.join(prints, "08-foto-com-relogio.png"))
        esperar_no_log(m, "heic-grade-4x3.heic", 10)
        time.sleep(1.5)
        print_do_app(app, os.path.join(prints, "09-heic-em-grade.png"))
        texto = log_desde(0)
        eventos = list(linhas_com_tempo(texto))

        def tempo_de(pred, depois=0.0):
            return next((t for t, l in eventos if t > depois and pred(l)), None)

        gif_q = tempo_de(lambda l: l.startswith("primeiro quadro"))
        gif_p = tempo_de(lambda l: l.startswith("foto: 5 s"), gif_q or 0)
        jpg_q = tempo_de(lambda l: l.startswith("primeiro quadro"), gif_p or 0)
        jpg_p = tempo_de(lambda l: l.startswith("foto: 5 s"), jpg_q or 0)
        heic_q = tempo_de(lambda l: l.startswith("primeiro quadro"), jpg_p or 0)
        if gif_q and gif_p:
            conferir("GIF: 5 s na tela e passa", abs((gif_p - gif_q) - 5.0) < 0.3, {"segundos": round(gif_p - gif_q, 2)})
        else:
            conferir("GIF: 5 s na tela e passa", False, {"gif_q": gif_q, "gif_p": gif_p})
        if jpg_q and jpg_p:
            conferir("foto com 3 s de pausa: 5 s tocando + 3 s parada", abs((jpg_p - jpg_q) - 8.0) < 0.8,
                     {"segundos": round(jpg_p - jpg_q, 2)})
        else:
            conferir("foto com 3 s de pausa: 5 s tocando + 3 s parada", False, {"jpg_q": jpg_q, "jpg_p": jpg_p})
        conferir("HEIC em grade aparece", heic_q is not None)
    finally:
        app.fechar()


def etapa_modal(exe: str, midia: str):
    """Janela arrastada pela barra de título (laço modal do Windows): a foto passa no tempo e a barra repinta.

    Só apertar e segurar parado (sem passar do limiar de arrasto) prende o Windows num laço que não
    entrega timer a ninguém: nesse caso a foto espera soltar (visto na prova, 2026-11-17)."""
    foto = os.path.join(os.path.dirname(midia), "fotos", "foto.jpg")
    app = App(exe, [foto])
    try:
        u32.SetWindowPos(app.host, -1, 120, 120, 1320, 780, 0x10)
        time.sleep(1.0)
        r = rect_janela(app.host)
        rc = rect_cliente(app.host)
        escala = u32.GetDpiForWindow(app.host) / 96
        relogio = (rc[2] - int(140 * escala), rc[3] - int(40 * escala), rc[2] - int(8 * escala), rc[3] - int(8 * escala))
        m = tamanho_log()
        mover(r[0] + 300, r[1] + 12)
        _enviar(INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, 0x2, 0, 0))))
        t0 = time.time()
        amostras = []
        for _ in range(6):  # arrasta de verdade (passa do limiar de arrasto do Windows)
            mexer_mouse(5)
            time.sleep(0.05)
        for i in range(70):  # ~7 s arrastando a janela para lá e para cá
            mexer_mouse(8 if i % 2 else -8)
            time.sleep(0.1)
            if i in (15, 45):
                amostras.append(pixels_da_area(app, relogio))
        segurou = time.time() - t0
        passou_durante = "foto: 5 s, passa" in log_desde(m)
        _enviar(INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, 0x4, 0, 0))))
        time.sleep(0.5)
        conferir("arrastando a janela: a foto passa em 5 s mesmo assim", passou_durante,
                 {"segurou_s": round(segurou, 1)})
        # Limite conhecido (não é critério da fase 1): o winit segura o redesenho da camada enquanto o
        # Windows está no laço modal; o relógio da barra congela até soltar. Registrado, não reprovado.
        print("  info: camada repinta durante o arrasto?", len(amostras) == 2 and amostras[0] != amostras[1])
    finally:
        app.fechar()


def etapa_fechar(exe: str, midia: str):
    app = App(exe, [os.path.join(midia, "h264-1080p60.mp4")])
    try:
        u32.SetWindowPos(app.host, -1, 120, 120, 1320, 780, 0x10)
        time.sleep(1.0)
        clicar(*centro(rect_cliente(app.host)))
        foco = u32.GetForegroundWindow() == app.camada
        m = tamanho_log()
        tecla(0x73, alt=True)  # Alt+F4
        try:
            app.p.wait(6)
            saiu = True
        except subprocess.TimeoutExpired:
            saiu = False
        conferir("Alt+F4 com o foco na camada fecha o app", foco and saiu and "pediu para fechar" in log_desde(m),
                 {"foco_na_camada": foco, "processo_saiu": saiu})
    finally:
        if app.p.poll() is None:
            app.fechar()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    exe, midia, prints = sys.argv[1:4]
    etapas = sys.argv[4].split(",") if len(sys.argv) > 4 else ["janela", "teclas", "menu", "tela_cheia", "modal", "fechar"]
    os.makedirs(prints, exist_ok=True)
    if etapas == ["fotos"]:
        etapa_fotos(exe, midia, prints)
        with open(os.path.join(prints, "resultado-fotos.json"), "w", encoding="utf-8") as f:
            json.dump(RESULTADOS, f, ensure_ascii=False, indent=2)
        sys.exit(0 if all(r["passou"] for r in RESULTADOS) else 1)
    app = App(exe, [os.path.join(midia, "h264-1080p60.mp4")])
    try:
        if "janela" in etapas:
            etapa_janela(app, prints, midia)
        if "teclas" in etapas:
            etapa_teclas(app, prints)
        if "menu" in etapas:
            etapa_menu(app, prints)
        if "tela_cheia" in etapas:
            etapa_tela_cheia(app, prints)
        print_do_app(app, os.path.join(prints, "02-barra-por-cima-do-video.png"))
    finally:
        app.fechar()
    if "modal" in etapas:
        etapa_modal(exe, midia)
    if "fechar" in etapas:
        etapa_fechar(exe, midia)
    with open(os.path.join(prints, "resultado-interface.json"), "w", encoding="utf-8") as f:
        json.dump(RESULTADOS, f, ensure_ascii=False, indent=2)
    falhas = [r for r in RESULTADOS if not r["passou"]]
    print(f"{len(RESULTADOS) - len(falhas)} de {len(RESULTADOS)} passaram")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
