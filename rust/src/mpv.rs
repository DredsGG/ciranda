//! Ligação fina e própria com o libmpv (libmpv-2.dll), carregado em tempo de execução.
//!
//! Escrita a partir de `include/mpv/client.h` do mpv v0.42.0 (API 2.6), que é ISC
//! ("to enable other wrappers outside of mpv"). Só o que a Ciranda usa.

use std::ffi::{CStr, CString, c_char, c_int, c_void};
use std::path::Path;

use libloading::Library;

#[repr(C)]
pub struct Handle {
    _privado: [u8; 0],
}

pub const FORMAT_NONE: c_int = 0;
pub const FORMAT_STRING: c_int = 1;
pub const FORMAT_FLAG: c_int = 3;
pub const FORMAT_INT64: c_int = 4;
pub const FORMAT_DOUBLE: c_int = 5;

pub const EVENTO_NADA: c_int = 0;
pub const EVENTO_FIM_DO_MOTOR: c_int = 1;
pub const EVENTO_LOG: c_int = 2;
pub const EVENTO_INICIO_ARQUIVO: c_int = 6;
pub const EVENTO_FIM_ARQUIVO: c_int = 7;
pub const EVENTO_ARQUIVO_CARREGADO: c_int = 8;
pub const EVENTO_PROPRIEDADE: c_int = 22;
pub const EVENTO_REINICIO: c_int = 21; // MPV_EVENT_PLAYBACK_RESTART

/// `mpv_event` (client.h): id, erro, reply_userdata, dados.
#[repr(C)]
pub struct EventoBruto {
    pub id: c_int,
    pub erro: c_int,
    pub reply_userdata: u64,
    pub dados: *mut c_void,
}

/// `mpv_event_property`.
#[repr(C)]
pub struct PropriedadeBruta {
    pub nome: *const c_char,
    pub formato: c_int,
    pub dados: *mut c_void,
}

/// `mpv_event_log_message`.
#[repr(C)]
pub struct LogBruto {
    pub prefixo: *const c_char,
    pub nivel: *const c_char,
    pub texto: *const c_char,
    pub nivel_num: c_int,
}

/// `mpv_event_end_file` (o começo dele: reason e error).
#[repr(C)]
pub struct FimBruto {
    pub motivo: c_int,
    pub erro: c_int,
}

type FnCreate = unsafe extern "C" fn() -> *mut Handle;
type FnInit = unsafe extern "C" fn(*mut Handle) -> c_int;
type FnDestroy = unsafe extern "C" fn(*mut Handle);
type FnSetOptStr = unsafe extern "C" fn(*mut Handle, *const c_char, *const c_char) -> c_int;
type FnCommand = unsafe extern "C" fn(*mut Handle, *mut *const c_char) -> c_int;
type FnCommandAsync = unsafe extern "C" fn(*mut Handle, u64, *mut *const c_char) -> c_int;
type FnSetProp = unsafe extern "C" fn(*mut Handle, *const c_char, c_int, *mut c_void) -> c_int;
type FnGetProp = unsafe extern "C" fn(*mut Handle, *const c_char, c_int, *mut c_void) -> c_int;
type FnGetPropStr = unsafe extern "C" fn(*mut Handle, *const c_char) -> *mut c_char;
type FnFree = unsafe extern "C" fn(*mut c_void);
type FnObserve = unsafe extern "C" fn(*mut Handle, u64, *const c_char, c_int) -> c_int;
type FnWait = unsafe extern "C" fn(*mut Handle, f64) -> *mut EventoBruto;
type FnWakeup = unsafe extern "C" fn(*mut Handle, Option<unsafe extern "C" fn(*mut c_void)>, *mut c_void);
type FnLogReq = unsafe extern "C" fn(*mut Handle, *const c_char) -> c_int;
type FnErrStr = unsafe extern "C" fn(c_int) -> *const c_char;
type FnApiVer = unsafe extern "C" fn() -> std::ffi::c_ulong;

struct Funcoes {
    create: FnCreate,
    initialize: FnInit,
    terminate_destroy: FnDestroy,
    set_option_string: FnSetOptStr,
    command: FnCommand,
    command_async: FnCommandAsync,
    set_property: FnSetProp,
    get_property: FnGetProp,
    get_property_string: FnGetPropStr,
    free: FnFree,
    observe_property: FnObserve,
    wait_event: FnWait,
    set_wakeup_callback: FnWakeup,
    request_log_messages: FnLogReq,
    error_string: FnErrStr,
    client_api_version: FnApiVer,
}

pub use crate::motor::{Evento, Valor};

