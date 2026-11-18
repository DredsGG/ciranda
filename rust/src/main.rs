//! Ciranda em Rust (fase 3): o executável. Junta as peças de verdade: a hospedeira Win32 (barra de
//! título, tela do vídeo), o mpv (a libmpv-2.dll oficial LGPL da 1.5.1) e a interface Slint numa
//! janela de topo transparente por cima. A lógica do player fica na biblioteca (`player.rs`).
//!
//! `DREDS_TESTE=1` (REGRA 13): nenhuma janela aparece, mpv com `vo=null`, `ao=null` e `mute`,
//! nada pega o foco, nada é aberto (Explorer, janelas de escolher) e a área de transferência não
//! muda: a plataforma é o `Registro`, que só grava. Teclas chegam por mensagem à hospedeira oculta.
#![windows_subsystem = "windows"]

mod hospedeira;

use std::cell::{Cell, RefCell};
use std::ffi::c_void;
use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use ciranda::config::Config;
use ciranda::modo_teste;
use ciranda::motor::Motor;
use ciranda::mpv::{self, Mpv};
use ciranda::plataforma::{Escolha, Plataforma, Registro, Resposta};
use ciranda::player::{Opcoes, Player};
use ciranda::sessao::Sessao;
use ciranda::sistema;
use ciranda::ui::Camada;
use slint::platform::Key;
use slint::winit_030::{EventResult, WinitWindowAccessor, winit};
use slint::{ComponentHandle, SharedString, Timer, TimerMode};

use hospedeira::Aviso;

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

/// O Windows de verdade: a hospedeira e o módulo `sistema` (Explorer, área de transferência,
/// janelas de escolher pasta e arquivos).
struct Win32;

impl Plataforma for Win32 {
    fn tela_cheia(&self, ligar: bool) {
        hospedeira::tela_cheia(ligar);
    }
    fn em_tela_cheia(&self) -> bool {
        hospedeira::em_tela_cheia()
    }
    fn definir_palco(&self, x: i32, y: i32, largura: i32, altura: i32) {
        hospedeira::definir_palco(x, y, largura, altura);
    }
    fn titulo(&self, texto: &str) {
        hospedeira::titulo(texto);
    }
    fn cursor(&self) -> Option<(i32, i32)> {
        hospedeira::cursor()
    }
    fn cursor_na_faixa_de_baixo(&self, altura: i32) -> bool {
        hospedeira::cursor_na_faixa_de_baixo(altura)
    }
    fn ctrl_apertado(&self) -> bool {
        use windows_sys::Win32::UI::Input::KeyboardAndMouse::{GetKeyState, VK_CONTROL};
        (unsafe { GetKeyState(VK_CONTROL as i32) } as u16 & 0x8000) != 0
    }
    fn mostrar_no_explorer(&self, caminho: &Path) -> bool {
        sistema::mostrar_no_explorer(caminho)
    }
    fn copiar_texto(&self, texto: &str) -> bool {
        sistema::copiar_texto(texto)
    }
    /// O diálogo roda numa thread própria (STA), dono da hospedeira: o laço do winit continua e
    /// o player não para (no laço modal dentro do evento do winit, os eventos da camada e os
    /// timers do Slint ficariam presos até o diálogo fechar). A camada é desligada enquanto ele
    /// está aberto (a hospedeira o próprio diálogo desliga), e a resposta volta pelo correio.
    fn escolher(&self, escolha: Escolha, titulo: &str, inicio: Option<&Path>, responder: Resposta) {
        use windows_sys::Win32::UI::Input::KeyboardAndMouse::EnableWindow;
        let dono = hospedeira::hwnd() as isize;
        let camada = hospedeira::camada() as isize;
        let titulo = titulo.to_string();
        let inicio = inicio.map(Path::to_path_buf);
        unsafe { EnableWindow(camada as _, 0) };
        std::thread::spawn(move || {
            let v = match escolha {
                Escolha::Pasta => sistema::escolher_pasta(dono, &titulo, inicio.as_deref()).into_iter().collect(),
                Escolha::Arquivos => sistema::escolher_arquivos(dono, &titulo, inicio.as_deref()),
            };
            unsafe { EnableWindow(camada as _, 1) };
            responder(v);
        });
    }
}

