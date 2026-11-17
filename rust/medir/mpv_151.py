"""Lê do mpv da 1.5.1 (código da main 304bc21, mesma libmpv-2.dll) os mesmos números que a
prova Rust grava: hwdec-current, quadros perdidos e atrasados, fps estimado.

O exe instalado não deixa ler o mpv de fora; o código-fonte da 1.5.1 é o mesmo do instalado.
Uso (com o Python do .venv da 1.5.1 e APPDATA separado):
  python medir/mpv_151.py <pasta_da_1.5.1> <arquivo> <saida.json> [segundos]
"""
import json
import os
import sys
import time

pasta, arquivo, saida = sys.argv[1:4]
segundos = int(sys.argv[4]) if len(sys.argv) > 4 else 30
sys.path.insert(0, pasta)
os.environ["PATH"] = pasta + os.pathsep + os.environ["PATH"]

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ciranda.janela import QSS, Janela  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)
t0 = time.perf_counter()
j = Janela([os.path.abspath(arquivo)])
j.show()
estado = {"inicio": None, "contando": None}
AQUECER = int(os.environ.get("CIRANDA_PROVA_AQUECER", "5"))
CONTADORES = ["frame-drop-count", "decoder-frame-drop-count", "vo-delayed-frame-count"]


def contadores():
    return [j.mpv._get_property(c) or 0 for c in CONTADORES]


def vigiar():
    agora = time.perf_counter()
    if estado["inicio"] is None:
        pos = j.mpv.time_pos
        if pos is not None and pos > 0:
            estado["inicio"] = agora
            estado["primeiro_s"] = round(agora - t0, 3)
        return
    if estado["contando"] is None:
        if agora - estado["inicio"] >= AQUECER:
            estado["contando"] = (agora, time.process_time(), contadores())
            open(os.path.splitext(saida)[0] + ".comecou", "w").close()
        return
    t1, cpu1, c1 = estado["contando"]
    if agora - t1 >= segundos and "feito" not in estado:
        estado["feito"] = True
        dt = agora - t1
        c2 = contadores()
        r = {"arquivo": arquivo, "primeiro_tempo_positivo_s": estado["primeiro_s"], "aquecer_s": AQUECER}
        for p in ["hwdec-current", "current-vo", "video-params/pixelformat", "video-params/hw-pixelformat",
                  "mpv-version", "ffmpeg-version", "video-sync",
                  *CONTADORES, "estimated-vf-fps", "container-fps", "display-fps", "width", "height",
                  "osd-width", "osd-height", "time-pos"]:
            r[p] = j.mpv._get_property(p)
        r["perdidos_na_janela"] = c2[0] - c1[0]
        r["perdidos_decoder_na_janela"] = c2[1] - c1[1]
        r["atrasados_na_janela"] = c2[2] - c1[2]
        r["cpu_pct_um_nucleo"] = round((time.process_time() - cpu1) / dt * 100, 2)
        r["janela_s"] = round(dt, 2)
        with open(saida, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, default=str)
        if os.environ.get("CIRANDA_PROVA_SAIR", "1") == "1":
            app.quit()


t = QTimer()
t.timeout.connect(vigiar)
t.start(50)
QTimer.singleShot((segundos + AQUECER + 60) * 1000, app.quit)
app.exec()
