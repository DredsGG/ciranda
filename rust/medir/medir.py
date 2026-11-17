"""Medição da fase 1: prova Rust contra a Ciranda 1.5.1 instalada, nos mesmos arquivos.

Mede de fora, igual para os dois:
  * CPU média do processo em 30 s tocando (Get-Counter, % de UM núcleo, e TotalProcessorTime);
  * memória (working set e privada) no fim;
  * tempo do "clique" (iniciar o processo com o arquivo, como o duplo clique do Explorer)
    até o 1º quadro na tela: lê o pixel do meio da janela até ficar magenta.

Uso: python -I medir.py <saida.json> <exe_rust> <exe_151> <py_151> <pasta_151> <pasta_midia> <appdata_151> <rodadas> [mpv,cpu,quadro,composicao]
Nada é gravado em %APPDATA%\\Ciranda: a 1.5.1 roda com APPDATA separado.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import json
import os
import subprocess
import sys
import time

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
u32.GetDC.restype = w.HDC
g32.GetPixel.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]
g32.GetPixel.restype = w.DWORD
u32.ReleaseDC.argtypes = [w.HWND, w.HDC]
# Sem argtypes, o -1 (HWND_TOPMOST) vai como int de 32 bits e a chamada falha calada no Windows 64-bit.
u32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
u32.SetWindowPos.restype = w.BOOL

VIDEOS = ["h264-1080p60.mp4", "hevc10-4k60.mp4", "av1-1080p60.mkv"]
SEGUNDOS = 30


def janelas_do_processo(pid: int) -> list[int]:
    achadas = []
    PROC = ctypes.WINFUNCTYPE(ctypes.c_int, w.HWND, w.LPARAM)

    def cb(h, _l):
        p = w.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h) and not u32.GetWindow(h, 4):  # GW_OWNER
            achadas.append(h)
        return 1

    u32.EnumWindows(PROC(cb), 0)
    return achadas


def maior_janela(pid: int):
    melhor, area = None, 0
    for h in janelas_do_processo(pid):
        r = w.RECT()
        u32.GetClientRect(h, ctypes.byref(r))
        a = r.right * r.bottom
        if a > area:
            melhor, area = h, a
    return melhor


def centro(h) -> tuple[int, int, int, int]:
    r = w.RECT()
    u32.GetClientRect(h, ctypes.byref(r))
    p = w.POINT(0, 0)
    u32.ClientToScreen(h, ctypes.byref(p))
    return p.x + r.right // 2, p.y + r.bottom // 3, r.right, r.bottom  # 1/3 da altura: longe da barra


def nenhum_ciranda_aberto() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Ciranda.exe", "/NH"], capture_output=True, text=True).stdout
    out2 = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ciranda-prova.exe", "/NH"], capture_output=True, text=True).stdout
    return "Ciranda.exe" not in out and "ciranda-prova.exe" not in out2


def ambiente(qual: str, appdata_151: str, extra: dict | None = None) -> dict:
    env = dict(os.environ)
    if qual == "151":
        env["APPDATA"] = appdata_151
    env.update(extra or {})
    return env


def fechar(p: subprocess.Popen):
    """Fecha pelo X da própria janela (WM_CLOSE); só força se não fechar em 10 s."""
    if p.poll() is not None:
        return
    for h in janelas_do_processo(p.pid):
        u32.PostMessageW(h, 0x10, 0, 0)
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()


def primeiro_quadro(exe: str, arquivo: str, env: dict) -> dict:
    """Tempo do início do processo até o pixel do meio ficar magenta."""
    hdc = u32.GetDC(None)
    t0 = time.perf_counter()
    p = subprocess.Popen([exe, arquivo], env=env)
    janela_em = None
    try:
        while time.perf_counter() - t0 < 20:
            h = maior_janela(p.pid)
            if h:
                if janela_em is None:
                    janela_em = time.perf_counter() - t0
                    u32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # por cima de tudo, sem ativar
                x, y, _, _ = centro(h)
                c = g32.GetPixel(hdc, x, y)
                r, g, b = c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF
                if r > 200 and g < 70 and b > 200:
                    return {"janela_s": round(janela_em, 3), "quadro_s": round(time.perf_counter() - t0, 3)}
            time.sleep(0.004)
        h = maior_janela(p.pid)
        info = {}
        if h:
            x, y, cw, ch = centro(h)
            c = g32.GetPixel(hdc, x, y)
            b = ctypes.create_unicode_buffer(200)
            u32.GetClassNameW(h, b, 200)
            info = {"cor": f"#{c & 0xFF:02x}{(c >> 8) & 0xFF:02x}{(c >> 16) & 0xFF:02x}", "ponto": (x, y),
                    "cliente": (cw, ch), "classe": b.value, "janelas": len(janelas_do_processo(p.pid))}
        return {"janela_s": janela_em, "quadro_s": None, **info}
    finally:
        fechar(p)
        u32.ReleaseDC(None, hdc)
        time.sleep(1.5)


CONTADOR_CPU = None


def contador_cpu() -> str:
    """Nome do contador de CPU do processo no idioma do Windows (PDH é traduzido)."""
    global CONTADOR_CPU
    if CONTADOR_CPU:
        return CONTADOR_CPU
    ps = ("$s=(Get-Counter -ListSet * | Where-Object { $_.CounterSetName -match '^(Process|Processo)$' })"
          "| Select-Object -First 1; $s.Paths | Where-Object { $_ -match 'Processor Time|tempo de processador' }"
          "| Select-Object -First 1")
    CONTADOR_CPU = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                                  text=True).stdout.strip()
    return CONTADOR_CPU


def processo_cpu_s(pid: int) -> float:
    ps = f"(Get-Process -Id {pid}).TotalProcessorTime.TotalSeconds"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    return float(out.strip().replace(",", "."))


def processo_mem(pid: int) -> dict:
    ps = f"$p=Get-Process -Id {pid}; '{{0}};{{1}}' -f $p.WorkingSet64,$p.PrivateMemorySize64"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    ws, priv = out.strip().split(";")
    return {"working_set_mb": round(int(ws) / 2**20, 1), "privada_mb": round(int(priv) / 2**20, 1)}


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", w.UINT), ("dwTime", w.DWORD)]


def ultimo_toque_ms() -> int:
    li = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    u32.GetLastInputInfo(ctypes.byref(li))
    return li.dwTime


RETANGULO = (120, 120, 1440, 900)  # mesma posição e tamanho (por fora) para as duas


def posicionar(pid: int, prazo=20.0):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < prazo:
        h = maior_janela(pid)
        if h:
            x0, y0, x1, y1 = RETANGULO
            u32.ShowWindow(h, 9)
            if not u32.SetWindowPos(h, -1, x0, y0, x1 - x0, y1 - y0, 0):  # por cima de tudo: nada cobre o vídeo
                print("  aviso: SetWindowPos falhou", ctypes.GetLastError(), flush=True)
            u32.SetForegroundWindow(h)
            return h
        time.sleep(0.05)
    return None


def esperar_arquivo(caminho: str, prazo: float) -> bool:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < prazo:
        if os.path.exists(caminho):
            return True
        time.sleep(0.05)
    return False


def rodada_mpv(qual: str, cmd: list[str], env: dict, saida: str) -> dict:
    """Série B: números do mpv de dentro do processo (5 s de aquecimento + 30 s contando)."""
    for f in (saida, os.path.splitext(saida)[0] + ".comecou"):
        if os.path.exists(f):
            os.replace(f, f + ".velho")
    env = {**env, "CIRANDA_PROVA_MEDIR": saida, "CIRANDA_PROVA_SEGUNDOS": str(SEGUNDOS),
           "CIRANDA_PROVA_AQUECER": "5", "CIRANDA_PROVA_SAIR": "1"}
    p = subprocess.Popen(cmd, env=env)
    try:
        posicionar(p.pid)
        toque0 = ultimo_toque_ms()
        ok = esperar_arquivo(saida, SEGUNDOS + 60)
        mexeram = ultimo_toque_ms() != toque0
        r = json.load(open(saida, encoding="utf-8")) if ok else {"erro": "sem resultado"}
        r["alguem_mexeu_no_pc"] = mexeram
        return r
    finally:
        fechar(p)
        time.sleep(2)


def rodada_cpu(exe: str, arquivo: str, env: dict, instancia: str) -> dict:
    """Série A: CPU pelo Get-Counter e memória, com o exe de verdade (1.5.1 instalada)."""
    p = subprocess.Popen([exe, arquivo], env=env)
    try:
        posicionar(p.pid)
        time.sleep(6)  # abre, carrega e aquece
        toque0 = ultimo_toque_ms()
        caminho = contador_cpu().replace("(*)", f"({instancia})")
        ps = (f"$c=Get-Counter -Counter '{caminho}' -SampleInterval 1 -MaxSamples {SEGUNDOS};"
              "$v=$c.CounterSamples | ForEach-Object { $_.CookedValue };"
              "($v | Measure-Object -Average -Maximum | ForEach-Object { "
              "[string]::Format([cultureinfo]::InvariantCulture, '{0:F2};{1:F2}', $_.Average, $_.Maximum) })")
        # Cultura invariante: ponto decimal em qualquer Windows (pt-BR ou en-US).
        cpu0, t0 = processo_cpu_s(p.pid), time.perf_counter()
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        cpu1, dt = processo_cpu_s(p.pid), time.perf_counter() - t0
        mem = processo_mem(p.pid)
        media, maximo = (out.stdout.strip().split(";") + ["", ""])[:2]
        return {"cpu_media_pct_um_nucleo_getcounter": float(media) if media else None,
                "cpu_max_pct_um_nucleo_getcounter": float(maximo) if maximo else None,
                "cpu_pct_um_nucleo_tempo_total": round((cpu1 - cpu0) / dt * 100, 2),
                "contador": caminho, **mem, "alguem_mexeu_no_pc": ultimo_toque_ms() != toque0,
                "erro": out.stderr.strip()[:200] or None}
    finally:
        fechar(p)
        time.sleep(2)


def medir_composicao() -> dict:
    """CPU do dwm.exe (Get-Counter) e uso da GPU (nvidia-smi, 1 amostra/s) por SEGUNDOS.

    A camada da Rust é uma janela de topo transparente por cima do vídeo: parte do custo dela
    cai no compositor do Windows e na GPU, fora do processo medido na série "cpu"."""
    caminho = contador_cpu().replace("(*)", "(dwm)")
    ps = (f"$c=Get-Counter -Counter '{caminho}' -SampleInterval 1 -MaxSamples {SEGUNDOS};"
          "$v=$c.CounterSamples | ForEach-Object { $_.CookedValue };"
          "($v | Measure-Object -Average -Maximum | ForEach-Object { "
          "[string]::Format([cultureinfo]::InvariantCulture, '{0:F2};{1:F2}', $_.Average, $_.Maximum) })")
    gpu = subprocess.Popen(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits",
                            "-l", "1"], stdout=subprocess.PIPE, text=True)
    toque0 = ultimo_toque_ms()
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    gpu.terminate()
    amostras = [int(x) for x in (gpu.communicate(timeout=10)[0] or "").split() if x.strip().isdigit()]
    media, maximo = (out.stdout.strip().split(";") + ["", ""])[:2]
    return {"dwm_cpu_media_pct_um_nucleo": float(media) if media else None,
            "dwm_cpu_max_pct_um_nucleo": float(maximo) if maximo else None,
            "gpu_uso_medio_pct": round(sum(amostras) / len(amostras), 1) if amostras else None,
            "gpu_uso_max_pct": max(amostras) if amostras else None,
            "gpu_amostras": len(amostras),
            "alguem_mexeu_no_pc": ultimo_toque_ms() != toque0,
            "erro": out.stderr.strip()[:200] or None}


def rodada_composicao(exe: str | None, arquivo: str, env: dict) -> dict:
    """Série C: o mesmo vídeo, mesma posição; exe None = linha de base, sem app nenhum aberto."""
    if exe is None:
        return medir_composicao()
    p = subprocess.Popen([exe, arquivo], env=env)
    try:
        posicionar(p.pid)
        time.sleep(6)  # abre, carrega e aquece
        return medir_composicao()
    finally:
        fechar(p)
        time.sleep(2)


def main():
    saida, exe_rust, exe_151, py_151, pasta_151, midia, appdata_151, rodadas = sys.argv[1:9]
    series = sys.argv[9].split(",") if len(sys.argv) > 9 else ["mpv", "cpu", "quadro"]
    aqui = os.path.dirname(os.path.abspath(__file__))
    if not nenhum_ciranda_aberto():
        sys.exit("feche a Ciranda antes de medir (o 2º processo entregaria o arquivo para a aberta)")
    res = {"segundos": SEGUNDOS, "retangulo": RETANGULO, "mpv": [], "cpu": [], "primeiro_quadro": {}}
    pasta_med = os.path.join(midia, "..", "medidas")
    os.makedirs(pasta_med, exist_ok=True)
    nome_rust = os.path.splitext(os.path.basename(exe_rust))[0]
    for r in range(1, int(rodadas) + 1):
        for v in VIDEOS:
            arq = os.path.join(midia, v)
            if "mpv" in series:
                for qual in ("rust", "151"):
                    cmd = [exe_rust, arq] if qual == "rust" else [py_151, os.path.join(aqui, "mpv_151.py"), pasta_151, arq,
                                                                 os.path.join(pasta_med, "x.json"), str(SEGUNDOS)]
                    s = os.path.join(pasta_med, f"mpv-{qual}-{r}-{v}.json")
                    if qual == "151":
                        cmd[4] = s
                    d = rodada_mpv(qual, cmd, ambiente(qual, appdata_151), s)
                    d.update(app=qual, rodada=r, video=v)
                    res["mpv"].append(d)
                    print("mpv", qual, r, v, {k: d.get(k) for k in ("hwdec-current", "perdidos_na_janela",
                          "atrasados_na_janela", "cpu_pct_um_nucleo", "repinturas_da_interface", "alguem_mexeu_no_pc")}, flush=True)
            if "cpu" in series:
                for qual, exe, inst in (("rust", exe_rust, nome_rust), ("151", exe_151, "Ciranda")):
                    d = rodada_cpu(exe, arq, ambiente(qual, appdata_151, {"CIRANDA_PROVA_MEDIR": os.path.join(pasta_med, "lixo.json"),
                                                                            "CIRANDA_PROVA_SEGUNDOS": "300", "CIRANDA_PROVA_SAIR": "0"}), inst)
                    d.update(app=qual, rodada=r, video=v)
                    res["cpu"].append(d)
                    print("cpu", qual, r, v, d, flush=True)
    if "composicao" in series:
        res["composicao"] = []
        for r in range(1, int(rodadas) + 1):
            for v in VIDEOS[:2]:  # 1080p60 e 4K60
                arq = os.path.join(midia, v)
                env_rust = {"CIRANDA_PROVA_MEDIR": os.path.join(pasta_med, "lixo.json"),
                            "CIRANDA_PROVA_SEGUNDOS": "300", "CIRANDA_PROVA_SAIR": "0"}
                for qual, exe in (("nenhum", None), ("rust", exe_rust), ("151", exe_151)):
                    d = rodada_composicao(exe, arq, ambiente(qual if qual != "nenhum" else "rust", appdata_151, env_rust))
                    d.update(app=qual, rodada=r, video=v)
                    res["composicao"].append(d)
                    print("composicao", qual, r, v, d, flush=True)
    if "quadro" in series:
        arq = os.path.join(midia, "magenta-1080p60.mp4")
        for qual, exe in (("rust", exe_rust), ("151", exe_151)):
            env = ambiente(qual, appdata_151, {"CIRANDA_PROVA_MEDIR": os.path.join(pasta_med, "lixo.json"),
                                               "CIRANDA_PROVA_SEGUNDOS": "300", "CIRANDA_PROVA_SAIR": "0"})
            vezes = [primeiro_quadro(exe, arq, env) for _ in range(7)]
            res["primeiro_quadro"][qual] = vezes
            print("quadro", qual, vezes, flush=True)
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
