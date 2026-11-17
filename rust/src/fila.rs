//! Fila de reprodução, porta da `fila.py` da 1.5.1: em ordem ou aleatória, repetir nada / tudo /
//! um, e filtro Tudo / Fotos / Vídeos.
//!
//! O aleatório é um baralho: embaralha a fila inteira, toca cada item uma vez e só então
//! embaralha de novo (sem repetir o último que tocou logo no começo da rodada seguinte).

use crate::biblioteca::{Item, Tipo};
use crate::sorteio::Sorteio;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Filtro {
    Tudo,
    Fotos,
    Videos,
}

impl Filtro {
    pub const TODOS: [Filtro; 3] = [Filtro::Tudo, Filtro::Fotos, Filtro::Videos];
    pub fn nome(self) -> &'static str {
        match self {
            Filtro::Tudo => "tudo",
            Filtro::Fotos => "fotos",
            Filtro::Videos => "videos",
        }
    }
    pub fn de_nome(s: &str) -> Option<Self> {
        Self::TODOS.into_iter().find(|f| f.nome() == s)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Repetir {
    Nao,
    Tudo,
    Um,
}

impl Repetir {
    pub const TODOS: [Repetir; 3] = [Repetir::Nao, Repetir::Tudo, Repetir::Um];
    pub fn nome(self) -> &'static str {
        match self {
            Repetir::Nao => "nao",
            Repetir::Tudo => "tudo",
            Repetir::Um => "um",
        }
    }
    pub fn de_nome(s: &str) -> Option<Self> {
        Self::TODOS.into_iter().find(|r| r.nome() == s)
    }
}

pub struct Fila {
    pub itens: Vec<Item>,
    pub filtro: Filtro,
    pub aleatorio: bool,
    pub repetir: Repetir,
    /// Índices em `itens`, na ordem de tocar.
    ordem: Vec<usize>,
    /// Posição em `ordem` do item atual (-1 = antes do primeiro).
    pos: isize,
    rng: Sorteio,
}

impl Default for Fila {
    fn default() -> Self {
        Self::nova(None)
    }
}

impl Fila {
    pub fn nova(semente: Option<u64>) -> Self {
        Fila {
            itens: Vec::new(),
            filtro: Filtro::Tudo,
            aleatorio: false,
            repetir: Repetir::Tudo,
            ordem: Vec::new(),
            pos: -1,
            rng: semente.map(Sorteio::com_semente).unwrap_or_else(Sorteio::novo),
        }
    }

    // ---------- consulta ----------
    fn passa(&self, i: usize) -> bool {
        match self.filtro {
            Filtro::Fotos => self.itens[i].tipo == Tipo::Foto,
            Filtro::Videos => self.itens[i].tipo == Tipo::Video,
            Filtro::Tudo => true,
        }
    }

    pub fn visiveis(&self) -> Vec<usize> {
        (0..self.itens.len()).filter(|&i| self.passa(i)).collect()
    }

    pub fn indice_atual(&self) -> Option<usize> {
        usize::try_from(self.pos).ok().and_then(|p| self.ordem.get(p).copied())
    }

    pub fn atual(&self) -> Option<&Item> {
        self.indice_atual().map(|i| &self.itens[i])
    }

    pub fn ordem(&self) -> &[usize] {
        &self.ordem
    }

    /// (número do item atual começando em 1, total na fila).
    pub fn posicao(&self) -> (usize, usize) {
        let n = if self.indice_atual().is_some() { self.pos as usize + 1 } else { 0 };
        (n, self.ordem.len())
    }

    pub fn len(&self) -> usize {
        self.ordem.len()
    }

    pub fn is_empty(&self) -> bool {
        self.ordem.is_empty()
    }

    // ---------- montagem ----------
    fn baralho(&mut self, indices: &[usize], primeiro: Option<usize>, evitar_primeiro: Option<usize>) -> Vec<usize> {
        let mut resto: Vec<usize> = indices.iter().copied().filter(|&i| Some(i) != primeiro).collect();
        self.rng.embaralhar(&mut resto);
        if let Some(ev) = evitar_primeiro {
            if resto.len() > 1 && resto[0] == ev {
                let j = self.rng.faixa(1, resto.len());
                resto.swap(0, j);
            }
        }
        primeiro.into_iter().chain(resto).collect()
    }

    fn remontar(&mut self) {
        let atual = self.indice_atual();
        let vis = self.visiveis();
        let manter = atual.filter(|&a| self.passa(a));
        if self.aleatorio {
            self.ordem = self.baralho(&vis, manter, None);
            self.pos = if manter.is_some() { 0 } else { -1 };
        } else {
            self.pos = match manter {
                Some(m) => vis.iter().position(|&i| i == m).map_or(-1, |p| p as isize),
                None => -1,
            };
            self.ordem = vis;
        }
    }

    pub fn definir_itens(&mut self, itens: Vec<Item>) {
        self.itens = itens;
        self.pos = -1;
        self.ordem.clear();
        self.remontar();
    }

    /// Junta itens à fila sem interromper o que está tocando.
    pub fn adicionar(&mut self, novos: Vec<Item>) {
        if novos.is_empty() {
            return;
        }
        let base = self.itens.len();
        self.itens.extend(novos);
        let novos_idx: Vec<usize> = (base..self.itens.len()).filter(|&i| self.passa(i)).collect();
        if self.aleatorio {
            let inicio = (self.pos + 1) as usize;
            for i in novos_idx {
                let onde = self.rng.entre(inicio, self.ordem.len());
                self.ordem.insert(onde, i);
            }
        } else {
            let atual = self.indice_atual();
            self.ordem = self.visiveis();
            self.pos = match atual {
                Some(a) => self.ordem.iter().position(|&i| i == a).map_or(-1, |p| p as isize),
                None => -1,
            };
        }
    }

