//! O player: a lógica da `janela.py` da 1.5.1 ligada à interface Slint (`ui/app.slint`).
//!
//! Tudo o que sai do processo passa por dois traços: `Motor` (o mpv, ou um falso nos testes) e
//! `Plataforma` (janela do Windows, Explorer, área de transferência, escolher pasta). O tempo vem
//! de um relógio injetado, para os testes andarem com o tempo de mentira do Slint.
//!
//! O que chega de outras threads (varredura, leitura do giro do HEIC) entra pelo `correio`; quem
//! criou o player diz como acordá-lo (`acordar`). O que o motor manda é lido em `drenar_motor`.

use std::cell::{Cell, RefCell};
use std::collections::{BTreeSet, HashSet};
use std::path::{Path, PathBuf};
use std::rc::{Rc, Weak};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::time::Duration;

use serde_json::Value;
use slint::{ComponentHandle, Model, ModelRc, SharedString, Timer, TimerMode, VecModel};

use crate::biblioteca::{Estatisticas, Item, Tipo, normcase, varrer_varios};
use crate::fila::{Filtro, Repetir};
use crate::heif;
use crate::motor::{Evento, FIM_POR_ERRO, Motor, Valor};
use crate::plataforma::{Escolha, Plataforma};
use crate::sessao::{Passo, Sessao};
use crate::textos::{t, tf};
use crate::ui::{Camada, LinhaFila, LinhaMenu, Textos};

pub const NOME: &str = "Ciranda";
/// HEIC que não aparece: recarrega até 5 vezes, com espera que cresce (foto grande demora).
pub const HEIC_TENTATIVAS: u32 = 5;
const HEIC_ESPERA_S: f64 = 1.5;
const HEIC_PASSO_S: f64 = 1.0;
/// Os tempos prontos do botão "Foto: 5 s".
pub const OPCOES_FOTO: [i64; 9] = [2, 3, 5, 8, 10, 15, 20, 30, 60];
/// Tela cheia: os controles somem depois de 2,5 s sem mexer o mouse.
const ESCONDER: Duration = Duration::from_millis(2500);

/// O que outras threads mandam para a interface.
pub enum Correio {
    Progresso { geracao: u64, n: usize, pasta: String },
    Varreu { geracao: u64, itens: Vec<Item>, juntar: bool, stats: Estatisticas, segundos: f64 },
    Giro { token: u64, filtro: String },
    /// A janela de escolher fechou (vazio = cancelou).
    Escolheu { arquivos: bool, juntar: bool, caminhos: Vec<PathBuf> },
}

/// Uma ação de tecla (ou de botão). O nome vai para o log.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Acao {
    TocarPausar,
    Proximo,
    Anterior,
    Pular(f64),
    Volume(i64),
    Mudo,
    AlternarTelaCheia,
    Esc,
    Aleatorio,
    Repetir,
    Painel,
    Explorer,
    FotoMais,
    FotoMenos,
    AbrirPasta,
    JuntarPasta,
    Filtro(Filtro),
    Buscar,
}

impl Acao {
    /// Ações que ligam e desligam: segurar a tecla não fica alternando (decisão da fase 1).
    fn alterna(self) -> bool {
        matches!(
            self,
            Acao::TocarPausar
                | Acao::AlternarTelaCheia
                | Acao::Esc
                | Acao::Mudo
                | Acao::Aleatorio
                | Acao::Repetir
                | Acao::Painel
                | Acao::Explorer
                | Acao::AbrirPasta
                | Acao::JuntarPasta
                | Acao::Buscar
                | Acao::Filtro(_)
        )
    }
}

