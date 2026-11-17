//! Ciranda em Rust: mpv numa janela-hospedeira Win32 e a interface Slint numa janela de topo
//! transparente por cima do vídeo (prova da fase 1), agora com o núcleo da fase 2 (varredura,
//! fila, sessão e config da biblioteca `ciranda`).
//!
//! `DREDS_TESTE=1` (REGRA 13): nenhuma janela aparece, mpv com `vo=null`, `ao=null` e `mute`,
//! nada pega o foco. Teclas chegam por mensagem à hospedeira oculta (sem mexer no teclado real).
#![windows_subsystem = "windows"]

mod hospedeira;
mod mpv;

use std::cell::{Cell, RefCell};
use std::ffi::c_void;
use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use ciranda::biblioteca::{Estatisticas, Item, Tipo, varrer_varios};
use ciranda::config::Config;
use ciranda::fila::{Filtro, Repetir};
use ciranda::modo_teste;
use ciranda::sessao::{Passo, Sessao};
use slint::platform::Key;
use slint::winit_030::{EventResult, WinitWindowAccessor, winit};
use slint::{ComponentHandle, SharedString, Timer, TimerMode};

use hospedeira::Aviso;
use mpv::{Evento, Mpv, Valor};

slint::include_modules!();

const OCULTAR: Duration = Duration::from_millis(2500);
/// Altura da barra de controles (a mesma do app.slint), em DIP.
const BARRA_DIP: i32 = 76;

/// Pasta de dados: `%APPDATA%\Ciranda-rust-prova`, ou `CIRANDA_DADOS` (testes). Nunca a da
/// Ciranda 1.x (`%APPDATA%\Ciranda`): o app se recusa a usar essa.
fn pasta_dados() -> Result<PathBuf, String> {
    use ciranda::biblioteca::{absoluto, destino_real, normcase};
    let appdata = std::env::var_os("APPDATA")
        .filter(|a| !a.is_empty())
        .map(PathBuf::from)
        .ok_or("APPDATA vazio: sem ele não dá para saber onde fica a pasta da Ciranda 1.x")?;
    let p = std::env::var_os("CIRANDA_DADOS").map(PathBuf::from).unwrap_or_else(|| appdata.join("Ciranda-rust-prova"));
    let p = absoluto(&p);
    // A pasta da 1.x pelo APPDATA e pelo perfil (dentro de um pacote MSIX o APPDATA é
    // redirecionado), cada uma também pelo destino real (junção, link, nome 8.3, `\\?\`). Recusa a
    // pasta e qualquer coisa dentro dela, com ou sem barra no fim.
    let mut proibidas = vec![absoluto(&appdata.join("Ciranda"))];
    if let Some(perfil) = std::env::var_os("USERPROFILE").filter(|a| !a.is_empty()) {
        proibidas.push(absoluto(&PathBuf::from(perfil).join(r"AppData\Roaming\Ciranda")));
    }
    let chaves_proibidas: Vec<String> = proibidas.iter().flat_map(|x| [normcase(x), destino_real(x)]).collect();
    let dentro = |c: &str, q: &str| c == q || c.starts_with(&format!("{}\\", q.trim_end_matches('\\')));
    if [normcase(&p), destino_real(&p)].iter().any(|c| chaves_proibidas.iter().any(|q| dentro(c, q))) {
        return Err(format!("pasta de dados proibida (é a da Ciranda 1.x ou fica dentro dela): {}", p.display()));
    }
    std::fs::create_dir_all(&p).map_err(|e| format!("{}: {e}", p.display()))?;
    Ok(p)
}

#[derive(Debug, Clone, Copy)]
enum Acao {
    TocarPausar,
    Proximo,
    Anterior,
    Pular(f64),
    AlternarTelaCheia,
    SairTelaCheia,
    Aleatorio,
    Repetir,
    Filtro(Filtro),
}

struct Medicao {
    saida: PathBuf,
    segundos: u64,
    aquecer: u64,
    sair: bool,
}

/// sha256 da libmpv-2.dll oficial LGPL 0.42 (a mesma da 1.5.1). Outra DLL (um build GPL, por
/// exemplo) mudaria a licença do conjunto: o app se recusa a carregar.
const DLL_SHA256: &str = "94fb87247732c59915cd59808bc582e843a71c22214b7b6c1e5563aa8149cef4";

fn sha256_hex(caminho: &Path) -> Result<String, String> {
    use windows_sys::Win32::Security::Cryptography::{BCRYPT_SHA256_ALG_HANDLE, BCryptHash};
    let dados = std::fs::read(caminho).map_err(|e| format!("{}: {e}", caminho.display()))?;
    let mut saida = [0u8; 32];
    let st = unsafe {
        BCryptHash(BCRYPT_SHA256_ALG_HANDLE, std::ptr::null(), 0, dados.as_ptr(), dados.len() as u32, saida.as_mut_ptr(), 32)
    };
    if st != 0 {
        return Err(format!("BCryptHash falhou: {st:#x}"));
    }
    Ok(saida.iter().map(|b| format!("{b:02x}")).collect())
}

/// Tempo de CPU (usuário + núcleo) de todas as threads do processo, em segundos.
fn cpu_do_processo_s() -> f64 {
    use windows_sys::Win32::Foundation::FILETIME;
    use windows_sys::Win32::System::Threading::{GetCurrentProcess, GetProcessTimes};
    let z = || FILETIME { dwLowDateTime: 0, dwHighDateTime: 0 };
    let (mut a, mut b, mut k, mut u) = (z(), z(), z(), z());
    unsafe { GetProcessTimes(GetCurrentProcess(), &mut a, &mut b, &mut k, &mut u) };
    let s = |f: FILETIME| ((f.dwHighDateTime as u64) << 32 | f.dwLowDateTime as u64) as f64 / 1e7;
    s(k) + s(u)
}

fn ctrl_apertado() -> bool {
    use windows_sys::Win32::UI::Input::KeyboardAndMouse::{GetKeyState, VK_CONTROL};
    (unsafe { GetKeyState(VK_CONTROL as i32) } as u16 & 0x8000) != 0
}