pub struct Mpv {
    f: Funcoes,
    h: *mut Handle,
    _lib: Library,
}

fn cs(s: &str) -> CString {
    CString::new(s.replace('\0', "")).unwrap()
}

impl Mpv {
    /// Carrega a DLL e cria o motor (ainda não inicializado).
    pub fn carregar(dll: &Path) -> Result<Mpv, String> {
        unsafe {
            let lib = Library::new(dll).map_err(|e| format!("não carregou {}: {e}", dll.display()))?;
            macro_rules! sym {
                ($n:literal) => {
                    *lib.get(concat!($n, "\0").as_bytes()).map_err(|e| format!("{}: {e}", $n))?
                };
            }
            let f = Funcoes {
                create: sym!("mpv_create"),
                initialize: sym!("mpv_initialize"),
                terminate_destroy: sym!("mpv_terminate_destroy"),
                set_option_string: sym!("mpv_set_option_string"),
                command: sym!("mpv_command"),
                command_async: sym!("mpv_command_async"),
                set_property: sym!("mpv_set_property"),
                get_property: sym!("mpv_get_property"),
                get_property_string: sym!("mpv_get_property_string"),
                free: sym!("mpv_free"),
                observe_property: sym!("mpv_observe_property"),
                wait_event: sym!("mpv_wait_event"),
                set_wakeup_callback: sym!("mpv_set_wakeup_callback"),
                request_log_messages: sym!("mpv_request_log_messages"),
                error_string: sym!("mpv_error_string"),
                client_api_version: sym!("mpv_client_api_version"),
            };
            let ver = (f.client_api_version)();
            if (ver >> 16) != 2 {
                return Err(format!("API do mpv {}.{}, esperava 2.x", ver >> 16, ver & 0xffff));
            }
            let h = (f.create)();
            if h.is_null() {
                return Err("mpv_create devolveu nulo".into());
            }
            Ok(Mpv { f, h, _lib: lib })
        }
    }

    fn erro(&self, r: c_int) -> Result<(), String> {
        if r >= 0 {
            Ok(())
        } else {
            let t = unsafe { CStr::from_ptr((self.f.error_string)(r)) };
            Err(t.to_string_lossy().into_owned())
        }
    }

    pub fn versao_api(&self) -> (u32, u32) {
        let v = unsafe { (self.f.client_api_version)() } as u32;
        (v >> 16, v & 0xffff)
    }

    pub fn opcao(&self, nome: &str, valor: &str) -> Result<(), String> {
        let (n, v) = (cs(nome), cs(valor));
        self.erro(unsafe { (self.f.set_option_string)(self.h, n.as_ptr(), v.as_ptr()) })
            .map_err(|e| format!("{nome}={valor}: {e}"))
    }

    pub fn iniciar(&self) -> Result<(), String> {
        self.erro(unsafe { (self.f.initialize)(self.h) })
    }

    pub fn comando(&self, args: &[&str]) -> Result<(), String> {
        let donos: Vec<CString> = args.iter().map(|a| cs(a)).collect();
        let mut p: Vec<*const c_char> = donos.iter().map(|c| c.as_ptr()).collect();
        p.push(std::ptr::null());
        self.erro(unsafe { (self.f.command)(self.h, p.as_mut_ptr()) })
            .map_err(|e| format!("{args:?}: {e}"))
    }

    pub fn comando_async(&self, id: u64, args: &[&str]) -> Result<(), String> {
        let donos: Vec<CString> = args.iter().map(|a| cs(a)).collect();
        let mut p: Vec<*const c_char> = donos.iter().map(|c| c.as_ptr()).collect();
        p.push(std::ptr::null());
        self.erro(unsafe { (self.f.command_async)(self.h, id, p.as_mut_ptr()) })
    }

    pub fn por_texto(&self, nome: &str, valor: &str) -> Result<(), String> {
        let n = cs(nome);
        let v = cs(valor);
        let mut p = v.as_ptr();
        self.erro(unsafe {
            (self.f.set_property)(self.h, n.as_ptr(), FORMAT_STRING, &mut p as *mut _ as *mut c_void)
        })
    }

    pub fn por_sim(&self, nome: &str, valor: bool) -> Result<(), String> {
        let n = cs(nome);
        let mut v: c_int = valor as c_int;
        self.erro(unsafe {
            (self.f.set_property)(self.h, n.as_ptr(), FORMAT_FLAG, &mut v as *mut _ as *mut c_void)
        })
    }

