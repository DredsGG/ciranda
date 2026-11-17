//! Janela-hospedeira Win32: tem a barra de título do Windows, recebe o vídeo do mpv numa
//! janela filha (opção `wid`) e arrasta junto a janela Slint (de topo, "owned" por ela),
//! que fica exatamente sobre a área cliente.

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
    Tecla { vk: u32, shift: bool, repetida: bool, ctrl_alt: bool },
    Soltou(Vec<std::path::PathBuf>),
    Fechar,
    Ativou,
}

static HOSPEDEIRA: AtomicIsize = AtomicIsize::new(0);
static CAMADA: AtomicIsize = AtomicIsize::new(0);
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
        let (w, hh) = (largura_dip * dpi / 96, altura_dip * dpi / 96);
        let mon = MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST);
        let mut mi: MONITORINFO = std::mem::zeroed();
        mi.cbSize = std::mem::size_of::<MONITORINFO>() as u32;
        GetMonitorInfoW(mon, &mut mi);
        let wa = mi.rcWork;
        let x = wa.left + ((wa.right - wa.left) - w) / 2;
        let y = wa.top + ((wa.bottom - wa.top) - hh) / 2;
        SetWindowPos(h, std::ptr::null_mut(), x, y, w, hh, SWP_NOZORDER | SWP_NOACTIVATE);
        // Barra de título escura (Windows 11): DWMWA_USE_IMMERSIVE_DARK_MODE = 20.
        let escuro: i32 = 1;
        DwmSetWindowAttribute(h, 20, &escuro as *const _ as *const _, 4);
        DragAcceptFiles(h, 1);
        h
    }
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

/// O cursor está sobre a faixa de baixo da área cliente (a barra de controles)?
pub fn cursor_sobre_a_barra(altura_dip: i32) -> bool {
    unsafe {
        let mut p = POINT { x: 0, y: 0 };
        if GetCursorPos(&mut p) == 0 {
            return false;
        }
        let r = area_cliente();
        let alt = altura_dip * GetDpiForWindow(hwnd()).max(96) as i32 / 96;
        p.x >= r.left && p.x < r.right && p.y >= r.bottom - alt && p.y < r.bottom
    }
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
                let ctrl_alt = apertada(VK_CONTROL) || apertada(VK_MENU);
                let repetida = (lp >> 30) & 1 == 1; // bit 30: a tecla já estava apertada
                avisar(Aviso::Tecla { vk, shift, repetida, ctrl_alt });
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