struct App {
    mpv: Mpv,
    ui: Camada,
    inicio: Instant,
    log: RefCell<std::fs::File>,
    /// Modo de teste invisível e mudo (DREDS_TESTE=1).
    teste: bool,
    /// No modo de teste: fecha sozinho quando a fila acaba (CIRANDA_SAIR_NO_FIM=1).
    sair_no_fim: bool,
    sessao: RefCell<Sessao>,
    /// A varredura em andamento (o sinal de cancelar) e o número dela (resultado velho é ignorado).
    varrendo: RefCell<Option<Arc<AtomicBool>>>,
    geracao: Cell<u64>,
    carregado_em: Cell<Option<Instant>>,
    esperando_quadro: Cell<bool>,
    motor_anotado: Cell<bool>,
    /// No modo teste: o `current-ao` só existe quando toca algo com som; anota na primeira vez.
    audio_anotado: Cell<bool>,
    eh_foto: Cell<bool>,
    foto_timer: Timer,
    foto_total: Cell<Duration>,
    foto_restante: Cell<Duration>,
    foto_desde: Cell<Option<Instant>>,
    foto_ativa: Cell<bool>,
    pausado: Cell<bool>,
    ocultar_timer: Timer,
    relogio: Timer,
    soltos: RefCell<Vec<PathBuf>>,
    soltar_timer: Timer,
    aviso_timer: Timer,
    repinturas: Cell<u64>,
    medicao: Option<Medicao>,
    medir_timer: Timer,
    primeiro_quadro_ms: Cell<f64>,
    desde_inicio_ms: Cell<f64>,
    medida_inicio: Cell<Option<(Instant, f64, [Option<i64>; 3], u64)>>,
    medicao_agendada: Cell<bool>,
    notificador_ok: Cell<bool>,
    pular_timer: Timer,
}

thread_local! {
    static APP: RefCell<Option<Rc<App>>> = const { RefCell::new(None) };
}
static EVENTOS_PENDENTES: AtomicBool = AtomicBool::new(false);

fn app() -> Option<Rc<App>> {
    APP.with(|a| a.borrow().clone())
}

impl App {
    fn log(&self, texto: &str) {
        let t = self.inicio.elapsed().as_secs_f64();
        let mut f = self.log.borrow_mut();
        let _ = writeln!(f, "{t:9.3} {texto}");
        let _ = f.flush();
    }

    fn avisar_na_tela(&self, texto: &str) {
        self.ui.set_aviso(texto.into());
        let fraco = self.ui.as_weak();
        self.aviso_timer.start(TimerMode::SingleShot, Duration::from_millis(1300), move || {
            if let Some(ui) = fraco.upgrade() {
                ui.set_aviso("".into());
            }
        });
    }

    fn atualizar_nome(&self) {
        let s = self.sessao.borrow();
        let (pos, total) = s.fila.posicao();
        if let Some(it) = s.item_atual() {
            self.ui.set_nome(format!("{}  ·  {pos} de {total}", it.nome).into());
        }
    }

    /// Toca o item `i` de `fila.itens` (a sessão já o marcou como o da tela).
    fn tocar(&self, i: usize) {
        let Some(item) = self.sessao.borrow().fila.itens.get(i).cloned() else { return };
        let repetir_um = self.sessao.borrow().fila.repetir == Repetir::Um;
        self.parar_relogio_foto();
        self.pular_timer.stop(); // um "pular" pendente do arquivo anterior não vale mais
        let foto = item.tipo == Tipo::Foto;
        self.eh_foto.set(foto);
        // GIF anima em loop pelo tempo da foto; vídeo em "repetir um" fica em loop; o resto toca uma vez.
        let laco = item.animada() || (!foto && repetir_um);
        let _ = self.mpv.por_texto("loop-file", if laco { "inf" } else { "no" });
        // Só arma no FILE_LOADED deste arquivo: um playback-restart atrasado do anterior não conta.
        self.esperando_quadro.set(false);
        self.carregado_em.set(Some(Instant::now()));
        let texto = item.caminho.to_string_lossy().into_owned();
        if let Err(e) = self.mpv.comando(&["loadfile", &texto, "replace"]) {
            // Como a 1.5.1: conta como arquivo que não abriu (senão a fila parava aqui).
            self.log(&format!("loadfile falhou: {e}"));
            let p = self.sessao.borrow_mut().arquivo_falhou();
            self.seguir(p);
            return;
        }
        let _ = self.mpv.por_sim("pause", false);
        // A "pause" já era falsa no mpv ocioso: o evento de mudança não vem, então o botão muda aqui.
        self.pausado.set(false);
        self.ui.set_tocando(true);
        self.atualizar_nome();
        let (pos, total) = self.sessao.borrow().fila.posicao();
        self.log(&format!("tocando {pos}/{total} {}", item.caminho.display()));
    }

    /// Executa a decisão da sessão.
    fn seguir(&self, p: Passo) {
        match p {
            Passo::Nada => {}
            Passo::Tocar(i) => self.tocar(i),
            Passo::FimDaFila | Passo::NenhumAbriu => {
                self.parar_relogio_foto();
                let _ = self.mpv.por_sim("pause", true);
                if p == Passo::FimDaFila {
                    self.log("fim da fila");
                    self.avisar_na_tela("Fim da fila");
                } else {
                    self.log("nenhum arquivo da fila abriu, parando");
                    self.avisar_na_tela("Nenhum arquivo abriu");
                }
                self.sair_se_teste();
            }
            Passo::NadaComFiltro => {
                self.parar_relogio_foto();
                let _ = self.mpv.comando(&["stop"]);
                self.ui.set_nome("Nada com este filtro".into());
                self.log("nada com este filtro");
            }
            Passo::NenhumaMidia => {
                self.log("nenhuma foto ou vídeo");
                self.avisar_na_tela("Nada para tocar aqui");
                if self.sessao.borrow().fila.itens.is_empty() {
                    self.sair_se_teste();
                }
            }
            Passo::Juntou => {
                self.log(&format!("juntou: fila com {}", self.sessao.borrow().fila.len()));
                self.atualizar_nome();
            }
            Passo::PularFalho => {
                self.avisar_na_tela("Não abriu: pulando");
                // Como a 1.5.1: o próximo é escolhido 50 ms depois, com o filtro de então.
                self.pular_timer.start(TimerMode::SingleShot, Duration::from_millis(50), || {
                    if let Some(a) = app() {
                        let p = a.sessao.borrow_mut().pular_falho();
                        a.seguir(p);
                    }
                });
            }
        }
    }