/// Os atalhos da 1.5.1 (`_atalhos`), com o jeito do Qt de casar teclas: letra só sem Shift, Ctrl
/// ou Alt; "+" vale com ou sem Shift. `texto` é o texto de tecla do Slint (ou "midia-proximo" /
/// "midia-anterior", que o executável manda para as teclas de mídia).
pub fn acao_da_tecla(texto: &str, shift: bool, ctrl: bool, alt: bool) -> Option<Acao> {
    use slint::platform::Key;
    let e = |k: Key| texto == SharedString::from(k).as_str();
    if alt {
        return None;
    }
    if ctrl {
        // Ctrl+letra às vezes chega como caractere de controle (Ctrl+O = 0x0F).
        let mut l = texto.to_lowercase();
        if let [c] = texto.as_bytes() {
            if (1..=26).contains(c) {
                l = ((b'a' + c - 1) as char).to_string();
            }
        }
        return match (l.as_str(), shift) {
            ("o", false) => Some(Acao::AbrirPasta),
            ("o", true) => Some(Acao::JuntarPasta),
            ("f", false) => Some(Acao::Buscar),
            _ => None,
        };
    }
    if e(Key::RightArrow) {
        return Some(Acao::Pular(if shift { 30.0 } else { 5.0 }));
    }
    if e(Key::LeftArrow) {
        return Some(Acao::Pular(if shift { -30.0 } else { -5.0 }));
    }
    if texto == "+" || texto == "=" {
        return Some(Acao::FotoMais);
    }
    if shift {
        return None;
    }
    Some(match texto {
        " " => Acao::TocarPausar,
        "midia-proximo" => Acao::Proximo,
        "midia-anterior" => Acao::Anterior,
        "-" => Acao::FotoMenos,
        "1" => Acao::Filtro(Filtro::Tudo),
        "2" => Acao::Filtro(Filtro::Fotos),
        "3" => Acao::Filtro(Filtro::Videos),
        _ if e(Key::PageDown) => Acao::Proximo,
        _ if e(Key::PageUp) => Acao::Anterior,
        _ if e(Key::UpArrow) => Acao::Volume(5),
        _ if e(Key::DownArrow) => Acao::Volume(-5),
        _ if e(Key::Return) || e(Key::F11) => Acao::AlternarTelaCheia,
        _ if e(Key::Escape) => Acao::Esc,
        _ => match texto.to_lowercase().as_str() {
            "k" => Acao::TocarPausar,
            "n" => Acao::Proximo,
            "p" => Acao::Anterior,
            "m" => Acao::Mudo,
            "f" => Acao::AlternarTelaCheia,
            "s" => Acao::Aleatorio,
            "r" => Acao::Repetir,
            "l" => Acao::Painel,
            "e" => Acao::Explorer,
            _ => return None,
        },
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Pergunta {
    LimparTudo,
    OutroTempo,
}

/// O HEIC da tela enquanto não aparece (`_heic_*` da 1.5.1).
#[derive(Default)]
struct Heic {
    /// (token, caminho, filtro, tentativa)
    espera: Option<(u64, PathBuf, String, u32)>,
    apareceu: bool,
    reiniciou: bool,
    carregado: bool,
    /// Lendo o cabeçalho (o giro) em outra thread, antes do loadfile.
    lendo: bool,
    pausa_na_leitura: Option<bool>,
}

pub struct Opcoes {
    /// Modo de teste (REGRA 13): o motor fica sempre mudo, nada é aberto de verdade.
    pub teste: bool,
    /// No modo de teste: fecha sozinho quando a fila acaba.
    pub sair_no_fim: bool,
}

pub type Relogio = Rc<dyn Fn() -> Duration>;

pub struct Player {
    eu: Weak<Player>,
    pub ui: Camada,
    motor: Rc<dyn Motor>,
    plat: Rc<dyn Plataforma>,
    relogio: Relogio,
    escrever: Box<dyn Fn(&str)>,
    opcoes: Opcoes,
    pub sessao: RefCell<Sessao>,
    correio_tx: Sender<Correio>,
    correio_rx: Receiver<Correio>,
    acordar: Arc<dyn Fn() + Send + Sync>,
    varrendo: RefCell<Option<Arc<AtomicBool>>>,
    geracao: Cell<u64>,
    token: Cell<u64>,
    carregou_em: Cell<Duration>,
    esperando_quadro: Cell<bool>,
    motor_anotado: Cell<bool>,
    audio_anotado: Cell<bool>,
    duracao: Cell<f64>,
    t_atual: Cell<f64>,
    mostrar_restante: Cell<bool>,
    pastas_lidas: Cell<usize>,
    ignorados: Cell<usize>,
    filtro_giro: RefCell<String>,
    heic: RefCell<Heic>,
    segundos_foto: Cell<i64>,
    foto_total_ms: Cell<u64>,
    foto_restante_ms: Cell<u64>,
    foto_desde: Cell<Duration>,
    t_foto: Timer,
    t_ui: Timer,
    t_esconder: Timer,
    t_cursor: Timer,
    t_clique: Timer,
    t_pular: Timer,
    t_soltar: Timer,
    cursor_antes: Cell<Option<(i32, i32)>>,
    painel_antes: Cell<bool>,
    soltos: RefCell<Vec<PathBuf>>,
    menu_alvo: RefCell<Vec<usize>>,
    pergunta: Cell<Option<Pergunta>>,
    modelo: Rc<VecModel<LinhaFila>>,
    /// Índices de `fila.itens` de cada linha da lista (a ordem de tocar, só o que a busca deixa).
    linhas: RefCell<Vec<usize>>,
    selecao: RefCell<BTreeSet<usize>>,
    ancora: Cell<Option<usize>>,
    /// A janela de escolher pasta ou arquivos está aberta (é modal, como na 1.5.1).
    dialogo_aberto: Cell<bool>,
    /// Ctrl no primeiro arquivo solto (o lote é processado 40 ms depois).
    ctrl_ao_soltar: Cell<bool>,
    busca: RefCell<String>,
    primeiro_quadro: RefCell<Option<Box<dyn Fn(f64, f64)>>>,
}

pub fn fmt_tempo(seg: f64) -> String {
    if !seg.is_finite() || seg < 0.0 {
        return "0:00".into();
    }
    let s = seg as u64;
    let (h, m, s) = (s / 3600, (s % 3600) / 60, s % 60);
    if h > 0 { format!("{h}:{m:02}:{s:02}") } else { format!("{m}:{s:02}") }
}

/// `f"{x:,}".replace(",", ".")`
pub fn milhar(x: usize) -> String {
    let s = x.to_string();
    let mut o = String::new();
    for (i, c) in s.chars().enumerate() {
        if i > 0 && (s.len() - i) % 3 == 0 {
            o.push('.');
        }
        o.push(c);
    }
    o
}

/// `"5 s"` ou `"2 min"`.
pub fn fmt_foto(v: i64) -> String {
    if v >= 60 && v % 60 == 0 { format!("{} min", v / 60) } else { format!("{v} s") }
}

/// `os.path.basename(p.rstrip("\\/")) or p` da 1.5.1: a raiz (`C:\`, `\\srv\share\`) fica inteira.
pub fn nome_da_pasta(p: &Path) -> String {
    let s = p.to_string_lossy();
    let sem_barra = s.trim_end_matches(['\\', '/']);
    let base = sem_drive(sem_barra).rsplit(['\\', '/']).next().unwrap_or("");
    if base.is_empty() { s.into_owned() } else { base.to_string() }
}

/// O resto depois do drive, como o `ntpath.splitdrive`: `C:` ou `\\servidor\compartilhamento`.
fn sem_drive(s: &str) -> &str {
    let b = s.as_bytes();
    if b.len() >= 2 && b[1] == b':' {
        return &s[2..]; // b[1] é ':', então b[0] é ASCII
    }
    let barra = |c: u8| c == b'\\' || c == b'/';
    if b.len() >= 2 && barra(b[0]) && barra(b[1]) {
        let resto = &s[2..];
        let Some(i) = resto.find(['\\', '/']) else { return "" };
        return match resto[i + 1..].find(['\\', '/']) {
            Some(j) => &resto[i + 1 + j..],
            None => "",
        };
    }
    s
}

fn pasta_do_item(it: &Item) -> String {
    if !it.pasta_rel.is_empty() {
        return it.pasta_rel.clone();
    }
    nome_da_pasta(&it.raiz)
}

fn titulo_menu(texto: String) -> LinhaMenu {
    LinhaMenu { tipo: "titulo".into(), texto: texto.into(), ativo: false, ..Default::default() }
}
fn explica_menu(texto: String) -> LinhaMenu {
    LinhaMenu { tipo: "explica".into(), texto: texto.into(), ativo: false, ..Default::default() }
}
fn sep_menu() -> LinhaMenu {
    LinhaMenu { tipo: "sep".into(), ativo: false, ..Default::default() }
}
fn linha_menu(icone: &str, texto: String, dica: String, atalho: &str, acao: &str, perigo: bool, ativo: bool) -> LinhaMenu {
    LinhaMenu {
        tipo: "linha".into(),
        icone: icone.into(),
        texto: texto.into(),
        atalho: atalho.into(),
        dica: dica.into(),
        perigo,
        ativo,
        marcado: false,
        acao: acao.into(),
    }
}
fn radio_menu(texto: String, marcado: bool, acao: String) -> LinhaMenu {
    LinhaMenu { tipo: "radio".into(), texto: texto.into(), ativo: true, marcado, acao: acao.into(), ..Default::default() }
}

impl Player {
    #[allow(clippy::too_many_arguments)]
    pub fn novo(
        ui: Camada,
        motor: Rc<dyn Motor>,
        plat: Rc<dyn Plataforma>,
        sessao: Sessao,
        relogio: Relogio,
        escrever: Box<dyn Fn(&str)>,
        acordar: Arc<dyn Fn() + Send + Sync>,
        opcoes: Opcoes,
    ) -> Rc<Player> {
        let (tx, rx) = channel();
        let segundos = sessao.cfg.segundos_foto().clamp(1, 600);
        let p = Rc::new_cyclic(|eu| Player {
            eu: eu.clone(),
            ui,
            motor,
            plat,
            relogio,
            escrever,
            opcoes,
            sessao: RefCell::new(sessao),
            correio_tx: tx,
            correio_rx: rx,
            acordar,
            varrendo: RefCell::new(None),
            geracao: Cell::new(0),
            token: Cell::new(0),
            carregou_em: Cell::new(Duration::ZERO),
            esperando_quadro: Cell::new(false),
            motor_anotado: Cell::new(false),
            audio_anotado: Cell::new(false),
            duracao: Cell::new(0.0),
            t_atual: Cell::new(0.0),
            mostrar_restante: Cell::new(false),
            pastas_lidas: Cell::new(0),
            ignorados: Cell::new(0),
            filtro_giro: RefCell::new(String::new()),
            heic: RefCell::new(Heic::default()),
            segundos_foto: Cell::new(segundos),
            foto_total_ms: Cell::new(segundos as u64 * 1000),
            foto_restante_ms: Cell::new(segundos as u64 * 1000),
            foto_desde: Cell::new(Duration::ZERO),
            t_foto: Timer::default(),
            t_ui: Timer::default(),
            t_esconder: Timer::default(),
            t_cursor: Timer::default(),
            t_clique: Timer::default(),
            t_pular: Timer::default(),
            t_soltar: Timer::default(),
            cursor_antes: Cell::new(None),
            painel_antes: Cell::new(true),
            soltos: RefCell::new(Vec::new()),
            menu_alvo: RefCell::new(Vec::new()),
            pergunta: Cell::new(None),
            modelo: Rc::new(VecModel::default()),
            linhas: RefCell::new(Vec::new()),
            selecao: RefCell::new(BTreeSet::new()),
            ancora: Cell::new(None),
            dialogo_aberto: Cell::new(false),
            ctrl_ao_soltar: Cell::new(false),
            busca: RefCell::new(String::new()),
            primeiro_quadro: RefCell::new(None),
        });
        p.ligar();
        p
    }

    fn agora(&self) -> Duration {
        (self.relogio)()
    }

    pub fn log(&self, texto: &str) {
        (self.escrever)(texto);
    }

    /// Chamado a cada primeiro quadro (ms depois do loadfile, ms desde o início do relógio).
    pub fn ao_primeiro_quadro(&self, f: impl Fn(f64, f64) + 'static) {
        *self.primeiro_quadro.borrow_mut() = Some(Box::new(f));
    }

    /// Um `Timer` de uma vez que chama `f` no player (se ele ainda existir).
    fn depois(&self, timer: &Timer, ms: u64, f: impl Fn(&Player) + 'static) {
        let eu = self.eu.clone();
        timer.start(TimerMode::SingleShot, Duration::from_millis(ms), move || {
            if let Some(p) = eu.upgrade() {
                f(&p);
            }
        });
    }

    fn uma_vez(&self, ms: u64, f: impl FnOnce(&Player) + 'static) {
        let eu = self.eu.clone();
        Timer::single_shot(Duration::from_millis(ms), move || {
            if let Some(p) = eu.upgrade() {
                f(&p);
            }
        });
    }

    // ================= montagem =================
    fn ligar(&self) {
        let ui = &self.ui;
        ui.global::<Textos>().on_t(|chave, _| t(&chave).into());
        ui.set_fila(ModelRc::from(self.modelo.clone()));

        // Estilo do aviso por cima do vídeo, o mesmo da 1.5.1 (show-text).
        for (k, v) in [
            ("input-cursor-passthrough", "yes"),
            ("osd-font", "Segoe UI Semibold"),
            ("osd-font-size", "30"),
            ("osd-bold", "no"),
            ("osd-color", "#FFFFFFFF"),
            ("osd-border-style", "background-box"),
            ("osd-back-color", "#C0141519"),
            ("osd-border-size", "0"),
            ("osd-shadow-offset", "0"),
            ("osd-margin-y", "48"),
            ("osd-align-x", "center"),
            ("osd-align-y", "bottom"),
            ("osd-playing-msg", ""),
            ("osd-bar", "no"),
        ] {
            let _ = self.motor.por_texto(k, v);
        }

        let eu = self.eu.clone();
        macro_rules! com {
            (|$p:ident $(, $a:ident)*| $corpo:expr) => {{
                let eu = eu.clone();
                move |$($a),*| {
                    if let Some($p) = eu.upgrade() {
                        $corpo
                    }
                }
            }};
        }
        ui.on_acao(com!(|p, a| p.acao_da_interface(a.as_str())));
        ui.on_abrir_menu(com!(|p, id, x, y, w, h| p.abrir_menu(id.as_str(), x, y, w, h)));
        ui.on_menu_video(com!(|p, x, y| p.menu_video(x, y)));
        ui.on_menu_lista(com!(|p, i, x, y| p.menu_lista(i, x, y)));
        ui.on_menu_escolheu(com!(|p, a| p.menu_escolheu(a.as_str())));
        ui.on_menu_fechou(com!(|p| p.fechar_menu()));
        ui.on_busca_soltou(com!(|p, v| p.soltou_busca(v)));
        ui.on_volume_mudou(com!(|p, v| p.volume_da_barra(v as i64)));
        ui.on_palco_clique(com!(|p| p.palco_clique()));
        ui.on_palco_duplo(com!(|p| p.palco_duplo()));
        ui.on_palco_roda(com!(|p, d| p.mudar_volume(5 * d as i64)));
        ui.on_lista_clique(com!(|p, i, c, s| p.lista_clique(i, c, s)));
        ui.on_lista_duplo(com!(|p, i| p.lista_duplo(i)));
        ui.on_busca_mudou(com!(|p, s| p.busca_mudou(s.as_str())));
        {
            let eu = eu.clone();
            ui.on_tecla(move |texto, shift, ctrl, alt, repetida| match eu.upgrade() {
                Some(p) => p.tecla(texto.as_str(), shift, ctrl, alt, repetida, "camada"),
                None => false,
            });
        }
        ui.on_mexeu(com!(|p| p.mexeu()));
        ui.on_palco_mudou(com!(|p| p.palco_mudou()));
        ui.on_caixa_respondeu(com!(|p, s| p.caixa_respondeu(s)));

        // Estado inicial vindo do config.
        let (painel, volume, mudo, aleatorio, repetir, filtro) = {
            let s = self.sessao.borrow();
            (s.cfg.painel(), s.cfg.volume().clamp(0, 100), s.cfg.mudo(), s.fila.aleatorio, s.fila.repetir, s.fila.filtro)
        };
        ui.set_painel_visivel(painel);
        ui.set_volume(volume as i32);
        ui.set_mudo(mudo);
        ui.set_aleatorio(aleatorio);
        ui.set_repetir(repetir.nome().into());
        ui.set_filtro(filtro.nome().into());
        self.textos_da_foto();
        self.tela_de_inicio();
        self.atualizar_lista();
        self.plat.titulo(NOME);

        self.t_ui.start(TimerMode::Repeated, Duration::from_millis(100), {
            let eu = eu.clone();
            move || {
                if let Some(p) = eu.upgrade() {
                    p.tique();
                }
            }
        });
    }

    /// O que a barra e a tela de início mostram sem nada tocando.
    fn tela_de_inicio(&self) {
        self.ui.set_vazio(true);
        self.ui.set_nome(t("nada_tocando").into());
        self.ui.set_info(t("arraste_para_janela").into());
        self.ui.set_tipo_icone("pasta".into());
        self.ui.set_tipo_falhou(false);
        self.ui.set_caminho_atual("".into());
        self.ui.set_tempo_txt("0:00".into());
        self.ui.set_total_txt("0:00".into());
        self.ui.set_progresso(0.0);
        self.ui.set_busca_ativa(false);
        self.ui.set_tocando(false);
        self.atualizar_continuar();
    }

    fn ultimas_que_existem(&self) -> Vec<PathBuf> {
        self.sessao.borrow().cfg.ultimas_pastas().into_iter().filter(|p| p.exists()).collect()
    }

    fn atualizar_continuar(&self) {
        let pastas = self.ultimas_que_existem();
        let txt = match pastas.len() {
            0 => String::new(),
            1 => tf("continuar_ultima", &[("nomes", &nome_da_pasta(&pastas[0]))]),
            n => tf("continuar_ultima", &[("nomes", &tf("n_pastas", &[("n", &n)]))]),
        };
        self.ui.set_continuar_txt(txt.into());
    }

    fn textos_da_foto(&self) {
        let v = self.segundos_foto.get();
        self.ui.set_foto_longo(format!("{}  ▾", tf("foto_rotulo", &[("tempo", &fmt_foto(v))])).into());
        self.ui.set_foto_curto(format!("{} ▾", fmt_foto(v)).into());
    }

    // ================= correio e motor =================
    /// Quem está fora da thread da interface manda por aqui.
    pub fn remetente(&self) -> (Sender<Correio>, Arc<dyn Fn() + Send + Sync>) {
        (self.correio_tx.clone(), self.acordar.clone())
    }

    /// Lê o que as outras threads mandaram. Devolve quantas mensagens.
    pub fn drenar_correio(&self) -> usize {
        let mut n = 0;
        while let Ok(m) = self.correio_rx.try_recv() {
            n += 1;
            match m {
                Correio::Progresso { geracao, n, pasta } => {
                    if geracao == self.geracao.get() {
                        let mut s = tf("lendo_n", &[("n", &milhar(n))]);
                        if !pasta.is_empty() {
                            s.push_str(&format!("  ·  {pasta}"));
                        }
                        self.status(&s);
                    }
                }
                Correio::Varreu { geracao, itens, juntar, stats, segundos } => {
                    self.varredura_terminou(geracao, itens, juntar, stats, segundos)
                }
                Correio::Giro { token, filtro } => self.giro_pronto(token, filtro),
                Correio::Escolheu { arquivos, juntar, caminhos } => self.escolheu(arquivos, juntar, caminhos),
            }
        }
        n
    }

    /// Lê os eventos do motor. Devolve `false` se o motor encerrou.
    pub fn drenar_motor(&self) -> bool {
        while let Some(e) = self.motor.proximo_evento() {
            match e {
                Evento::ArquivoCarregado => {
                    self.log("arquivo carregado");
                    self.esperando_quadro.set(true);
                    if self.opcoes.teste && !self.motor_anotado.replace(true) {
                        let l = |p: &str| self.motor.ler_texto(p).unwrap_or_else(|| "?".into());
                        self.log(&format!(
                            "modo teste: vo={} ao={} mute={} (opções vo={} ao={})",
                            l("current-vo"),
                            l("current-ao"),
                            l("mute"),
                            l("options/vo"),
                            l("options/ao")
                        ));
                    }
                    self.heic_carregou();
                }
                Evento::Reinicio => {
                    if self.opcoes.teste && !self.audio_anotado.get() {
                        if let Some(ao) = self.motor.ler_texto("current-ao") {
                            self.audio_anotado.set(true);
                            let mudo = self.motor.ler_texto("mute").unwrap_or_else(|| "?".into());
                            self.log(&format!("modo teste: áudio em ao={ao} mute={mudo}"));
                        }
                    }
                    if self.esperando_quadro.replace(false) {
                        let ms = (self.agora().saturating_sub(self.carregou_em.get())).as_secs_f64() * 1000.0;
                        let desde = self.agora().as_secs_f64() * 1000.0;
                        self.log(&format!("primeiro quadro: {ms:.0} ms depois do loadfile, {desde:.0} ms depois de abrir"));
                        if let Some(f) = &*self.primeiro_quadro.borrow() {
                            f(ms, desde);
                        }
                    }
                    self.imagem_apareceu();
                }
                Evento::FimArquivo { motivo, .. } => {
                    if motivo == FIM_POR_ERRO {
                        self.arquivo_falhou();
                    }
                }
                Evento::Propriedade { nome, valor, .. } => match (nome.as_str(), valor) {
                    ("pause", Valor::Sim(p)) => self.recebeu_pausa(p),
                    ("eof-reached", Valor::Sim(true)) => self.video_acabou(),
                    _ => {}
                },
                Evento::Log { nivel, prefixo, texto } => {
                    self.log(&format!("[mpv {nivel}] {prefixo}: {}", texto.trim_end()));
                }
                Evento::FimDoMotor => {
                    self.log("motor encerrou");
                    return false;
                }
                _ => {}
            }
        }
        true
    }

    // ================= abrir =================
    fn inicio_do_dialogo(&self) -> Option<PathBuf> {
        let ultima = self.sessao.borrow().pastas_abertas.last().cloned();
        ultima.or_else(|| std::env::var_os("USERPROFILE").map(PathBuf::from))
    }

    pub fn abrir_pasta(&self) {
        self.escolher_pasta(false);
    }
    pub fn adicionar_pasta(&self) {
        self.escolher_pasta(true);
    }
    fn escolher_pasta(&self, adicionar: bool) {
        if self.dialogo_aberto.get() {
            return;
        }
        let titulo = if adicionar { t("dlg_adicionar_pasta") } else { t("abrir_pasta") };
        let inicio = self.inicio_do_dialogo();
        self.log(&format!("escolher pasta ({})", if adicionar { "juntar" } else { "abrir" }));
        self.pedir_escolha(Escolha::Pasta, &titulo, inicio, adicionar);
    }
    pub fn abrir_arquivos(&self) {
        if self.dialogo_aberto.get() {
            return;
        }
        let inicio = std::env::var_os("USERPROFILE").map(PathBuf::from);
        self.log("escolher arquivos");
        self.pedir_escolha(Escolha::Arquivos, &t("dlg_abrir_arquivos"), inicio, false);
    }
    /// A resposta volta pelo correio (a janela pode ficar aberta enquanto o player anda).
    fn pedir_escolha(&self, escolha: Escolha, titulo: &str, inicio: Option<PathBuf>, juntar: bool) {
        self.fechar_menu();
        self.dialogo_aberto.set(true);
        let (tx, acordar) = self.remetente();
        let arquivos = escolha == Escolha::Arquivos;
        self.plat.escolher(
            escolha,
            titulo,
            inicio.as_deref(),
            Box::new(move |caminhos| {
                let _ = tx.send(Correio::Escolheu { arquivos, juntar, caminhos });
                acordar();
            }),
        );
    }
    fn escolheu(&self, arquivos: bool, juntar: bool, caminhos: Vec<PathBuf>) {
        self.dialogo_aberto.set(false);
        if caminhos.is_empty() {
            self.log("escolha cancelada");
        } else if arquivos {
            self.carregar(caminhos, false);
        } else {
            self.carregar(caminhos.into_iter().take(1).collect(), juntar);
        }
    }
    pub fn continuar_ultimas(&self) {
        let pastas = self.ultimas_que_existem();
        if !pastas.is_empty() {
            self.carregar(pastas, false);
        }
    }

    /// Abre (troca a fila) ou junta: a varredura roda numa thread e uma nova cancela a anterior.
    pub fn carregar(&self, caminhos: Vec<PathBuf>, adicionar: bool) {
        let carga = self.sessao.borrow_mut().preparar_carga(&caminhos, adicionar);
        let Some(carga) = carga else {
            self.log("nada que exista para abrir");
            return;
        };
        if let Some(antiga) = self.varrendo.borrow_mut().take() {
            antiga.store(true, Ordering::Relaxed);
            self.log("varredura anterior cancelada");
        }
        let cancelar = Arc::new(AtomicBool::new(false));
        *self.varrendo.borrow_mut() = Some(cancelar.clone());
        let geracao = self.geracao.get() + 1;
        self.geracao.set(geracao);
        let nome = {
            let n = nome_da_pasta(&carga.caminhos[0]);
            if carga.caminhos.len() > 1 { format!("{n} +{}", carga.caminhos.len() - 1) } else { n }
        };
        self.status(&tf("lendo", &[("nome", &nome)]));
        self.log(&format!(
            "lendo {} caminho(s){}",
            carga.caminhos.len(),
            if carga.juntar { ", juntando à fila" } else { "" }
        ));
        let (tx, acordar) = self.remetente();
        let t0 = std::time::Instant::now();
        std::thread::spawn(move || {
            let mut stats = Estatisticas::default();
            let c = cancelar.clone();
            let itens = varrer_varios(
                &carga.caminhos,
                &move || c.load(Ordering::Relaxed),
                &mut |n, pasta| {
                    let _ = tx.send(Correio::Progresso { geracao, n, pasta: pasta.to_string() });
                    acordar();
                },
                &mut stats,
            );
            if cancelar.load(Ordering::Relaxed) {
                return;
            }
            let segundos = t0.elapsed().as_secs_f64();
            let _ = tx.send(Correio::Varreu { geracao, itens, juntar: carga.juntar, stats, segundos });
            acordar();
        });
    }

    /// Ao fechar: para a varredura e sai da tela cheia (o painel volta ao que era, para o config).
    pub fn limpar_ao_sair(&self) {
        if let Some(c) = self.varrendo.borrow_mut().take() {
            c.store(true, Ordering::Relaxed);
        }
        self.sair_tela_cheia();
    }

    /// Há uma varredura em andamento, ou o cabeçalho de um HEIC sendo lido.
    pub fn lendo(&self) -> bool {
        self.varrendo.borrow().is_some() || self.heic.borrow().lendo
    }

    fn varredura_terminou(&self, geracao: u64, itens: Vec<Item>, juntar: bool, stats: Estatisticas, segundos: f64) {
        if geracao != self.geracao.get() {
            return;
        }
        self.varrendo.borrow_mut().take();
        for l in self.sessao.borrow().linhas_da_varredura(&itens, &stats) {
            self.log(&l);
        }
        self.log(&format!("varredura em {segundos:.3} s"));
        self.ignorados.set(stats.total_ignorados());
        self.pastas_lidas.set(stats.pastas_lidas);
        if itens.is_empty() && !juntar {
            self.status(&t("nenhuma_midia"));
            self.log("nenhuma foto ou vídeo");
            if self.sessao.borrow().fila.itens.is_empty() {
                self.sair_se_teste();
            }
            return;
        }
        if !juntar {
            self.parar_motor();
            // Seleção, âncora e alvo do menu são índices da fila antiga (a 1.5.1 zera a seleção
            // no beginResetModel): um "Tirar" depois apagaria itens que ninguém escolheu.
            if !self.menu_alvo.borrow().is_empty() {
                self.fechar_menu();
            }
            self.menu_alvo.borrow_mut().clear();
            self.selecao.borrow_mut().clear();
            self.ancora.set(None);
        }
        let filtro_antes = self.sessao.borrow().fila.filtro;
        let p = self.sessao.borrow_mut().varredura_pronta(itens, juntar);
        let filtro = self.sessao.borrow().fila.filtro;
        if filtro != filtro_antes {
            // O filtro escondia tudo: voltou para Tudo (como o definir_filtro da 1.5.1).
            self.log(&format!("filtro: {}", filtro.nome()));
            self.ui.set_filtro(filtro.nome().into());
        }
        self.atualizar_continuar();
        self.atualizar_lista();
        match p {
            Passo::Juntou => {
                self.log(&format!("juntou: fila com {}", self.sessao.borrow().fila.len()));
                self.atualizar_info();
            }
            Passo::Tocar(_) => {
                self.ui.set_vazio(false);
                self.ui.set_status("".into());
                self.seguir(p);
                if filtro != filtro_antes {
                    self.aviso(&t(&format!("osd_filtro_{}", filtro.nome())));
                }
            }
            outro => self.seguir(outro),
        }
    }

    // ================= tocar =================
    fn parar_motor(&self) {
        self.t_foto.stop();
        let _ = self.motor.comando(&["stop"]);
    }

    /// Executa a decisão da sessão.
    fn seguir(&self, p: Passo) {
        match p {
            Passo::Nada => {}
            Passo::Tocar(i) => self.tocar(i),
            Passo::FimDaFila => self.fim(false),
            Passo::NenhumAbriu => self.fim(true),
            Passo::NadaComFiltro => {
                self.parar_motor();
                self.ui.set_info(t("nada_com_filtro").into());
                self.ui.set_tocando(false);
                self.log("nada com este filtro");
            }
            Passo::NenhumaMidia => {
                self.status(&t("nenhuma_midia"));
                self.log("nenhuma foto ou vídeo");
            }
            Passo::Juntou => {
                self.atualizar_lista();
                self.atualizar_info();
            }
            Passo::PularFalho => {
                // O próximo é escolhido 50 ms depois, com o filtro de então (como a 1.5.1).
                self.depois(&self.t_pular, 50, |p| {
                    let passo = p.sessao.borrow_mut().pular_falho();
                    p.seguir(passo);
                });
            }
        }
    }

    fn fim(&self, nenhum_abriu: bool) {
        self.t_foto.stop();
        let _ = self.motor.por_sim("pause", true);
        let msg = if nenhum_abriu { t("nenhum_abriu") } else { t("fim_fila") };
        self.ui.set_info(msg.into());
        self.ui.set_tocando(false);
        self.log(if nenhum_abriu { "nenhum arquivo da fila abriu, parando" } else { "fim da fila" });
        self.sair_se_teste();
    }

    fn sair_se_teste(&self) {
        if self.opcoes.teste && self.opcoes.sair_no_fim {
            self.log("modo teste: fila acabou, saindo");
            Timer::single_shot(Duration::from_millis(100), || {
                slint::quit_event_loop().ok();
            });
        }
    }

    /// Toca o item `i` de `fila.itens` (a sessão já o marcou como o da tela).
    fn tocar(&self, i: usize) {
        let Some(item) = self.sessao.borrow().fila.itens.get(i).cloned() else { return };
        self.t_foto.stop();
        self.t_pular.stop();
        *self.heic.borrow_mut() = Heic::default();
        let total = self.segundos_foto.get() as u64 * 1000;
        self.foto_total_ms.set(total);
        self.foto_restante_ms.set(total);
        self.token.set(self.token.get() + 1);
        self.duracao.set(0.0);
        self.t_atual.set(0.0);
        self.ui.set_vazio(false);
        self.ui.set_tocando(true);
        let (pos, n) = self.sessao.borrow().fila.posicao();
        self.log(&format!("tocando {pos}/{n} {}", item.caminho.display()));
        if heif::eh_heif(&item.ext) {
            // Ler o cabeçalho pode demorar (rede, foto só na nuvem): fora da interface.
            self.heic.borrow_mut().lendo = true;
            let (tx, acordar) = self.remetente();
            let token = self.token.get();
            let caminho = item.caminho.clone();
            std::thread::spawn(move || {
                let filtro = heif::filtro_de_giro(&caminho);
                let _ = tx.send(Correio::Giro { token, filtro });
                acordar();
            });
        } else {
            self.carregar_no_motor(&item.caminho, "", 1);
        }
        self.atualizar_info();
        self.marcar_atual_na_lista();
        self.rolar_para_atual();
    }

    fn giro_pronto(&self, token: u64, filtro: String) {
        if token != self.token.get() {
            return;
        }
        let Some(caminho) = self.sessao.borrow().item_atual().map(|i| i.caminho.clone()) else { return };
        self.heic.borrow_mut().lendo = false;
        if !filtro.is_empty() {
            self.log(&format!("HEIC: giro {filtro}"));
        }
        self.carregar_no_motor(&caminho, &filtro, 1);
    }

    fn carregar_no_motor(&self, caminho: &Path, filtro: &str, tentativa: u32) {
        let Some(item) = self.sessao.borrow().item_atual().cloned() else { return };
        let rep_um = self.sessao.borrow().fila.repetir == Repetir::Um;
        let heic = heif::eh_heif(&item.ext);
        let laco = item.animada() || (item.tipo == Tipo::Video && rep_um);
        let _ = self.motor.por_texto("loop-file", if laco { "inf" } else { "no" });
        if *self.filtro_giro.borrow() != filtro {
            // Trocar o filtro refaz a cadeia de vídeo: só quando muda.
            let _ = self.motor.por_texto("vf", filtro);
            *self.filtro_giro.borrow_mut() = filtro.to_string();
        }
        if heic {
            let mut h = self.heic.borrow_mut();
            h.espera = Some((self.token.get(), caminho.to_path_buf(), filtro.to_string(), tentativa));
            h.apareceu = false;
            h.reiniciou = false;
            h.carregado = false;
        }
        let manter_pausa = if tentativa > 1 { Some(self.motor.ler_sim("pause").unwrap_or(false)) } else { None };
        self.esperando_quadro.set(false);
        let texto = caminho.to_string_lossy().into_owned();
        if let Err(e) = self.motor.comando(&["loadfile", &texto, "replace"]) {
            self.log(&format!("loadfile falhou: {e}"));
            self.arquivo_falhou();
            return;
        }
        let pausa = match manter_pausa {
            Some(p) => p,
            None => self.heic.borrow_mut().pausa_na_leitura.take().unwrap_or(false),
        };
        let _ = self.motor.por_sim("pause", pausa);
        self.ui.set_tocando(!pausa);
        self.carregou_em.set(self.agora());
        if heic {
            let espera = HEIC_ESPERA_S + HEIC_PASSO_S * (tentativa - 1) as f64;
            let prazo = self.agora() + Duration::from_secs_f64(espera);
            self.vigiar_heic(self.token.get(), tentativa, prazo, espera);
        } else if item.tipo == Tipo::Foto && !pausa {
            self.iniciar_relogio_foto(None);
        }
    }

    // ---------- HEIC ----------
    /// O HEIC em espera, se o motor está mesmo nele (aviso atrasado de outro arquivo não conta).
    fn esp_atual(&self) -> bool {
        let h = self.heic.borrow();
        let Some((token, caminho, ..)) = &h.espera else { return false };
        if *token != self.token.get() {
            return false;
        }
        let atual = self.motor.ler_texto("path").unwrap_or_default();
        !atual.is_empty() && normcase(Path::new(&atual)) == normcase(caminho)
    }

    /// file-loaded: voltar ao início faz o motor reler a grade com as faixas já escolhidas.
    fn heic_carregou(&self) {
        if self.esp_atual() && !self.heic.borrow().apareceu {
            {
                let mut h = self.heic.borrow_mut();
                h.carregado = true;
                h.reiniciou = false;
            }
            let _ = self.motor.comando(&["seek", "0", "absolute+exact"]);
        }
    }

    /// playback-restart: sozinho não prova nada (chega também quando a grade trava).
    fn imagem_apareceu(&self) {
        if self.esp_atual() && self.heic.borrow().carregado {
            self.heic.borrow_mut().reiniciou = true;
        }
    }

    fn heic_esperando(&self) -> bool {
        let h = self.heic.borrow();
        h.lendo || (h.espera.is_some() && !h.apareceu)
    }

    /// O tamanho na tela bate com o da faixa de vídeo do arquivo (de pé ou deitado).
    fn heic_na_tela(&self) -> bool {
        if !self.heic.borrow().carregado {
            return false;
        }
        let m = &self.motor;
        let n = m.ler_inteiro("track-list/count").unwrap_or(0);
        let faixa = (0..n).find(|i| {
            m.ler_texto(&format!("track-list/{i}/type")).as_deref() == Some("video")
                && m.ler_sim(&format!("track-list/{i}/selected")) == Some(true)
        });
        let Some(i) = faixa else { return false };
        let (Some(w), Some(h)) =
            (m.ler_inteiro(&format!("track-list/{i}/demux-w")), m.ler_inteiro(&format!("track-list/{i}/demux-h")))
        else {
            return false;
        };
        let (Some(dw), Some(dh)) = (m.ler_inteiro("dwidth"), m.ler_inteiro("dheight")) else { return false };
        w > 0 && h > 0 && ((dw, dh) == (w, h) || (dw, dh) == (h, w))
    }

    fn vigiar_heic(&self, token: u64, tentativa: u32, prazo: Duration, espera: f64) {
        {
            let h = self.heic.borrow();
            let vale = h.espera.as_ref().is_some_and(|e| e.3 == tentativa) && !h.apareceu;
            let s = self.sessao.borrow();
            let item_ok = s.item_atual().is_some_and(|i| !i.falhou) && !s.fim_da_fila;
            if token != self.token.get() || !vale || !item_ok {
                return;
            }
        }
        if self.heic.borrow().reiniciou && self.heic_na_tela() && self.esp_atual() {
            self.heic.borrow_mut().apareceu = true;
            if tentativa > 1 {
                self.log(&format!("HEIC apareceu na tentativa {tentativa} de {HEIC_TENTATIVAS}"));
            }
            if self.sessao.borrow().item_atual().is_some_and(|i| i.tipo == Tipo::Foto) {
                // O tempo começa inteiro agora; pausado, conta ao despausar.
                let total = self.segundos_foto.get() as u64 * 1000;
                self.foto_total_ms.set(total);
                self.foto_restante_ms.set(total);
                if !self.motor.ler_sim("pause").unwrap_or(false) {
                    self.iniciar_relogio_foto(None);
                }
            }
            return;
        }
        if self.agora() < prazo {
            self.uma_vez(50, move |p| p.vigiar_heic(token, tentativa, prazo, espera));
            return;
        }
        self.conferir_heic(token, tentativa, espera);
    }

    fn conferir_heic(&self, token: u64, tentativa: u32, espera: f64) {
        let esp = self.heic.borrow().espera.clone();
        let Some((_, caminho, filtro, t_esp)) = esp else { return };
        if token != self.token.get() || t_esp != tentativa || self.heic.borrow().apareceu || self.sessao.borrow().item.is_none() {
            return;
        }
        if tentativa >= HEIC_TENTATIVAS {
            self.log(&format!("HEIC não apareceu em {HEIC_TENTATIVAS} tentativas: pulando"));
            self.heic.borrow_mut().espera = None;
            self.arquivo_falhou();
            return;
        }
        self.log(&format!(
            "HEIC não apareceu em {espera:.1} s: recarregando (tentativa {} de {HEIC_TENTATIVAS})",
            tentativa + 1
        ));
        self.carregar_no_motor(&caminho, &filtro, tentativa + 1);
    }

    // ---------- relógio da foto ----------
    fn foto_passado_ms(&self) -> u64 {
        self.agora().saturating_sub(self.foto_desde.get()).as_millis() as u64
    }

    fn iniciar_relogio_foto(&self, restante_ms: Option<u64>) {
        let total = self.segundos_foto.get() as u64 * 1000;
        self.foto_total_ms.set(total);
        self.foto_restante_ms.set(restante_ms.unwrap_or(total));
        self.foto_desde.set(self.agora());
        if self.sessao.borrow().fila.repetir != Repetir::Um {
            self.armar_foto();
        }
    }

    fn armar_foto(&self) {
        let ms = self.foto_restante_ms.get().max(1);
        self.depois(&self.t_foto, ms, |p| p.foto_acabou());
    }

    fn foto_acabou(&self) {
        if self.sessao.borrow().item_atual().map(|i| i.tipo) != Some(Tipo::Foto) {
            return;
        }
        self.log(&format!("foto: {} s, passa", self.segundos_foto.get()));
        let p = self.sessao.borrow_mut().foto_acabou();
        self.seguir(p);
    }

    fn video_acabou(&self) {
        if self.sessao.borrow().item_atual().map(|i| i.tipo) != Some(Tipo::Video) {
            return;
        }
        if self.agora().saturating_sub(self.carregou_em.get()) < Duration::from_millis(300) {
            return; // aviso atrasado do arquivo anterior
        }
        if self.motor.ler_sim("eof-reached") != Some(true) {
            return;
        }
        self.log("fim do vídeo");
        let p = self.sessao.borrow_mut().video_acabou();
        self.seguir(p);
    }

    fn arquivo_falhou(&self) {
        self.heic.borrow_mut().espera = None;
        let Some((i, caminho)) = ({
            let s = self.sessao.borrow();
            s.item.zip(s.item_atual().map(|it| it.caminho.clone()))
        }) else {
            return;
        };
        self.log(&format!("não abriu: {}", caminho.display()));
        let p = self.sessao.borrow_mut().arquivo_falhou();
        self.atualizar_linha(i);
        self.atualizar_resumo();
        self.atualizar_info();
        self.seguir(p);
    }

    /// Aviso rápido desenhado pelo motor por cima do vídeo/foto (ou no status sem nada na tela).
    fn aviso(&self, texto: &str) {
        self.log(&format!("aviso: {texto}"));
        if self.sessao.borrow().item.is_some() && !self.ui.get_vazio() && self.motor.comando(&["show-text", texto, "1300", "1"]).is_ok() {
            return;
        }
        self.status(texto);
    }

    fn status(&self, texto: &str) {
        if self.ui.get_vazio() {
            self.ui.set_status(texto.into());
        } else {
            self.ui.set_info(texto.into());
        }
    }

    // ================= controles =================
    pub fn executar(&self, a: Acao) {
        match a {
            Acao::TocarPausar => self.alternar_pausa(),
            Acao::Proximo => self.proximo(),
            Acao::Anterior => self.anterior(),
            Acao::Pular(s) => self.pular(s),
            Acao::Volume(d) => self.mudar_volume(d),
            Acao::Mudo => self.alternar_mudo(),
            Acao::AlternarTelaCheia => self.alternar_tela_cheia(),
            Acao::Esc => {
                if self.ui.get_caixa_visivel() {
                    self.caixa_respondeu(false);
                } else if self.ui.get_menu_visivel() {
                    self.fechar_menu();
                } else {
                    self.sair_tela_cheia();
                }
            }
            Acao::Aleatorio => self.alternar_aleatorio(),
            Acao::Repetir => self.ciclar_repetir(),
            Acao::Painel => self.mostrar_painel(!self.ui.get_painel_visivel()),
            Acao::Explorer => self.mostrar_atual_no_explorer(),
            Acao::FotoMais => self.definir_segundos_foto(self.segundos_foto.get() + 1),
            Acao::FotoMenos => self.definir_segundos_foto(self.segundos_foto.get() - 1),
            Acao::AbrirPasta => self.abrir_pasta(),
            Acao::JuntarPasta => self.adicionar_pasta(),
            Acao::Filtro(f) => self.definir_filtro(f),
            Acao::Buscar => {
                self.mostrar_painel(true);
                self.ui.invoke_focar_busca();
            }
        }
    }

    /// Uma tecla (da camada Slint ou da hospedeira). Devolve se foi usada.
    pub fn tecla(&self, texto: &str, shift: bool, ctrl: bool, alt: bool, repetida: bool, origem: &str) -> bool {
        let Some(acao) = acao_da_tecla(texto, shift, ctrl, alt) else { return false };
        if repetida && acao.alterna() {
            return true; // engole a repetição
        }
        if self.dialogo_aberto.get() {
            return true; // a janela de escolher é modal
        }
        if (self.ui.get_menu_visivel() || self.ui.get_caixa_visivel()) && acao != Acao::Esc {
            return true; // com menu ou caixa aberta só o Esc vale
        }
        self.log(&format!("tecla na {origem}: {acao:?}"));
        self.executar(acao);
        true
    }

    fn acao_da_interface(&self, a: &str) {
        self.log(&format!("botão: {a}"));
        match a {
            "abrir-pasta" => self.abrir_pasta(),
            "juntar-pasta" => self.adicionar_pasta(),
            "continuar" => self.continuar_ultimas(),
            "mostrar-na-fila" => {
                self.mostrar_painel(true);
                self.rolar_para_atual();
            }
            "aleatorio" => self.alternar_aleatorio(),
            "anterior" => self.anterior(),
            "tocar-pausar" => self.alternar_pausa(),
            "proximo" => self.proximo(),
            "repetir" => self.ciclar_repetir(),
            "alternar-restante" => self.alternar_restante(),
            "mudo" => self.alternar_mudo(),
            "painel" => self.mostrar_painel(!self.ui.get_painel_visivel()),
            "tela-cheia" => self.alternar_tela_cheia(),
            "filtro-tudo" => self.definir_filtro(Filtro::Tudo),
            "filtro-fotos" => self.definir_filtro(Filtro::Fotos),
            "filtro-videos" => self.definir_filtro(Filtro::Videos),
            _ => {}
        }
    }

    pub fn alternar_pausa(&self) {
        let (vazia, fim, sem_item) = {
            let s = self.sessao.borrow();
            (s.fila.itens.is_empty(), s.fim_da_fila, s.item.is_none())
        };
        if vazia {
            self.abrir_pasta();
            return;
        }
        if fim || sem_item {
            if let Some(p) = self.sessao.borrow_mut().tocar_sem_item() {
                self.seguir(p);
            }
            return;
        }
        let pausar = !self.motor.ler_sim("pause").unwrap_or(false);
        let _ = self.motor.por_sim("pause", pausar);
        self.ui.set_tocando(!pausar);
        if self.heic.borrow().lendo {
            // O motor ainda está no arquivo anterior: vale quando este carregar.
            self.heic.borrow_mut().pausa_na_leitura = Some(pausar);
        }
        let foto = self.sessao.borrow().item_atual().is_some_and(|i| i.tipo == Tipo::Foto);
        if foto && !self.heic_esperando() {
            if pausar {
                self.foto_restante_ms.set(self.foto_restante_ms.get().saturating_sub(self.foto_passado_ms()));
                self.t_foto.stop();
            } else {
                self.foto_desde.set(self.agora());
                if self.sessao.borrow().fila.repetir != Repetir::Um {
                    self.armar_foto();
                }
            }
        }
    }

    pub fn proximo(&self) {
        let p = self.sessao.borrow_mut().proximo(false);
        self.seguir(p);
    }

    pub fn anterior(&self) {
        let (vazia, video, fim) = {
            let s = self.sessao.borrow();
            (s.fila.itens.is_empty(), s.item_atual().is_some_and(|i| i.tipo == Tipo::Video), s.fim_da_fila)
        };
        if vazia {
            return;
        }
        // Como no VLC/Spotify: vídeo com mais de 3 s volta para o começo dele.
        if video && !fim && self.motor.ler_real("time-pos").unwrap_or(0.0) > 3.0 {
            let _ = self.motor.comando(&["seek", "0", "absolute"]);
            return;
        }
        let p = self.sessao.borrow_mut().anterior();
        self.seguir(p);
    }

    fn pular(&self, seg: f64) {
        let Some(tipo) = self.sessao.borrow().item_atual().map(|i| i.tipo) else { return };
        if tipo == Tipo::Foto {
            if seg > 0.0 { self.proximo() } else { self.anterior() }
            return;
        }
        let _ = self.motor.comando(&["seek", &format!("{seg}"), "relative"]);
    }

    fn soltou_busca(&self, v: f32) {
        let video = self.sessao.borrow().item_atual().is_some_and(|i| i.tipo == Tipo::Video);
        if video && self.duracao.get() > 0.0 {
            let pct = (v as f64 * 100.0).clamp(0.0, 100.0);
            let _ = self.motor.comando(&["seek", &format!("{pct:.1}"), "absolute-percent"]);
        }
    }

    pub fn mudar_volume(&self, delta: i64) {
        let v = (self.ui.get_volume() as i64 + delta).clamp(0, 100);
        if v != self.ui.get_volume() as i64 {
            self.ui.set_volume(v as i32);
            self.volume_mudou(v);
        }
        self.aviso(&tf("osd_volume", &[("v", &v)]));
    }

    fn volume_da_barra(&self, v: i64) {
        let v = v.clamp(0, 100);
        if v != self.ui.get_volume() as i64 {
            self.ui.set_volume(v as i32);
            self.volume_mudou(v);
        }
    }

    fn volume_mudou(&self, v: i64) {
        let _ = self.motor.por_texto("volume", &v.to_string());
        let mudo = self.sessao.borrow().cfg.mudo();
        if v > 0 && mudo {
            self.alternar_mudo();
        }
        self.sessao.borrow_mut().cfg.definir("volume", Value::from(v));
    }

    pub fn alternar_mudo(&self) {
        let mudo = !self.sessao.borrow().cfg.mudo();
        // No modo de teste o motor fica mudo sempre; só o estado da pessoa muda.
        if !self.opcoes.teste {
            let _ = self.motor.por_sim("mute", mudo);
        }
        self.sessao.borrow_mut().cfg.definir("mudo", Value::Bool(mudo));
        self.ui.set_mudo(mudo);
        self.log(&format!("mudo: {mudo}"));
        self.aviso(&t(if mudo { "osd_sem_som" } else { "osd_som" }));
    }

    pub fn alternar_aleatorio(&self) {
        let ligado = self.sessao.borrow_mut().alternar_aleatorio();
        self.ui.set_aleatorio(ligado);
        self.log(&format!("aleatório: {}", if ligado { "ligado" } else { "desligado" }));
        self.aviso(&t(if ligado { "osd_aleatorio" } else { "osd_em_ordem" }));
        self.atualizar_lista();
        self.atualizar_info();
    }

    pub fn ciclar_repetir(&self) {
        let r = self.sessao.borrow_mut().ciclar_repetir();
        self.ui.set_repetir(r.nome().into());
        self.log(&format!("repetir: {}", r.nome()));
        self.aviso(&t(&format!("osd_repetir_{}", r.nome())));
        let Some(tipo) = self.sessao.borrow().item_atual().map(|i| i.tipo) else { return };
        // Vale na hora para o que está na tela.
        if tipo == Tipo::Video {
            let _ = self.motor.por_texto("loop-file", if r == Repetir::Um { "inf" } else { "no" });
        }
        if tipo == Tipo::Foto && !self.motor.ler_sim("pause").unwrap_or(false) && !self.heic_esperando() {
            if r == Repetir::Um {
                self.foto_restante_ms.set(self.foto_restante_ms.get().saturating_sub(self.foto_passado_ms()));
                self.foto_desde.set(self.agora());
                self.t_foto.stop();
            } else if !self.t_foto.running() {
                self.foto_desde.set(self.agora());
                self.armar_foto();
            }
        }
    }

    pub fn definir_filtro(&self, f: Filtro) {
        if f == self.sessao.borrow().fila.filtro {
            return;
        }
        let p = self.sessao.borrow_mut().definir_filtro(f);
        self.log(&format!("filtro: {}", f.nome()));
        self.ui.set_filtro(f.nome().into());
        self.aviso(&t(&format!("osd_filtro_{}", f.nome())));
        self.atualizar_lista();
        self.seguir(p);
        self.atualizar_info();
    }

    fn alternar_restante(&self) {
        self.mostrar_restante.set(!self.mostrar_restante.get());
        self.tique();
    }

    pub fn definir_segundos_foto(&self, v: i64) {
        let v = v.clamp(1, 600);
        if v == self.segundos_foto.get() {
            return;
        }
        self.segundos_foto.set(v);
        self.sessao.borrow_mut().cfg.definir("segundos_foto", Value::from(v));
        self.textos_da_foto();
        self.log(&format!("tempo da foto: {v} s"));
        self.aviso(&tf("osd_cada_foto", &[("v", &v)]));
        let foto = self.sessao.borrow().item_atual().is_some_and(|i| i.tipo == Tipo::Foto);
        if foto && self.t_foto.running() {
            let passado = (self.foto_total_ms.get().saturating_sub(self.foto_restante_ms.get())) + self.foto_passado_ms();
            self.iniciar_relogio_foto(Some((v as u64 * 1000).saturating_sub(passado).max(300)));
            self.foto_total_ms.set(v as u64 * 1000);
        }
    }

    fn recebeu_pausa(&self, pausado: bool) {
        // Sem nada tocando o mpv fica ocioso com pause=no: o botão tem que mostrar "tocar".
        let s = self.sessao.borrow();
        self.ui.set_tocando(!pausado && s.item.is_some() && !s.fim_da_fila);
    }

    /// 10 vezes por segundo: tempo e barra (da foto, a contagem até a próxima).
    pub fn tique(&self) {
        let (tipo, rep_um) = {
            let s = self.sessao.borrow();
            (s.item_atual().map(|i| i.tipo), s.fila.repetir == Repetir::Um)
        };
        let por = |prog: f32, tempo: String, total: String| {
            let prog = ((prog * 1000.0).round() / 1000.0).clamp(0.0, 1.0);
            if (self.ui.get_progresso() - prog).abs() > 0.0005 {
                self.ui.set_progresso(prog);
            }
            if self.ui.get_tempo_txt().as_str() != tempo {
                self.ui.set_tempo_txt(tempo.into());
            }
            if self.ui.get_total_txt().as_str() != total {
                self.ui.set_total_txt(total.into());
            }
        };
        match tipo {
            None => {
                if self.ui.get_busca_ativa() {
                    self.ui.set_busca_ativa(false);
                }
            }
            Some(Tipo::Video) => {
                if !self.ui.get_busca_ativa() {
                    self.ui.set_busca_ativa(true);
                }
                let tpos = self.motor.ler_real("time-pos").unwrap_or(self.t_atual.get());
                let dur = self.motor.ler_real("duration").unwrap_or(0.0);
                self.t_atual.set(tpos);
                self.duracao.set(dur);
                let total = if self.mostrar_restante.get() && dur > 0.0 {
                    format!("-{}", fmt_tempo(dur - tpos))
                } else {
                    fmt_tempo(dur)
                };
                let prog = if dur > 0.0 { (tpos / dur) as f32 } else { 0.0 };
                por(prog, fmt_tempo(tpos), total);
            }
            Some(Tipo::Foto) => {
                if self.ui.get_busca_ativa() {
                    self.ui.set_busca_ativa(false);
                }
                let total = self.foto_total_ms.get().max(1);
                let base = total.saturating_sub(self.foto_restante_ms.get());
                let feito = if self.t_foto.running() { base + self.foto_passado_ms() } else { base }.min(total);
                let total_txt = if rep_um {
                    "∞".to_string()
                } else if self.mostrar_restante.get() {
                    format!("-{}", fmt_tempo((total - feito) as f64 / 1000.0))
                } else {
                    fmt_tempo(total as f64 / 1000.0)
                };
                por(feito as f32 / total as f32, fmt_tempo(feito as f64 / 1000.0), total_txt);
            }
        }
    }

    // ================= palco =================
    fn palco_clique(&self) {
        // Espera 230 ms: se vier o segundo clique, é tela cheia, não pausa.
        self.depois(&self.t_clique, 230, |p| p.alternar_pausa());
    }

    fn palco_duplo(&self) {
        self.t_clique.stop();
        self.alternar_tela_cheia();
    }

    fn palco_mudou(&self) {
        let e = self.ui.window().scale_factor();
        let r = |v: f32| (v * e).round() as i32;
        self.plat.definir_palco(r(self.ui.get_palco_x()), r(self.ui.get_palco_y()), r(self.ui.get_palco_w()), r(self.ui.get_palco_h()));
    }

    /// Manda de novo onde fica o vídeo (a janela mudou de tamanho, de escala ou de monitor).
    pub fn reenviar_palco(&self) {
        self.palco_mudou();
    }

    // ================= tela cheia =================
    pub fn alternar_tela_cheia(&self) {
        if self.plat.em_tela_cheia() {
            self.sair_tela_cheia();
            return;
        }
        if self.sessao.borrow().fila.itens.is_empty() {
            return;
        }
        self.painel_antes.set(self.ui.get_painel_visivel());
        self.ui.set_painel_visivel(false);
        self.plat.tela_cheia(true);
        self.log_tela_cheia(true);
        self.ui.set_tela_cheia(true);
        self.ui.set_controles_visiveis(true);
        self.cursor_antes.set(self.plat.cursor());
        let eu = self.eu.clone();
        self.t_cursor.start(TimerMode::Repeated, Duration::from_millis(150), move || {
            if let Some(p) = eu.upgrade() {
                p.vigiar_cursor();
            }
        });
        self.depois(&self.t_esconder, ESCONDER.as_millis() as u64, |p| p.esconder_controles());
    }

    pub fn sair_tela_cheia(&self) {
        if !self.plat.em_tela_cheia() {
            return;
        }
        self.t_cursor.stop();
        self.t_esconder.stop();
        self.plat.tela_cheia(false);
        self.log_tela_cheia(false);
        self.ui.set_tela_cheia(false);
        self.ui.set_controles_visiveis(true);
        self.ui.set_painel_visivel(self.painel_antes.get());
    }

    fn log_tela_cheia(&self, pedido: bool) {
        if self.plat.so_registra() {
            self.log(&format!("tela cheia: não aplicada no modo teste (pedido {pedido})"));
        } else {
            self.log(&format!("tela cheia: {} (pedido {pedido})", self.plat.em_tela_cheia()));
        }
    }

    fn mostrar_controles(&self) {
        if !self.ui.get_controles_visiveis() {
            self.ui.set_controles_visiveis(true);
            self.log("controles voltam");
        }
        self.depois(&self.t_esconder, ESCONDER.as_millis() as u64, |p| p.esconder_controles());
    }

    fn vigiar_cursor(&self) {
        let pos = self.plat.cursor();
        if pos != self.cursor_antes.get() {
            self.cursor_antes.set(pos);
            self.mostrar_controles();
        }
    }

    fn mexeu(&self) {
        if self.plat.em_tela_cheia() {
            self.mostrar_controles();
        }
    }

    fn esconder_controles(&self) {
        if !self.plat.em_tela_cheia() {
            return;
        }
        let altura = (self.ui.get_barra_h() * self.ui.window().scale_factor()).round() as i32;
        if self.ui.get_controles_visiveis() && self.plat.cursor_na_faixa_de_baixo(altura) {
            self.depois(&self.t_esconder, ESCONDER.as_millis() as u64, |p| p.esconder_controles());
            return;
        }
        if self.ui.get_controles_visiveis() {
            self.ui.set_controles_visiveis(false);
            self.log("controles somem");
        }
    }

    // ================= fila lateral =================
    pub fn mostrar_painel(&self, ver: bool) {
        self.ui.set_painel_visivel(ver);
        if !self.plat.em_tela_cheia() {
            self.sessao.borrow_mut().cfg.definir("painel", Value::Bool(ver));
        }
        if ver {
            self.rolar_para_atual();
        }
    }

    fn linha_do_item(&self, i: usize) -> Option<LinhaFila> {
        let s = self.sessao.borrow();
        let it = s.fila.itens.get(i)?;
        Some(LinhaFila {
            nome: it.nome.as_str().into(),
            pasta: pasta_do_item(it).into(),
            foto: it.tipo == Tipo::Foto,
            atual: s.fila.indice_atual() == Some(i),
            falhou: it.falhou,
            selecionada: self.selecao.borrow().contains(&i),
            indice: i as i32,
        })
    }

    /// Refaz a lista (ordem de tocar e filtro de tipo da fila, mais a busca).
    fn recarregar_lista(&self) {
        let linhas: Vec<usize> = {
            let s = self.sessao.borrow();
            let busca = self.busca.borrow().to_lowercase();
            s.fila
                .ordem()
                .iter()
                .copied()
                .filter(|&i| {
                    busca.is_empty() || {
                        let it = &s.fila.itens[i];
                        format!("{} {}", it.nome, it.pasta_rel).to_lowercase().contains(&busca)
                    }
                })
                .collect()
        };
        {
            let vistas: HashSet<usize> = linhas.iter().copied().collect();
            self.selecao.borrow_mut().retain(|i| vistas.contains(i));
        }
        let dados: Vec<LinhaFila> = linhas.iter().filter_map(|&i| self.linha_do_item(i)).collect();
        *self.linhas.borrow_mut() = linhas;
        self.modelo.set_vec(dados);
    }

    fn atualizar_linha(&self, i: usize) {
        let pos = self.linhas.borrow().iter().position(|&x| x == i);
        if let (Some(r), Some(l)) = (pos, self.linha_do_item(i)) {
            if self.modelo.row_data(r).as_ref() != Some(&l) {
                self.modelo.set_row_data(r, l);
            }
        }
    }

    /// Só as linhas que mudaram de "atual".
    fn marcar_atual_na_lista(&self) {
        let atual = self.sessao.borrow().fila.indice_atual();
        for r in 0..self.modelo.row_count() {
            if let Some(mut l) = self.modelo.row_data(r) {
                let deve = Some(l.indice as usize) == atual;
                if l.atual != deve {
                    l.atual = deve;
                    self.modelo.set_row_data(r, l);
                }
            }
        }
    }

    fn atualizar_lista(&self) {
        self.recarregar_lista();
        self.atualizar_resumo();
        self.rolar_para_atual();
    }

    fn atualizar_resumo(&self) {
        let s = self.sessao.borrow();
        let itens = &s.fila.itens;
        if itens.is_empty() {
            self.ui.set_resumo(t("fila_vazia").into());
            self.ui.set_contagem("".into());
            return;
        }
        let nf = itens.iter().filter(|i| i.tipo == Tipo::Foto).count();
        let nv = itens.len() - nf;
        let n_pastas = itens.iter().filter_map(|i| i.caminho.parent()).collect::<HashSet<_>>().len();
        let mut txt = tf(
            "resumo",
            &[("fila", &milhar(s.fila.len())), ("fotos", &milhar(nf)), ("videos", &milhar(nv))],
        );
        txt.push('\n');
        txt.push_str(&tf(
            if s.pastas_abertas.len() == 1 { "resumo_pastas_1" } else { "resumo_pastas_n" },
            &[
                ("pastas", &milhar(n_pastas)),
                ("abertas", &milhar(s.pastas_abertas.len())),
                ("lidas", &milhar(self.pastas_lidas.get())),
            ],
        ));
        if self.ignorados.get() > 0 {
            txt.push_str(&tf("outros_tipos", &[("n", &milhar(self.ignorados.get()))]));
        }
        let falhas = itens.iter().filter(|i| i.falhou).count();
        if falhas == 1 {
            txt.push_str(&t("um_nao_abriu"));
        } else if falhas > 1 {
            txt.push_str(&tf("n_nao_abriram", &[("n", &milhar(falhas))]));
        }
        self.ui.set_resumo(txt.into());
        self.ui.set_contagem(milhar(s.fila.len()).into());
    }

    fn rolar_para_atual(&self) {
        if !self.ui.get_painel_visivel() {
            return;
        }
        let atual = self.sessao.borrow().fila.indice_atual();
        let Some(atual) = atual else { return };
        let linha = self.linhas.borrow().iter().position(|&i| i == atual);
        if let Some(l) = linha {
            self.ui.invoke_rolar_para(l as i32);
        }
    }

    fn busca_mudou(&self, texto: &str) {
        *self.busca.borrow_mut() = texto.to_string();
        self.recarregar_lista();
        self.rolar_para_atual();
    }

    fn definir_selecao(&self, nova: BTreeSet<usize>) {
        let antiga = std::mem::replace(&mut *self.selecao.borrow_mut(), nova);
        let nova = self.selecao.borrow().clone();
        for i in antiga.symmetric_difference(&nova) {
            self.atualizar_linha(*i);
        }
    }

    /// Clique na lista (seleção estendida do Qt: Ctrl alterna, Shift pega o intervalo).
    fn lista_clique(&self, i: i32, ctrl: bool, shift: bool) {
        let i = i as usize;
        let linhas = self.linhas.borrow().clone();
        let Some(r) = linhas.iter().position(|&x| x == i) else { return };
        let mut sel = if ctrl { self.selecao.borrow().clone() } else { BTreeSet::new() };
        if shift {
            let a = self.ancora.get().and_then(|a| linhas.iter().position(|&x| x == a)).unwrap_or(r);
            let (de, ate) = if a <= r { (a, r) } else { (r, a) };
            sel.extend(linhas[de..=ate].iter().copied());
        } else if ctrl && sel.contains(&i) {
            sel.remove(&i);
            self.ancora.set(Some(i));
        } else {
            sel.insert(i);
            self.ancora.set(Some(i));
        }
        self.definir_selecao(sel);
    }

    fn lista_duplo(&self, i: i32) {
        self.log(&format!("lista: tocar {i}"));
        let p = self.sessao.borrow_mut().ir_para(i as usize);
        self.seguir(p);
    }

    pub fn mostrar_atual_no_explorer(&self) {
        let Some(c) = self.sessao.borrow().item_atual().map(|i| i.caminho.clone()) else { return };
        self.sair_tela_cheia(); // senão o Explorer abre atrás da tela cheia
        self.mostrar_no_explorer(&c);
    }

    fn mostrar_no_explorer(&self, c: &Path) {
        let ok = self.plat.mostrar_no_explorer(c);
        self.log(&format!("explorer: {} ({})", c.display(), if ok { "ok" } else { "falhou" }));
    }

    fn tirar(&self, indices: &[usize]) {
        self.log(&format!("tirar da fila: {} item(ns)", indices.len()));
        let p = self.sessao.borrow_mut().tirar(indices);
        self.selecao.borrow_mut().clear();
        self.ancora.set(None); // os índices andaram
        self.menu_alvo.borrow_mut().clear();
        let (vazia, sem_item) = {
            let s = self.sessao.borrow();
            (s.fila.itens.is_empty(), s.item.is_none())
        };
        if vazia && sem_item {
            self.limpar();
            return;
        }
        self.atualizar_lista();
        self.seguir(p);
        self.atualizar_info();
    }

    pub fn limpar(&self) {
        if let Some(c) = self.varrendo.borrow_mut().take() {
            c.store(true, Ordering::Relaxed);
        }
        self.geracao.set(self.geracao.get() + 1);
        self.parar_motor();
        *self.heic.borrow_mut() = Heic::default();
        self.token.set(self.token.get() + 1);
        self.sessao.borrow_mut().limpar();
        self.selecao.borrow_mut().clear();
        self.tela_de_inicio();
        self.atualizar_lista();
        self.plat.titulo(NOME);
        self.log("fila limpa");
    }

    pub fn limpar_tudo(&self, confirmar: bool) {
        if confirmar && !self.sessao.borrow().cfg.ultimas_pastas().is_empty() {
            self.perguntar(Pergunta::LimparTudo, t("limpar_tudo"), t("limpar_tudo_confirma"), false, "");
            return;
        }
        self.sessao.borrow_mut().cfg.definir_ultimas_pastas(&[]);
        if let Err(e) = self.sessao.borrow().salvar() {
            self.log(&format!("config não salvo: {e}"));
        }
        self.limpar();
        self.ui.set_continuar_txt("".into());
        self.ui.set_status(t("limpos").into());
    }

    fn atualizar_info(&self) {
        let Some(it) = self.sessao.borrow().item_atual().cloned() else { return };
        let (n, total) = self.sessao.borrow().fila.posicao();
        self.ui.set_nome(it.nome.as_str().into());
        self.ui.set_info(format!("{} · {}", pasta_do_item(&it), tf("n_de_total", &[("n", &n), ("total", &total)])).into());
        self.ui.set_tipo_icone(if it.tipo == Tipo::Foto { "foto" } else { "video" }.into());
        self.ui.set_tipo_falhou(it.falhou);
        self.ui.set_caminho_atual(it.caminho.to_string_lossy().as_ref().into());
        self.plat.titulo(&format!("{} — {NOME}", it.nome));
    }

    // ================= arrastar e soltar =================
    pub fn arrastando(&self, sim: bool) {
        self.ui.set_arrastando(sim);
    }

    /// O winit entrega um evento por arquivo: junta os que chegam juntos (40 ms).
    pub fn soltar(&self, caminhos: Vec<PathBuf>) {
        self.ui.set_arrastando(false);
        if self.ui.get_caixa_visivel() || self.dialogo_aberto.get() {
            self.log(&format!("solto ignorado: {} (caixa ou janela de escolher aberta)", caminhos.len()));
            return;
        }
        self.fechar_menu();
        if self.soltos.borrow().is_empty() {
            self.ctrl_ao_soltar.set(self.plat.ctrl_apertado());
        }
        self.soltos.borrow_mut().extend(caminhos);
        self.depois(&self.t_soltar, 40, |p| p.processar_soltos());
    }

    fn processar_soltos(&self) {
        let soltos: Vec<PathBuf> = self.soltos.borrow_mut().drain(..).collect();
        if soltos.is_empty() {
            return;
        }
        for p in &soltos {
            self.log(&format!("solto: {}", p.display()));
        }
        // Ctrl ao soltar junta à fila sem parar o que toca.
        let juntar = self.ctrl_ao_soltar.get() && !self.sessao.borrow().fila.itens.is_empty();
        self.carregar(soltos, juntar);
    }

    // ================= menus =================
    fn mostrar_menu(&self, itens: Vec<LinhaMenu>, jeito: &str, x: f32, y: f32, w: f32, h: f32, qual: &str) {
        self.ui.set_menu_itens(ModelRc::new(VecModel::from(itens)));
        self.ui.set_menu_ancora_x(x);
        self.ui.set_menu_ancora_y(y);
        self.ui.set_menu_ancora_w(w);
        self.ui.set_menu_ancora_h(h);
        self.ui.set_menu_jeito(jeito.into());
        self.ui.set_menu_visivel(true);
        self.log(&format!("menu: {qual}"));
    }

    pub fn fechar_menu(&self) {
        if self.ui.get_menu_visivel() {
            self.ui.set_menu_visivel(false);
        }
    }

    fn abrir_menu(&self, id: &str, x: f32, y: f32, w: f32, h: f32) {
        match id {
            "pastas" => self.mostrar_menu(self.itens_menu_pastas(), "acima-direita", x, y, w, h, id),
            "foto" => self.mostrar_menu(self.itens_menu_foto(), "acima-esquerda", x, y, w, h, id),
            "limpar" => {
                let tem = !self.sessao.borrow().fila.itens.is_empty();
                let itens = vec![
                    linha_menu("limpar", t("limpar_fila"), t("limpar_fila_desc"), "", "limpar-fila", true, tem),
                    linha_menu("limpar", t("limpar_tudo"), t("limpar_tudo_desc"), "", "limpar-tudo", true, true),
                ];
                self.mostrar_menu(itens, "acima-esquerda", x, y, w, h, id);
            }
            _ => {}
        }
    }

    fn itens_menu_pastas(&self) -> Vec<LinhaMenu> {
        let tem_item = self.sessao.borrow().item.is_some();
        let tem_fila = !self.sessao.borrow().fila.itens.is_empty();
        let mut m = vec![
            titulo_menu(t("m_abrir")),
            linha_menu("pasta", t("abrir_pasta"), t("abrir_pasta_desc"), "Ctrl+O", "abrir-pasta", false, true),
            linha_menu("pastamais", t("juntar_outra"), t("juntar_desc"), "Ctrl+Shift+O", "juntar-pasta", false, true),
            linha_menu("foto", t("abrir_arquivos"), t("abrir_arquivos_desc"), "", "abrir-arquivos", false, true),
        ];
        let ultimas = self.ultimas_que_existem();
        if !ultimas.is_empty() {
            m.push(titulo_menu(t("ultima_fila")));
            let mut nomes = ultimas.iter().take(3).map(|p| nome_da_pasta(p)).collect::<Vec<_>>().join(", ");
            if ultimas.len() > 3 {
                nomes.push_str(&tf("e_mais", &[("n", &(ultimas.len() - 3))]));
            }
            let chave = if ultimas.len() == 1 { "continuar_1" } else { "continuar_n" };
            m.push(linha_menu("repetir", tf(chave, &[("n", &ultimas.len())]), nomes, "", "continuar", false, true));
        }
        m.push(titulo_menu(t("arquivo_na_tela")));
        m.push(linha_menu("explorer", t("mostrar_explorer"), t("mostrar_explorer_desc"), "E", "explorer", false, tem_item));
        m.push(titulo_menu(t("limpar")));
        m.push(linha_menu("limpar", t("limpar_fila"), t("limpar_fila_desc"), "", "limpar-fila", true, tem_fila));
        let historico = !self.sessao.borrow().cfg.ultimas_pastas().is_empty() || tem_fila;
        m.push(linha_menu("limpar", t("limpar_tudo"), t("limpar_tudo_desc"), "", "limpar-tudo", true, historico));
        // Usar como app padrão (só no instalado, fase 5), atualização, relato de bug, tutorial e
        // restaurar chegam nas fases 4 e 5: aparecem apagados.
        m.push(titulo_menu("Windows".into()));
        m.push(linha_menu("foto", t("usar_padrao"), t("usar_padrao_desc"), "", "", false, false));
        m.push(titulo_menu(NOME.into()));
        m.push(linha_menu("atualizar", t("procurar_atualizacao"), tf("procurar_desc", &[("versao", &env!("CARGO_PKG_VERSION"))]), "", "", false, false));
        m.push(linha_menu("bug", format!("{}…", t("relatar_bug")), t("relatar_bug_desc"), "", "", false, false));
        m.push(linha_menu("buscar", t("como_usar"), t("como_usar_desc"), "", "", false, false));
        m.push(linha_menu("repetir", t("restaurar"), t("restaurar_desc"), "", "", true, false));
        m
    }

    fn itens_menu_foto(&self) -> Vec<LinhaMenu> {
        let v = self.segundos_foto.get();
        let mut m = vec![titulo_menu(t("tempo_de_cada_foto")), explica_menu(t("video_nao_usa"))];
        for o in OPCOES_FOTO {
            m.push(radio_menu(fmt_foto(o), o == v, format!("foto:{o}")));
        }
        m.push(sep_menu());
        let outro = if OPCOES_FOTO.contains(&v) { t("outro_tempo") } else { tf("outro_tempo_agora", &[("tempo", &fmt_foto(v))]) };
        m.push(linha_menu("", outro, String::new(), "", "foto-outro", false, true));
        m
    }

    fn menu_video(&self, x: f32, y: f32) {
        let s = self.sessao.borrow();
        let pausado = s.item.is_none() || self.motor.ler_sim("pause").unwrap_or(false);
        let (alea, rep, tem_item) = (s.fila.aleatorio, s.fila.repetir, s.item.is_some());
        drop(s);
        let cheia = self.plat.em_tela_cheia();
        let itens = vec![
            linha_menu(
                if pausado { "play" } else { "pause" },
                t(if pausado { "tocar" } else { "pausar" }),
                String::new(),
                &t("tecla_espaco"),
                "tocar-pausar",
                false,
                true,
            ),
            linha_menu("proximo", t("proximo"), String::new(), "N", "proximo", false, true),
            linha_menu(
                "aleatorio",
                t(if alea { "aleatorio_ligado" } else { "aleatorio_desligado" }),
                String::new(),
                "S",
                "aleatorio",
                false,
                true,
            ),
            linha_menu("repetir", t(&format!("repetir_{}", rep.nome())), String::new(), "R", "repetir", false, true),
            titulo_menu(t("m_pastas")),
            linha_menu("pastamais", t("juntar_outra"), t("juntar_desc_curta"), "Ctrl+Shift+O", "juntar-pasta", false, true),
            linha_menu("pasta", t("abrir_pasta"), t("abrir_desc_curta"), "Ctrl+O", "abrir-pasta", false, true),
            titulo_menu(t("arquivo_na_tela")),
            linha_menu("explorer", t("mostrar_explorer"), t("mostrar_explorer_desc"), "E", "explorer", false, tem_item),
            linha_menu(
                "telacheia",
                t(if cheia { "sair_tela_cheia" } else { "tela_cheia" }),
                String::new(),
                "F",
                "tela-cheia",
                false,
                true,
            ),
        ];
        self.mostrar_menu(itens, "ponteiro", x, y, 0.0, 0.0, "video");
    }

    fn menu_lista(&self, i: i32, x: f32, y: f32) {
        let i = i as usize;
        if !self.selecao.borrow().contains(&i) {
            // Como o Qt: o botão direito numa linha fora da seleção seleciona só ela.
            self.ancora.set(Some(i));
            self.definir_selecao(BTreeSet::from([i]));
        }
        let sel: Vec<usize> = self.selecao.borrow().iter().copied().collect();
        *self.menu_alvo.borrow_mut() = std::iter::once(i).chain(sel.iter().copied().filter(|&x| x != i)).collect();
        let tirar = if sel.len() == 1 { t("tirar_da_fila") } else { tf("tirar_n_da_fila", &[("n", &sel.len())]) };
        let itens = vec![
            linha_menu("play", t("tocar_agora"), String::new(), "", "lista-tocar", false, true),
            linha_menu("explorer", t("mostrar_explorer"), String::new(), "", "lista-explorer", false, true),
            linha_menu("", t("copiar_caminho"), String::new(), "", "lista-copiar", false, true),
            sep_menu(),
            linha_menu("limpar", tirar, String::new(), "", "lista-tirar", false, true),
        ];
        self.mostrar_menu(itens, "ponteiro", x, y, 0.0, 0.0, "lista");
    }

    fn menu_escolheu(&self, a: &str) {
        self.fechar_menu();
        self.log(&format!("menu escolheu: {a}"));
        let alvo = self.menu_alvo.borrow().first().copied();
        let caminho_alvo = alvo.and_then(|i| self.sessao.borrow().fila.itens.get(i).map(|it| it.caminho.clone()));
        match a {
            "abrir-pasta" => self.abrir_pasta(),
            "juntar-pasta" => self.adicionar_pasta(),
            "abrir-arquivos" => self.abrir_arquivos(),
            "continuar" => self.continuar_ultimas(),
            "explorer" => self.mostrar_atual_no_explorer(),
            "limpar-fila" => self.limpar(),
            "limpar-tudo" => self.limpar_tudo(true),
            "tocar-pausar" => self.alternar_pausa(),
            "proximo" => self.proximo(),
            "aleatorio" => self.alternar_aleatorio(),
            "repetir" => self.ciclar_repetir(),
            "tela-cheia" => self.alternar_tela_cheia(),
            "foto-outro" => {
                let v = self.segundos_foto.get().to_string();
                self.perguntar(Pergunta::OutroTempo, t("tempo_de_cada_foto"), t("segundos"), true, &v);
            }
            "lista-tocar" => {
                if let Some(i) = alvo {
                    self.lista_duplo(i as i32);
                }
            }
            "lista-explorer" => {
                if let Some(c) = caminho_alvo {
                    self.mostrar_no_explorer(&c);
                }
            }
            "lista-copiar" => {
                if let Some(c) = caminho_alvo {
                    let ok = self.plat.copiar_texto(&c.to_string_lossy());
                    self.log(&format!("copiar caminho: {} ({})", c.display(), if ok { "ok" } else { "falhou" }));
                }
            }
            "lista-tirar" => {
                let sel: Vec<usize> = self.menu_alvo.borrow().clone();
                if !sel.is_empty() {
                    self.tirar(&sel);
                }
            }
            _ => {
                if let Some(v) = a.strip_prefix("foto:").and_then(|v| v.parse().ok()) {
                    self.definir_segundos_foto(v);
                }
            }
        }
    }

    // ================= caixa =================
    fn perguntar(&self, p: Pergunta, titulo: String, texto: String, numero: bool, valor: &str) {
        self.fechar_menu();
        self.pergunta.set(Some(p));
        self.ui.set_caixa_titulo(titulo.into());
        self.ui.set_caixa_texto(texto.into());
        self.ui.set_caixa_sim(if numero { "OK".into() } else { t("sim").into() });
        self.ui.set_caixa_nao(if numero { t("cancelar").into() } else { t("nao").into() });
        self.ui.set_caixa_numero(numero);
        self.ui.set_caixa_valor(valor.into());
        self.ui.set_caixa_visivel(true);
        self.log(&format!("caixa: {p:?}"));
    }

    fn caixa_respondeu(&self, sim: bool) {
        let Some(p) = self.pergunta.take() else { return };
        self.ui.set_caixa_visivel(false);
        self.ui.invoke_focar_janela();
        self.log(&format!("caixa: {p:?} = {}", if sim { "sim" } else { "não" }));
        if !sim {
            return;
        }
        match p {
            Pergunta::LimparTudo => self.limpar_tudo(false),
            Pergunta::OutroTempo => {
                if let Ok(v) = self.ui.get_caixa_valor().trim().parse::<i64>() {
                    self.definir_segundos_foto(v);
                }
            }
        }
    }
}
