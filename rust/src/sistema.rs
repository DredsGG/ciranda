//! (fase 3) Efeitos no Windows: mostrar no Explorer, área de transferência, escolher pasta e
//! arquivos, abrir endereço. Porta do `mostrar_no_explorer` da `janela.py` da 1.5.1 e do que lá o
//! Qt fazia (`QFileDialog`, `QClipboard`, `QDesktopServices`).
//!
//! Os diálogos são o `IFileOpenDialog` do Windows. O `windows-sys` não traz as tabelas de métodos
//! (vtables) das interfaces COM, então elas estão aqui à mão, na ordem exata do `ShObjIdl_core.h`.
//! Cada posição é conferida na compilação (`offset_of!`) e as que o programa chama são exercitadas
//! nos testes sem abrir janela nenhuma.
//!
//! Nenhuma função daqui entra em pânico: falhou, devolve `false`, `None` ou lista vazia.

use std::ffi::{OsStr, OsString, c_void};
use std::marker::PhantomData;
use std::os::windows::ffi::{OsStrExt, OsStringExt};
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::ptr::{NonNull, null, null_mut};

use windows_sys::Win32::Foundation::{HWND, RPC_E_CHANGED_MODE, S_OK};
use windows_sys::Win32::System::Com::{
    CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED, COINIT_DISABLE_OLE1DDE, CoCreateInstance, CoInitializeEx,
    CoTaskMemFree, CoUninitialize,
};
use windows_sys::Win32::UI::Shell::{
    FOS_ALLOWMULTISELECT, FOS_FILEMUSTEXIST, FOS_FORCEFILESYSTEM, FOS_PATHMUSTEXIST, FOS_PICKFOLDERS, FileOpenDialog,
    SHCreateItemFromParsingName, SIGDN_FILESYSPATH,
};
use windows_sys::core::{GUID, HRESULT, PCWSTR, PWSTR};

const SEP: u16 = b'\\' as u16;
const ALTSEP: u16 = b'/' as u16;
const PONTO: u16 = b'.' as u16;
const DOIS_PONTOS: u16 = b':' as u16;

fn e_sep(c: u16) -> bool {
    c == SEP || c == ALTSEP
}

/// `os.path.normpath` do Python 3.12 no Windows (o `_Py_normpath_and_size` do `fileutils.c`, que
/// o `ntpath.normpath` chama): junta `.`, `..` e separadores repetidos, troca `/` por `\`, mantém
/// o prefixo `C:`, `\\servidor\pasta\`, `\\?\` e `\\.\`. Caminho vazio vira `.`.
pub fn normpath(caminho: &str) -> String {
    let largo: Vec<u16> = caminho.encode_utf16().collect();
    String::from_utf16_lossy(&normpath_largo(&largo))
}