    pub fn ler_real(&self, nome: &str) -> Option<f64> {
        let n = cs(nome);
        let mut v: f64 = 0.0;
        let r = unsafe {
            (self.f.get_property)(self.h, n.as_ptr(), FORMAT_DOUBLE, &mut v as *mut _ as *mut c_void)
        };
        (r >= 0).then_some(v)
    }

    pub fn ler_inteiro(&self, nome: &str) -> Option<i64> {
        let n = cs(nome);
        let mut v: i64 = 0;
        let r = unsafe {
            (self.f.get_property)(self.h, n.as_ptr(), FORMAT_INT64, &mut v as *mut _ as *mut c_void)
        };
        (r >= 0).then_some(v)
    }

    pub fn ler_sim(&self, nome: &str) -> Option<bool> {
        let n = cs(nome);
        let mut v: c_int = 0;
        let r = unsafe {
            (self.f.get_property)(self.h, n.as_ptr(), FORMAT_FLAG, &mut v as *mut _ as *mut c_void)
        };
        (r >= 0).then_some(v != 0)
    }

    pub fn ler_texto(&self, nome: &str) -> Option<String> {
        let n = cs(nome);
        unsafe {
            let p = (self.f.get_property_string)(self.h, n.as_ptr());
            if p.is_null() {
                return None;
            }
            let s = CStr::from_ptr(p).to_string_lossy().into_owned();
            (self.f.free)(p as *mut c_void);
            Some(s)
        }
    }

    pub fn observar(&self, id: u64, nome: &str, formato: c_int) -> Result<(), String> {
        let n = cs(nome);
        self.erro(unsafe { (self.f.observe_property)(self.h, id, n.as_ptr(), formato) })
    }

    pub fn pedir_log(&self, nivel: &str) -> Result<(), String> {
        let n = cs(nivel);
        self.erro(unsafe { (self.f.request_log_messages)(self.h, n.as_ptr()) })
    }

    /// O callback roda numa thread do mpv: só pode acordar a thread da interface.
    ///
    /// # Safety
    /// `dado` vai cru para o `cb`, em outra thread: tem de valer enquanto o callback estiver
    /// registrado (ou ser nulo, como no `main.rs`).
    pub unsafe fn ao_acordar(&self, cb: unsafe extern "C" fn(*mut c_void), dado: *mut c_void) {
        unsafe { (self.f.set_wakeup_callback)(self.h, Some(cb), dado) }
    }

    /// Próximo evento sem esperar; `None` quando a fila esvaziou.
    pub fn proximo_evento(&self) -> Option<Evento> {
        unsafe {
            let e = &*(self.f.wait_event)(self.h, 0.0);
            let txt = |p: *const c_char| {
                if p.is_null() { String::new() } else { CStr::from_ptr(p).to_string_lossy().into_owned() }
            };
            Some(match e.id {
                EVENTO_NADA => return None,
                EVENTO_FIM_DO_MOTOR => Evento::FimDoMotor,
                EVENTO_INICIO_ARQUIVO => Evento::InicioArquivo,
                EVENTO_ARQUIVO_CARREGADO => Evento::ArquivoCarregado,
                EVENTO_REINICIO => Evento::Reinicio,
                EVENTO_FIM_ARQUIVO => {
                    let f = &*(e.dados as *const FimBruto);
                    Evento::FimArquivo { motivo: f.motivo, erro: f.erro }
                }
                EVENTO_LOG => {
                    let l = &*(e.dados as *const LogBruto);
                    Evento::Log { nivel: txt(l.nivel), prefixo: txt(l.prefixo), texto: txt(l.texto) }
                }
                EVENTO_PROPRIEDADE => {
                    let p = &*(e.dados as *const PropriedadeBruta);
                    let valor = if p.dados.is_null() {
                        Valor::Nada
                    } else {
                        match p.formato {
                            FORMAT_STRING => Valor::Texto(txt(*(p.dados as *const *const c_char))),
                            FORMAT_FLAG => Valor::Sim(*(p.dados as *const c_int) != 0),
                            FORMAT_INT64 => Valor::Inteiro(*(p.dados as *const i64)),
                            FORMAT_DOUBLE => Valor::Real(*(p.dados as *const f64)),
                            _ => Valor::Nada,
                        }
                    };
                    Evento::Propriedade { id: e.reply_userdata, nome: txt(p.nome), valor }
                }
                outro => Evento::Outro(outro),
            })
        }
    }
}

impl Drop for Mpv {
    fn drop(&mut self) {
        unsafe {
            // Tira o callback antes: o mpv não pode chamar o app enquanto se desmonta.
            (self.f.set_wakeup_callback)(self.h, None, std::ptr::null_mut());
            (self.f.terminate_destroy)(self.h)
        }
    }
}