    fn sair_se_teste(&self) {
        if self.teste && self.sair_no_fim {
            self.log("modo teste: fila acabou, saindo");
            Timer::single_shot(Duration::from_millis(100), || {
                slint::quit_event_loop().ok();
            });
        }
    }

    // ---- relógio da foto (só conta quando a foto aparece; pausa congela; repetir um não passa) ----
    fn iniciar_relogio_foto(&self) {
        self.foto_restante.set(self.foto_total.get());
        self.foto_ativa.set(true);
        if !self.pausado.get() && self.sessao.borrow().fila.repetir != Repetir::Um {
            self.retomar_relogio_foto();
        }
    }
    fn retomar_relogio_foto(&self) {
        if !self.foto_ativa.get() {
            return;
        }
        self.foto_desde.set(Some(Instant::now()));
        self.foto_timer.start(TimerMode::SingleShot, self.foto_restante.get(), || {
            if let Some(a) = app() {
                a.foto_ativa.set(false);
                a.foto_desde.set(None);
                a.log(&format!("foto: {} s, passa", a.foto_total.get().as_secs()));
                let p = a.sessao.borrow_mut().foto_acabou();
                a.seguir(p);
            }
        });
    }
    fn pausar_relogio_foto(&self) {
        if let Some(d) = self.foto_desde.take() {
            self.foto_restante.set(self.foto_restante.get().saturating_sub(d.elapsed()));
        }
        self.foto_timer.stop();
    }
    fn parar_relogio_foto(&self) {
        self.foto_timer.stop();
        self.foto_desde.set(None);
        self.foto_ativa.set(false);
    }
    fn foto_falta(&self) -> Duration {
        match self.foto_desde.get() {
            Some(d) => self.foto_restante.get().saturating_sub(d.elapsed()),
            None => self.foto_restante.get(),
        }
    }

    fn executar(&self, a: Acao) {
        match a {
            Acao::TocarPausar => {
                let p = self.sessao.borrow_mut().tocar_sem_item();
                match p {
                    Some(p) => self.seguir(p),
                    None => {
                        let p = self.mpv.ler_sim("pause").unwrap_or(false);
                        let _ = self.mpv.por_sim("pause", !p);
                    }
                }
            }
            Acao::Proximo => {
                let p = self.sessao.borrow_mut().proximo(false);
                self.seguir(p);
            }
            Acao::Anterior => {
                // Como no VLC/Spotify: vídeo com mais de 3 s volta para o começo dele.
                let fim = self.sessao.borrow().fim_da_fila;
                if !self.eh_foto.get() && !fim && self.mpv.ler_real("time-pos").unwrap_or(0.0) > 3.0 {
                    let _ = self.mpv.comando(&["seek", "0", "absolute"]);
                    return;
                }
                let p = self.sessao.borrow_mut().anterior();
                self.seguir(p);
            }
            Acao::Pular(s) => {
                if self.eh_foto.get() {
                    self.executar(if s > 0.0 { Acao::Proximo } else { Acao::Anterior });
                } else {
                    let _ = self.mpv.comando(&["seek", &format!("{s}"), "relative"]);
                }
            }
            Acao::AlternarTelaCheia => self.tela_cheia(!hospedeira::em_tela_cheia()),
            Acao::SairTelaCheia => self.tela_cheia(false),
            Acao::Aleatorio => {
                let ligado = self.sessao.borrow_mut().alternar_aleatorio();
                self.log(&format!("aleatório: {}", if ligado { "ligado" } else { "desligado" }));
                self.avisar_na_tela(if ligado { "Aleatório" } else { "Em ordem" });
                self.atualizar_nome();
            }
            Acao::Repetir => {
                let r = self.sessao.borrow_mut().ciclar_repetir();
                self.log(&format!("repetir: {}", r.nome()));
                self.avisar_na_tela(match r {
                    Repetir::Nao => "Repetir: desligado",
                    Repetir::Tudo => "Repetir: a fila",
                    Repetir::Um => "Repetir: só este",
                });
                // Vale na hora para o que está na tela.
                if self.sessao.borrow().item.is_some() {
                    if !self.eh_foto.get() {
                        let _ = self.mpv.por_texto("loop-file", if r == Repetir::Um { "inf" } else { "no" });
                    } else if self.foto_ativa.get() && !self.pausado.get() {
                        if r == Repetir::Um {
                            self.pausar_relogio_foto();
                        } else if self.foto_desde.get().is_none() {
                            self.retomar_relogio_foto();
                        }
                    }
                }
            }
            Acao::Filtro(f) => {
                let p = self.sessao.borrow_mut().definir_filtro(f);
                self.log(&format!("filtro: {}", f.nome()));
                self.avisar_na_tela(match f {
                    Filtro::Tudo => "Tudo",
                    Filtro::Fotos => "Só fotos",
                    Filtro::Videos => "Só vídeos",
                });
                self.seguir(p);
                self.atualizar_nome();
            }
        }
    }

    fn tela_cheia(&self, ligar: bool) {
        if self.teste {
            self.log(&format!("tela cheia: não aplicada no modo teste (pedido {ligar})"));
            return;
        }
        hospedeira::tela_cheia(ligar);
        // Registra o estado de fato, não o pedido: Esc em modo janela não pode parecer "saiu".
        self.log(&format!("tela cheia: {} (pedido {ligar})", hospedeira::em_tela_cheia()));
        self.mostrar_controles();
        if !ligar {
            self.ocultar_timer.stop();
        }
    }

    fn mostrar_controles(&self) {
        if !self.ui.get_controles_visiveis() {
            self.ui.set_controles_visiveis(true);
            self.log("controles voltam");
        }
        if hospedeira::em_tela_cheia() {
            self.ocultar_timer.start(TimerMode::SingleShot, OCULTAR, || {
                if let Some(a) = app() {
                    if hospedeira::em_tela_cheia() && hospedeira::cursor_sobre_a_barra(BARRA_DIP) {
                        a.mostrar_controles(); // mouse parado sobre a barra: ela fica
                    } else if hospedeira::em_tela_cheia() && a.ui.get_controles_visiveis() {
                        a.ui.set_controles_visiveis(false);
                        a.log("controles somem");
                    }
                }
            });
        }
    }

