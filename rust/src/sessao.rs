//! A parte da `janela.py` da 1.5.1 que decide o que tocar, sem interface nem motor: abrir ou
//! juntar pastas, varredura pronta, próximo/anterior, fim de foto e de vídeo, arquivo que falha,
//! aleatório, repetir e filtro. A janela só executa o `Passo` que volta daqui.

use std::path::{Path, PathBuf};

use crate::biblioteca::{Estatisticas, Item, Tipo, absoluto};
use crate::config::Config;
use crate::fila::{Fila, Filtro, Repetir};

/// O que a janela faz depois de uma decisão.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Passo {
    Nada,
    /// Tocar este índice de `fila.itens`.
    Tocar(usize),
    /// Acabou a fila (pausa e mostra "fim da fila").
    FimDaFila,
    /// Nenhum arquivo da fila abriu: para com aviso.
    NenhumAbriu,
    /// O filtro esconde tudo: para o motor e avisa.
    NadaComFiltro,
    /// A varredura não achou foto nem vídeo (a fila não muda).
    NenhumaMidia,
    /// Itens juntados à fila sem trocar o que toca.
    Juntou,
    /// Um arquivo não abriu: daqui a 50 ms, `pular_falho()`.
    PularFalho,
}

/// Uma varredura a fazer: os caminhos já conferidos e se junta ou troca a fila.
#[derive(Debug, Clone, PartialEq)]
pub struct Carga {
    pub caminhos: Vec<PathBuf>,
    pub juntar: bool,
}

pub struct Sessao {
    pub cfg: Config,
    /// Onde o config é salvo.
    pub pasta_dados: PathBuf,
    pub fila: Fila,
    pub pastas_abertas: Vec<PathBuf>,
    /// Índice em `fila.itens` do que está na tela.
    pub item: Option<usize>,
    pub fim_da_fila: bool,
    erros_seguidos: usize,
}

impl Sessao {
    pub fn nova(cfg: Config, pasta_dados: &Path, semente: Option<u64>) -> Self {
        let mut fila = Fila::nova(semente);
        fila.aleatorio = cfg.aleatorio();
        fila.repetir = cfg.repetir();
        fila.filtro = cfg.filtro();
        Sessao {
            cfg,
            pasta_dados: pasta_dados.to_path_buf(),
            fila,
            pastas_abertas: Vec::new(),
            item: None,
            fim_da_fila: false,
            erros_seguidos: 0,
        }
    }

    pub fn salvar(&self) -> std::io::Result<()> {
        self.cfg.salvar(&self.pasta_dados)
    }

    pub fn item_atual(&self) -> Option<&Item> {
        self.item.and_then(|i| self.fila.itens.get(i))
    }

    fn tocar(&mut self, i: Option<usize>) -> Passo {
        match i {
            Some(i) => {
                self.fim_da_fila = false;
                self.item = Some(i);
                Passo::Tocar(i)
            }
            None => self.fim(Passo::FimDaFila),
        }
    }

    fn fim(&mut self, p: Passo) -> Passo {
        self.fim_da_fila = true;
        p
    }

    /// `carregar()`: confere os caminhos (absolutos, que existem) e diz o que varrer.
    /// `None` = nada que exista.
    pub fn preparar_carga(&mut self, caminhos: &[PathBuf], adicionar: bool) -> Option<Carga> {
        let caminhos: Vec<PathBuf> =
            caminhos.iter().filter(|c| !c.as_os_str().is_empty() && c.exists()).map(|c| absoluto(c)).collect();
        if caminhos.is_empty() {
            return None;
        }
        if !adicionar || self.fila.itens.is_empty() {
            self.pastas_abertas = caminhos.clone();
        } else {
            // Como a 1.5.1 (`+= [c for c in caminhos if c not in self.pastas_abertas]`): confere
            // contra a lista de antes, então o mesmo caminho duas vezes no mesmo pedido entra duas.
            let antes = self.pastas_abertas.len();
            for c in &caminhos {
                if !self.pastas_abertas[..antes].contains(c) {
                    self.pastas_abertas.push(c.clone());
                }
            }
        }
        let juntar = adicionar && !self.fila.itens.is_empty();
        Some(Carga { caminhos, juntar })
    }

    /// As linhas de log da varredura, iguais às da 1.5.1.
    pub fn linhas_da_varredura(&self, itens: &[Item], stats: &Estatisticas) -> Vec<String> {
        let mut v = vec![format!(
            "varredura: {} pastas abertas, {} pastas lidas, {} fotos/vídeos, {} arquivos de outros tipos",
            self.pastas_abertas.len(),
            stats.pastas_lidas,
            itens.len(),
            stats.total_ignorados()
        )];
        if !stats.ignorados.is_empty() {
            let lista: Vec<String> = stats.mais_comuns(25).into_iter().map(|(e, n)| format!("{e} {n}")).collect();
            v.push(format!("  outros tipos (não são foto/vídeo): {}", lista.join(", ")));
        }
        v.extend(stats.sem_acesso.iter().take(200).map(|p| format!("  sem acesso: {p}")));
        v.extend(stats.puladas.iter().take(200).map(|p| format!("  pulada: {p}")));
        v
    }

