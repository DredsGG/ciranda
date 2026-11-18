//! Janela-hospedeira Win32: tem a barra de título do Windows (escura, nas cores da 1.5.1), recebe
//! o vídeo do mpv numa janela filha, a "tela" (opção `wid`), do tamanho do palco que a interface
//! informa, e arrasta junto a janela Slint (de topo, "owned" por ela), que fica exatamente sobre a
//! área cliente.

use std::sync::atomic::{AtomicBool, AtomicIsize, Ordering};

use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, POINT, RECT, WPARAM};
use windows_sys::Win32::Graphics::Dwm::DwmSetWindowAttribute;
use windows_sys::Win32::Graphics::Gdi::{
    ClientToScreen, CreateSolidBrush, GetMonitorInfoW, MONITOR_DEFAULTTONEAREST, MONITORINFO,
    MonitorFromWindow,
};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::UI::HiDpi::{
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2, GetDpiForWindow, SetProcessDpiAwarenessContext,
};
use windows_sys::Win32::UI::Shell::{DragAcceptFiles, DragFinish, DragQueryFileW, HDROP};
use windows_sys::Win32::UI::WindowsAndMessaging::*;

/// O que a hospedeira avisa o resto do app (sempre fora do WndProc, pela fila do Slint).
#[derive(Debug, Clone)]
pub enum Aviso {
    Tecla { vk: u32, shift: bool, ctrl: bool, alt: bool, repetida: bool },
    Soltou(Vec<std::path::PathBuf>),
    Fechar,
    Ativou,
}

static HOSPEDEIRA: AtomicIsize = AtomicIsize::new(0);
static CAMADA: AtomicIsize = AtomicIsize::new(0);
static TELA: AtomicIsize = AtomicIsize::new(0);
/// Tamanho mínimo da área cliente, em DIP (o `setMinimumSize(880, 520)` da 1.5.1).
const MINIMO_DIP: (i32, i32) = (880, 520);
static TELA_CHEIA: AtomicBool = AtomicBool::new(false);
static mut AO_AVISAR: Option<fn(Aviso)> = None;
/// Chamado ~60×/s enquanto a pessoa segura a barra de título ou a borda (laço modal do Windows):
/// nesse tempo o laço do winit/Slint não gira, e sem isto timers e eventos do mpv ficam parados.
static mut NO_LACO_MODAL: Option<fn()> = None;
const TIMER_MODAL: usize = 0xC1;
static mut ANTES_DA_TELA_CHEIA: Option<(u32, WINDOWPLACEMENT)> = None;

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

pub fn hwnd() -> HWND {
    HOSPEDEIRA.load(Ordering::Relaxed) as HWND
}

/// Tem que vir antes de qualquer janela (a do winit também pede isso; quem chega primeiro vale).
pub fn ligar_dpi_por_monitor() {
    unsafe {
        SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    }
}

/// Tamanho da janela inteira (com borda e barra de título) para uma área cliente de `w`×`h` px.
fn janela_para_cliente(h: HWND, w: i32, hh: i32) -> (i32, i32) {
    use windows_sys::Win32::UI::HiDpi::AdjustWindowRectExForDpi;
    unsafe {
        let mut r = RECT { left: 0, top: 0, right: w, bottom: hh };
        let estilo = GetWindowLongW(h, GWL_STYLE) as u32;
        let ex = GetWindowLongW(h, GWL_EXSTYLE) as u32;
        AdjustWindowRectExForDpi(&mut r, estilo, 0, ex, GetDpiForWindow(h).max(96));
        (r.right - r.left, r.bottom - r.top)
    }
}

/// Barra de título escura da cor do app (Windows 11): fundo #0e0f12, texto #ececf1, borda #24262d.
fn barra_de_titulo_escura(h: HWND) {
    unsafe {
        for (attr, valor) in [(20u32, 1i32), (35, 0x0012_0F0E), (36, 0x00F1_ECEC), (34, 0x002D_2624)] {
            DwmSetWindowAttribute(h, attr, &valor as *const _ as *const _, 4);
        }
    }
}

