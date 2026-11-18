"""Gera ui/icones.slint a partir dos ícones da 1.5.1 (ciranda/icones.py): o mesmo desenho
(grade 24x24, traço 2 px ou preenchido), convertido em caminho SVG para o `Path` do Slint.

    python -I rust/ferramentas/gerar_icones.py

Lê o icones.py como texto (não importa o PySide6): avalia só o dicionário SVG.
"""
from __future__ import annotations

import ast
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
ORIGEM = os.path.join(RAIZ, "ciranda", "icones.py")
DESTINO = os.path.join(os.path.dirname(AQUI), "ui", "icones.slint")


def ler_svg() -> dict[str, str]:
    arvore = ast.parse(open(ORIGEM, encoding="utf-8").read())
    nomes: dict = {}
    for no in arvore.body:
        if isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(no.targets[0], ast.Name):
            alvo = no.targets[0].id
            if alvo in ("_T", "_C", "SVG"):
                nomes[alvo] = eval(compile(ast.Expression(no.value), ORIGEM, "eval"), {}, dict(nomes))
    return nomes["SVG"]


def num(x: float) -> str:
    s = f"{x:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def atributos(tag: str) -> dict[str, str]:
    return dict(re.findall(r'([a-z-]+)="([^"]*)"', tag))


def caminho_do_elemento(tag: str, nome: str) -> str:
    a = atributos(tag)
    if nome == "path":
        return a["d"]
    if nome == "rect":
        x, y, w, h = (float(a[k]) for k in ("x", "y", "width", "height"))
        rx = float(a.get("rx", "0"))
        if rx <= 0:
            return f"M{num(x)} {num(y)}H{num(x + w)}V{num(y + h)}H{num(x)}Z"
        return (f"M{num(x + rx)} {num(y)}H{num(x + w - rx)}A{num(rx)} {num(rx)} 0 0 1 {num(x + w)} {num(y + rx)}"
                f"V{num(y + h - rx)}A{num(rx)} {num(rx)} 0 0 1 {num(x + w - rx)} {num(y + h)}"
                f"H{num(x + rx)}A{num(rx)} {num(rx)} 0 0 1 {num(x)} {num(y + h - rx)}"
                f"V{num(y + rx)}A{num(rx)} {num(rx)} 0 0 1 {num(x + rx)} {num(y)}Z")
    if nome == "circle":
        cx, cy, r = (float(a[k]) for k in ("cx", "cy", "r"))
        return (f"M{num(cx - r)} {num(cy)}A{num(r)} {num(r)} 0 1 0 {num(cx + r)} {num(cy)}"
                f"A{num(r)} {num(r)} 0 1 0 {num(cx - r)} {num(cy)}Z")
    raise ValueError(f"elemento {nome} não previsto")


def converter(svg: str) -> tuple[str, bool]:
    """(caminho, cheio): todos os ícones usados são só traço ou só preenchimento."""
    cheio = 'fill="currentColor"' in svg
    traco = 'stroke="currentColor"' in svg
    if cheio == traco:
        raise ValueError("ícone misto")
    partes = [caminho_do_elemento(m.group(0), m.group(1)) for m in re.finditer(r"<(path|rect|circle)\b[^>]*/>", svg)]
    return " ".join(partes), cheio


def main():
    svg = ler_svg()
    linhas_d, cheios = [], []
    for nome, desenho in svg.items():
        if nome == "bandeira_br":  # cores fixas, só no quadro Apoiar (fase 5)
            continue
        d, cheio = converter(desenho)
        linhas_d.append(f'        if nome == "{nome}" {{ return "{d}"; }}')
        if cheio:
            cheios.append(nome)
    corpo = [
        "// Gerado por rust/ferramentas/gerar_icones.py a partir de ciranda/icones.py (1.5.1). Não edite.",
        "// Grade 24x24; os de traço usam 2 px na grade (arredondado), os cheios são preenchidos.",
        "",
        "export global Icones {",
        "    pure public function d(nome: string) -> string {",
        *linhas_d,
        '        return "";',
        "    }",
        "    pure public function cheio(nome: string) -> bool {",
        "        return " + " || ".join(f'nome == "{n}"' for n in cheios) + ";",
        "    }",
        "}",
        "",
    ]
    open(DESTINO, "w", encoding="utf-8", newline="\n").write("\n".join(corpo))
    print(f"{len(linhas_d)} ícones em {DESTINO} ({len(cheios)} cheios)")


if __name__ == "__main__":
    sys.exit(main())