/// O mesmo em UTF-16 (como o `wchar_t` do Python): serve também para nome que não é UTF-8 válido.
/// Porta linha a linha do C, no mesmo buffer (lê na frente de onde escreve), para dar exatamente
/// o mesmo resultado, inclusive nos casos estranhos.
fn normpath_largo(entrada: &[u16]) -> Vec<u16> {
    let n = entrada.len();
    if n == 0 {
        return vec![PONTO];
    }
    let mut b = entrada.to_vec();
    b.push(0); // o NUL do fim da string do Python
    let em = |b: &[u16], i: usize| b.get(i).copied().unwrap_or(0);
    let sep_ou_fim = |b: &[u16], i: usize| i >= n || e_sep(b[i]);

    let mut inicio = 0; // o `path` do C: avança quando pula o `.\` do começo
    let mut p1 = 0; // próximo caractere lido
    let mut p2 = 0; // onde vai o próximo caractere escrito
    let mut min_p2 = 0; // daqui para trás o `..` não apaga
    let mut ultimo: u16 = 0;

    if b[0] == PONTO && e_sep(em(&b, 1)) {
        // pula o `.\` do começo (e os separadores depois dele)
        inicio = 2;
        while inicio < n && e_sep(b[inicio]) {
            inicio += 1;
        }
        p1 = inicio;
        p2 = inicio;
        min_p2 = inicio;
        ultimo = SEP;
    } else if b[0] != 0 && em(&b, 1) == DOIS_PONTOS {
        // unidade (`C:`): fica como está
        p1 = 2;
        p2 = 2;
        min_p2 = 2;
        ultimo = DOIS_PONTOS;
    } else if e_sep(b[0]) && e_sep(em(&b, 1)) {
        // `\\servidor\pasta\`, `\\?\C:\`, `\\.\`: copia o prefixo até o segundo separador
        b[0] = SEP;
        b[1] = SEP;
        p1 = 2;
        p2 = 2;
        let mut seps = 2;
        while p1 < n && seps > 0 {
            if e_sep(b[p1]) {
                seps -= 1;
                b[p2] = SEP;
                ultimo = SEP;
            } else {
                b[p2] = b[p1];
                ultimo = b[p1];
            }
            p2 += 1;
            p1 += 1;
        }
        min_p2 = p2 - 1;
    }

    while p1 < n {
        let c = if b[p1] == ALTSEP { SEP } else { b[p1] };
        if ultimo == SEP && c == PONTO {
            let sep_em_1 = sep_ou_fim(&b, p1 + 1);
            let sep_em_2 = !sep_em_1 && sep_ou_fim(&b, p1 + 2);
            if sep_em_2 && b[p1 + 1] == PONTO {
                // `..`: volta um trecho
                let mut p3 = p2;
                while p3 != min_p2 {
                    p3 -= 1;
                    if b[p3] != SEP {
                        break;
                    }
                }
                while p3 != min_p2 && b[p3 - 1] != SEP {
                    p3 -= 1;
                }
                if p2 == min_p2 || (b[p3] == PONTO && em(&b, p3 + 1) == PONTO && e_sep(em(&b, p3 + 2))) {
                    // o trecho de antes também é `..` (ou não há trecho): acrescenta
                    b[p2] = PONTO;
                    b[p2 + 1] = PONTO;
                    p2 += 2;
                    ultimo = PONTO;
                } else if b[p3] == SEP {
                    p2 = p3 + 1; // caminho absoluto: apaga o trecho e fica a barra
                } else {
                    p2 = p3;
                }
                p1 += 1;
            } else if !sep_em_1 {
                b[p2] = c;
                p2 += 1;
                ultimo = c;
            }
            // `.` sozinho: some
        } else if ultimo == SEP && c == SEP {
            // separador repetido: some
        } else {
            b[p2] = c;
            p2 += 1;
            ultimo = c;
        }
        p1 += 1;
    }

    // tira os separadores do fim, mas nunca o do prefixo
    let tamanho = if p2 == min_p2 {
        min_p2 - inicio
    } else {
        loop {
            p2 -= 1;
            if p2 == min_p2 || b[p2] != SEP {
                break;
            }
        }
        p2 - inicio + 1
    };
    if tamanho == 0 {
        return vec![PONTO];
    }
    b[inicio..inicio + tamanho].to_vec()
}

/// Os argumentos do `explorer.exe` para abrir a pasta com o arquivo selecionado, com as aspas do
/// jeito que o Explorer entende: `/select,"C:\pasta\arquivo.mp4"`. Vai inteiro, sem as regras de
/// aspas do Rust (`raw_arg`); o `Command` põe `"explorer.exe"` antes.
pub fn linha_explorer(caminho: &str) -> String {
    linha_explorer_os(OsStr::new(caminho)).to_string_lossy().into_owned()
}

fn linha_explorer_os(caminho: &OsStr) -> OsString {
    let mut linha = OsString::from("/select,\"");
    linha.push(caminho);
    linha.push("\"");
    linha
}

fn com_nul(texto: impl IntoIterator<Item = u16>) -> Vec<u16> {
    texto.into_iter().chain(std::iter::once(0)).collect()
}

fn largo_de_caminho(caminho: &Path) -> Vec<u16> {
    let largo: Vec<u16> = caminho.as_os_str().encode_wide().collect();
    normpath_largo(&largo)
}

// ---------------------------------------------------------------------------------------------
// COM

/// `CoInitializeEx` apartamento (STA) enquanto vive. `S_FALSE` (já iniciado nesta linha, o winit
/// faz `OleInitialize`) conta como sucesso e é equilibrado; `RPC_E_CHANGED_MODE` (linha já em
/// MTA) também serve, mas aí não é nosso para desfazer.
struct Apartamento {
    equilibrar: bool,
}

impl Apartamento {
    fn entrar() -> Option<Apartamento> {
        let hr = unsafe { CoInitializeEx(null(), (COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE) as u32) };
        if hr >= 0 {
            Some(Apartamento { equilibrar: true })
        } else if hr == RPC_E_CHANGED_MODE {
            Some(Apartamento { equilibrar: false })
        } else {
            None
        }
    }
}

impl Drop for Apartamento {
    fn drop(&mut self) {
        if self.equilibrar {
            unsafe { CoUninitialize() };
        }
    }
}

type Liberar = unsafe extern "system" fn(*mut c_void) -> u32;
type MetodoPtr = unsafe extern "system" fn(*mut c_void, *mut *mut c_void) -> HRESULT;

/// Os três primeiros métodos de toda interface COM.
#[repr(C)]
#[allow(dead_code)] // só o Release é chamado
struct VtblUnknown {
    query_interface: usize,
    add_ref: usize,
    release: Liberar,
}

/// Marca as vtables daqui.
///
/// # Safety
///
/// A struct é `#[repr(C)]` e começa com os três métodos de `IUnknown` (`QueryInterface`,
/// `AddRef`, `Release`), para o `Drop` do [`Com`] achar o `Release`.
unsafe trait Vtabela {}

