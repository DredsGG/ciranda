"""Teste ponta a ponta do app em DREDS_TESTE=1 (REGRA 13): nenhuma janela, nenhum som, nenhum
foco roubado, sem mexer em mouse nem teclado. As teclas vão por PostMessage para a hospedeira
oculta. Um vigia olha a cada 100 ms as janelas visíveis do processo e a janela da frente.

    python -I rust/medir/teste_invisivel.py <ciranda-prova.exe> <pasta-midia-teste>
Os dados de cada caso ficam em %APPDATA%\\Ciranda-rust-prova\\teste-invisivel\\<caso>.
"""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8")
u32 = ctypes.WinDLL("user32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
u32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u32.GetWindowThreadProcessId.restype = wintypes.DWORD
u32.IsWindowVisible.argtypes = [wintypes.HWND]
u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.GetLayeredWindowAttributes.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80000, 0x20
k32 = ctypes.WinDLL("kernel32")
WINEVENTPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG,
                                  wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
u32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
                                wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
u32.SetWinEventHook.restype = wintypes.HANDLE
u32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
u32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
u32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_SHOW, WINEVENT_OUTOFCONTEXT, WM_QUIT = 0x0003, 0x8002, 0x0000, 0x0012
u32.GetForegroundWindow.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u32.PostMessageW.restype = wintypes.BOOL
WM_KEYDOWN, WM_KEYUP, WM_CLOSE = 0x100, 0x101, 0x10

EXE, MIDIA = sys.argv[1], sys.argv[2]
BASE = os.path.join(os.environ["APPDATA"], "Ciranda-rust-prova", "teste-invisivel")
resultados = []


def pid_de(h):
    p = wintypes.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def janelas_do_pid(pid):
    achadas = []

    def cb(h, _):
        if pid_de(h) == pid:
            nome = ctypes.create_unicode_buffer(128)
            u32.GetClassNameW(h, nome, 128)
            achadas.append((h, nome.value, bool(u32.IsWindowVisible(h))))
        return True

    u32.EnumWindows(WNDENUMPROC(cb), 0)
    return achadas


def classe_de(h):
    nome = ctypes.create_unicode_buffer(128)
    u32.GetClassNameW(h, nome, 128)
    return nome.value


def auxiliar_do_winit(h, classe):
    """A "Winit Thread Event Target": o winit a cria 16x16, em camadas e transparente, sem conteúdo
    de camada, e a marca WS_VISIBLE só para receber WM_PAINT. O DWM não a compõe: não aparece.
    Só ela é isenta, e só com exatamente esse feitio."""
    if classe != "Winit Thread Event Target":
        return False
    r = wintypes.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    ex = u32.GetWindowLongPtrW(h, -20)  # GWL_EXSTYLE
    feitio = WS_EX_LAYERED | WS_EX_TRANSPARENT
    return (r.right - r.left) * (r.bottom - r.top) <= 16 * 16 and ex & feitio == feitio and \
        not u32.GetLayeredWindowAttributes(h, None, None, None)


class Vigia(threading.Thread):
    """Anota toda janela visível do processo e toda vez que ele fica na frente, de dois jeitos:
    pelos eventos do Windows (EVENT_OBJECT_SHOW e EVENT_SYSTEM_FOREGROUND, que pegam até um piscar)
    e olhando a cada 100 ms."""

    def __init__(self, pid):
        super().__init__(daemon=True)
        self.pid, self.parar, self.visiveis, self.frente, self.amostras = pid, False, set(), 0, 0
        self.isentas, self.eventos = set(), 0
        self.ganchos = Ganchos(self)
        self.ganchos.start()

    def anotar(self, h, por_evento=False):
        if not u32.IsWindowVisible(h):
            return
        classe = classe_de(h)
        (self.isentas if auxiliar_do_winit(h, classe) else self.visiveis).add(classe)
        self.eventos += por_evento

    def run(self):
        while not self.parar:
            for h, _classe, vis in janelas_do_pid(self.pid):
                if vis:
                    self.anotar(h)
            if pid_de(u32.GetForegroundWindow()) == self.pid:
                self.frente += 1
            self.amostras += 1
            time.sleep(0.1)
        self.ganchos.encerrar()


class Ganchos(threading.Thread):
    """SetWinEventHook fora de contexto: o Windows chama de volta nesta thread (que precisa de um
    laço de mensagens) a cada janela que aparece e a cada troca da janela da frente."""

    def __init__(self, vigia):
        super().__init__(daemon=True)
        self.vigia, self.tid, self.pronto = vigia, None, threading.Event()

    def run(self):
        self.tid = k32.GetCurrentThreadId()
        v = self.vigia

        def cb(_gancho, evento, h, id_obj, id_filho, _thread, _tempo):
            if not h or id_obj != 0 or id_filho != 0 or pid_de(h) != v.pid:  # 0 = OBJID_WINDOW, CHILDID_SELF
                return
            if evento == EVENT_OBJECT_SHOW:
                v.anotar(h, por_evento=True)
            elif evento == EVENT_SYSTEM_FOREGROUND:
                v.frente += 1

        self.cb = WINEVENTPROC(cb)  # guardado: o ctypes não pode coletar o callback
        g1 = u32.SetWinEventHook(EVENT_OBJECT_SHOW, EVENT_OBJECT_SHOW, None, self.cb, v.pid, 0, WINEVENT_OUTOFCONTEXT)
        g2 = u32.SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, None, self.cb, 0, 0, WINEVENT_OUTOFCONTEXT)
        self.ok = bool(g1 and g2)
        self.pronto.set()
        msg = wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
        for g in (g1, g2):
            if g:
                u32.UnhookWinEvent(g)

    def encerrar(self):
        self.pronto.wait(5)
        if self.tid:
            u32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)
        self.join(5)


