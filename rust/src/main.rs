//! Ciranda em Rust, fase 1 (prova técnica): mpv numa janela-hospedeira Win32 e a interface
//! Slint numa janela de topo transparente por cima do vídeo.
#![windows_subsystem = "windows"]

mod hospedeira;
mod mpv;

use std::cell::{Cell, RefCell};
use std::ffi::c_void;
use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use slint::platform::Key;
use slint::winit_030::{EventResult, WinitWindowAccessor, winit};
use slint::{ComponentHandle, SharedString, Timer, TimerMode};

use hospedeira::Aviso;
use mpv::{Evento, Mpv, Valor};

slint::include_modules!();

const FOTO: Duration = Duration::from_secs(5);
const OCULTAR: Duration = Duration::from_millis(2500);
/// Altura da barra de controles (a mesma do app.slint), em DIP.
const BARRA_DIP: i32 = 76;

const EXT_VIDEO: &[&str] = &[
    "mp4", "m4v", "mov", "mkv", "webm", "avi", "wmv", "flv", "ts", "m2ts", "mts", "mpg", "mpeg",
    "3gp", "ogv",
];
const EXT_FOTO: &[&str] = &[
    "jpg", "jpeg", "png", "bmp", "gif", "webp", "tif", "tiff", "heic", "heif", "avif", "jxl",
];

fn ext(p: &Path) -> String {
    p.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default()
}
fn eh_midia(p: &Path) -> bool {
    let e = ext(p);
    EXT_VIDEO.contains(&e.as_str()) || EXT_FOTO.contains(&e.as_str())
}
fn eh_foto(p: &Path) -> bool {
    EXT_FOTO.contains(&ext(p).as_str())
}

/// Pasta de dados da prova. Nunca a da Ciranda 1.x.
fn pasta_dados() -> PathBuf {
    let base = std::env::var_os("APPDATA").map(PathBuf::from).unwrap_or_else(std::env::temp_dir);
    let p = base.join("Ciranda-rust-prova");
    let _ = std::fs::create_dir_all(&p);
    p
}

#[derive(Debug, Clone, Copy)]
enum Acao {
    TocarPausar,
    Proximo,
    Anterior,
    Pular(f64),
    AlternarTelaCheia,
    SairTelaCheia,
}

struct Medicao {
    saida: PathBuf,
    segundos: u64,
    aquecer: u64,
    sair: bool,
}

/// Tempo de CPU (usuário + núcleo) de todas as threads do processo, em segundos.
/// sha256 da libmpv-2.dll oficial LGPL 0.42 (a mesma da 1.5.1). Outra DLL (um build GPL, por
/// exemplo) mudaria a licença do conjunto: a prova se recusa a carregar.
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

fn cpu_do_processo_s() -> f64 {
    use windows_sys::Win32::Foundation::FILETIME;
    use windows_sys::Win32::System::Threading::{GetCurrentProcess, GetProcessTimes};
    let z = || FILETIME { dwLowDateTime: 0, dwHighDateTime: 0 };
    let (mut a, mut b, mut k, mut u) = (z(), z(), z(), z());
    unsafe { GetProcessTimes(GetCurrentProcess(), &mut a, &mut b, &mut k, &mut u) };
    let s = |f: FILETIME| ((f.dwHighDateTime as u64) << 32 | f.dwLowDateTime as u64) as f64 / 1e7;
    s(k) + s(u)
}

struct App {
    mpv: Mpv,
    ui: Camada,
    inicio: Instant,
    log: RefCell<std::fs::File>,
    fila: RefCell<Vec<PathBuf>>,
    atual: Cell<usize>,
    carregado_em: Cell<Option<Instant>>,
    esperando_quadro: Cell<bool>,
    eh_foto: Cell<bool>,
    foto_timer: Timer,
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
    falhas_seguidas: Cell<usize>,
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
        let _ = writeln!(self.log.borrow_mut(), "{t:9.3} {texto}");
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

    fn tocar_indice(&self, i: usize) {
        let caminho = {
            let fila = self.fila.borrow();
            if fila.is_empty() {
                return;
            }
            fila[i % fila.len()].clone()
        };
        let n = self.fila.borrow().len();
        self.atual.set(i % n);
        self.parar_relogio_foto();
        self.pular_timer.stop(); // um "pular" pendente do arquivo anterior não vale mais
        let foto = eh_foto(&caminho);
        self.eh_foto.set(foto);
        // GIF anima em loop pelo tempo da foto; o resto toca uma vez.
        let _ = self.mpv.por_texto("loop-file", if ext(&caminho) == "gif" { "inf" } else { "no" });
        // Só arma no FILE_LOADED deste arquivo: um playback-restart atrasado do anterior não conta.
        self.esperando_quadro.set(false);
        self.carregado_em.set(Some(Instant::now()));
        let texto = caminho.to_string_lossy().into_owned();
        if let Err(e) = self.mpv.comando(&["loadfile", &texto, "replace"]) {
            self.log(&format!("loadfile falhou: {e}"));
        }
        let _ = self.mpv.por_sim("pause", false);
        // A "pause" já era falsa no mpv ocioso: o evento de mudança não vem, então o botão muda aqui.
        self.pausado.set(false);
        self.ui.set_tocando(true);
        let nome = caminho.file_name().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
        self.ui.set_nome(format!("{nome}  ·  {} de {n}", self.atual.get() + 1).into());
        self.log(&format!("tocando {}", caminho.display()));
    }