struct Medicao {
    saida: PathBuf,
    segundos: u64,
    aquecer: u64,
    sair: bool,
}

/// Modo de medição (`CIRANDA_PROVA_MEDIR`): CPU, quadros perdidos e repinturas da interface
/// numa janela de tempo depois do primeiro quadro (o mesmo das fases 1 e 2).
struct Medidor {
    m: Medicao,
    mpv: Rc<Mpv>,
    timer: Timer,
    agendada: Cell<bool>,
    inicio: Cell<Option<(Instant, f64, [Option<i64>; 3], u64)>>,
    primeiro_ms: Cell<(f64, f64)>,
    repinturas: Rc<Cell<u64>>,
    notificador_ok: Cell<bool>,
}

impl Medidor {
    fn contadores(&self) -> [Option<i64>; 3] {
        ["frame-drop-count", "decoder-frame-drop-count", "vo-delayed-frame-count"].map(|p| self.mpv.ler_inteiro(p))
    }

    fn primeiro_quadro(self: &Rc<Self>, ms: f64, desde: f64) {
        self.primeiro_ms.set((ms, desde));
        // Uma vez por processo: o próximo arquivo não pode reiniciar a janela de medição.
        if self.agendada.replace(true) {
            return;
        }
        let eu = Rc::downgrade(self);
        self.timer.start(TimerMode::SingleShot, Duration::from_secs(self.m.aquecer), move || {
            if let Some(m) = eu.upgrade() {
                m.comecar();
            }
        });
    }

    fn comecar(self: &Rc<Self>) {
        self.inicio.set(Some((Instant::now(), cpu_do_processo_s(), self.contadores(), self.repinturas.get())));
        let _ = std::fs::write(self.m.saida.with_extension("comecou"), b"1");
        log("medição: começou a contar");
        let eu = Rc::downgrade(self);
        self.timer.start(TimerMode::SingleShot, Duration::from_secs(self.m.segundos), move || {
            if let Some(m) = eu.upgrade() {
                m.gravar();
            }
        });
    }