/// Cria a hospedeira (oculta) e a tela do vídeo dentro dela. `largura_dip`×`altura_dip` é a área
/// cliente, como o `resize(1180, 720)` da 1.5.1.
pub fn criar(titulo: &str, largura_dip: i32, altura_dip: i32, avisar: fn(Aviso), no_laco_modal: fn()) -> HWND {
    unsafe {
        AO_AVISAR = Some(avisar);
        NO_LACO_MODAL = Some(no_laco_modal);
        let inst = GetModuleHandleW(std::ptr::null());
        let classe = wide("CirandaHospedeira");
        let wc = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            style: CS_HREDRAW | CS_VREDRAW | CS_DBLCLKS,
            lpfnWndProc: Some(wndproc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: inst,
            hIcon: LoadIconW(std::ptr::null_mut(), IDI_APPLICATION),
            hCursor: LoadCursorW(std::ptr::null_mut(), IDC_ARROW),
            hbrBackground: CreateSolidBrush(0x0019_1514), // BGR de #141519
            lpszMenuName: std::ptr::null(),
            lpszClassName: classe.as_ptr(),
            hIconSm: std::ptr::null_mut(),
        };
        RegisterClassExW(&wc);
        let t = wide(titulo);
        let h = CreateWindowExW(
            0,
            classe.as_ptr(),
            t.as_ptr(),
            WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            largura_dip,
            altura_dip,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            inst,
            std::ptr::null(),
        );
        HOSPEDEIRA.store(h as isize, Ordering::Relaxed);
        // Tamanho em DIP convertido para o DPI do monitor onde a janela nasceu, centralizada.
        let dpi = GetDpiForWindow(h).max(96) as i32;
        let (w, hh) = janela_para_cliente(h, largura_dip * dpi / 96, altura_dip * dpi / 96);
        let mon = MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST);
        let mut mi: MONITORINFO = std::mem::zeroed();
        mi.cbSize = std::mem::size_of::<MONITORINFO>() as u32;
        GetMonitorInfoW(mon, &mut mi);
        let wa = mi.rcWork;
        let x = wa.left + ((wa.right - wa.left) - w) / 2;
        let y = wa.top + ((wa.bottom - wa.top) - hh) / 2;
        SetWindowPos(h, std::ptr::null_mut(), x, y, w, hh, SWP_NOZORDER | SWP_NOACTIVATE);
        barra_de_titulo_escura(h);
        DragAcceptFiles(h, 1);
        // A tela do vídeo: filha, preta, desativada (clique e teclado ficam com a camada por cima).
        let classe_tela = wide("CirandaTela");
        let wt = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            style: 0,
            lpfnWndProc: Some(DefWindowProcW),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: inst,
            hIcon: std::ptr::null_mut(),
            hCursor: LoadCursorW(std::ptr::null_mut(), IDC_ARROW),
            hbrBackground: CreateSolidBrush(0),
            lpszMenuName: std::ptr::null(),
            lpszClassName: classe_tela.as_ptr(),
            hIconSm: std::ptr::null_mut(),
        };
        RegisterClassExW(&wt);
        let tela = CreateWindowExW(
            0,
            classe_tela.as_ptr(),
            std::ptr::null(),
            WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN | WS_DISABLED,
            0,
            0,
            1,
            1,
            h,
            std::ptr::null_mut(),
            inst,
            std::ptr::null(),
        );
        TELA.store(tela as isize, Ordering::Relaxed);
        h
    }
}

/// A janela onde o mpv desenha (opção `wid`).
pub fn tela() -> HWND {
    TELA.load(Ordering::Relaxed) as HWND
}

/// Põe a tela do vídeo no palco (pixels físicos da área cliente).
pub fn definir_palco(x: i32, y: i32, w: i32, h: i32) {
    let t = tela();
    if t.is_null() {
        return;
    }
    unsafe {
        SetWindowPos(t, std::ptr::null_mut(), x, y, w.max(1), h.max(1), SWP_NOZORDER | SWP_NOACTIVATE);
    }
}

pub fn titulo(texto: &str) {
    let t = wide(texto);
    unsafe {
        SetWindowTextW(hwnd(), t.as_ptr());
    }
}

/// Posição do cursor na tela, em pixels físicos.
pub fn cursor() -> Option<(i32, i32)> {
    let mut p = POINT { x: 0, y: 0 };
    (unsafe { GetCursorPos(&mut p) } != 0).then_some((p.x, p.y))
}

pub fn mostrar() {
    unsafe {
        ShowWindow(hwnd(), SW_SHOW);
        SetForegroundWindow(hwnd());
    }
}

/// Liga a janela Slint e já a põe por cima da área cliente.
pub fn ligar_camada(camada: HWND) {
    CAMADA.store(camada as isize, Ordering::Relaxed);
    seguir();
}

pub fn camada() -> HWND {
    CAMADA.load(Ordering::Relaxed) as HWND
}

/// Retângulo da área cliente da hospedeira em pixels físicos da tela.
pub fn area_cliente() -> RECT {
    unsafe {
        let h = hwnd();
        let mut r: RECT = std::mem::zeroed();
        GetClientRect(h, &mut r);
        let mut p = POINT { x: 0, y: 0 };
        ClientToScreen(h, &mut p);
        RECT { left: p.x, top: p.y, right: p.x + r.right, bottom: p.y + r.bottom }
    }
}