    fn proximo(&self) {
        if !self.fila.borrow().is_empty() {
            self.tocar_indice(self.atual.get() + 1);
        }
    }

    fn anterior(&self) {
        let n = self.fila.borrow().len();
        if n > 0 {
            self.tocar_indice((self.atual.get() + n - 1) % n);
        }
    }

    // ---- relógio da foto (5 s, só conta quando a foto aparece; pausa congela) ----
    fn iniciar_relogio_foto(&self) {
        self.foto_restante.set(FOTO);
        self.foto_ativa.set(true);
        if !self.pausado.get() {
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
                a.log("foto: 5 s, passa");
                a.proximo();
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
                let p = self.mpv.ler_sim("pause").unwrap_or(false);
                let _ = self.mpv.por_sim("pause", !p);
            }
            Acao::Proximo => self.proximo(),
            Acao::Anterior => self.anterior(),
            Acao::Pular(s) => {
                if self.eh_foto.get() {
                    if s > 0.0 { self.proximo() } else { self.anterior() }
                } else {
                    let _ = self.mpv.comando(&["seek", &format!("{s}"), "relative"]);
                }
            }
            Acao::AlternarTelaCheia => self.tela_cheia(!hospedeira::em_tela_cheia()),
            Acao::SairTelaCheia => self.tela_cheia(false),
        }
    }

    fn tela_cheia(&self, ligar: bool) {
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
            let total = FOTO.as_secs_f64();
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

    fn drenar_mpv(&self) {
        EVENTOS_PENDENTES.store(false, Ordering::Release);
        while let Some(e) = self.mpv.proximo_evento() {
            match e {
                Evento::ArquivoCarregado => {
                    self.log("arquivo carregado");
                    self.esperando_quadro.set(true);
                    let atual = self.fila.borrow().get(self.atual.get()).cloned();
                    if let Some(p) = atual {
                        if matches!(ext(&p).as_str(), "heic" | "heif") {
                            // Mesmo truque da 1.5.1: a grade só fica certa depois de um seek 0.
                            let _ = self.mpv.comando(&["seek", "0", "absolute+exact"]);
                        }
                    }
                }
                Evento::Reinicio => {
                    if self.esperando_quadro.replace(false) {
                        self.falhas_seguidas.set(0);
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
                        let falhas = self.falhas_seguidas.get() + 1;
                        self.falhas_seguidas.set(falhas);
                        if falhas >= self.fila.borrow().len() {
                            // A fila inteira falhou: para em vez de girar para sempre.
                            self.log(&format!("arquivo falhou (erro {erro}); nenhum da fila abriu, parando"));
                            self.avisar_na_tela("Nenhum arquivo abriu");
                        } else {
                            self.log(&format!("arquivo falhou (erro {erro}): pulando"));
                            self.avisar_na_tela("Não abriu: pulando");
                            self.pular_timer.start(TimerMode::SingleShot, Duration::from_millis(400), || {
                                if let Some(a) = app() {
                                    a.proximo();
                                }
                            });
                        }
                    }
                }
                Evento::Propriedade { nome, valor, .. } => match (nome.as_str(), valor) {
                    ("pause", Valor::Sim(p)) => {
                        self.pausado.set(p);
                        // Com a fila vazia (mpv ocioso) o botão mostra "tocar", não "pausar".
                        self.ui.set_tocando(!p && !self.fila.borrow().is_empty());
                        if self.eh_foto.get() && self.foto_ativa.get() {
                            if p { self.pausar_relogio_foto() } else { self.retomar_relogio_foto() }
                        }
                    }
                    ("eof-reached", Valor::Sim(true)) => {
                        if !self.eh_foto.get() {
                            self.log("fim do vídeo");
                            self.proximo();
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
        let atual = self.fila.borrow().get(self.atual.get()).cloned().unwrap_or_default();
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
        let corpo = campos
            .iter()
            .map(|(k, v)| format!("  {}: {v}", json_txt(k)))
            .collect::<Vec<_>>()
            .join(",
");
        let _ = std::fs::write(&m.saida, format!("{{
{corpo}
}}
"));
        self.log(&format!("medição gravada em {}", m.saida.display()));
        if m.sair {
            slint::quit_event_loop().ok();
        }
    }

    fn processar_soltos(&self) {
        let soltos: Vec<PathBuf> = self.soltos.borrow_mut().drain(..).collect();
        if soltos.is_empty() {
            return;
        }
        for p in &soltos {
            self.log(&format!("solto: {}", p.display()));
        }
        let fila = varrer_um_nivel(&soltos);
        self.log(&format!("fila: {} arquivos de mídia", fila.len()));
        if fila.is_empty() {
            self.avisar_na_tela("Nada para tocar aqui");
            return;
        }
        *self.fila.borrow_mut() = fila;
        self.tocar_indice(0);
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

/// Varredura simples da fase 1: arquivos soltos + o primeiro nível de cada pasta.
fn varrer_um_nivel(entradas: &[PathBuf]) -> Vec<PathBuf> {
    // Pula ocultos e os "._" do macOS; o mesmo arquivo (pasta + arquivo dela soltos juntos) entra uma vez.
    let visivel = |p: &Path| !p.file_name().map(|n| n.to_string_lossy().starts_with('.')).unwrap_or(true);
    let mut vistos = std::collections::HashSet::new();
    let mut v: Vec<PathBuf> = Vec::new();
    let mut por = |p: PathBuf, v: &mut Vec<PathBuf>| {
        if vistos.insert(p.to_string_lossy().to_lowercase()) {
            v.push(p);
        }
    };
    for e in entradas {
        if e.is_dir() {
            let mut daqui: Vec<PathBuf> = std::fs::read_dir(e)
                .into_iter()
                .flatten()
                .flatten()
                .map(|d| d.path())
                .filter(|p| p.is_file() && eh_midia(p) && visivel(p))
                .collect();
            // Ordem natural (como a 1.5.1) fica para a fase 2; aqui é por nome, sem maiúsculas.
            daqui.sort_by_key(|p| p.file_name().map(|s| s.to_string_lossy().to_lowercase()));
            for p in daqui {
                por(p, &mut v);
            }
        } else if eh_midia(e) && visivel(e) {
            por(e.clone(), &mut v);
        }
    }
    v
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
        0x27 => Acao::Pular(passo),                    // VK_RIGHT
        0x25 => Acao::Pular(-passo),                   // VK_LEFT
        _ => return None,
    })
}

/// Ações que alternam estado: segurar a tecla não pode ficar ligando e desligando.
fn alterna(a: &Acao) -> bool {
    matches!(a, Acao::TocarPausar | Acao::AlternarTelaCheia | Acao::SairTelaCheia)
}

fn ao_avisar(a: Aviso) {
    let Some(app) = app() else { return };
    match a {
        Aviso::Tecla { vk, shift, repetida, ctrl_alt } => {
            if ctrl_alt {
                return; // Ctrl+F, Alt+N etc. não são atalhos da prova
            }
            if let Some(acao) = acao_do_vk(vk, shift).filter(|a| !(repetida && alterna(a))) {
                app.log(&format!("tecla na hospedeira: {acao:?}"));
                app.executar(acao);
            }
        }
        Aviso::Soltou(v) => app.soltar(v),
        Aviso::Fechar => {
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
        let p = pasta_dados().join("erro.txt");
        let _ = std::fs::write(&p, format!("{e}\n"));
        eprintln!("{e}");
        std::process::exit(1);
    }
}

fn rodar() -> Result<(), String> {
    let inicio = Instant::now();
    hospedeira::ligar_dpi_por_monitor();
    let dados = pasta_dados();
    let log = std::fs::File::create(dados.join("prova.log")).map_err(|e| e.to_string())?;

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
    let opcoes = [
        ("wid", (host as isize).to_string()),
        ("vo", "gpu-next".into()),
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
    ];
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
    if medicao.is_some() {
        ui.set_quadro_visivel(false);
    }

    let (amaj, amin) = m.versao_api();
    let estado = Rc::new(App {
        mpv: m,
        ui: ui.clone_strong(),
        inicio,
        log: RefCell::new(log),
        fila: RefCell::new(Vec::new()),
        atual: Cell::new(0),
        carregado_em: Cell::new(None),
        esperando_quadro: Cell::new(false),
        eh_foto: Cell::new(false),
        foto_timer: Timer::default(),
        foto_restante: Cell::new(FOTO),
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
        falhas_seguidas: Cell::new(0),
        pular_timer: Timer::default(),
    });
    APP.with(|a| *a.borrow_mut() = Some(estado.clone()));
    estado.log(&format!("Ciranda prova Rust, mpv API {amaj}.{amin}, Slint 1.19 (winit + femtovg)"));

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
    estado.log("saindo");
    APP.with(|a| a.borrow_mut().take());
    drop(estado);
    let _ = ui.hide();
    hospedeira::fechar();
    Ok(())
}
