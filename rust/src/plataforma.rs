//! Tudo o que o player faz fora dele mesmo: janela do Windows (tela cheia, título, onde o vídeo
//! fica), Explorer, área de transferência e as janelas de escolher pasta ou arquivos.
//!
//! O app de verdade usa a implementação Win32 (no executável). No modo de teste (REGRA 13) e
//! nos testes da interface entra o `Registro`: grava cada pedido e não abre nada.

use std::cell::{Cell, RefCell};
use std::collections::VecDeque;
use std::path::{Path, PathBuf};

/// O que a janela de escolher pede.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Escolha {
    Pasta,
    Arquivos,
}

/// Quem recebe a resposta da janela de escolher.
pub type Resposta = Box<dyn FnOnce(Vec<PathBuf>) + Send>;

pub trait Plataforma {
    /// Liga ou desliga a tela cheia da janela.
    fn tela_cheia(&self, ligar: bool);
    fn em_tela_cheia(&self) -> bool;
    /// Onde o vídeo fica, em pixels físicos da área cliente (o resto é barra e fila).
    fn definir_palco(&self, x: i32, y: i32, largura: i32, altura: i32);
    /// Título da janela (barra de título e barra de tarefas).
    fn titulo(&self, texto: &str);
    /// Posição do cursor na tela, em pixels físicos (para ver se o mouse mexeu na tela cheia).
    fn cursor(&self) -> Option<(i32, i32)>;
    /// O cursor está sobre a faixa de baixo da área cliente, de `altura` pixels físicos?
    fn cursor_na_faixa_de_baixo(&self, altura: i32) -> bool;
    /// Ctrl apertado agora (soltar com Ctrl junta à fila).
    fn ctrl_apertado(&self) -> bool;
    fn mostrar_no_explorer(&self, caminho: &Path) -> bool;
    fn copiar_texto(&self, texto: &str) -> bool;
    /// Abre a janela de escolher pasta ou arquivos e entrega o que a pessoa escolheu a
    /// `responder` (vazio se cancelou). Pode responder depois e de outra thread: com a janela
    /// aberta, o player continua (foto passa, vídeo acaba e troca), como na 1.5.1, em que o Qt
    /// roda os timers durante o diálogo.
    fn escolher(&self, escolha: Escolha, titulo: &str, inicio: Option<&Path>, responder: Resposta);
    /// Só grava os pedidos, não faz nada de verdade (modo de teste e testes da interface).
    fn so_registra(&self) -> bool {
        false
    }
}

/// Plataforma que só grava: nada aparece, nada é aberto, a área de transferência do Windows não
/// muda. As escolhas de pasta e arquivos vêm de respostas prontas (`responder_*`).
#[derive(Default)]
pub struct Registro {
    pub pedidos: RefCell<Vec<String>>,
    tela_cheia: Cell<bool>,
    pub palco: Cell<(i32, i32, i32, i32)>,
    pub titulo_atual: RefCell<String>,
    pub area_de_transferencia: RefCell<Option<String>>,
    pub respostas_pasta: RefCell<VecDeque<Option<PathBuf>>>,
    pub respostas_arquivos: RefCell<VecDeque<Vec<PathBuf>>>,
    /// Segura a resposta da janela de escolher (o teste responde com `responder_agora`), para
    /// ver o player andando com a janela aberta.
    pub segurar_escolha: Cell<bool>,
    pub escolha_pendente: RefCell<Option<(Escolha, Resposta)>>,
    pub cursor_pos: Cell<Option<(i32, i32)>>,
    pub cursor_na_barra: Cell<bool>,
    pub ctrl: Cell<bool>,
}

impl Registro {
    pub fn novo() -> Self {
        Registro::default()
    }
    fn anotar(&self, s: String) {
        self.pedidos.borrow_mut().push(s);
    }
    pub fn responder_pasta(&self, p: Option<PathBuf>) {
        self.respostas_pasta.borrow_mut().push_back(p);
    }
    pub fn responder_arquivos(&self, v: Vec<PathBuf>) {
        self.respostas_arquivos.borrow_mut().push_back(v);
    }
    /// Entrega a resposta segurada (`segurar_escolha`) com a próxima resposta pronta.
    pub fn responder_agora(&self) -> bool {
        let Some((escolha, responder)) = self.escolha_pendente.borrow_mut().take() else { return false };
        responder(self.proxima_resposta(escolha));
        true
    }
    fn proxima_resposta(&self, escolha: Escolha) -> Vec<PathBuf> {
        match escolha {
            Escolha::Pasta => self.respostas_pasta.borrow_mut().pop_front().flatten().into_iter().collect(),
            Escolha::Arquivos => self.respostas_arquivos.borrow_mut().pop_front().unwrap_or_default(),
        }
    }
    /// Os pedidos que começam com `prefixo` (ex.: "explorer").
    pub fn pedidos_de(&self, prefixo: &str) -> Vec<String> {
        self.pedidos.borrow().iter().filter(|p| p.starts_with(prefixo)).cloned().collect()
    }
}

impl Plataforma for Registro {
    fn so_registra(&self) -> bool {
        true
    }
    fn tela_cheia(&self, ligar: bool) {
        self.anotar(format!("tela-cheia {ligar}"));
        self.tela_cheia.set(ligar);
    }
    fn em_tela_cheia(&self) -> bool {
        self.tela_cheia.get()
    }
    fn definir_palco(&self, x: i32, y: i32, largura: i32, altura: i32) {
        self.palco.set((x, y, largura, altura));
    }
    fn titulo(&self, texto: &str) {
        *self.titulo_atual.borrow_mut() = texto.to_string();
    }
    fn cursor(&self) -> Option<(i32, i32)> {
        self.cursor_pos.get()
    }
    fn cursor_na_faixa_de_baixo(&self, _altura: i32) -> bool {
        self.cursor_na_barra.get()
    }
    fn ctrl_apertado(&self) -> bool {
        self.ctrl.get()
    }
    fn mostrar_no_explorer(&self, caminho: &Path) -> bool {
        self.anotar(format!("explorer {}", caminho.display()));
        true
    }
    fn copiar_texto(&self, texto: &str) -> bool {
        self.anotar(format!("copiar {texto}"));
        *self.area_de_transferencia.borrow_mut() = Some(texto.to_string());
        true
    }
    fn escolher(&self, escolha: Escolha, titulo: &str, inicio: Option<&Path>, responder: Resposta) {
        let nome = if escolha == Escolha::Pasta { "escolher-pasta" } else { "escolher-arquivos" };
        self.anotar(format!("{nome} {titulo} | {}", inicio.map(|p| p.display().to_string()).unwrap_or_default()));
        if self.segurar_escolha.get() {
            *self.escolha_pendente.borrow_mut() = Some((escolha, responder));
        } else {
            responder(self.proxima_resposta(escolha));
        }
    }
}