    pub fn limpar(&mut self) {
        self.itens.clear();
        self.ordem.clear();
        self.pos = -1;
    }

    // ---------- modos ----------
    pub fn definir_aleatorio(&mut self, ligado: bool) {
        if ligado != self.aleatorio {
            self.aleatorio = ligado;
            self.remontar();
        }
    }

    /// Troca o filtro. Devolve `true` se o item atual continua na fila.
    pub fn definir_filtro(&mut self, filtro: Filtro) -> bool {
        self.filtro = filtro;
        self.remontar();
        self.indice_atual().is_some()
    }

    pub fn definir_repetir(&mut self, modo: Repetir) {
        self.repetir = modo;
    }

    pub fn proximo_modo_repetir(&mut self) -> Repetir {
        let i = Repetir::TODOS.iter().position(|&r| r == self.repetir).unwrap_or(0);
        self.repetir = Repetir::TODOS[(i + 1) % Repetir::TODOS.len()];
        self.repetir
    }

    // ---------- navegação ----------
    /// Avança e devolve o índice (em `itens`) do que toca agora. `automatico` quando o item acabou
    /// sozinho (fim do vídeo ou do tempo da foto): aí "repetir um" repete o mesmo.
    /// `None` = fim da fila (ou tudo falhou).
    pub fn proximo(&mut self, automatico: bool) -> Option<usize> {
        if self.ordem.is_empty() {
            return None;
        }
        if automatico && self.repetir == Repetir::Um {
            if let Some(a) = self.indice_atual() {
                return Some(a);
            }
        }
        for _ in 0..=self.ordem.len() {
            self.pos += 1;
            if self.pos as usize >= self.ordem.len() {
                if self.repetir == Repetir::Nao {
                    self.pos = self.ordem.len() as isize - 1;
                    return None;
                }
                let ultimo = *self.ordem.last().expect("fila não vazia");
                if self.aleatorio {
                    let ordem = std::mem::take(&mut self.ordem);
                    self.ordem = self.baralho(&ordem, None, Some(ultimo));
                }
                self.pos = 0;
            }
            let i = self.ordem[self.pos as usize];
            if !self.itens[i].falhou {
                return Some(i);
            }
        }
        None // tudo na fila falhou
    }

    pub fn anterior(&mut self) -> Option<usize> {
        if self.ordem.is_empty() {
            return None;
        }
        for _ in 0..=self.ordem.len() {
            if self.pos <= 0 {
                if self.repetir == Repetir::Nao || self.pos < 0 {
                    self.pos = 0;
                    let i = self.ordem[0];
                    return if !self.itens[i].falhou { Some(i) } else { self.proximo(false) };
                }
                self.pos = self.ordem.len() as isize - 1;
            } else {
                self.pos -= 1;
            }
            let i = self.ordem[self.pos as usize];
            if !self.itens[i].falhou {
                return Some(i);
            }
        }
        None
    }

    /// Toca um item escolhido na lista (índice em `itens`).
    pub fn ir_para(&mut self, indice_item: usize) -> Option<usize> {
        let p = self.ordem.iter().position(|&i| i == indice_item)?;
        self.pos = p as isize;
        Some(indice_item)
    }

    /// Tira itens da fila (não apaga arquivo nenhum).
    pub fn remover(&mut self, indices_itens: &[usize]) {
        let tirar: std::collections::HashSet<usize> = indices_itens.iter().copied().filter(|&i| i < self.itens.len()).collect();
        if tirar.is_empty() {
            return;
        }
        let atual = self.indice_atual();
        let pos_antiga = self.pos;
        // Índice novo de cada item que fica (os que saem viram None).
        let mut mapa: Vec<Option<usize>> = Vec::with_capacity(self.itens.len());
        let mut n = 0;
        for i in 0..self.itens.len() {
            if tirar.contains(&i) {
                mapa.push(None);
            } else {
                mapa.push(Some(n));
                n += 1;
            }
        }
        let ordem_antiga = std::mem::take(&mut self.ordem);
        let itens = std::mem::take(&mut self.itens);
        self.itens = itens.into_iter().enumerate().filter(|(i, _)| !tirar.contains(i)).map(|(_, it)| it).collect();
        self.ordem = ordem_antiga.iter().filter_map(|&i| mapa[i]).collect();
        match atual {
            Some(a) if !tirar.contains(&a) => {
                let novo = mapa[a].expect("atual fica");
                self.pos = self.ordem.iter().position(|&i| i == novo).map_or(-1, |p| p as isize);
            }
            _ => {
                // O atual saiu: o próximo `proximo()` toca o que vinha depois dele.
                let ate = pos_antiga.max(0) as usize;
                let antes = ordem_antiga[..ate.min(ordem_antiga.len())].iter().filter(|&&i| mapa[i].is_some()).count();
                self.pos = antes as isize - 1;
            }
        }
    }

    /// Volta para o começo (no aleatório, embaralha uma rodada nova).
    pub fn reiniciar(&mut self) -> Option<usize> {
        if self.aleatorio {
            let ultimo = self.indice_atual();
            let vis = self.visiveis();
            self.ordem = self.baralho(&vis, None, ultimo);
        }
        self.pos = -1;
        self.proximo(false)
    }
}