/// `IFileOpenDialog` (que herda `IFileDialog`, que herda `IModalWindow`), ordem do
/// `ShObjIdl_core.h`. O que o programa não chama fica como `usize` (só ocupa o lugar).
#[repr(C)]
#[allow(dead_code)]
struct VtblDialogo {
    // IUnknown
    query_interface: usize,
    add_ref: usize,
    release: Liberar,
    // IModalWindow
    show: unsafe extern "system" fn(*mut c_void, HWND) -> HRESULT,
    // IFileDialog
    set_file_types: usize,
    set_file_type_index: usize,
    get_file_type_index: usize,
    advise: usize,
    unadvise: usize,
    set_options: unsafe extern "system" fn(*mut c_void, u32) -> HRESULT,
    get_options: unsafe extern "system" fn(*mut c_void, *mut u32) -> HRESULT,
    set_default_folder: usize,
    set_folder: unsafe extern "system" fn(*mut c_void, *mut c_void) -> HRESULT,
    get_folder: usize,
    get_current_selection: usize,
    set_file_name: usize,
    get_file_name: usize,
    set_title: unsafe extern "system" fn(*mut c_void, PCWSTR) -> HRESULT,
    set_ok_button_label: usize,
    set_file_name_label: usize,
    get_result: MetodoPtr,
    add_place: usize,
    set_default_extension: usize,
    close: usize,
    set_client_guid: usize,
    clear_client_data: usize,
    set_filter: usize,
    // IFileOpenDialog
    get_results: MetodoPtr,
    get_selected_items: usize,
}

/// `IShellItem`.
#[repr(C)]
#[allow(dead_code)]
struct VtblItem {
    query_interface: usize,
    add_ref: usize,
    release: Liberar,
    bind_to_handler: usize,
    get_parent: usize,
    get_display_name: unsafe extern "system" fn(*mut c_void, i32, *mut PWSTR) -> HRESULT,
    get_attributes: usize,
    compare: usize,
}

/// `IShellItemArray`.
#[repr(C)]
#[allow(dead_code)]
struct VtblLista {
    query_interface: usize,
    add_ref: usize,
    release: Liberar,
    bind_to_handler: usize,
    get_property_store: usize,
    get_property_description_list: usize,
    get_attributes: usize,
    get_count: unsafe extern "system" fn(*mut c_void, *mut u32) -> HRESULT,
    get_item_at: unsafe extern "system" fn(*mut c_void, u32, *mut *mut c_void) -> HRESULT,
    enum_items: usize,
}

unsafe impl Vtabela for VtblUnknown {}
unsafe impl Vtabela for VtblDialogo {}
unsafe impl Vtabela for VtblItem {}
unsafe impl Vtabela for VtblLista {}

// Cada método no lugar certo (em ponteiros): qualquer troca de ordem não compila.
const P: usize = size_of::<usize>();
const _: () = {
    use std::mem::offset_of;
    assert!(offset_of!(VtblUnknown, release) == 2 * P);
    assert!(offset_of!(VtblDialogo, release) == 2 * P);
    assert!(offset_of!(VtblDialogo, show) == 3 * P);
    assert!(offset_of!(VtblDialogo, set_file_types) == 4 * P);
    assert!(offset_of!(VtblDialogo, set_options) == 9 * P);
    assert!(offset_of!(VtblDialogo, get_options) == 10 * P);
    assert!(offset_of!(VtblDialogo, set_folder) == 12 * P);
    assert!(offset_of!(VtblDialogo, set_title) == 17 * P);
    assert!(offset_of!(VtblDialogo, get_result) == 20 * P);
    assert!(offset_of!(VtblDialogo, set_filter) == 26 * P);
    assert!(offset_of!(VtblDialogo, get_results) == 27 * P);
    assert!(size_of::<VtblDialogo>() == 29 * P);
    assert!(offset_of!(VtblItem, release) == 2 * P);
    assert!(offset_of!(VtblItem, get_display_name) == 5 * P);
    assert!(size_of::<VtblItem>() == 8 * P);
    assert!(offset_of!(VtblLista, release) == 2 * P);
    assert!(offset_of!(VtblLista, get_count) == 7 * P);
    assert!(offset_of!(VtblLista, get_item_at) == 8 * P);
    assert!(size_of::<VtblLista>() == 10 * P);
};

// {D57C7288-D4AD-4768-BE02-9D969532D960}
const IID_IFILEOPENDIALOG: GUID = GUID::from_u128(0xd57c7288_d4ad_4768_be02_9d969532d960);
// {43826D1E-E718-42EE-BC55-A1E261C37BFE}
const IID_ISHELLITEM: GUID = GUID::from_u128(0x43826d1e_e718_42ee_bc55_a1e261c37bfe);
// {B63EA76D-1F85-456F-A19C-48159EFA858B}
#[cfg(test)]
const IID_ISHELLITEMARRAY: GUID = GUID::from_u128(0xb63ea76d_1f85_456f_a19c_48159efa858b);

