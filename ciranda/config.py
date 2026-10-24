"""Ajustes salvos entre uma abertura e outra (%APPDATA%\\Ciranda\\config.json).
Fica fora da pasta do programa para não se perder quando a versão é trocada."""

from __future__ import annotations

import json
import os

PADRAO = {
    "volume": 80,
    "mudo": False,
    "aleatorio": True,
    "repetir": "tudo",
    "filtro": "tudo",
    "segundos_foto": 5,
    "painel": True,
    "ultimas_pastas": [],
    "geometria": None,
}


def pasta_dados() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    p = os.path.join(base, "Ciranda")
    os.makedirs(p, exist_ok=True)
    return p


def _arquivo() -> str:
    return os.path.join(pasta_dados(), "config.json")


def carregar() -> dict:
    cfg = dict(PADRAO)
    try:
        with open(_arquivo(), encoding="utf-8") as f:
            salvo = json.load(f)
        if isinstance(salvo, dict):
            cfg.update({k: v for k, v in salvo.items() if k in PADRAO})
    except (OSError, ValueError):
        pass
    return cfg


def salvar(cfg: dict):
    tmp = _arquivo() + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _arquivo())
    except OSError:
        pass