    /// Atualiza barra e tempo 4 vezes por segundo, e só se o texto/posição mudou
    /// (o Slint só repinta quando uma propriedade muda).
    fn atualizar_relogio(&self) {
        let (prog, texto) = if self.eh_foto.get() {
            let falta = self.foto_falta().as_secs_f64();
            let total = self.foto_total.get().as_secs_f64().max(0.001);
            let prog = if self.foto_ativa.get() { ((total - falta) / total) as f32 } else { 0.0 };
            (prog, format!("foto · {:.0} s", falta.ceil()))
        } else {
            let pos = self.mpv.ler_real("time-pos").unwrap_or(0.0);
            let dur = self.mpv.ler_real("duration").unwrap_or(0.0);
            let prog = if dur > 0.0 { (pos / dur) as f32 } else { 0.0 };
            (prog, format!("{} / {}", hms(pos), hms(dur)))
        };
        let prog = (prog * 1000.0).round() / 1000.0;
        if (self.ui.get_progresso() - prog).abs() > 0.0005 {
            self.ui.set_progresso(prog);
        }
        if self.ui.get_tempo_texto().as_str() != texto {
            self.ui.set_tempo_texto(texto.into());
        }
    }

    fn caminho_da_tela(&self) -> Option<PathBuf> {
        self.sessao.borrow().item_atual().map(|i| i.caminho.clone())
    }

    fn drenar_mpv(&self) {
        EVENTOS_PENDENTES.store(false, Ordering::Release);
        while let Some(e) = self.mpv.proximo_evento() {
            match e {
                Evento::ArquivoCarregado => {
                    self.log("arquivo carregado");
                    self.esperando_quadro.set(true);
                    let heic = self.sessao.borrow().item_atual().is_some_and(|i| matches!(i.ext.as_str(), ".heic" | ".heif"));
                    if heic {
                        // Mesmo truque da 1.5.1: a grade só fica certa depois de um seek 0.
                        let _ = self.mpv.comando(&["seek", "0", "absolute+exact"]);
                    }
                    if self.teste && !self.motor_anotado.replace(true) {
                        let l = |p: &str| self.mpv.ler_texto(p).unwrap_or_else(|| "?".into());
                        self.log(&format!(
                            "modo teste: vo={} ao={} mute={} (opções vo={} ao={})",
                            l("current-vo"),
                            l("current-ao"),
                            l("mute"),
                            l("options/vo"),
                            l("options/ao")
                        ));
                    }
                }
                Evento::Reinicio => {
                    if self.teste && !self.audio_anotado.get() {
                        if let Some(ao) = self.mpv.ler_texto("current-ao") {
                            self.audio_anotado.set(true);
                            let mudo = self.mpv.ler_texto("mute").unwrap_or_else(|| "?".into());
                            self.log(&format!("modo teste: áudio em ao={ao} mute={mudo}"));
                        }
                    }
                    if self.esperando_quadro.replace(false) {
                        let ms = self
                            .carregado_em
                            .get()
                            .map(|t| t.elapsed().as_secs_f64() * 1000.0)
                            .unwrap_or(0.0);
                        let desde = self.inicio.elapsed().as_secs_f64() * 1000.0;
                        self.primeiro_quadro_ms.set(ms);
                        self.desde_inicio_ms.set(desde);
                        self.log(&format!(
                            "primeiro quadro: {ms:.0} ms depois do loadfile, {desde:.0} ms depois de abrir"
                        ));
                        if self.eh_foto.get() {
                            self.iniciar_relogio_foto();
                        }
                        self.agendar_medicao();
                    }
                }
                Evento::FimArquivo { motivo, erro } => {
                    if motivo == 4 {
                        let caminho = self.caminho_da_tela().map(|p| p.display().to_string()).unwrap_or_default();
                        self.log(&format!("não abriu: {caminho} (erro {erro})"));
                        let p = self.sessao.borrow_mut().arquivo_falhou();
                        self.seguir(p);
                    }
                }
                Evento::Propriedade { nome, valor, .. } => match (nome.as_str(), valor) {
                    ("pause", Valor::Sim(p)) => {
                        self.pausado.set(p);
                        // Com a fila vazia (mpv ocioso) o botão mostra "tocar", não "pausar".
                        self.ui.set_tocando(!p && !self.sessao.borrow().fila.itens.is_empty());
                        if self.eh_foto.get() && self.foto_ativa.get() {
                            if p {
                                self.pausar_relogio_foto()
                            } else if self.sessao.borrow().fila.repetir != Repetir::Um {
                                self.retomar_relogio_foto()
                            }
                        }
                    }
                    ("eof-reached", Valor::Sim(true)) => {
                        // Guarda da 1.5.1 (_video_acabou): aviso de menos de 0,3 s depois do loadfile
                        // é do arquivo anterior (apertar N bem no fim do vídeo); e relê o eof-reached.
                        let atrasado = self.carregado_em.get().is_some_and(|t| t.elapsed() < Duration::from_millis(300));
                        let ainda = self.mpv.ler_sim("eof-reached").unwrap_or(true);
                        if !self.eh_foto.get() && !atrasado && ainda {
                            self.log("fim do vídeo");
                            let p = self.sessao.borrow_mut().video_acabou();
                            self.seguir(p);
                        }
                    }
                    _ => {}
                },
                Evento::Log { nivel, prefixo, texto } => {
                    self.log(&format!("[mpv {nivel}] {prefixo}: {}", texto.trim_end()));
                }
                Evento::FimDoMotor => {
                    // O núcleo do mpv saiu: não há mais o que tocar, e a API não pode mais ser usada.
                    self.log("motor encerrou");
                    slint::quit_event_loop().ok();
                    return;
                }
                _ => {}
            }
        }
    }

    fn agendar_medicao(&self) {
        let Some(m) = &self.medicao else { return };
        // Uma vez por processo: o próximo arquivo não pode reiniciar a janela de medição.
        if self.medicao_agendada.replace(true) {
            return;
        }
        // Aquece alguns segundos (shaders, cache) e só então começa a contar.
        self.medir_timer.start(TimerMode::SingleShot, Duration::from_secs(m.aquecer), || {
            if let Some(a) = app() {
                a.marcar_inicio_da_medicao();
            }
        });
    }

