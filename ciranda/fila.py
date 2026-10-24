"""Fila de reprodução: em ordem ou aleatória, com repetir nada / tudo / um,
e filtro Tudo / Fotos / Vídeos.

O aleatório funciona como baralho: embaralha a fila inteira, toca cada item uma
vez e só então embaralha de novo (sem repetir o último que tocou logo no
começo da rodada seguinte). Sorteio puro, a cada item, repete arquivo antes de
passar por todos, que é a queixa nº 1 de aleatório em player.
"""

from __future__ import annotations

import random

from .biblioteca import Item

FILTROS = ("tudo", "fotos", "videos")
REPETIR = ("nao", "tudo", "um")


class Fila:
    def __init__(self, semente: int | None = None):
        self.itens: list[Item] = []
        self.filtro = "tudo"
        self.aleatorio = False
        self.repetir = "tudo"
        self._ordem: list[int] = []   # índices em self.itens, na ordem de tocar
        self._pos = -1                # posição em _ordem do item atual
        self._rng = random.Random(semente)

    # ---------- consulta ----------
    def _passa(self, i: int) -> bool:
        tipo = self.itens[i].tipo
        if self.filtro == "fotos":
            return tipo == "foto"
        if self.filtro == "videos":
            return tipo == "video"
        return True

    def visiveis(self) -> list[int]:
        return [i for i in range(len(self.itens)) if self._passa(i)]

    @property
    def indice_atual(self) -> int | None:
        if 0 <= self._pos < len(self._ordem):
            return self._ordem[self._pos]
        return None

    @property
    def atual(self) -> Item | None:
        i = self.indice_atual
        return self.itens[i] if i is not None else None

    @property
    def ordem(self) -> list[int]:
        return list(self._ordem)

    def posicao(self) -> tuple[int, int]:
        """(número do item atual começando em 1, total na fila)."""
        return (self._pos + 1 if self.indice_atual is not None else 0, len(self._ordem))

    def __len__(self):
        return len(self._ordem)

    # ---------- montagem ----------
    def _baralho(self, indices: list[int], primeiro: int | None = None,
                 evitar_primeiro: int | None = None) -> list[int]:
        resto = [i for i in indices if i != primeiro]
        self._rng.shuffle(resto)
        if evitar_primeiro is not None and len(resto) > 1 and resto[0] == evitar_primeiro:
            j = self._rng.randrange(1, len(resto))
            resto[0], resto[j] = resto[j], resto[0]
        return ([primeiro] if primeiro is not None else []) + resto

    def _remontar(self):
        atual = self.indice_atual
        vis = self.visiveis()
        manter = atual if atual is not None and self._passa(atual) else None
        if self.aleatorio:
            self._ordem = self._baralho(vis, primeiro=manter)
            self._pos = 0 if manter is not None else -1
        else:
            self._ordem = vis
            self._pos = vis.index(manter) if manter is not None else -1

    def definir_itens(self, itens: list[Item]):
        self.itens = list(itens)
        self._pos = -1
        self._ordem = []
        self._remontar()

    def adicionar(self, novos: list[Item]):
        """Junta itens à fila sem interromper o que está tocando."""
        if not novos:
            return
        base = len(self.itens)
        self.itens.extend(novos)
        novos_idx = [i for i in range(base, len(self.itens)) if self._passa(i)]
        if self.aleatorio:
            inicio = self._pos + 1
            for i in novos_idx:
                self._ordem.insert(self._rng.randint(inicio, len(self._ordem)), i)
        else:
            atual = self.indice_atual
            self._ordem = self.visiveis()
            self._pos = self._ordem.index(atual) if atual is not None else -1

    def limpar(self):
        self.itens, self._ordem, self._pos = [], [], -1

    # ---------- modos ----------
    def definir_aleatorio(self, ligado: bool):
        if ligado != self.aleatorio:
            self.aleatorio = ligado
            self._remontar()

    def definir_filtro(self, filtro: str) -> bool:
        """Troca o filtro. Devolve True se o item atual continua na fila."""
        if filtro not in FILTROS:
            raise ValueError(filtro)
        self.filtro = filtro
        self._remontar()
        return self.indice_atual is not None

    def definir_repetir(self, modo: str):
        if modo not in REPETIR:
            raise ValueError(modo)
        self.repetir = modo

    def proximo_modo_repetir(self) -> str:
        self.repetir = REPETIR[(REPETIR.index(self.repetir) + 1) % len(REPETIR)]
        return self.repetir

    # ---------- navegação ----------
    def proximo(self, automatico: bool = False) -> Item | None:
        """Avança. `automatico=True` quando o item acabou sozinho (fim do vídeo
        ou do tempo da foto): aí 'repetir um' repete o mesmo. None = fim da fila."""
        if not self._ordem:
            return None
        if automatico and self.repetir == "um" and self.atual is not None:
            return self.atual
        for _ in range(len(self._ordem) + 1):
            self._pos += 1
            if self._pos >= len(self._ordem):
                if self.repetir == "nao":
                    self._pos = len(self._ordem) - 1
                    return None
                ultimo = self._ordem[-1]
                if self.aleatorio:
                    self._ordem = self._baralho(self._ordem, evitar_primeiro=ultimo)
                self._pos = 0
            item = self.itens[self._ordem[self._pos]]
            if not item.falhou:
                return item
        return None  # tudo na fila falhou

    def anterior(self) -> Item | None:
        if not self._ordem:
            return None
        for _ in range(len(self._ordem) + 1):
            if self._pos <= 0:
                if self.repetir == "nao" or self._pos < 0:
                    self._pos = 0
                    item = self.itens[self._ordem[0]]
                    return item if not item.falhou else self.proximo()
                self._pos = len(self._ordem) - 1
            else:
                self._pos -= 1
            item = self.itens[self._ordem[self._pos]]
            if not item.falhou:
                return item
        return None

    def ir_para(self, indice_item: int) -> Item | None:
        """Toca um item escolhido na lista (índice em self.itens)."""
        if indice_item not in self._ordem:
            return None
        self._pos = self._ordem.index(indice_item)
        return self.itens[indice_item]

    def espiar_proximo(self) -> Item | None:
        """O item que vem depois, sem andar a fila (para preparar HEIC antes)."""
        if self._pos + 1 < len(self._ordem):
            return self.itens[self._ordem[self._pos + 1]]
        return None

    def remover(self, indices_itens):
        """Tira itens da fila (não apaga arquivo nenhum)."""
        tirar = set(indices_itens)
        if not tirar:
            return
        atual = self.indice_atual
        ordem_objs = [self.itens[i] for i in self._ordem]
        pos_antiga = self._pos
        novos = [it for i, it in enumerate(self.itens) if i not in tirar]
        mapa = {id(it): n for n, it in enumerate(novos)}
        self.itens = novos
        self._ordem = [mapa[id(o)] for o in ordem_objs if id(o) in mapa]
        if atual is not None and atual not in tirar:
            obj = ordem_objs[pos_antiga]
            self._pos = self._ordem.index(mapa[id(obj)])
        else:
            # o atual saiu: o próximo "proximo()" toca o que vinha depois dele
            antes = sum(1 for o in ordem_objs[:max(pos_antiga, 0)] if id(o) in mapa)
            self._pos = antes - 1

    def reiniciar(self) -> Item | None:
        """Volta para o começo (no aleatório, embaralha uma rodada nova)."""
        if self.aleatorio:
            ultimo = self.indice_atual
            self._ordem = self._baralho(self.visiveis(), evitar_primeiro=ultimo)
        self._pos = -1
        return self.proximo()