/// Ponteiro de interface COM com dono: chama `Release` quando sai de escopo.
struct Com<V: Vtabela> {
    bruto: NonNull<c_void>,
    _v: PhantomData<*const V>,
}

impl<V: Vtabela> Com<V> {
    /// Segurança: `bruto` é nulo ou um ponteiro de interface cuja vtable tem o formato `V`, com
    /// uma referência que passa a ser nossa.
    unsafe fn tomar(bruto: *mut c_void) -> Option<Self> {
        NonNull::new(bruto).map(|bruto| Com { bruto, _v: PhantomData })
    }

    fn vt(&self) -> &V {
        // o objeto COM começa com o ponteiro para a vtable
        unsafe { &**self.bruto.as_ptr().cast::<*const V>() }
    }

    fn cru(&self) -> *mut c_void {
        self.bruto.as_ptr()
    }
}

impl<V: Vtabela> Drop for Com<V> {
    fn drop(&mut self) {
        unsafe {
            let vt = *self.bruto.as_ptr().cast::<*const VtblUnknown>();
            ((*vt).release)(self.bruto.as_ptr());
        }
    }
}

/// Pede um ponteiro de interface por um método `(this, **saida) -> HRESULT`.
fn obter<V: Vtabela>(chamar: impl FnOnce(*mut *mut c_void) -> HRESULT) -> Option<Com<V>> {
    let mut saida: *mut c_void = null_mut();
    let hr = chamar(&mut saida);
    // Segurança: quem chama dá o IID da vtable `V`; em falha o ponteiro pode ter sobrado, e só
    // é nosso no sucesso.
    if hr < 0 { None } else { unsafe { Com::tomar(saida) } }
}

fn criar_dialogo() -> Option<Com<VtblDialogo>> {
    obter(|saida| unsafe {
        CoCreateInstance(&FileOpenDialog, null_mut(), CLSCTX_INPROC_SERVER, &IID_IFILEOPENDIALOG, saida)
    })
}

/// `IShellItem` de um caminho (`SHCreateItemFromParsingName`). `None` se não existe.
fn item_de_caminho(caminho: &Path) -> Option<Com<VtblItem>> {
    let largo = com_nul(largo_de_caminho(caminho));
    obter(|saida| unsafe { SHCreateItemFromParsingName(largo.as_ptr(), null_mut(), &IID_ISHELLITEM, saida) })
}

/// Caminho no disco de um `IShellItem` (`GetDisplayName(SIGDN_FILESYSPATH)` + `CoTaskMemFree`).
/// `None` para o que não é arquivo (Bibliotecas, Este Computador).
fn caminho_do_item(item: &Com<VtblItem>) -> Option<PathBuf> {
    let mut texto: PWSTR = null_mut();
    let hr = unsafe { (item.vt().get_display_name)(item.cru(), SIGDN_FILESYSPATH, &mut texto) };
    if hr < 0 || texto.is_null() {
        return None;
    }
    let caminho = unsafe {
        let mut n = 0;
        while *texto.add(n) != 0 {
            n += 1;
        }
        let s = OsString::from_wide(std::slice::from_raw_parts(texto, n));
        CoTaskMemFree(texto as *const c_void);
        s
    };
    Some(PathBuf::from(caminho))
}

/// Todos os caminhos de um `IShellItemArray`, na ordem dele; pula o que não é arquivo.
fn caminhos_da_lista(lista: &Com<VtblLista>) -> Vec<PathBuf> {
    let mut quantos = 0u32;
    if unsafe { (lista.vt().get_count)(lista.cru(), &mut quantos) } < 0 {
        return Vec::new();
    }
    (0..quantos)
        .filter_map(|i| {
            let item: Com<VtblItem> = obter(|saida| unsafe { (lista.vt().get_item_at)(lista.cru(), i, saida) })?;
            caminho_do_item(&item)
        })
        .collect()
}

/// Opções atuais do diálogo mais `extra`.
fn acrescentar_opcoes(dialogo: &Com<VtblDialogo>, extra: u32) -> bool {
    let mut atuais = 0u32;
    unsafe {
        (dialogo.vt().get_options)(dialogo.cru(), &mut atuais) >= 0
            && (dialogo.vt().set_options)(dialogo.cru(), atuais | extra) >= 0
    }
}

/// Cria, configura e mostra o diálogo. `None` se cancelou (`HRESULT_FROM_WIN32(ERROR_CANCELLED)`,
/// 0x800704C7) ou se algo falhou.
fn mostrar_dialogo(dono: isize, titulo: &str, inicio: Option<&Path>, extra: u32) -> Option<Com<VtblDialogo>> {
    let dialogo = criar_dialogo()?;
    if !acrescentar_opcoes(&dialogo, extra) {
        return None;
    }
    let titulo = com_nul(titulo.encode_utf16());
    unsafe { (dialogo.vt().set_title)(dialogo.cru(), titulo.as_ptr()) };
    if let Some(pasta) = inicio.filter(|p| p.exists()).and_then(item_de_caminho) {
        unsafe { (dialogo.vt().set_folder)(dialogo.cru(), pasta.cru()) };
    }
    let hr = unsafe { (dialogo.vt().show)(dialogo.cru(), dono as HWND) };
    (hr == S_OK).then_some(dialogo)
}