def conferir(caso, nome, ok, detalhe=""):
    resultados.append({"caso": caso, "verificacao": nome, "passou": bool(ok), "detalhe": detalhe})
    print(f"  [{'ok' if ok else 'FALHOU'}] {nome}" + (f" ({detalhe})" if detalhe and not ok else ""))


def preparar(caso, cfg):
    dados = os.path.join(BASE, caso)
    shutil.rmtree(dados, ignore_errors=True)
    os.makedirs(dados)
    if cfg is not None:
        with open(os.path.join(dados, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    return dados


def abrir(dados, caminhos, limite=60, sair_no_fim=True):
    env = dict(os.environ, DREDS_TESTE="1", CIRANDA_DADOS=dados, CIRANDA_TESTE_LIMITE_S=str(limite))
    if sair_no_fim:
        env["CIRANDA_SAIR_NO_FIM"] = "1"
    p = subprocess.Popen([EXE, *caminhos], env=env)
    v = Vigia(p.pid)
    v.start()
    return p, v


def log(dados):
    try:
        with open(os.path.join(dados, "prova.log"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def esperar_no_log(dados, texto, s=20, desde=0):
    t0 = time.time()
    while time.time() - t0 < s:
        if texto in log(dados)[desde:]:
            return True
        time.sleep(0.1)
    return False


def tocados(dados):
    return [l.split(" tocando ", 1)[1] for l in log(dados).splitlines() if " tocando " in l]


def fechar_e_conferir_invisivel(caso, p, v, s=90):
    try:
        cod = p.wait(timeout=s)
    except subprocess.TimeoutExpired:
        p.kill()
        cod = "preso (morto)"
    v.parar = True
    v.join()
    conferir(caso, "saiu sozinho, código 0", cod == 0, f"código {cod}")
    conferir(caso, "ganchos de evento do Windows instalados", getattr(v.ganchos, "ok", False))
    conferir(caso, "nenhuma janela visível em nenhum momento", not v.visiveis,
             f"visíveis: {sorted(v.visiveis)}; {v.amostras} amostras, {v.eventos} eventos de janela mostrada")
    v.isentas_vistas = sorted(v.isentas)
    conferir(caso, "nunca ficou na frente (foco não roubado)", v.frente == 0, f"{v.frente} amostras na frente")
    return v.amostras


def tecla(host, vk, repetida=False):
    lp = 1 | (1 << 30 if repetida else 0)
    u32.PostMessageW(host, WM_KEYDOWN, vk, lp)
    u32.PostMessageW(host, WM_KEYUP, vk, 1 | (1 << 30) | (1 << 31))


def hospedeira_de(pid):
    for h, classe, _vis in janelas_do_pid(pid):
        if classe == "CirandaHospedeira":
            return h
    return None


def ler_cfg(dados):
    with open(os.path.join(dados, "config.json"), "rb") as f:
        b = f.read()
    return json.loads(b.decode("utf-8")), b


# As chaves do PADRAO da 1.5.1 (ciranda/config.py), na ordem dele: o config gravado tem estas e só estas.
CHAVES_151 = ["volume", "mudo", "aleatorio", "repetir", "filtro", "segundos_foto", "painel", "ultimas_pastas",
              "geometria", "versao_vista", "idioma", "aviso_adiado_versao", "aviso_adiado_ate", "novidades_vista",
              "tutorial_visto", "retomar", "apoio_escolha"]


def mesmo_formato_da_151(d, b):
    """Os bytes são os que o json.dump(indent=2, ensure_ascii=False) da 1.5.1 grava no Windows,
    com as chaves do PADRAO na ordem dele (só reler o que o Rust gravou não pegaria chave fora de ordem)."""
    return list(d) == CHAVES_151 and b ==json.dumps(d, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode("utf-8")


# ---------- caso 1: fila natural até o fim, com um arquivo que não abre ----------
def caso_fila_natural():
    caso = "fila-natural"
    print(caso)
    dados = preparar(caso, {"aleatorio": False, "repetir": "nao", "segundos_foto": 1, "volume": 37})
    pasta = os.path.join(dados, "midia")
    os.makedirs(pasta)
    for rel in [r"Aniversário\anim.gif", r"Aniversário\foto.bmp", r"Aniversário\foto.webp", "clipe.mkv", "corrompido.mp4"]:
        shutil.copy(os.path.join(MIDIA, rel), pasta)
    t0 = time.time()
    p, v = abrir(dados, [pasta])
    fechar_e_conferir_invisivel(caso, p, v)
    dt = time.time() - t0
    t = tocados(dados)
    nomes = [os.path.basename(x) for x in t]
    conferir(caso, "tocou os 5 na ordem natural", nomes == ["anim.gif", "clipe.mkv", "corrompido.mp4", "foto.bmp", "foto.webp"],
             str(nomes))
    conferir(caso, "posição na fila certa", [x.split(" ", 1)[0] for x in t] == ["1/5", "2/5", "3/5", "4/5", "5/5"], str(t))
    lg = log(dados)
    conferir(caso, "o corrompido foi marcado e pulado", "não abriu: " in lg and "corrompido.mp4" in lg.split("não abriu: ", 1)[1][:400])
    conferir(caso, "fim da fila", "fim da fila" in lg)
    conferir(caso, "foto passa no tempo do config (1 s)", lg.count("foto: 1 s, passa") == 3, str(lg.count("foto: 1 s, passa")))
    conferir(caso, "motor sem vídeo e sem som (vo=null, ao=null, mute)",
             "modo teste: vo=null " in lg and "mute=yes (opções vo=null ao=null)" in lg
             and "modo teste: áudio em ao=null mute=yes" in lg,
             " | ".join(l for l in lg.splitlines() if "modo teste:" in l) or "sem linha")
    conferir(caso, "varredura no log como a 1.5.1",
             "varredura: 1 pastas abertas, 1 pastas lidas, 5 fotos/vídeos, 0 arquivos de outros tipos" in lg)
    d, b = ler_cfg(dados)
    conferir(caso, "config: Continuar com a pasta, volume mantido", d["ultimas_pastas"] == [pasta] and d["volume"] == 37, str(d))
    conferir(caso, "config: mesmos bytes que a 1.5.1 gravaria", mesmo_formato_da_151(d, b))
    conferir(caso, "terminou em menos de 30 s", dt < 30, f"{dt:.1f} s")
    return dt


# ---------- caso 2: teclas por mensagem (sem SendInput), fechar pela hospedeira ----------
def caso_teclas():
    caso = "teclas"
    print(caso)
    dados = preparar(caso, {"aleatorio": False, "repetir": "tudo", "segundos_foto": 60})
    p, v = abrir(dados, [MIDIA], sair_no_fim=False)
    ok = esperar_no_log(dados, "tocando 1/16")
    conferir(caso, "abriu a pasta de teste da 1.5.1 (16 itens) no primeiro", ok, log(dados)[-400:])
    host = None
    t0 = time.time()
    while host is None and time.time() - t0 < 5:
        host = hospedeira_de(p.pid)
        time.sleep(0.1)
    conferir(caso, "achou a hospedeira oculta", host is not None)
    # A fila começa num vídeo (abertura.mp4); a tecla 2 tira ele e vai para a 1ª foto.
    passos = [
        (0x32, False, "tocando 1/9", "2: só fotos (o vídeo da tela sai, vai para a 1ª foto)"),
        (0x4E, False, "tocando 2/9", "N: próximo"),
        (0x53, False, "aleatório: ligado", "S: aleatório"),
        (0x53, True, None, "S segurado (repetição) não desliga"),
        (0x52, False, "repetir: um", "R: repetir tudo → um"),
        (0x4E, False, "tocando 2/9", "N: próximo no baralho"),
        (0x31, False, "filtro: tudo", "1: tudo de novo"),
        (0x46, False, "tela cheia: não aplicada no modo teste", "F: tela cheia não abre janela no teste"),
    ]
    for vk, rep, esperado, nome in passos:
        antes = log(dados)
        tecla(host, vk, rep)
        if esperado:
            conferir(caso, nome, esperar_no_log(dados, esperado, 5, len(antes)), log(dados)[len(antes):][-300:])
        else:
            time.sleep(0.6)
            conferir(caso, nome, log(dados)[len(antes):].count("aleatório:") == 0, log(dados)[len(antes):][-300:])
    u32.PostMessageW(host, WM_CLOSE, 0, 0)
    fechar_e_conferir_invisivel(caso, p, v, 20)
    lg = log(dados)
    conferir(caso, "fechou pela hospedeira e salvou", "hospedeira pediu para fechar" in lg and "config salvo" in lg)
    d, b = ler_cfg(dados)
    conferir(caso, "config: aleatório ligado, repetir um, filtro tudo",
             d["aleatorio"] is True and d["repetir"] == "um" and d["filtro"] == "tudo", str({k: d[k] for k in ("aleatorio", "repetir", "filtro")}))
    conferir(caso, "config: mesmos bytes que a 1.5.1 gravaria", mesmo_formato_da_151(d, b))


# ---------- caso 3: nada da fila abre ----------
def caso_nada_abre():
    caso = "nada-abre"
    print(caso)
    dados = preparar(caso, {"aleatorio": False, "repetir": "tudo"})
    pasta = os.path.join(dados, "ruins")
    os.makedirs(pasta)
    for n in ("a.mp4", "b.mkv", "c.mov"):
        with open(os.path.join(pasta, n), "wb") as f:
            f.write(b"isto nao e um video " * 300)
    p, v = abrir(dados, [pasta])
    fechar_e_conferir_invisivel(caso, p, v)
    lg = log(dados)
    conferir(caso, "tenta os 3 uma vez e para (sem girar para sempre)",
             len(tocados(dados)) == 3 and "nenhum arquivo da fila abriu" in lg, f"{len(tocados(dados))} tentativas")


# ---------- caso 4: filtro do config esconde tudo ----------
def caso_filtro_volta():
    caso = "filtro-volta"
    print(caso)
    dados = preparar(caso, {"aleatorio": False, "repetir": "nao", "filtro": "videos", "segundos_foto": 1})
    pasta = os.path.join(dados, "so-fotos")
    os.makedirs(pasta)
    for rel in [r"Aniversário\foto.bmp", r"Aniversário\foto.webp"]:
        shutil.copy(os.path.join(MIDIA, rel), pasta)
    p, v = abrir(dados, [pasta])
    fechar_e_conferir_invisivel(caso, p, v)
    d, _ = ler_cfg(dados)
    conferir(caso, "pasta só de fotos com filtro Vídeos: volta para Tudo e toca as 2",
             len(tocados(dados)) == 2 and d["filtro"] == "tudo", f"{tocados(dados)} filtro={d['filtro']}")


# ---------- caso 5: a pasta da 1.x é recusada de todo jeito (com um APPDATA falso) ----------
def caso_pasta_proibida():
    """O processo recebe um APPDATA falso dentro da pasta de teste: mesmo se a trava falhar, a
    pasta de verdade da 1.x (%APPDATA%\\Ciranda) nunca está em jogo."""
    import _winapi
    caso = "pasta-proibida"
    print(caso)
    falso = os.path.join(BASE, caso, "appdata")
    shutil.rmtree(os.path.join(BASE, caso), ignore_errors=True)
    proibida = os.path.join(falso, "Ciranda")
    os.makedirs(proibida)
    sentinela = os.path.join(proibida, "config.json")
    with open(sentinela, "wb") as f:
        f.write(b'{"volume": 11}')
    juncao = os.path.join(falso, "atalho")
    _winapi.CreateJunction(proibida, juncao)
    curto = ctypes.create_unicode_buffer(600)
    ctypes.windll.kernel32.GetShortPathNameW(proibida, curto, 600)
    variantes: list[tuple[str, str | None]] = [
        ("barra no fim", proibida + "\\"),
        ("maiúsculas", os.path.join(falso, "CIRANDA")),
        ("subpasta", os.path.join(proibida, "sub")),
        ("prefixo \\\\?\\", "\\\\?\\" + proibida),
        ("com ..", os.path.join(proibida, "..", "Ciranda")),
        ("junção para ela", juncao),
    ]
    if curto.value and curto.value.lower() != proibida.lower():
        variantes.append(("nome curto 8.3", curto.value))
    else:
        print("  (o disco não tem nome curto 8.3 para a pasta: variante pulada)")
    variantes.append(("APPDATA vazio", None))

    def rodar(dados, appdata=falso):
        env = dict(os.environ, DREDS_TESTE="1", CIRANDA_TESTE_LIMITE_S="3", APPDATA=appdata)
        env.pop("CIRANDA_DADOS", None)
        if dados is not None:
            env["CIRANDA_DADOS"] = dados
        p = subprocess.Popen([EXE], env=env, stderr=subprocess.PIPE)
        v = Vigia(p.pid)
        v.start()
        try:
            _, err = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
            _, err = p.communicate()
        v.parar = True
        v.join()
        return p.returncode, err.decode("utf-8", "replace"), v

    for nome, dados in variantes:
        cod, err, v = rodar(dados, "" if dados is None else falso)
        motivo = "APPDATA vazio" if dados is None else "proibida"
        conferir(caso, f"recusa ({nome})", cod == 1 and motivo in err and not v.visiveis and v.frente == 0,
                 f"código {cod}: {err.strip()[:200]}")
    dentro = sorted(os.listdir(proibida))
    with open(sentinela, "rb") as f:
        intacto = f.read() == b'{"volume": 11}'
    conferir(caso, "nada foi gravado na pasta proibida", dentro == ["config.json"] and intacto, str(dentro))
    outra = os.path.join(falso, "Ciranda-outra")
    cod, err, v = rodar(outra)
    conferir(caso, "controle: uma pasta vizinha é aceita",
             cod == 0 and os.path.exists(os.path.join(outra, "prova.log")) and not v.visiveis, f"código {cod}: {err.strip()[:200]}")
    os.rmdir(juncao)  # tira só a junção, sem descer nela


# ---------- caso 0: o vigia pega mesmo uma janela que pisca (controle negativo) ----------
PISCA = r"""
import ctypes, time
u = ctypes.WinDLL("user32")
u.CreateWindowExW.restype = ctypes.c_void_p
u.CreateWindowExW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.c_void_p, ctypes.c_void_p]
u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
u.DestroyWindow.argtypes = [ctypes.c_void_p]
time.sleep(1.0)
# STATIC sem borda, de ferramenta e sem ativar, fora de qualquer monitor: ninguém vê, nada perde o foco.
h = u.CreateWindowExW(0x08000080, "STATIC", "pisca", 0x80000000, -20000, -20000, 40, 40, None, None, None, None)
u.ShowWindow(h, 4)  # SW_SHOWNOACTIVATE
time.sleep(0.05)
u.ShowWindow(h, 0)
u.DestroyWindow(h)
time.sleep(0.5)
"""


def caso_controle_vigia():
    caso = "controle-do-vigia"
    print(caso)
    p = subprocess.Popen([sys.executable, "-I", "-c", PISCA])
    v = Vigia(p.pid)
    v.start()
    p.wait(20)
    time.sleep(0.2)
    v.parar = True
    v.join()
    conferir(caso, "ganchos de evento do Windows instalados", getattr(v.ganchos, "ok", False))
    conferir(caso, "uma janela que fica 50 ms visível (fora da tela, sem ativar) é pega", "Static" in v.visiveis,
             f"visíveis: {sorted(v.visiveis)}, {v.eventos} eventos")
    conferir(caso, "e não tomou o foco", v.frente == 0)


# ---------- caso 7 (fase 3): todos os formatos e todos os HEIC, com o mpv de verdade ----------
PROVA = os.path.join(os.environ["APPDATA"], "Ciranda-rust-prova")
GIROS_ESPERADOS = {  # o que a 1.5.1 (heif.py) manda para o mpv em cada caso de tests/gerar_heic.py
    "giro-grade-48-4032x3024.heic": "lavfi=[transpose=clock]",
    "espelho-grade-12-2048x1536.heic": "lavfi=[hflip]",
}


def caso_formatos_e_heic():
    caso = "formatos-e-heic"
    print(caso)
    dados = preparar(caso, {"aleatorio": False, "repetir": "nao", "segundos_foto": 1, "filtro": "tudo"})
    pasta = os.path.join(dados, "midia")
    shutil.copytree(MIDIA, os.path.join(pasta, "a-formatos"))
    shutil.copytree(os.path.join(PROVA, "midia-teste-codecs"), os.path.join(pasta, "b-codecs"))
    shutil.copytree(os.path.join(PROVA, "heic-casos"), os.path.join(pasta, "c-heic"))
    shutil.copytree(os.path.join(PROVA, "heic-autoteste"), os.path.join(pasta, "d-heic-iphone"))
    t0 = time.time()
    p, v = abrir(dados, [pasta], limite=240)
    fechar_e_conferir_invisivel(caso, p, v, s=260)
    dt = time.time() - t0
    lg = log(dados)
    t = [os.path.basename(x.split(" ", 1)[1]) for x in tocados(dados)]
    conferir(caso, "tocou os 26 (16 da 1.5.1, 3 codecs, 7 HEIC), nenhum duas vezes", len(t) == 26 and len(set(t)) == 26, f"{len(t)}: {t}")
    conferir(caso, "pasta .oculta entra, como na 1.5.1 (abre tudo)", "nao-deve-aparecer.mp4" in t)
    falhas = [l for l in lg.splitlines() if "não abriu: " in l]
    conferir(caso, "só o corrompido não abriu", len(falhas) == 1 and "corrompido.mp4" in falhas[0], " | ".join(falhas))
    conferir(caso, "fim da fila", "fim da fila" in lg)
    fotos = lg.count("foto: 1 s, passa")
    conferir(caso, "as 16 fotos (com GIF, BMP, WebP, PNG e os 7 HEIC) contaram 1 s e passaram", fotos == 16, str(fotos))
    for nome, filtro in GIROS_ESPERADOS.items():
        conferir(caso, f"{nome}: giro {filtro}", f"HEIC: giro {filtro}" in lg,
                 " | ".join(l for l in lg.splitlines() if "HEIC" in l) or "sem linha HEIC")
    giros = [l.split("HEIC: giro ", 1)[1] for l in lg.splitlines() if "HEIC: giro " in l]
    conferir(caso, "nenhum outro HEIC de teste pede giro", len([g for g in giros if g not in GIROS_ESPERADOS.values()]) <= 2,
             str(giros))
    pulados = [l for l in lg.splitlines() if "HEIC não apareceu em 5 tentativas" in l]
    conferir(caso, "nenhum HEIC pulado por não aparecer", not pulados, " | ".join(pulados))
    recargas = [l for l in lg.splitlines() if "HEIC não apareceu em" in l and "recarregando" in l]
    print(f"    (recargas de HEIC: {len(recargas)})")
    conferir(caso, "motor sem vídeo e sem som", "mute=yes (opções vo=null ao=null)" in lg)
    conferir(caso, "terminou em menos de 150 s", dt < 150, f"{dt:.1f} s")
    return dt


fg0 = u32.GetForegroundWindow()
caso_controle_vigia()
caso_fila_natural()
caso_teclas()
caso_nada_abre()
caso_filtro_volta()
caso_pasta_proibida()
caso_formatos_e_heic()
passou = sum(r["passou"] for r in resultados)
print(f"{passou} de {len(resultados)} passaram")
os.makedirs(BASE, exist_ok=True)
with open(os.path.join(BASE, "resultado.json"), "w", encoding="utf-8") as f:
    json.dump({"passou": passou, "total": len(resultados), "itens": resultados}, f, ensure_ascii=False, indent=2)
sys.exit(0 if passou == len(resultados) else 1)