    fn gravar(&self) {
        let Some((t0, cpu0, c0, rep0)) = self.inicio.get() else { return };
        let dt = t0.elapsed().as_secs_f64();
        let cpu = cpu_do_processo_s() - cpu0;
        let c1 = self.contadores();
        let mut campos: Vec<(String, String)> = Vec::new();
        let atual = player().and_then(|p| p.sessao.borrow().item_atual().map(|i| i.caminho.clone())).unwrap_or_default();
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
        let (ms, desde) = self.primeiro_ms.get();
        campos.push(("cpu_pct_um_nucleo".into(), format!("{:.2}", cpu / dt * 100.0)));
        campos.push(("janela_s".into(), format!("{dt:.2}")));
        campos.push(("primeiro_quadro_ms".into(), format!("{ms:.1}")));
        campos.push(("desde_inicio_ms".into(), format!("{desde:.1}")));
        campos.push(("aquecer_s".into(), self.m.aquecer.to_string()));
        let rep = if self.notificador_ok.get() { (self.repinturas.get() - rep0).to_string() } else { "null".into() };
        campos.push(("repinturas_da_interface".into(), rep));
        let corpo = campos.iter().map(|(k, v)| format!("  {}: {v}", json_txt(k))).collect::<Vec<_>>().join(",\n");
        let _ = std::fs::write(&self.m.saida, format!("{{\n{corpo}\n}}\n"));
        log(&format!("medição gravada em {}", self.m.saida.display()));
        if self.m.sair {
            slint::quit_event_loop().ok();
        }
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

thread_local! {
    static PLAYER: RefCell<Option<Rc<Player>>> = const { RefCell::new(None) };
    static LOG: RefCell<Option<(std::fs::File, Instant)>> = const { RefCell::new(None) };
}
static MOTOR_PENDENTE: AtomicBool = AtomicBool::new(false);
static CORREIO_PENDENTE: AtomicBool = AtomicBool::new(false);

fn player() -> Option<Rc<Player>> {
    PLAYER.with(|p| p.borrow().clone())
}

fn log(texto: &str) {
    LOG.with(|l| {
        if let Some((f, inicio)) = &mut *l.borrow_mut() {
            let _ = writeln!(f, "{:9.3} {texto}", inicio.elapsed().as_secs_f64());
            let _ = f.flush();
        }
    });
}

fn drenar_tudo() {
    MOTOR_PENDENTE.store(false, Ordering::Release);
    CORREIO_PENDENTE.store(false, Ordering::Release);
    if let Some(p) = player() {
        p.drenar_correio();
        if !p.drenar_motor() {
            // O núcleo do mpv saiu: não há mais o que tocar, e a API não pode mais ser usada.
            slint::quit_event_loop().ok();
        }
    }
}

/// Agenda a leitura na thread da interface, uma por vez. Se o laço ainda não existe, a leitura
/// inicial (em `rodar`) pega o que chegou.
fn acordar(pendente: &'static AtomicBool) {
    if !pendente.swap(true, Ordering::AcqRel) && slint::invoke_from_event_loop(drenar_tudo).is_err() {
        pendente.store(false, Ordering::Release);
    }
}

unsafe extern "C" fn mpv_acordou(_: *mut c_void) {
    acordar(&MOTOR_PENDENTE);
}

/// Tecla virtual do Windows → texto de tecla do Slint (ou "midia-*" para as teclas de mídia).
fn texto_do_vk(vk: u32, shift: bool) -> Option<String> {
    let k = |key: Key| SharedString::from(key).to_string();
    Some(match vk {
        0x41..=0x5A => {
            let c = vk as u8 as char;
            if shift { c.to_string() } else { c.to_ascii_lowercase().to_string() }
        }
        0x30..=0x39 => (vk as u8 as char).to_string(),
        0x60..=0x69 => ((b'0' + (vk - 0x60) as u8) as char).to_string(), // teclado numérico
        0x20 => " ".into(),
        0x0D => k(Key::Return),
        0x1B => k(Key::Escape),
        0x25 => k(Key::LeftArrow),
        0x26 => k(Key::UpArrow),
        0x27 => k(Key::RightArrow),
        0x28 => k(Key::DownArrow),
        0x21 => k(Key::PageUp),
        0x22 => k(Key::PageDown),
        0x7A => k(Key::F11),
        0xBB => if shift { "+" } else { "=" }.into(), // VK_OEM_PLUS
        0x6B => "+".into(),                           // VK_ADD
        0xBD if !shift => "-".into(),                 // VK_OEM_MINUS
        0x6D => "-".into(),                           // VK_SUBTRACT
        0xB0 => "midia-proximo".into(),               // VK_MEDIA_NEXT_TRACK
        0xB1 => "midia-anterior".into(),              // VK_MEDIA_PREV_TRACK
        _ => return None,
    })
}

fn ao_avisar(a: Aviso) {
    let Some(p) = player() else { return };
    match a {
        Aviso::Tecla { vk, shift, ctrl, alt, repetida } => {
            if let Some(t) = texto_do_vk(vk, shift) {
                p.tecla(&t, shift, ctrl, alt, repetida, "hospedeira");
            }
        }
        Aviso::Soltou(v) => p.soltar(v),
        Aviso::Fechar => {
            p.log("hospedeira pediu para fechar");
            slint::quit_event_loop().ok();
        }
        Aviso::Ativou => p.log("hospedeira ativada"),
    }
}

/// Laço modal (barra de título segurada): roda os timers do Slint (relógio da foto, ocultar
/// controles, relógio da barra) e lê os eventos do mpv (fim do vídeo passa para o próximo).
fn no_laco_modal() {
    slint::platform::update_timers_and_animations();
    drenar_tudo();
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
    let arquivo_log = std::fs::File::create(dados.join("prova.log")).map_err(|e| e.to_string())?;
    LOG.with(|l| *l.borrow_mut() = Some((arquivo_log, inicio)));
    let cfg = Config::carregar(&dados);
    let idioma = ciranda::textos::iniciar(cfg.valor("idioma").and_then(|v| v.as_str()));

    // A hospedeira nasce oculta; no modo de teste continua assim (só recebe mensagens).
    let host = hospedeira::criar(ciranda::player::NOME, 1180, 720, ao_avisar, no_laco_modal);

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
        ("osd-on-seek", "no".into()),
        ("terminal", "no".into()),
        ("config", "no".into()),
        ("volume", volume),
    ];
    if teste {
        // REGRA 13: sem janela de vídeo, sem som.
        opcoes.extend([("vo", "null".into()), ("ao", "null".into()), ("mute", "yes".into())]);
    } else {
        opcoes.extend([
            ("wid", (hospedeira::tela() as isize).to_string()),
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
    // SAFETY: dado nulo; o callback não lê nada dele.
    unsafe { m.ao_acordar(mpv_acordou, std::ptr::null_mut()) };
    let (amaj, amin) = m.versao_api();
    let mpv = Rc::new(m);

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
    ui.window().set_size(slint::PhysicalSize::new((r.right - r.left).max(1) as u32, (r.bottom - r.top).max(1) as u32));

    let plat: Rc<dyn Plataforma> = if teste { Rc::new(Registro::novo()) } else { Rc::new(Win32) };
    let sessao = Sessao::nova(cfg, &dados, None);
    let p = Player::novo(
        ui.clone_strong(),
        mpv.clone() as Rc<dyn Motor>,
        plat,
        sessao,
        Rc::new(move || inicio.elapsed()),
        Box::new(log),
        Arc::new(|| acordar(&CORREIO_PENDENTE)),
        Opcoes { teste, sair_no_fim: std::env::var_os("CIRANDA_SAIR_NO_FIM").is_some_and(|v| v == "1") },
    );
    PLAYER.with(|x| *x.borrow_mut() = Some(p.clone()));
    p.log(&format!("Ciranda prova Rust (fase 3), mpv API {amaj}.{amin}, Slint 1.19 (winit + femtovg), idioma {idioma}"));
    {
        let s = p.sessao.borrow();
        p.log(&format!(
            "dados em {}; aleatório {}, repetir {}, filtro {}, foto {} s{}",
            dados.display(),
            s.fila.aleatorio,
            s.fila.repetir.nome(),
            s.fila.filtro.nome(),
            s.cfg.segundos_foto(),
            if teste { "; MODO TESTE (sem janela, sem som)" } else { "" }
        ));
    }

    // Conta quantas vezes a interface repinta (tem que ser só quando muda).
    let repinturas = Rc::new(Cell::new(0u64));
    let notificador = {
        let r = repinturas.clone();
        ui.window().set_rendering_notifier(move |estado, _| {
            if matches!(estado, slint::RenderingState::AfterRendering) {
                r.set(r.get() + 1);
            }
        })
    };
    let medicao = std::env::var_os("CIRANDA_PROVA_MEDIR").map(|s| Medicao {
        saida: PathBuf::from(s),
        segundos: std::env::var("CIRANDA_PROVA_SEGUNDOS").ok().and_then(|s| s.parse().ok()).unwrap_or(30),
        aquecer: std::env::var("CIRANDA_PROVA_AQUECER").ok().and_then(|s| s.parse().ok()).unwrap_or(0),
        sair: std::env::var("CIRANDA_PROVA_SAIR").map(|s| s == "1").unwrap_or(true),
    });
    let _medidor = medicao.map(|m| {
        let md = Rc::new(Medidor {
            m,
            mpv: mpv.clone(),
            timer: Timer::default(),
            agendada: Cell::new(false),
            inicio: Cell::new(None),
            primeiro_ms: Cell::new((0.0, 0.0)),
            repinturas: repinturas.clone(),
            notificador_ok: Cell::new(notificador.is_ok()),
        });
        let fraco = Rc::downgrade(&md);
        p.ao_primeiro_quadro(move |ms, desde| {
            if let Some(m) = fraco.upgrade() {
                m.primeiro_quadro(ms, desde);
            }
        });
        md
    });
    if let Err(e) = &notificador {
        p.log(&format!("sem contagem de repinturas: {e:?}"));
    }

    // Alt+F4 com o foco na camada: fecha o app inteiro (o padrão do Slint só esconderia a camada).
    ui.window().on_close_requested(|| {
        log("camada pediu para fechar (Alt+F4)");
        slint::quit_event_loop().ok();
        slint::CloseRequestResponse::KeepWindowShown
    });

    // Eventos crus do winit na camada: arrastar do Explorer, DPI, foco e teclas de mídia.
    ui.window().on_winit_window_event(|_w, ev| {
        let Some(p) = player() else { return EventResult::Propagate };
        use winit::event::WindowEvent as W;
        match ev {
            W::HoveredFile(_) => p.arrastando(true),
            W::HoveredFileCancelled => p.arrastando(false),
            W::DroppedFile(c) => p.soltar(vec![c.clone()]),
            W::ScaleFactorChanged { scale_factor, .. } => {
                p.log(&format!("camada: escala {scale_factor}"));
                // O winit aplica o tamanho sugerido; a hospedeira volta a mandar logo depois.
                let _ = slint::invoke_from_event_loop(|| {
                    hospedeira::seguir();
                    if let Some(p) = player() {
                        p.reenviar_palco();
                    }
                });
            }
            W::Focused(f) => {
                p.log(&format!("camada: foco {f}"));
                if !*f {
                    // Dá tempo de o Windows trocar a janela da frente antes de olhar.
                    Timer::single_shot(Duration::from_millis(60), hospedeira::apagar_titulo_se_inativa);
                }
            }
            W::KeyboardInput { event, .. } if event.state.is_pressed() => {
                use winit::keyboard::{Key as WK, NamedKey};
                let t = match &event.logical_key {
                    WK::Named(NamedKey::MediaTrackNext) => Some("midia-proximo"),
                    WK::Named(NamedKey::MediaTrackPrevious) => Some("midia-anterior"),
                    _ => None,
                };
                if let Some(t) = t {
                    p.tecla(t, false, false, false, event.repeat, "camada");
                    return EventResult::PreventDefault;
                }
            }
            _ => {}
        }
        EventResult::Propagate
    });

    if teste {
        // Nada aparece, nada pega o foco. Limite de tempo para o teste nunca ficar preso.
        let limite = std::env::var("CIRANDA_TESTE_LIMITE_S").ok().and_then(|s| s.parse().ok()).unwrap_or(120);
        Timer::single_shot(Duration::from_secs(limite), || {
            log("modo teste: tempo esgotado, saindo");
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
                        log(&format!(
                            "camada ligada; DPI hospedeira {} camada {}",
                            hospedeira::dpi(hospedeira::hwnd()),
                            hospedeira::dpi(h as _)
                        ));
                        if let Some(p) = player() {
                            p.reenviar_palco();
                        }
                    }
                }
                Err(e) => log(&format!("sem janela winit: {e}")),
            }
        })
        .map_err(|e| e.to_string())?;
    }

    // Eventos que o mpv soltou antes de o laço do Slint existir.
    Timer::single_shot(Duration::ZERO, drenar_tudo);

    // Arquivos ou pastas na linha de comando.
    let args: Vec<PathBuf> = std::env::args_os().skip(1).map(PathBuf::from).collect();
    if !args.is_empty() {
        let fraco = Rc::downgrade(&p);
        Timer::single_shot(Duration::ZERO, move || {
            if let Some(p) = fraco.upgrade() {
                p.carregar(args, false);
            }
        });
    }

    slint::run_event_loop_until_quit().map_err(|e| e.to_string())?;
    p.limpar_ao_sair();
    match p.sessao.borrow().salvar() {
        Ok(()) => p.log("config salvo"),
        Err(e) => p.log(&format!("config não salvo: {e}")),
    }
    p.log("saindo");
    PLAYER.with(|x| x.borrow_mut().take());
    drop(p);
    let _ = ui.hide();
    hospedeira::fechar();
    Ok(())
}