    fn contadores(&self) -> [Option<i64>; 3] {
        ["frame-drop-count", "decoder-frame-drop-count", "vo-delayed-frame-count"].map(|p| self.mpv.ler_inteiro(p))
    }

    fn marcar_inicio_da_medicao(&self) {
        let Some(m) = &self.medicao else { return };
        self.medida_inicio.set(Some((Instant::now(), cpu_do_processo_s(), self.contadores(), self.repinturas.get())));
        let _ = std::fs::write(m.saida.with_extension("comecou"), b"1");
        self.log("medição: começou a contar");
        self.medir_timer.start(TimerMode::SingleShot, Duration::from_secs(m.segundos), || {
            if let Some(a) = app() {
                a.gravar_medicao();
            }
        });
    }

    fn gravar_medicao(&self) {
        let Some(m) = &self.medicao else { return };
        let Some((t0, cpu0, c0, rep0)) = self.medida_inicio.get() else { return };
        let dt = t0.elapsed().as_secs_f64();
        let cpu = cpu_do_processo_s() - cpu0;
        let c1 = self.contadores();
        let mut campos: Vec<(String, String)> = Vec::new();
        let atual = self.caminho_da_tela().unwrap_or_default();
        campos.push(("arquivo".into(), json_txt(&atual.to_string_lossy())));
        for p in [
            "hwdec-current",
            "current-vo",
            "video-params/pixelformat",
            "video-params/hw-pixelformat",
            "video-codec",
            "mpv-version",
            "ffmpeg-version",
            "video-sync",
        ] {
            campos.push((p.into(), self.mpv.ler_texto(p).map(|s| json_txt(&s)).unwrap_or("null".into())));
        }
        for p in ["frame-drop-count", "decoder-frame-drop-count", "vo-delayed-frame-count", "width", "height", "osd-width", "osd-height"] {
            campos.push((p.into(), self.mpv.ler_inteiro(p).map(|v| v.to_string()).unwrap_or("null".into())));
        }
        for (i, nome) in ["perdidos_na_janela", "perdidos_decoder_na_janela", "atrasados_na_janela"].iter().enumerate() {
            // Contador que faltou vira null (nunca um número que pareça medido).
            let d = match (c0[i], c1[i]) {
                (Some(a), Some(b)) => (b - a).to_string(),
                _ => "null".into(),
            };
            campos.push(((*nome).into(), d));
        }
        for p in ["estimated-vf-fps", "container-fps", "display-fps", "time-pos"] {
            campos.push((p.into(), self.mpv.ler_real(p).map(|v| format!("{v:.3}")).unwrap_or("null".into())));
        }
        campos.push(("cpu_pct_um_nucleo".into(), format!("{:.2}", cpu / dt * 100.0)));
        campos.push(("janela_s".into(), format!("{dt:.2}")));
        campos.push(("primeiro_quadro_ms".into(), format!("{:.1}", self.primeiro_quadro_ms.get())));
        campos.push(("desde_inicio_ms".into(), format!("{:.1}", self.desde_inicio_ms.get())));
        campos.push(("aquecer_s".into(), m.aquecer.to_string()));
        let rep = if self.notificador_ok.get() { (self.repinturas.get() - rep0).to_string() } else { "null".into() };
        campos.push(("repinturas_da_interface".into(), rep));
        let corpo = campos.iter().map(|(k, v)| format!("  {}: {v}", json_txt(k))).collect::<Vec<_>>().join(",\n");
        let _ = std::fs::write(&m.saida, format!("{{\n{corpo}\n}}\n"));
        self.log(&format!("medição gravada em {}", m.saida.display()));
        if m.sair {
            slint::quit_event_loop().ok();
        }
    }

    /// Abre (troca a fila) ou junta (Ctrl ao soltar) pastas e arquivos: a varredura roda numa
    /// thread e pode ser cancelada por uma nova.
    fn carregar(&self, caminhos: Vec<PathBuf>, juntar: bool) {
        let carga = self.sessao.borrow_mut().preparar_carga(&caminhos, juntar);
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
        self.log(&format!("lendo {} caminho(s){}", carga.caminhos.len(), if carga.juntar { ", juntando à fila" } else { "" }));
        if self.sessao.borrow().item.is_none() {
            self.ui.set_nome("Lendo…".into());
        }
        let t0 = Instant::now();
        std::thread::spawn(move || {
            let mut stats = Estatisticas::default();
            let c = cancelar.clone();
            let itens = varrer_varios(
                &carga.caminhos,
                &move || c.load(Ordering::Relaxed),
                &mut |n, _| {
                    let _ = slint::invoke_from_event_loop(move || {
                        if let Some(a) = app() {
                            if a.geracao.get() == geracao && a.sessao.borrow().item.is_none() {
                                a.ui.set_nome(format!("Lendo… {n}").into());
                            }
                        }
                    });
                },
                &mut stats,
            );
            if cancelar.load(Ordering::Relaxed) {
                return;
            }
            let segundos = t0.elapsed().as_secs_f64();
            let _ = slint::invoke_from_event_loop(move || {
                if let Some(a) = app() {
                    a.varredura_terminou(geracao, itens, carga.juntar, stats, segundos);
                }
            });
        });
    }

    fn varredura_terminou(&self, geracao: u64, itens: Vec<Item>, juntar: bool, stats: Estatisticas, segundos: f64) {
        if geracao != self.geracao.get() {
            return; // de uma varredura que outra já substituiu
        }
        self.varrendo.borrow_mut().take();
        for l in self.sessao.borrow().linhas_da_varredura(&itens, &stats) {
            self.log(&l);
        }
        self.log(&format!("varredura em {segundos:.3} s"));
        let p = self.sessao.borrow_mut().varredura_pronta(itens, juntar);
        self.seguir(p);
    }

    fn processar_soltos(&self) {
        let soltos: Vec<PathBuf> = self.soltos.borrow_mut().drain(..).collect();
        if soltos.is_empty() {
            return;
        }
        for p in &soltos {
            self.log(&format!("solto: {}", p.display()));
        }
        // Ctrl ao soltar junta à fila sem parar o que toca (como a 1.5.1).
        let juntar = ctrl_apertado();
        self.carregar(soltos, juntar);
    }