/// Escolher uma pasta (o `QFileDialog.getExistingDirectory` da 1.5.1). `dono` é o HWND da janela
/// (fica bloqueada enquanto o diálogo está aberto); `inicio` é onde ele abre, se existir.
/// `None` se a pessoa cancelou.
pub fn escolher_pasta(dono: isize, titulo: &str, inicio: Option<&Path>) -> Option<PathBuf> {
    let _com = Apartamento::entrar()?; // declarado antes: sai por último, depois dos ponteiros
    let dialogo = mostrar_dialogo(dono, titulo, inicio, FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST)?;
    let item: Com<VtblItem> = obter(|saida| unsafe { (dialogo.vt().get_result)(dialogo.cru(), saida) })?;
    caminho_do_item(&item)
}

/// Escolher um ou vários arquivos (o `QFileDialog.getOpenFileNames` da 1.5.1). Vazio se a pessoa
/// cancelou.
pub fn escolher_arquivos(dono: isize, titulo: &str, inicio: Option<&Path>) -> Vec<PathBuf> {
    let Some(_com) = Apartamento::entrar() else {
        return Vec::new();
    };
    let Some(dialogo) =
        mostrar_dialogo(dono, titulo, inicio, FOS_ALLOWMULTISELECT | FOS_FILEMUSTEXIST | FOS_FORCEFILESYSTEM)
    else {
        return Vec::new();
    };
    let lista: Option<Com<VtblLista>> = obter(|saida| unsafe { (dialogo.vt().get_results)(dialogo.cru(), saida) });
    lista.map(|l| caminhos_da_lista(&l)).unwrap_or_default()
}

// ---------------------------------------------------------------------------------------------
// Explorer e endereços

/// `ShellExecuteW(NULL, "open", alvo, NULL, NULL, SW_SHOWNORMAL)`; sucesso é resultado > 32.
fn executar_abrir(alvo: &[u16]) -> bool {
    use windows_sys::Win32::UI::Shell::ShellExecuteW;
    use windows_sys::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;
    let _com = Apartamento::entrar(); // o ShellExecute pode usar extensões do shell (COM)
    let alvo = com_nul(alvo.iter().copied());
    let abrir = com_nul("open".encode_utf16());
    let r = unsafe { ShellExecuteW(null_mut(), abrir.as_ptr(), alvo.as_ptr(), null(), null(), SW_SHOWNORMAL) };
    r as isize > 32
}

/// Abre a pasta do arquivo no Explorer com ele já selecionado (porta do `mostrar_no_explorer` da
/// `janela.py` da 1.5.1): `SHOpenFolderAndSelectItems`; se não der, `explorer.exe /select,"..."`;
/// se nem isso, abre só a pasta.
pub fn mostrar_no_explorer(caminho: &Path) -> bool {
    let largo = largo_de_caminho(caminho);
    if selecionar_no_shell(&largo) {
        return true;
    }
    let texto = OsString::from_wide(&largo);
    let reserva = std::process::Command::new("explorer.exe").raw_arg(linha_explorer_os(&texto)).spawn();
    if reserva.is_ok() {
        return true; // como o `Popen` da 1.5.1: não espera o Explorer
    }
    // `os.startfile(os.path.dirname(caminho))`
    let normal = PathBuf::from(texto);
    let pasta = match normal.parent() {
        Some(p) if p.as_os_str().is_empty() => return false,
        Some(p) => p,
        None => normal.as_path(), // raiz (`C:\`): o dirname do Python devolve ela mesma
    };
    executar_abrir(&pasta.as_os_str().encode_wide().collect::<Vec<u16>>())
}

/// `ILCreateFromPathW` + `SHOpenFolderAndSelectItems(pidl, 0, NULL, 0)`, sempre com `ILFree`.
fn selecionar_no_shell(largo: &[u16]) -> bool {
    use windows_sys::Win32::UI::Shell::{ILCreateFromPathW, ILFree, SHOpenFolderAndSelectItems};
    let Some(_com) = Apartamento::entrar() else {
        return false;
    };
    let largo = com_nul(largo.iter().copied());
    let pidl = unsafe { ILCreateFromPathW(largo.as_ptr()) };
    if pidl.is_null() {
        return false;
    }
    let hr = unsafe { SHOpenFolderAndSelectItems(pidl, 0, null(), 0) };
    unsafe { ILFree(pidl) };
    hr == S_OK
}