/// Põe a camada exatamente sobre a área cliente (posição e tamanho físicos).
pub fn seguir() {
    let c = camada();
    let h = hwnd();
    if c.is_null() || h.is_null() {
        return;
    }
    unsafe {
        if IsIconic(h) != 0 {
            return; // minimizada: o Windows já esconde as janelas "owned"
        }
        let r = area_cliente();
        SetWindowPos(
            c,
            std::ptr::null_mut(),
            r.left,
            r.top,
            (r.right - r.left).max(1),
            (r.bottom - r.top).max(1),
            SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER,
        );
    }
}

pub fn em_tela_cheia() -> bool {
    TELA_CHEIA.load(Ordering::Relaxed)
}

pub fn tela_cheia(ligar: bool) {
    let h = hwnd();
    if ligar == em_tela_cheia() {
        return;
    }
    unsafe {
        if ligar {
            let estilo = GetWindowLongW(h, GWL_STYLE) as u32;
            let mut wp: WINDOWPLACEMENT = std::mem::zeroed();
            wp.length = std::mem::size_of::<WINDOWPLACEMENT>() as u32;
            GetWindowPlacement(h, &mut wp);
            ANTES_DA_TELA_CHEIA = Some((estilo, wp));
            let mon = MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST);
            let mut mi: MONITORINFO = std::mem::zeroed();
            mi.cbSize = std::mem::size_of::<MONITORINFO>() as u32;
            GetMonitorInfoW(mon, &mut mi);
            let r = mi.rcMonitor;
            TELA_CHEIA.store(true, Ordering::Relaxed);
            // Sem WS_MAXIMIZE: senão o Windows pode reencaixar a janela na área de trabalho.
            SetWindowLongW(h, GWL_STYLE, ((estilo & !WS_OVERLAPPEDWINDOW & !WS_MAXIMIZE) | WS_POPUP) as i32);
            SetWindowPos(
                h,
                HWND_TOP,
                r.left,
                r.top,
                r.right - r.left,
                r.bottom - r.top,
                SWP_FRAMECHANGED | SWP_NOOWNERZORDER,
            );
        } else {
            TELA_CHEIA.store(false, Ordering::Relaxed);
            #[allow(static_mut_refs)]
            if let Some((estilo, wp)) = ANTES_DA_TELA_CHEIA.take() {
                SetWindowLongW(h, GWL_STYLE, estilo as i32);
                SetWindowPlacement(h, &wp);
                SetWindowPos(
                    h,
                    std::ptr::null_mut(),
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOOWNERZORDER,
                );
            }
        }
    }
    seguir();
}

/// Em tela cheia, volta a cobrir o monitor inteiro (troca de DPI, de resolução ou de monitores).
fn reencaixar_tela_cheia() {
    let h = hwnd();
    unsafe {
        let mon = MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST);
        let mut mi: MONITORINFO = std::mem::zeroed();
        mi.cbSize = std::mem::size_of::<MONITORINFO>() as u32;
        GetMonitorInfoW(mon, &mut mi);
        let r = mi.rcMonitor;
        SetWindowPos(
            h,
            std::ptr::null_mut(),
            r.left,
            r.top,
            r.right - r.left,
            r.bottom - r.top,
            SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER,
        );
    }
    seguir();
}

/// A camada perdeu o foco para outro app: apaga a barra de título da hospedeira, que o truque
/// do WM_NCACTIVATE deixou acesa (ela não recebe o "desativar", porque não era a ativa).
pub fn apagar_titulo_se_inativa() {
    let h = hwnd();
    let c = camada();
    unsafe {
        let fg = GetForegroundWindow();
        if !h.is_null() && fg != h && fg != c {
            SendMessageW(h, WM_NCACTIVATE, 0, 0);
        }
    }
}

/// O cursor está sobre a faixa de baixo da área cliente (a barra), de `altura` pixels físicos?
pub fn cursor_na_faixa_de_baixo(altura: i32) -> bool {
    let Some((x, y)) = cursor() else { return false };
    let r = area_cliente();
    x >= r.left && x < r.right && y >= r.bottom - altura && y < r.bottom
}

pub fn fechar() {
    unsafe {
        DestroyWindow(hwnd());
    }
}

fn avisar(a: Aviso) {
    // Nunca chama o app de dentro do WndProc (pode ser reentrante): vai pela fila do Slint.
    unsafe {
        #[allow(static_mut_refs)]
        if let Some(f) = AO_AVISAR {
            let _ = slint::invoke_from_event_loop(move || f(a));
        }
    }
}