    /// `_varredura_pronta()`.
    pub fn varredura_pronta(&mut self, itens: Vec<Item>, juntar: bool) -> Passo {
        if itens.is_empty() && !juntar {
            return Passo::NenhumaMidia;
        }
        let pastas: Vec<PathBuf> = self.pastas_abertas.iter().filter(|p| p.is_dir()).cloned().collect();
        if !pastas.is_empty() {
            // Abrir só arquivos (dois cliques numa foto) não mexe no Continuar.
            self.cfg.definir_ultimas_pastas(&pastas);
            let _ = self.salvar();
        }
        if juntar {
            self.fila.adicionar(itens);
            return Passo::Juntou;
        }
        self.fila.definir_itens(itens);
        self.item = None;
        self.fim_da_fila = false;
        self.erros_seguidos = 0;
        let i = self.fila.proximo(false);
        if i.is_none() && self.fila.filtro != Filtro::Tudo && !self.fila.itens.is_empty() {
            // O filtro escondeu tudo (ex.: "Vídeos" numa pasta só de fotos).
            return self.definir_filtro(Filtro::Tudo);
        }
        self.tocar(i)
    }

    /// Botão/tecla "próximo" (`automatico=false`) ou fim natural (`true`).
    pub fn proximo(&mut self, automatico: bool) -> Passo {
        if self.fila.itens.is_empty() {
            return Passo::Nada;
        }
        self.erros_seguidos = 0;
        let i = self.fila.proximo(automatico);
        match i {
            None => self.fim(Passo::FimDaFila),
            Some(_) => self.tocar(i),
        }
    }

    /// "Anterior" (o "vídeo com mais de 3 s volta ao começo" fica com quem tem o motor).
    pub fn anterior(&mut self) -> Passo {
        if self.fila.itens.is_empty() {
            return Passo::Nada;
        }
        self.erros_seguidos = 0;
        let i = self.fila.anterior();
        self.tocar(i)
    }

    /// O tempo da foto acabou.
    pub fn foto_acabou(&mut self) -> Passo {
        let Some(tipo) = self.item_atual().map(|i| i.tipo) else { return Passo::Nada };
        if tipo != Tipo::Foto {
            return Passo::Nada;
        }
        if self.fila.len() <= 1 {
            // Uma foto só (aberta com dois cliques): fica na tela, sem piscar.
            return if self.fila.repetir == Repetir::Nao { self.fim(Passo::FimDaFila) } else { Passo::Nada };
        }
        self.erros_seguidos = 0;
        let i = self.fila.proximo(true);
        self.tocar(i)
    }

    /// O vídeo chegou ao fim.
    pub fn video_acabou(&mut self) -> Passo {
        if self.item_atual().map(|i| i.tipo) != Some(Tipo::Video) {
            return Passo::Nada;
        }
        self.erros_seguidos = 0;
        let i = self.fila.proximo(true);
        self.tocar(i)
    }

    /// O motor não abriu o arquivo da tela: marca; se nenhum abre, para. Senão devolve
    /// `PularFalho`: a janela espera 50 ms e chama `pular_falho`, que só então escolhe o próximo
    /// (como o `QTimer.singleShot(50, lambda: self.tocar(self.fila.proximo(...)))` da 1.5.1: uma
    /// tecla de filtro nesses 50 ms já vale para a escolha).
    pub fn arquivo_falhou(&mut self) -> Passo {
        let Some(i) = self.item else { return Passo::Nada };
        if let Some(it) = self.fila.itens.get_mut(i) {
            it.falhou = true;
        }
        self.erros_seguidos += 1;
        if self.erros_seguidos >= self.fila.len().max(1) {
            return self.fim(Passo::NenhumAbriu);
        }
        Passo::PularFalho
    }

    /// Os 50 ms depois de um arquivo que falhou: o próximo da fila, com o filtro de agora.
    pub fn pular_falho(&mut self) -> Passo {
        let i = self.fila.proximo(false);
        self.tocar(i)
    }

    /// Tocar/pausar quando não há o que pausar: no fim da fila recomeça, sem item toca o
    /// primeiro. `None` = é só pausar ou tocar o que está na tela.
    pub fn tocar_sem_item(&mut self) -> Option<Passo> {
        if self.fila.itens.is_empty() {
            return Some(Passo::Nada);
        }
        if self.fim_da_fila {
            let i = self.fila.reiniciar();
            return Some(self.tocar(i));
        }
        if self.item.is_none() {
            let i = self.fila.proximo(false);
            return Some(self.tocar(i));
        }
        None
    }

    pub fn alternar_aleatorio(&mut self) -> bool {
        let novo = !self.fila.aleatorio;
        self.fila.definir_aleatorio(novo);
        self.cfg.definir_aleatorio(novo);
        novo
    }

    pub fn ciclar_repetir(&mut self) -> Repetir {
        let r = self.fila.proximo_modo_repetir();
        self.cfg.definir_repetir(r);
        r
    }

    pub fn definir_filtro(&mut self, filtro: Filtro) -> Passo {
        if filtro == self.fila.filtro {
            return Passo::Nada;
        }
        let continua = self.fila.definir_filtro(filtro);
        self.cfg.definir_filtro(filtro);
        if !self.fila.itens.is_empty() && !continua {
            let i = self.fila.proximo(false);
            if i.is_none() {
                self.item = None;
                return Passo::NadaComFiltro;
            }
            return self.tocar(i);
        }
        Passo::Nada
    }
}
