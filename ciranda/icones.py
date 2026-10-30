"""Ícones desenhados em SVG (traço 2 px, grade 24x24), coloridos na hora."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_T = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
_C = 'fill="currentColor" stroke="none"'

SVG = {
    "play": f'<path {_C} d="M7.5 4.6v14.8a1 1 0 0 0 1.5.86l12-7.4a1 1 0 0 0 0-1.72l-12-7.4a1 1 0 0 0-1.5.86z"/>',
    "pause": f'<rect {_C} x="6" y="4.5" width="4" height="15" rx="1.2"/><rect {_C} x="14" y="4.5" width="4" height="15" rx="1.2"/>',
    "anterior": f'<path {_C} d="M19 5.6v12.8a.9.9 0 0 1-1.4.75L8.8 13a1.2 1.2 0 0 1 0-2l8.8-6.15A.9.9 0 0 1 19 5.6z"/><rect {_C} x="5" y="5" width="2.4" height="14" rx="1"/>',
    "proximo": f'<path {_C} d="M5 5.6v12.8a.9.9 0 0 0 1.4.75L15.2 13a1.2 1.2 0 0 0 0-2L6.4 4.85A.9.9 0 0 0 5 5.6z"/><rect {_C} x="16.6" y="5" width="2.4" height="14" rx="1"/>',
    "aleatorio": f'<g {_T}><path d="M16 3h5v5"/><path d="M4 20 21 3"/><path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/></g>',
    "repetir": f'<g {_T}><path d="M17 2l4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/></g>',
    "repetir1": f'<g {_T}><path d="M17 2l4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/><path d="M11 10.5l1.5-1v5"/></g>',
    "volume": f'<g {_T}><path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9.5 9.5 0 0 1 0 13"/></g>',
    "mudo": f'<g {_T}><path d="M11 5 6 9H3v6h3l5 4z"/><path d="M22 9l-6 6"/><path d="M16 9l6 6"/></g>',
    "lista": f'<g {_T}><path d="M9 6h12"/><path d="M9 12h12"/><path d="M9 18h12"/><path d="M4 6h.01"/><path d="M4 12h.01"/><path d="M4 18h.01"/></g>',
    "telacheia": f'<g {_T}><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></g>',
    "sairtela": f'<g {_T}><path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/><path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/></g>',
    "pasta": f'<g {_T}><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.2h7.5A2.5 2.5 0 0 1 21 9.7v7.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/></g>',
    "pastamais": f'<g {_T}><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.2h7.5A2.5 2.5 0 0 1 21 9.7v7.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/><path d="M12 10.5v6"/><path d="M9 13.5h6"/></g>',
    "foto": f'<g {_T}><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="M21 15.5l-4.6-4.6a1.5 1.5 0 0 0-2.1 0L5 20"/></g>',
    "video": f'<g {_T}><rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M10 9.2v5.6l4.6-2.8z"/></g>',
    "relogio": f'<g {_T}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></g>',
    "buscar": f'<g {_T}><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></g>',
    "explorer": f'<g {_T}><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/></g>',
    "limpar": f'<g {_T}><path d="M4 7h16"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12"/><path d="M9 7V4h6v3"/></g>',
    "seta": f'<g {_T}><path d="M6 9l6 6 6-6"/></g>',
    "atualizar": f'<g {_T}><path d="M21 12a9 9 0 0 1-15.5 6.2"/><path d="M3 12A9 9 0 0 1 18.5 5.8"/><path d="M18.5 2v3.8h-3.8"/><path d="M5.5 22v-3.8h3.8"/></g>',
    "bug": f'<g {_T}><rect x="7" y="7" width="10" height="13" rx="5"/><path d="M9.5 7V5.5a2.5 2.5 0 0 1 5 0V7"/><path d="M12 11v9"/><path d="M3 13h4"/><path d="M17 13h4"/><path d="M4 8l3 2"/><path d="M20 8l-3 2"/><path d="M4 19l3-2"/><path d="M20 19l-3-2"/></g>',
    "fechar": f'<g {_T}><path d="M6 6l12 12"/><path d="M18 6L6 18"/></g>',
    "copiar": f'<g {_T}><rect x="8.5" y="8.5" width="12" height="12" rx="2.5"/><path d="M15.5 8.5V5.5a2 2 0 0 0-2-2h-8a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h3"/></g>',
    "globo": f'<g {_T}><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18"/><path d="M12 3a14 14 0 0 0 0 18"/></g>',
    # bandeira do Brasil desenhada (o Windows não mostra a bandeira em emoji); cores fixas
    "bandeira_br": ('<rect x="1" y="4.5" width="22" height="15" rx="2.2" fill="#009c3b"/>'
                    '<path d="M12 6.4 21 12l-9 5.6L3 12z" fill="#ffdf00"/>'
                    '<circle cx="12" cy="12" r="3.6" fill="#002776"/>'
                    '<path d="M8.6 11.2a7 3.6 0 0 1 6.8 1.4" fill="none" stroke="#ffffff" stroke-width="0.8"/>'),
}

_cache: dict = {}


def icone(nome: str, cor: str = "#e9e9ee", tamanho: int = 24) -> QIcon:
    chave = (nome, cor, tamanho)
    if chave in _cache:
        return _cache[chave]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" color="{cor}">'
           + SVG[nome].replace("currentColor", cor) + "</svg>")
    ren = QSvgRenderer(QByteArray(svg.encode()))
    ic = QIcon()
    for escala in (1, 2):
        pm = QPixmap(tamanho * escala, tamanho * escala)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        ren.render(p, QRectF(0, 0, tamanho * escala, tamanho * escala))
        p.end()
        pm.setDevicePixelRatio(escala)
        ic.addPixmap(pm)
    _cache[chave] = ic
    return ic
