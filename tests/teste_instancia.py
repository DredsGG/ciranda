"""Janela única: o 2º Ciranda entrega o arquivo para o 1º e sai; o 1º mostra só aquele
arquivo; vários arquivos abertos em seguida se juntam; o Continuar não é apagado.
    CIRANDA_VO=x11 xvfb-run -a python testes/teste_instancia.py <pasta-de-midia> <saida>"""
import json
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA, SAIDA = sys.argv[1], sys.argv[2]
APPDATA = os.path.join(SAIDA, "appdata-instancia")
os.makedirs(APPDATA, exist_ok=True)
env = dict(os.environ, APPDATA=APPDATA)
app = [sys.executable, os.path.join(RAIZ, "app.py")]
log = os.path.join(APPDATA, "Ciranda", "ciranda.log")
cfg = os.path.join(APPDATA, "Ciranda", "config.json")


def esperar(cond, s=15):
    t = time.time()
    while time.time() - t < s:
        if cond():
            return True
        time.sleep(0.3)
    return False


def no_log(txt):
    try:
        return open(log, encoding="utf-8").read().count(txt)
    except OSError:
        return 0


primeiro = subprocess.Popen(app + [PASTA], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    assert esperar(lambda: os.path.exists(cfg) and json.load(open(cfg))["ultimas_pastas"]), "1º não abriu a pasta"
    continuar_antes = json.load(open(cfg))["ultimas_pastas"]

    foto = os.path.join(PASTA, "capa.jpg")
    t0 = time.time()
    seg = subprocess.run(app + [foto], env=env, timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dt = time.time() - t0
    assert seg.returncode == 0, f"2º saiu com {seg.returncode}"
    assert dt < 8, f"2º demorou {dt:.1f}s para sair (abriu outra janela?)"
    assert esperar(lambda: no_log("recebido de outra instância: 1 caminho") >= 1), "1º não recebeu"
    print(f"ok: 2º entregou e saiu em {dt:.1f}s")

    # vários arquivos em seguida (vários selecionados no Explorer): o 2º e 3º juntam
    outros = [os.path.join(PASTA, "2024 Praia", "praia geral.png"), os.path.join(PASTA, "abertura.mp4")]
    for f in outros:
        subprocess.run(app + [f], env=env, timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert esperar(lambda: no_log("(junta)") >= 1), "arquivos seguidos não se juntaram"
    print("ok: arquivos abertos em seguida se juntam")

    time.sleep(1)
    assert json.load(open(cfg))["ultimas_pastas"] == continuar_antes, "abrir arquivo apagou o Continuar"
    print("ok: Continuar preservado")
    assert primeiro.poll() is None, "1º fechou"
    print("INSTANCIA PASSOU")
finally:
    primeiro.terminate()
    try:
        primeiro.wait(5)
    except subprocess.TimeoutExpired:
        primeiro.kill()