/// Abre um endereço (`https://...`, `mailto:`) no programa padrão (o `QDesktopServices.openUrl`
/// da 1.5.1).
pub fn abrir_uri(uri: &str) -> bool {
    executar_abrir(&uri.encode_utf16().collect::<Vec<u16>>())
}

// ---------------------------------------------------------------------------------------------
// Área de transferência

/// Põe `texto` na área de transferência (`CF_UNICODETEXT`). Se outro programa está com ela aberta,
/// tenta de novo algumas vezes, 10 ms entre uma e outra.
pub fn copiar_texto(texto: &str) -> bool {
    use windows_sys::Win32::System::DataExchange::{CloseClipboard, OpenClipboard};
    let largo = com_nul(texto.encode_utf16());
    let mut aberta = false;
    for tentativa in 0..10 {
        if tentativa > 0 {
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        if unsafe { OpenClipboard(null_mut()) } != 0 {
            aberta = true;
            break;
        }
    }
    if !aberta {
        return false;
    }
    let ok = unsafe { preencher_area(&largo) };
    unsafe { CloseClipboard() };
    ok
}

/// Segurança: a área de transferência está aberta por esta linha.
unsafe fn preencher_area(largo: &[u16]) -> bool {
    use windows_sys::Win32::Foundation::{GlobalFree, HANDLE};
    use windows_sys::Win32::System::DataExchange::{EmptyClipboard, SetClipboardData};
    use windows_sys::Win32::System::Memory::{GMEM_MOVEABLE, GlobalAlloc, GlobalLock, GlobalUnlock};
    use windows_sys::Win32::System::Ole::CF_UNICODETEXT;
    unsafe {
        if EmptyClipboard() == 0 {
            return false;
        }
        let memoria = GlobalAlloc(GMEM_MOVEABLE, std::mem::size_of_val(largo));
        if memoria.is_null() {
            return false;
        }
        let destino = GlobalLock(memoria).cast::<u16>();
        if destino.is_null() {
            GlobalFree(memoria);
            return false;
        }
        std::ptr::copy_nonoverlapping(largo.as_ptr(), destino, largo.len());
        GlobalUnlock(memoria);
        if SetClipboardData(u32::from(CF_UNICODETEXT), memoria as HANDLE).is_null() {
            GlobalFree(memoria); // só passa a ser do sistema se deu certo
            return false;
        }
        true
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    /// Saída do `ntpath.normpath` do Python 3.12.10 (Windows) para cada entrada.
    const CASOS_NORMPATH: &[(&str, &str)] = &[
        (r"", r"."),
        (r".", r"."),
        (r"..", r".."),
        (r"./", r"."),
        (r".\", r"."),
        (r"a", r"a"),
        (r"a/b", r"a\b"),
        (r"a\b", r"a\b"),
        (r"a//b", r"a\b"),
        (r"a\\b", r"a\b"),
        (r"a/./b", r"a\b"),
        (r"a/../b", r"b"),
        (r"a/b/..", r"a"),
        (r"a/b/../..", r"."),
        (r"a/b/../../..", r".."),
        (r"../a", r"..\a"),
        (r"../../a/b", r"..\..\a\b"),
        (r"./a/./b/.", r"a\b"),
        (r"a/", r"a"),
        (r"a\", r"a"),
        (r"a/b/", r"a\b"),
        (r"/", r"\"),
        (r"\", r"\"),
        (r"//", r"\\"),
        (r"///", r"\\\"),
        (r"/a", r"\a"),
        (r"\a", r"\a"),
        (r"/..", r"\"),
        (r"/../a", r"\a"),
        (r"\..\..\a", r"\a"),
        (r"C:", r"C:"),
        (r"C:/", r"C:\"),
        (r"C:\", r"C:\"),
        (r"C:a", r"C:a"),
        (r"C:a/..", r"C:"),
        (r"C:a/../..", r"C:.."),
        (r"C:..", r"C:.."),
        (r"C:../a", r"C:..\a"),
        (r"C:/..", r"C:\"),
        (r"C:\..\a", r"C:\a"),
        (r"C:\Users\x\..\y", r"C:\Users\y"),
        (r"C:/Users//x/./y/", r"C:\Users\x\y"),
        (r"c:\a\b\..\c.txt", r"c:\a\c.txt"),
        (r"C:\a\.", r"C:\a"),
        (r"C:\a\..", r"C:\"),
        (r"C:\a\b\c\..\..\..\..\d", r"C:\d"),
        (r"C:\a b\c d.mp4", r"C:\a b\c d.mp4"),
        (r"C:\pasta\vídeo ção.mkv", r"C:\pasta\vídeo ção.mkv"),
        (r"C:\a\...\b", r"C:\a\...\b"),
        (r"C:\a\..b\c", r"C:\a\..b\c"),
        (r"C:\a\b.\c", r"C:\a\b.\c"),
        (r"C:\a\ \b", r"C:\a\ \b"),
        (r"\\server\share", r"\\server\share"),
        (r"\\server\share\", r"\\server\share\"),
        (r"\\server\share\a\..\b", r"\\server\share\b"),
        (r"//server/share/a/./b", r"\\server\share\a\b"),
        (r"\\server\share\..\a", r"\\server\share\a"),
        (r"\\server", r"\\server"),
        (r"\\server\", r"\\server\"),
        (r"\\?\C:\a\..\b", r"\\?\C:\b"),
        (r"\\?\C:\a\.\b", r"\\?\C:\a\b"),
        (r"\\.\C:\a\..\b", r"\\.\C:\b"),
        (r"\\?\UNC\server\share\a\..\b", r"\\?\UNC\server\share\b"),
        (r"//?/C:/a/b", r"\\?\C:\a\b"),
        (r"a/b/c/../../../..", r".."),
        (r"a/../../b", r"..\b"),
        (r"./..", r".."),
        (r"../.", r".."),
        (r"a\.\.\b", r"a\b"),
        (r"C:\\a\\\b", r"C:\a\b"),
        (r"\\a\..", r"\\a\.."),
        (r"\\a\b\..", r"\\a\b\"),
        (r"\\a\b\c\..\..", r"\\a\b\"),
        (r".\..\a", r"..\a"),
        (r"./../..", r"..\.."),
        (r".//a", r"a"),
        (r"C:\a/b\../c", r"C:\a\c"),
        (r"C:\a\b\..\..\..", r"C:\"),
        (r"x:..\..\a", r"x:..\..\a"),
        (r"::a", r"::a"),
        (r"C:\..\..", r"C:\"),
        (r"..\..", r"..\.."),
        (r"a\..\..\..\b\..", r"..\.."),
        (r"\\?\C:\..\..\a", r"\\?\C:\a"),
        (r"C:\a\b\\\..\c", r"C:\a\c"),
        ("C:\\a\\\u{1F600}\\..\\b", r"C:\a\b"),
        ("C:\\\u{1F600}\\.", "C:\\\u{1F600}"),
        (r"/a/b/../../../c/", r"\c"),
        (r"a/b\./../c", r"a\c"),
    ];

    #[test]
    fn normpath_igual_ao_python() {
        for (entrada, esperado) in CASOS_NORMPATH {
            assert_eq!(normpath(entrada), *esperado, "normpath({entrada:?})");
        }
    }

    #[test]
    fn normpath_nao_utf8() {
        // surrogate solto (nome que não é UTF-8 válido): passa intacto
        let entrada: Vec<u16> = "C:\\x\\..\\a".encode_utf16().chain([0xD800]).chain("/b".encode_utf16()).collect();
        let esperado: Vec<u16> = "C:\\a".encode_utf16().chain([0xD800]).chain("\\b".encode_utf16()).collect();
        assert_eq!(normpath_largo(&entrada), esperado);
    }

    #[test]
    fn linha_do_explorer() {
        assert_eq!(linha_explorer(r"C:\a b\c.mp4"), r#"/select,"C:\a b\c.mp4""#);
        assert_eq!(linha_explorer(r"C:\vídeo, ção\x.mkv"), r#"/select,"C:\vídeo, ção\x.mkv""#);
        assert_eq!(linha_explorer(r"\\servidor\pasta\f.jpg"), r#"/select,"\\servidor\pasta\f.jpg""#);
    }

    #[test]
    fn apartamento_ja_em_mta() {
        // linha já em MTA: RPC_E_CHANGED_MODE serve e não desfaz o que não é nosso
        std::thread::spawn(|| {
            use windows_sys::Win32::System::Com::COINIT_MULTITHREADED;
            let hr = unsafe { CoInitializeEx(null(), COINIT_MULTITHREADED as u32) };
            assert!(hr >= 0);
            let a = Apartamento::entrar().expect("RPC_E_CHANGED_MODE deve servir");
            assert!(!a.equilibrar);
            drop(a);
            unsafe { CoUninitialize() };
        })
        .join()
        .unwrap();
    }

    #[test]
    fn apartamento_sta_equilibra() {
        std::thread::spawn(|| {
            let a = Apartamento::entrar().expect("CoInitializeEx");
            assert!(a.equilibrar);
            let b = Apartamento::entrar().expect("S_FALSE deve servir");
            assert!(b.equilibrar);
        })
        .join()
        .unwrap();
    }

    /// Cria o diálogo sem mostrar (não abre janela) e usa os métodos pela vtable: prova os lugares
    /// de GetOptions, SetOptions, SetTitle, SetFolder e Release.
    #[test]
    fn dialogo_opcoes_sem_mostrar() {
        let _com = Apartamento::entrar().expect("CoInitializeEx");
        let dialogo = criar_dialogo().expect("CoCreateInstance(FileOpenDialog)");
        let mut antes = 0u32;
        assert_eq!(unsafe { (dialogo.vt().get_options)(dialogo.cru(), &mut antes) }, S_OK);
        assert_eq!(antes & FOS_PICKFOLDERS, 0, "opções padrão: {antes:#x}");
        assert_ne!(antes, 0, "o padrão do FileOpenDialog tem FOS_PATHMUSTEXIST e outras");
        assert_eq!(unsafe { (dialogo.vt().set_options)(dialogo.cru(), antes | FOS_PICKFOLDERS) }, S_OK);
        let mut depois = 0u32;
        assert_eq!(unsafe { (dialogo.vt().get_options)(dialogo.cru(), &mut depois) }, S_OK);
        assert_eq!(depois, antes | FOS_PICKFOLDERS);

        assert!(acrescentar_opcoes(&dialogo, FOS_FORCEFILESYSTEM));
        let mut terceira = 0u32;
        assert_eq!(unsafe { (dialogo.vt().get_options)(dialogo.cru(), &mut terceira) }, S_OK);
        assert_eq!(terceira, antes | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM);

        let titulo = com_nul("Escolher pasta".encode_utf16());
        assert_eq!(unsafe { (dialogo.vt().set_title)(dialogo.cru(), titulo.as_ptr()) }, S_OK);
        let pasta = item_de_caminho(Path::new(r"C:\Windows")).expect("item de C:\\Windows");
        assert_eq!(unsafe { (dialogo.vt().set_folder)(dialogo.cru(), pasta.cru()) }, S_OK);
        drop(pasta);
        drop(dialogo); // Release
    }

    /// `SHCreateItemFromParsingName` + `GetDisplayName(SIGDN_FILESYSPATH)`: prova a vtable do
    /// IShellItem. Também com barra normal e `..`, que o `normpath` acerta antes.
    #[test]
    fn item_ida_e_volta() {
        let _com = Apartamento::entrar().expect("CoInitializeEx");
        let item = item_de_caminho(Path::new(r"C:\Windows")).expect("item de C:\\Windows");
        let volta = caminho_do_item(&item).expect("GetDisplayName");
        assert!(volta.as_os_str().eq_ignore_ascii_case(r"C:\Windows"), "{volta:?}");

        let item = item_de_caminho(Path::new("C:/Windows/System32/..")).expect("item com / e ..");
        let volta = caminho_do_item(&item).expect("GetDisplayName");
        assert!(volta.as_os_str().eq_ignore_ascii_case(r"C:\Windows"), "{volta:?}");

        assert!(item_de_caminho(Path::new(r"C:\nao\existe\mesmo\ciranda-7f3a")).is_none());
    }

    /// Um IShellItemArray feito sem diálogo (`SHCreateShellItemArrayFromShellItem`): prova
    /// GetCount e GetItemAt.
    #[test]
    fn lista_de_itens() {
        use windows_sys::Win32::UI::Shell::SHCreateShellItemArrayFromShellItem;
        let _com = Apartamento::entrar().expect("CoInitializeEx");
        let item = item_de_caminho(Path::new(r"C:\Windows")).expect("item de C:\\Windows");
        let lista: Com<VtblLista> =
            obter(|saida| unsafe { SHCreateShellItemArrayFromShellItem(item.cru(), &IID_ISHELLITEMARRAY, saida) })
                .expect("SHCreateShellItemArrayFromShellItem");
        let mut quantos = 0u32;
        assert_eq!(unsafe { (lista.vt().get_count)(lista.cru(), &mut quantos) }, S_OK);
        assert_eq!(quantos, 1);
        let caminhos = caminhos_da_lista(&lista);
        assert_eq!(caminhos.len(), 1);
        assert!(caminhos[0].as_os_str().eq_ignore_ascii_case(r"C:\Windows"), "{caminhos:?}");
        let fora: Option<Com<VtblItem>> = obter(|saida| unsafe { (lista.vt().get_item_at)(lista.cru(), 5, saida) });
        assert!(fora.is_none());
    }

    /// Só o primeiro passo do `mostrar_no_explorer` (sem `SHOpenFolderAndSelectItems`, que abriria o
    /// Explorer): o PIDL sai do caminho normalizado e é liberado.
    #[test]
    fn pidl_do_caminho() {
        use windows_sys::Win32::UI::Shell::{ILCreateFromPathW, ILFree};
        let _com = Apartamento::entrar().expect("CoInitializeEx");
        let largo = com_nul(largo_de_caminho(Path::new("C:/Windows/./System32/../explorer.exe")));
        let pidl = unsafe { ILCreateFromPathW(largo.as_ptr()) };
        assert!(!pidl.is_null());
        unsafe { ILFree(pidl) };
        let nada = com_nul(largo_de_caminho(Path::new(r"C:\nao\existe\mesmo\ciranda-7f3a.mp4")));
        assert!(unsafe { ILCreateFromPathW(nada.as_ptr()) }.is_null());
    }
}
