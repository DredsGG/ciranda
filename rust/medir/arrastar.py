"""Arrasto OLE de verdade (CF_HDROP, o mesmo formato do Explorer) para a prova, com mouse real (SendInput).

A fonte do arrasto é uma janelinha WinForms (fonte_arrasto.ps1) com DoDragDrop: não controla o Explorer.
Uso: python -I arrastar.py <pasta_medir> <exe> <fonte_arrasto.ps1> <arquivo_ou_pasta> <pasta_prints> <nome.png>
"""
import os, subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import interface as I
exe, ps1, caminho, prints, nome_print = sys.argv[2:7]
app = I.App(exe, [])
try:
    I.u32.SetWindowPos(app.host, -1, 1500, 200, 1200, 720, 0x10)
    time.sleep(1.0)
    m = I.tamanho_log()
    fonte = subprocess.Popen(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", ps1, caminho],
                             stdout=subprocess.PIPE, text=True)
    h = 0
    for _ in range(100):
        h = I.u32.FindWindowW(None, "Fonte de arrasto (teste)")
        if h: break
        time.sleep(0.1)
    assert h, "fonte não abriu"
    time.sleep(0.5)
    sx, sy = 360, 410
    I.mover(sx, sy)
    I._enviar(I.INPUT(0, I._U(mi=I.MOUSEINPUT(0, 0, 0, 0x2, 0, 0))))
    time.sleep(0.3)
    cx, cy = I.centro(I.rect_cliente(app.host))
    passos = 30
    for i in range(1, passos + 1):
        I.mover(sx + (cx - sx) * i / passos, sy + (cy - sy) * i / passos)
        time.sleep(0.03)
    for _ in range(5):
        I.mexer_mouse(2); time.sleep(0.05); I.mexer_mouse(-2); time.sleep(0.05)
    time.sleep(0.4)
    borda = I.esperar_no_log(m, "arrastando por cima", 2)
    I.print_do_app(app, os.path.join(prints, nome_print))
    I._enviar(I.INPUT(0, I._U(mi=I.MOUSEINPUT(0, 0, 0, 0x4, 0, 0))))
    saida = fonte.communicate(timeout=15)[0]
    ok = I.esperar_no_log(m, "varredura:", 5)  # linha de log da varredura (fase 2)
    time.sleep(2.0)
    print("fonte:", saida.strip(), "| borda no log:", borda, "| fila no log:", ok)
    sys.stdout.reconfigure(encoding="utf-8"); print(I.log_desde(m))
finally:
    app.fechar()