    fn soltar(&self, caminhos: Vec<PathBuf>) {
        self.soltos.borrow_mut().extend(caminhos);
        // O winit entrega um evento por arquivo: junta os que chegam juntos.
        self.soltar_timer.start(TimerMode::SingleShot, Duration::from_millis(40), || {
            if let Some(a) = app() {
                a.processar_soltos();
            }
        });
    }
}

fn hms(s: f64) -> String {
    let s = s.max(0.0) as u64;
    if s >= 3600 {
        format!("{}:{:02}:{:02}", s / 3600, (s / 60) % 60, s % 60)
    } else {
        format!("{}:{:02}", s / 60, s % 60)
    }
}

fn json_txt(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)),
            c => o.push(c),
        }
    }
    o.push('"');
    o
}

fn acao_do_texto(t: &str, shift: bool) -> Option<Acao> {
    let k = |key: Key| SharedString::from(key);
    let s = SharedString::from(t);
    let passo = if shift { 30.0 } else { 5.0 };
    Some(match t {
        " " => Acao::TocarPausar,
        "f" | "F" => Acao::AlternarTelaCheia,
        "n" | "N" => Acao::Proximo,
        "p" | "P" => Acao::Anterior,
        "s" | "S" => Acao::Aleatorio,
        "r" | "R" => Acao::Repetir,
        "1" => Acao::Filtro(Filtro::Tudo),
        "2" => Acao::Filtro(Filtro::Fotos),
        "3" => Acao::Filtro(Filtro::Videos),
        _ if s == k(Key::Return) => Acao::AlternarTelaCheia,
        _ if s == k(Key::F11) => Acao::AlternarTelaCheia,
        _ if s == k(Key::Escape) => Acao::SairTelaCheia,
        _ if s == k(Key::RightArrow) => Acao::Pular(passo),
        _ if s == k(Key::LeftArrow) => Acao::Pular(-passo),
        _ => return None,
    })
}

fn acao_do_vk(vk: u32, shift: bool) -> Option<Acao> {
    let passo = if shift { 30.0 } else { 5.0 };
    Some(match vk {
        0x20 => Acao::TocarPausar,                     // VK_SPACE
        0x46 | 0x0D | 0x7A => Acao::AlternarTelaCheia, // F, VK_RETURN, VK_F11
        0x1B => Acao::SairTelaCheia,                   // VK_ESCAPE
        0x4E => Acao::Proximo,                         // N
        0x50 => Acao::Anterior,                        // P
        0x53 => Acao::Aleatorio,                       // S
        0x52 => Acao::Repetir,                         // R
        0x31 => Acao::Filtro(Filtro::Tudo),            // 1
        0x32 => Acao::Filtro(Filtro::Fotos),           // 2
        0x33 => Acao::Filtro(Filtro::Videos),          // 3
        0x27 => Acao::Pular(passo),                    // VK_RIGHT
        0x25 => Acao::Pular(-passo),                   // VK_LEFT
        _ => return None,
    })
}

/// Ações que alternam estado: segurar a tecla não pode ficar ligando e desligando.
fn alterna(a: &Acao) -> bool {
    matches!(a, Acao::TocarPausar | Acao::AlternarTelaCheia | Acao::SairTelaCheia | Acao::Aleatorio | Acao::Repetir)
}

fn ao_avisar(a: Aviso) {
    let Some(app) = app() else { return };
    match a {
        Aviso::Tecla { vk, shift, repetida, ctrl_alt } => {
            if ctrl_alt {
                return; // Ctrl+F, Alt+N etc. ainda não são atalhos (fase 3)
            }
            if let Some(acao) = acao_do_vk(vk, shift).filter(|a| !(repetida && alterna(a))) {
                app.log(&format!("tecla na hospedeira: {acao:?}"));
                app.executar(acao);
            }
        }
        Aviso::Soltou(v) => app.soltar(v),
        Aviso::Fechar => {
            app.log("hospedeira pediu para fechar");
            slint::quit_event_loop().ok();
        }
        Aviso::Ativou => app.log("hospedeira ativada"),
    }
}

/// Laço modal (barra de título segurada): roda os timers do Slint (relógio da foto, ocultar
/// controles, relógio da barra) e lê os eventos do mpv (fim do vídeo passa para o próximo).
fn no_laco_modal() {
    slint::platform::update_timers_and_animations();
    if let Some(a) = app() {
        a.drenar_mpv();
    }
}

unsafe extern "C" fn mpv_acordou(_: *mut c_void) {
    // Roda numa thread do mpv: só agenda a leitura na thread da interface (uma por vez).
    if !EVENTOS_PENDENTES.swap(true, Ordering::AcqRel) {
        let r = slint::invoke_from_event_loop(|| {
            if let Some(a) = app() {
                a.drenar_mpv();
            }
        });
        if r.is_err() {
            // Laço do Slint ainda não existe: a leitura inicial (em rodar) pega estes eventos.
            EVENTOS_PENDENTES.store(false, Ordering::Release);
        }
    }
}

fn hwnd_do_winit(w: &winit::window::Window) -> Option<isize> {
    use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
    match w.window_handle().ok()?.as_raw() {
        RawWindowHandle::Win32(h) => Some(h.hwnd.get()),
        _ => None,
    }
}

fn main() {
    if let Err(e) = rodar() {
        let base = pasta_dados().unwrap_or_else(|_| std::env::temp_dir());
        let _ = std::fs::write(base.join("erro.txt"), format!("{e}\n"));
        eprintln!("{e}");
        std::process::exit(1);
    }
}