unsafe extern "system" fn wndproc(h: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    unsafe {
        match msg {
            WM_WINDOWPOSCHANGED => {
                // Só aqui: o DefWindowProc dele ainda gera WM_SIZE e WM_MOVE (seguir 3 vezes à toa).
                let r = DefWindowProcW(h, msg, wp, lp);
                seguir();
                return r;
            }
            WM_GETMINMAXINFO => {
                let dpi = GetDpiForWindow(h).max(96) as i32;
                let (w, hh) = janela_para_cliente(h, MINIMO_DIP.0 * dpi / 96, MINIMO_DIP.1 * dpi / 96);
                let mmi = &mut *(lp as *mut MINMAXINFO);
                mmi.ptMinTrackSize = POINT { x: w, y: hh };
                return 0;
            }
            WM_DPICHANGED => {
                if em_tela_cheia() {
                    reencaixar_tela_cheia();
                    return 0;
                }
                // O Windows sugere o novo retângulo no DPI novo.
                let r = &*(lp as *const RECT);
                SetWindowPos(
                    h,
                    std::ptr::null_mut(),
                    r.left,
                    r.top,
                    r.right - r.left,
                    r.bottom - r.top,
                    SWP_NOZORDER | SWP_NOACTIVATE,
                );
                seguir();
                return 0;
            }
            WM_SYSCOMMAND | WM_CONTEXTMENU => {
                // Mover, redimensionar e o menu da barra de título rodam num laço modal dentro do
                // DefWindowProc (já ao apertar o botão, antes de o arrasto começar): o pulso cobre todo ele.
                SetTimer(h, TIMER_MODAL, 16, None);
                let r = DefWindowProcW(h, msg, wp, lp);
                KillTimer(h, TIMER_MODAL);
                return r;
            }
            WM_TIMER if wp == TIMER_MODAL => {
                #[allow(static_mut_refs)]
                if let Some(f) = NO_LACO_MODAL {
                    f();
                }
                return 0;
            }
            WM_DISPLAYCHANGE => {
                if em_tela_cheia() {
                    reencaixar_tela_cheia();
                }
            }
            WM_NCACTIVATE => {
                // Clique na camada ativa a camada; a barra de título continua acesa.
                let c = camada();
                if wp == 0 && !c.is_null() && (lp as HWND == c || GetForegroundWindow() == c) {
                    return DefWindowProcW(h, msg, 1, lp);
                }
            }
            WM_ACTIVATE => {
                if (wp & 0xffff) != 0 {
                    avisar(Aviso::Ativou);
                }
            }
            WM_KEYDOWN | WM_SYSKEYDOWN => {
                let vk = wp as u32;
                if msg == WM_SYSKEYDOWN && vk != 0x79 {
                    return DefWindowProcW(h, msg, wp, lp);
                }
                use windows_sys::Win32::UI::Input::KeyboardAndMouse::{GetKeyState, VK_CONTROL, VK_MENU, VK_SHIFT};
                let apertada = |k: u16| (GetKeyState(k as i32) as u16 & 0x8000) != 0;
                let shift = apertada(VK_SHIFT);
                let ctrl = apertada(VK_CONTROL);
                let alt = apertada(VK_MENU);
                let repetida = (lp >> 30) & 1 == 1; // bit 30: a tecla já estava apertada
                avisar(Aviso::Tecla { vk, shift, ctrl, alt, repetida });
                return 0;
            }
            WM_DROPFILES => {
                let hd = wp as HDROP;
                let n = DragQueryFileW(hd, 0xFFFF_FFFF, std::ptr::null_mut(), 0);
                let mut v = Vec::new();
                for i in 0..n {
                    let len = DragQueryFileW(hd, i, std::ptr::null_mut(), 0) as usize;
                    let mut buf = vec![0u16; len + 1];
                    DragQueryFileW(hd, i, buf.as_mut_ptr(), (len + 1) as u32);
                    buf.truncate(len);
                    v.push(std::path::PathBuf::from(String::from_utf16_lossy(&buf)));
                }
                DragFinish(hd);
                avisar(Aviso::Soltou(v));
                return 0;
            }
            WM_CLOSE => {
                avisar(Aviso::Fechar);
                return 0;
            }
            WM_ERASEBKGND => {
                return DefWindowProcW(h, msg, wp, lp);
            }
            _ => {}
        }
        DefWindowProcW(h, msg, wp, lp)
    }
}

/// Chamado pela camada ao trocar de DPI: a hospedeira manda na posição.
pub fn dpi(h: HWND) -> u32 {
    unsafe { GetDpiForWindow(h) }
}