fn rodar() -> Result<(), String> {
    let inicio = Instant::now();
    let teste = modo_teste::ligado();
    hospedeira::ligar_dpi_por_monitor();
    let dados = pasta_dados()?;
    let log = std::fs::File::create(dados.join("prova.log")).map_err(|e| e.to_string())?;
    let cfg = Config::carregar(&dados);

    // A hospedeira nasce oculta; no modo de teste continua assim (só recebe mensagens).
    let host = hospedeira::criar("Ciranda (prova Rust)", 1280, 720, ao_avisar, no_laco_modal);

    // Motor: a mesma libmpv-2.dll oficial LGPL da 1.5.1, ao lado do exe.
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(Path::to_path_buf))
        .unwrap_or_default();
    let dll = exe_dir.join("libmpv-2.dll");
    let sha = sha256_hex(&dll)?;
    if sha != DLL_SHA256 {
        return Err(format!("libmpv-2.dll diferente da oficial (sha256 {sha}); esperado {DLL_SHA256}"));
    }
    let m = Mpv::carregar(&dll)?;
    let volume = cfg.volume().clamp(0, 100).to_string();
    let mut opcoes: Vec<(&str, String)> = vec![
        ("hwdec", "auto-safe".into()),
        ("keep-open", "yes".into()),
        ("idle", "yes".into()),
        ("input-default-bindings", "no".into()),
        ("input-vo-keyboard", "no".into()),
        ("osc", "no".into()),
        ("image-display-duration", "inf".into()),
        ("osd-level", "1".into()),
        ("terminal", "no".into()),
        ("config", "no".into()),
        ("volume", volume),
    ];
    if teste {
        // REGRA 13: sem janela de vídeo, sem som.
        opcoes.extend([("vo", "null".into()), ("ao", "null".into()), ("mute", "yes".into())]);
    } else {
        opcoes.extend([
            ("wid", (host as isize).to_string()),
            ("vo", "gpu-next".into()),
            ("mute", if cfg.mudo() { "yes" } else { "no" }.into()),
        ]);
    }
    for (k, v) in &opcoes {
        m.opcao(k, v)?;
    }
    m.iniciar()?;
    m.pedir_log("info")?;
    m.observar(1, "pause", mpv::FORMAT_FLAG)?;
    m.observar(2, "eof-reached", mpv::FORMAT_FLAG)?;
    m.ao_acordar(mpv_acordou, std::ptr::null_mut());

    // Interface: janela Slint de topo, "owned" pela hospedeira, transparente, sem borda.
    let dono = host as isize;
    slint::BackendSelector::new()
        .backend_name("winit".into())
        .renderer_name("femtovg".into())
        .with_winit_window_attributes_hook(move |a| {
            use winit::platform::windows::WindowAttributesExtWindows;
            a.with_owner_window(dono)
                .with_skip_taskbar(true)
                .with_transparent(true)
                .with_decorations(false)
                .with_drag_and_drop(true)
        })
        .select()
        .map_err(|e| format!("Slint: {e}"))?;

    let ui = Camada::new().map_err(|e| e.to_string())?;
    let r = hospedeira::area_cliente();
    ui.window().set_position(slint::PhysicalPosition::new(r.left, r.top));
    ui.window().set_size(slint::PhysicalSize::new(
        (r.right - r.left).max(1) as u32,
        (r.bottom - r.top).max(1) as u32,
    ));

    let medicao = std::env::var_os("CIRANDA_PROVA_MEDIR").map(|s| Medicao {
        saida: PathBuf::from(s),
        segundos: std::env::var("CIRANDA_PROVA_SEGUNDOS").ok().and_then(|s| s.parse().ok()).unwrap_or(30),
        aquecer: std::env::var("CIRANDA_PROVA_AQUECER").ok().and_then(|s| s.parse().ok()).unwrap_or(0),
        sair: std::env::var("CIRANDA_PROVA_SAIR").map(|s| s == "1").unwrap_or(true),
    });
    if medicao.is_some() || teste {
        ui.set_quadro_visivel(false);
    }

    let foto_total = Duration::from_secs(cfg.segundos_foto().clamp(1, 3600) as u64);
    let sessao = Sessao::nova(cfg, &dados, None);
    let (amaj, amin) = m.versao_api();
    let estado = Rc::new(App {
        mpv: m,
        ui: ui.clone_strong(),
        inicio,
        log: RefCell::new(log),
        teste,
        sair_no_fim: std::env::var_os("CIRANDA_SAIR_NO_FIM").is_some_and(|v| v == "1"),
        sessao: RefCell::new(sessao),
        varrendo: RefCell::new(None),
        geracao: Cell::new(0),
        carregado_em: Cell::new(None),
        esperando_quadro: Cell::new(false),
        motor_anotado: Cell::new(false),
        audio_anotado: Cell::new(false),
        eh_foto: Cell::new(false),
        foto_timer: Timer::default(),
        foto_total: Cell::new(foto_total),
        foto_restante: Cell::new(foto_total),
        foto_desde: Cell::new(None),
        foto_ativa: Cell::new(false),
        pausado: Cell::new(false),
        ocultar_timer: Timer::default(),
        relogio: Timer::default(),
        soltos: RefCell::new(Vec::new()),
        soltar_timer: Timer::default(),
        aviso_timer: Timer::default(),
        repinturas: Cell::new(0),
        medicao,
        medir_timer: Timer::default(),
        primeiro_quadro_ms: Cell::new(0.0),
        desde_inicio_ms: Cell::new(0.0),
        medida_inicio: Cell::new(None),
        medicao_agendada: Cell::new(false),
        notificador_ok: Cell::new(true),
        pular_timer: Timer::default(),
    });
    APP.with(|a| *a.borrow_mut() = Some(estado.clone()));
    estado.log(&format!("Ciranda prova Rust, mpv API {amaj}.{amin}, Slint 1.19 (winit + femtovg)"));
    {
        let s = estado.sessao.borrow();
        estado.log(&format!(
            "dados em {}; aleatório {}, repetir {}, filtro {}, foto {} s{}",
            dados.display(),
            s.fila.aleatorio,
            s.fila.repetir.nome(),
            s.fila.filtro.nome(),
            foto_total.as_secs(),
            if teste { "; MODO TESTE (sem janela, sem som)" } else { "" }
        ));
    }

    // Callbacks da interface.
    ui.on_tocar_pausar(|| {
        if let Some(a) = app() {
            a.executar(Acao::TocarPausar)
        }
    });
    ui.on_proximo(|| {
        if let Some(a) = app() {
            a.executar(Acao::Proximo)
        }
    });
    ui.on_buscar(|f| {
        if let Some(a) = app() {
            if !a.eh_foto.get() {
                let pct = format!("{}", (f * 100.0).clamp(0.0, 100.0));
                let _ = a.mpv.comando(&["seek", &pct, "absolute-percent"]);
            }
        }
    });
    ui.on_tecla(|t, shift, repetida, ctrl_alt| {
        let Some(a) = app() else { return false };
        if ctrl_alt {
            return false;
        }
        match acao_do_texto(t.as_str(), shift) {
            Some(acao) if repetida && alterna(&acao) => true, // engole a repetição
            Some(acao) => {
                a.log(&format!("tecla na camada: {acao:?}"));
                a.executar(acao);
                true
            }
            None => false,
        }
    });
    ui.on_mexeu(|| {
        if let Some(a) = app() {
            a.mostrar_controles()
        }
    });
    ui.on_duplo_clique(|| {
        if let Some(a) = app() {
            a.executar(Acao::AlternarTelaCheia)
        }
    });
    ui.on_menu(|qual| {
        let Some(a) = app() else { return };
        a.log(&format!("menu: {qual}"));
        match qual.as_str() {
            "tocar" => a.executar(Acao::TocarPausar),
            "proximo" => a.executar(Acao::Proximo),
            "tela-cheia" => a.executar(Acao::AlternarTelaCheia),
            "quadro" => a.ui.set_quadro_visivel(true),
            _ => {}
        }
    });
    ui.on_fechar_quadro(|| {
        if let Some(a) = app() {
            a.ui.set_quadro_visivel(false);
            a.log("quadro fechado");
        }
    });

    // Conta quantas vezes a interface repinta (tem que ser só quando muda).
    let notificador = ui.window().set_rendering_notifier(|estado, _| {
        if matches!(estado, slint::RenderingState::AfterRendering) {
            if let Some(a) = app() {
                a.repinturas.set(a.repinturas.get() + 1);
            }
        }
    });
    if let Err(e) = notificador {
        estado.notificador_ok.set(false);
        estado.log(&format!("sem contagem de repinturas: {e:?}"));
    }

    // Alt+F4 com o foco na camada: fecha o app inteiro (o padrão do Slint só esconderia a camada).
    ui.window().on_close_requested(|| {
        if let Some(a) = app() {
            a.log("camada pediu para fechar (Alt+F4)");
        }
        slint::quit_event_loop().ok();
        slint::CloseRequestResponse::KeepWindowShown
    });

    // Eventos crus do winit na camada: arrastar do Explorer, DPI e foco.
    ui.window().on_winit_window_event(|_w, ev| {
        let Some(a) = app() else { return EventResult::Propagate };
        match ev {
            winit::event::WindowEvent::HoveredFile(_) => a.ui.set_arrastando(true),
            winit::event::WindowEvent::HoveredFileCancelled => a.ui.set_arrastando(false),
            winit::event::WindowEvent::DroppedFile(p) => {
                a.ui.set_arrastando(false);
                a.soltar(vec![p.clone()]);
            }
            winit::event::WindowEvent::ScaleFactorChanged { scale_factor, .. } => {
                a.log(&format!("camada: escala {scale_factor}"));
                // O winit aplica o tamanho sugerido; a hospedeira volta a mandar logo depois.
                let _ = slint::invoke_from_event_loop(hospedeira::seguir);
            }
            winit::event::WindowEvent::Focused(f) => {
                a.log(&format!("camada: foco {f}"));
                if !*f {
                    // Dá tempo de o Windows trocar a janela da frente antes de olhar.
                    Timer::single_shot(Duration::from_millis(60), hospedeira::apagar_titulo_se_inativa);
                }
            }
            _ => {}
        }
        EventResult::Propagate
    });

    estado.relogio.start(TimerMode::Repeated, Duration::from_millis(250), || {
        if let Some(a) = app() {
            a.atualizar_relogio();
        }
    });

    if teste {
        // Nada aparece, nada pega o foco. Limite de tempo para o teste nunca ficar preso.
        let limite = std::env::var("CIRANDA_TESTE_LIMITE_S").ok().and_then(|s| s.parse().ok()).unwrap_or(120);
        Timer::single_shot(Duration::from_secs(limite), || {
            if let Some(a) = app() {
                a.log("modo teste: tempo esgotado, saindo");
            }
            slint::quit_event_loop().ok();
        });
    } else {
        ui.show().map_err(|e| e.to_string())?;
        hospedeira::mostrar();

        // A janela do winit só existe com o laço rodando: liga a camada à hospedeira aí.
        let fraco = ui.as_weak();
        slint::spawn_local(async move {
            let Some(ui) = fraco.upgrade() else { return };
            match ui.window().winit_window().await {
                Ok(w) => {
                    if let Some(h) = hwnd_do_winit(&w) {
                        hospedeira::ligar_camada(h as _);
                        if let Some(a) = app() {
                            a.log(&format!(
                                "camada ligada; DPI hospedeira {} camada {}",
                                hospedeira::dpi(hospedeira::hwnd()),
                                hospedeira::dpi(h as _)
                            ));
                        }
                    }
                }
                Err(e) => {
                    if let Some(a) = app() {
                        a.log(&format!("sem janela winit: {e}"));
                    }
                }
            }
        })
        .map_err(|e| e.to_string())?;
    }

    // Eventos que o mpv soltou antes de o laço do Slint existir.
    Timer::single_shot(Duration::ZERO, || {
        if let Some(a) = app() {
            a.drenar_mpv();
        }
    });

    // Arquivos ou pastas na linha de comando.
    let args: Vec<PathBuf> = std::env::args_os().skip(1).map(PathBuf::from).collect();
    if !args.is_empty() {
        estado.soltar(args);
    }

    slint::run_event_loop_until_quit().map_err(|e| e.to_string())?;
    if let Some(c) = estado.varrendo.borrow_mut().take() {
        c.store(true, Ordering::Relaxed);
    }
    match estado.sessao.borrow().salvar() {
        Ok(()) => estado.log("config salvo"),
        Err(e) => estado.log(&format!("config não salvo: {e}")),
    }
    estado.log("saindo");
    APP.with(|a| a.borrow_mut().take());
    drop(estado);
    let _ = ui.hide();
    hospedeira::fechar();
    Ok(())
}
