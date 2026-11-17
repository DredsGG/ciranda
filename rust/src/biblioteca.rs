//! Varredura de pastas, porta da `biblioteca.py` da 1.5.1: acha todas as fotos e vídeos de uma
//! pasta e de todas as subpastas, em qualquer profundidade, numa lista achatada.
//!
//! Ordem natural (foto2 < foto10): em cada pasta, primeiro os arquivos dela, depois cada
//! subpasta em ordem de nome. Sem recursão (pilha própria): aguenta qualquer profundidade.
//!
//! Cada pasta é lida com `FindFirstFileExW`, como o `os.scandir` do Python. Assim a varredura vê o
//! mesmo que a 1.5.1: o atributo de pasta, a marca de link simbólico (segue o destino) e a de
//! junção (a 1.5.1 trata como pasta e confere o destino real para não entrar em laço).

use std::path::{Path, PathBuf};

use indexmap::IndexMap;

use crate::ordem::{Parte, chave_natural};

pub const FOTOS: &[&str] = &[
    ".jpg", ".jpeg", ".jfif", ".jpe", ".png", ".gif", ".webp", ".bmp", ".dib", ".tif", ".tiff", ".heic", ".heif",
    ".avif", ".jxl", ".tga", ".ico", ".apng", ".mpo",
];
pub const VIDEOS: &[&str] = &[
    ".mp4", ".m4v", ".mov", ".qt", ".mkv", ".webm", ".avi", ".wmv", ".asf", ".flv", ".f4v", ".mpg", ".mpeg", ".mpe",
    ".m2v", ".ts", ".mts", ".m2ts", ".vob", ".3gp", ".3g2", ".ogv", ".divx", ".xvid", ".rm", ".rmvb", ".mxf", ".dv",
    ".y4m", ".hevc", ".h264", ".264", ".265", ".mod", ".tod", ".mp4v", ".ogm", ".wtv", ".dvr-ms", ".m2t", ".trp",
    ".nsv", ".amv",
];
/// Pastas de sistema e de lixeira que nunca têm mídia do usuário (comparadas sem maiúsculas).
pub const PASTAS_IGNORADAS: &[&str] = &[
    "$recycle.bin",
    "system volume information",
    "recycler",
    "$windows.~bt",
    "$windows.~ws",
    "windows.old",
    "__pycache__",
    "node_modules",
    ".git",
    ".thumbnails",
    ".trash",
    ".trashes",
    ".spotlight-v100",
    ".fseventsd",
];
/// Tratadas como foto, mas animando em loop.
pub const FOTOS_ANIMADAS: &[&str] = &[".gif"];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tipo {
    Foto,
    Video,
}

impl Tipo {
    pub fn nome(self) -> &'static str {
        match self {
            Tipo::Foto => "foto",
            Tipo::Video => "video",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Item {
    /// Caminho absoluto do arquivo.
    pub caminho: PathBuf,
    pub tipo: Tipo,
    /// Pasta que a pessoa abriu.
    pub raiz: PathBuf,
    /// Subpasta relativa à raiz ("" = a própria raiz).
    pub pasta_rel: String,
    pub nome: String,
    /// Extensão em minúsculas, com o ponto (".jpg").
    pub ext: String,
    /// O motor não conseguiu abrir.
    pub falhou: bool,
}

impl Item {
    pub fn animada(&self) -> bool {
        FOTOS_ANIMADAS.contains(&self.ext.as_str())
    }
}

/// O que foi lido e o que ficou de fora, para o log (o `stats` da 1.5.1).
#[derive(Debug, Default, Clone)]
pub struct Estatisticas {
    pub pastas_lidas: usize,
    /// Extensão → quantos arquivos que não são foto nem vídeo, na ordem em que apareceram.
    pub ignorados: IndexMap<String, usize>,
    pub sem_acesso: Vec<String>,
    pub puladas: Vec<String>,
}

impl Estatisticas {
    fn ignorar(&mut self, nome: &str) {
        let e = extensao(nome);
        let e = if e.is_empty() { "(sem extensão)".to_string() } else { e };
        *self.ignorados.entry(e).or_insert(0) += 1;
    }

    pub fn total_ignorados(&self) -> usize {
        self.ignorados.values().sum()
    }

    /// `Counter.most_common(n)`: mais frequentes primeiro; empate fica na ordem em que apareceu.
    pub fn mais_comuns(&self, n: usize) -> Vec<(&str, usize)> {
        let mut v: Vec<(&str, usize)> = self.ignorados.iter().map(|(k, v)| (k.as_str(), *v)).collect();
        v.sort_by(|a, b| b.1.cmp(&a.1)); // estável
        v.truncate(n);
        v
    }
}

/// `os.path.splitext(nome)[1].lower()`: a extensão só existe se antes do último ponto houver algo
/// que não seja ponto (".jpg" e "..jpg" não têm extensão).
pub fn extensao(nome: &str) -> String {
    let Some(i) = nome.rfind('.') else { return String::new() };
    if nome[..i].chars().all(|c| c == '.') {
        return String::new();
    }
    nome[i..].to_lowercase()
}

pub fn tipo_do_arquivo(nome: &str) -> Option<Tipo> {
    let e = extensao(nome);
    if FOTOS.contains(&e.as_str()) {
        Some(Tipo::Foto)
    } else if VIDEOS.contains(&e.as_str()) {
        Some(Tipo::Video)
    } else {
        None
    }
}

/// `os.path.normcase` do Python 3.12 no Windows: barra invertida e
/// `LCMapStringEx(LOCALE_NAME_INVARIANT, LCMAP_LOWERCASE)`, a mesma tabela do NTFS. Não é o
/// `to_lowercase` do Unicode: K (Kelvin), Ω (ohm), ẞ e İ ficam como estão, e não há sigma final.
pub fn normcase(p: &Path) -> String {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Globalization::{LCMAP_LOWERCASE, LCMapStringEx};
    let fonte: Vec<u16> = p.as_os_str().encode_wide().map(|c| if c == u16::from(b'/') { u16::from(b'\\') } else { c }).collect();
    if fonte.is_empty() {
        return String::new();
    }
    let invariante = [0u16]; // LOCALE_NAME_INVARIANT = ""
    let chamar = |destino: *mut u16, tamanho: i32| unsafe {
        LCMapStringEx(
            invariante.as_ptr(),
            LCMAP_LOWERCASE,
            fonte.as_ptr(),
            fonte.len() as i32,
            destino,
            tamanho,
            std::ptr::null(),
            std::ptr::null(),
            0,
        )
    };
    let n = chamar(std::ptr::null_mut(), 0);
    if n <= 0 {
        return String::from_utf16_lossy(&fonte).to_lowercase(); // não acontece com texto válido
    }
    let mut destino = vec![0u16; n as usize];
    let n = chamar(destino.as_mut_ptr(), n);
    destino.truncate(n.max(0) as usize);
    String::from_utf16_lossy(&destino)
}

/// `os.path.abspath` do Python 3.12: o `GetFullPathNameW` (que o `std::path::absolute` chama) e sem
/// a barra do fim, menos na raiz (`C:\`, `\\servidor\pasta\`). `.\Fotos\` vira `C:\...\Fotos`,
/// como na 1.5.1 (o autocompletar do terminal põe a barra).
pub fn absoluto(p: &Path) -> PathBuf {
    let a = std::path::absolute(p).unwrap_or_else(|_| p.to_path_buf());
    let s = a.as_os_str().to_string_lossy();
    if (s.ends_with('\\') || s.ends_with('/')) && a.parent().is_some() {
        if let Some(t) = a.to_str() {
            return PathBuf::from(t.trim_end_matches(['\\', '/']));
        }
    }
    a
}

/// Tira o `\\?\` que o Windows devolve (o `realpath` do Python também tira).
fn sem_prefixo(p: &Path) -> PathBuf {
    let s = p.to_string_lossy();
    if let Some(resto) = s.strip_prefix(r"\\?\UNC\") {
        PathBuf::from(format!(r"\\{resto}"))
    } else if let Some(resto) = s.strip_prefix(r"\\?\") {
        PathBuf::from(resto)
    } else {
        p.to_path_buf()
    }
}

fn juntar(p: &Path, cauda: &Path) -> PathBuf {
    if cauda.as_os_str().is_empty() { p.to_path_buf() } else { p.join(cauda) }
}

/// `_readlink_deep` do Python 3.12: segue link sobre link (sem laço) e devolve o último destino,
/// ou `None` se `p` não é link.
fn ler_link_fundo(p: &Path) -> Option<PathBuf> {
    let mut vistos = std::collections::HashSet::new();
    let mut atual = p.to_path_buf();
    let mut mudou = false;
    while vistos.insert(normcase(&atual)) {
        match std::fs::read_link(&atual) {
            Ok(alvo) => {
                atual = if alvo.is_absolute() {
                    alvo
                } else {
                    absoluto(&atual.parent().unwrap_or(Path::new("")).join(alvo))
                };
                mudou = true;
            }
            Err(_) => break,
        }
    }
    mudou.then_some(atual)
}

/// `os.path.normcase(os.path.realpath(p))` do Python 3.12 (não estrito): o destino real; se ele
/// não abre (junção quebrada), segue o link à mão; se nem isso, sobe pastas até achar uma que
/// abra e junta o resto. Duas junções quebradas para o mesmo lugar dão a mesma chave.
pub fn destino_real(p: &Path) -> String {
    let mut caminho = absoluto(p);
    let mut cauda = PathBuf::new();
    loop {
        if let Ok(r) = std::fs::canonicalize(&caminho) {
            return normcase(&juntar(&sem_prefixo(&r), &cauda));
        }
        if let Some(alvo) = ler_link_fundo(&caminho) {
            if alvo != caminho {
                return normcase(&juntar(&sem_prefixo(&alvo), &cauda));
            }
        }
        match (caminho.parent(), caminho.file_name()) {
            (Some(pai), Some(nome)) => {
                cauda = juntar(Path::new(nome), &cauda);
                caminho = pai.to_path_buf();
            }
            _ => return normcase(&juntar(&caminho, &cauda)),
        }
    }
}

// ---------- leitura de uma pasta (Windows) ----------

const FILE_ATTRIBUTE_DIRECTORY: u32 = 0x10;
const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
const IO_REPARSE_TAG_SYMLINK: u32 = 0xA000_000C;
const IO_REPARSE_TAG_MOUNT_POINT: u32 = 0xA000_0003;

struct Entrada {
    nome: String,
    caminho: PathBuf,
    atributos: u32,
    marca: u32,
}

impl Entrada {
    fn eh_symlink(&self) -> bool {
        self.atributos & FILE_ATTRIBUTE_REPARSE_POINT != 0 && self.marca == IO_REPARSE_TAG_SYMLINK
    }
    fn eh_juncao(&self) -> bool {
        self.atributos & FILE_ATTRIBUTE_REPARSE_POINT != 0 && self.marca == IO_REPARSE_TAG_MOUNT_POINT
    }
}

/// Nome da classe de erro que o Python 3.12 daria a um erro do Windows (winerror → errno do
/// `PC/errmap.h` → subclasse do OSError). Tabela tirada do próprio Python:
/// `type(OSError(0, "", None, w)).__name__` para w de 0 a 19999. Vai na linha "sem acesso".
pub fn classe_do_erro(codigo: u32) -> &'static str {
    match codigo {
        2 | 3 | 15 | 18 | 53 | 67 | 161 | 206 => "FileNotFoundError",
        5 | 16 | 19..=36 | 65 | 82 | 83 | 108 | 132 | 158 | 167 | 10013 => "PermissionError",
        80 | 183 => "FileExistsError",
        89 | 164 | 215 | 10035..=10037 => "BlockingIOError",
        109 | 232 | 10058 => "BrokenPipeError",
        128 | 129 => "ChildProcessError",
        267 => "NotADirectoryError",
        10004 => "InterruptedError",
        10053 => "ConnectionAbortedError",
        10054 => "ConnectionResetError",
        10060 => "TimeoutError",
        10061 => "ConnectionRefusedError",
        _ => "OSError",
    }
}

/// Caminho para a API do Windows: longo demais ganha o prefixo `\\?\` (a 1.5.1 depende do
/// LongPathsEnabled do sistema; aqui funciona com ou sem ele).
fn para_api(p: &Path) -> Vec<u16> {
    use std::os::windows::ffi::OsStrExt;
    let s = p.as_os_str();
    let mut v: Vec<u16> = Vec::new();
    let longo = s.len() > 240 && !s.to_string_lossy().starts_with(r"\\?\");
    if longo {
        let t = s.to_string_lossy();
        if let Some(resto) = t.strip_prefix(r"\\") {
            v.extend(r"\\?\UNC\".encode_utf16());
            v.extend(resto.encode_utf16());
        } else {
            v.extend(r"\\?\".encode_utf16());
            v.extend(s.encode_wide());
        }
    } else {
        v.extend(s.encode_wide());
    }
    if !matches!(v.last(), Some(&0x5C) | Some(&0x2F)) {
        v.push(0x5C);
    }
    v.push(b'*' as u16);
    v.push(0);
    v
}

/// Lista uma pasta. Erro em qualquer ponto (abrir ou continuar) perde a pasta inteira, como o
/// `list(os.scandir(pasta))` da 1.5.1.
fn ler_pasta(pasta: &Path) -> Result<Vec<Entrada>, u32> {
    use std::os::windows::ffi::OsStringExt;
    use windows_sys::Win32::Foundation::{GetLastError, INVALID_HANDLE_VALUE};
    use windows_sys::Win32::Storage::FileSystem::{
        FIND_FIRST_EX_LARGE_FETCH, FindClose, FindExInfoBasic, FindExSearchNameMatch, FindFirstFileExW,
        FindNextFileW, WIN32_FIND_DATAW,
    };
    const ERROR_NO_MORE_FILES: u32 = 18;

    let busca = para_api(pasta);
    let mut dados: WIN32_FIND_DATAW = unsafe { std::mem::zeroed() };
    let h = unsafe {
        FindFirstFileExW(
            busca.as_ptr(),
            FindExInfoBasic,
            &mut dados as *mut _ as *mut _,
            FindExSearchNameMatch,
            std::ptr::null(),
            FIND_FIRST_EX_LARGE_FETCH,
        )
    };
    if h == INVALID_HANDLE_VALUE {
        return Err(unsafe { GetLastError() });
    }
    let mut v = Vec::new();
    loop {
        let fim = dados.cFileName.iter().position(|&c| c == 0).unwrap_or(dados.cFileName.len());
        let largo = &dados.cFileName[..fim];
        if largo != [0x2E] && largo != [0x2E, 0x2E] {
            let os = std::ffi::OsString::from_wide(largo);
            v.push(Entrada {
                nome: os.to_string_lossy().into_owned(),
                caminho: pasta.join(&os),
                atributos: dados.dwFileAttributes,
                marca: dados.dwReserved0,
            });
        }
        if unsafe { FindNextFileW(h, &mut dados) } == 0 {
            let e = unsafe { GetLastError() };
            unsafe { FindClose(h) };
            return if e == ERROR_NO_MORE_FILES { Ok(v) } else { Err(e) };
        }
    }
}

/// O que a entrada é, seguindo link simbólico (o `is_dir`/`is_file(follow_symlinks=True)`).
enum Genero {
    Pasta,
    Arquivo,
    /// Link quebrado: nem pasta nem arquivo (a 1.5.1 deixa de fora sem contar).
    Nenhum,
    /// Erro ao seguir o link (vai para "sem acesso").
    Erro,
}

fn genero(e: &Entrada) -> Genero {
    if e.eh_symlink() {
        return match std::fs::metadata(&e.caminho) {
            Ok(m) if m.is_dir() => Genero::Pasta,
            Ok(m) if m.is_file() => Genero::Arquivo,
            Ok(_) => Genero::Nenhum,
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => Genero::Nenhum,
            Err(_) => Genero::Erro,
        };
    }
    if e.atributos & FILE_ATTRIBUTE_DIRECTORY != 0 { Genero::Pasta } else { Genero::Arquivo }
}

/// Índices de `itens` em ordem natural pelo nome; empate fica na ordem lida (o `sorted` é estável).
pub fn em_ordem<T>(itens: &[T], nome: impl Fn(&T) -> &str, decrescente: bool) -> Vec<usize> {
    let mut chaves: Vec<(Vec<Parte>, usize)> = itens.iter().enumerate().map(|(i, x)| (chave_natural(nome(x)), i)).collect();
    if decrescente {
        // `sorted(reverse=True)` também é estável: empate continua na ordem lida.
        chaves.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    } else {
        chaves.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    }
    chaves.into_iter().map(|(_, i)| i).collect()
}

/// Varre `raiz` em qualquer profundidade. `cancelado()` interrompe; `progresso(n, pasta)` vem a
/// cada 200 achados e no fim; `stats` recebe o que foi lido e o que ficou de fora.
pub fn varrer(
    raiz: &Path,
    cancelado: &dyn Fn() -> bool,
    progresso: &mut dyn FnMut(usize, &str),
    stats: &mut Estatisticas,
) -> Vec<Item> {
    let raiz = absoluto(raiz);
    if raiz.is_file() {
        let nome = raiz.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        let Some(tipo) = tipo_do_arquivo(&nome) else {
            stats.ignorar(&nome);
            return Vec::new();
        };
        let pai = raiz.parent().map(Path::to_path_buf).unwrap_or_default();
        let ext = extensao(&nome);
        return vec![Item { caminho: raiz, tipo, raiz: pai, pasta_rel: String::new(), nome, ext, falhou: false }];
    }

    let mut achados: Vec<Item> = Vec::new();
    // Só atalhos/junções podem fazer laço; pasta comum nunca. Guarda o destino real deles.
    let mut links_vistos: std::collections::HashSet<String> = [destino_real(&raiz)].into_iter().collect();
    let mut ultimo_aviso = 0usize;
    let mut pilha: Vec<PathBuf> = vec![raiz.clone()];

    while let Some(pasta) = pilha.pop() {
        if cancelado() {
            break;
        }
        let entradas = match ler_pasta(&pasta) {
            Ok(v) => v,
            Err(codigo) => {
                stats.sem_acesso.push(format!("{} ({})", pasta.display(), classe_do_erro(codigo)));
                continue;
            }
        };
        stats.pastas_lidas += 1;

        let mut arquivos: Vec<(Entrada, Tipo)> = Vec::new();
        let mut subpastas: Vec<Entrada> = Vec::new();
        for e in entradas {
            match genero(&e) {
                Genero::Pasta => {
                    if PASTAS_IGNORADAS.contains(&crate::ordem::dobrar(&e.nome).as_str()) {
                        stats.puladas.push(e.caminho.display().to_string());
                        continue;
                    }
                    if e.eh_symlink() || e.eh_juncao() {
                        let destino = destino_real(&e.caminho);
                        if links_vistos.contains(&destino) {
                            stats.puladas.push(format!("{} (atalho repetido)", e.caminho.display()));
                            continue;
                        }
                        links_vistos.insert(destino);
                    }
                    subpastas.push(e);
                }
                Genero::Arquivo => match tipo_do_arquivo(&e.nome) {
                    Some(t) if !e.nome.starts_with("._") => arquivos.push((e, t)),
                    _ => stats.ignorar(&e.nome),
                },
                // Nem pasta nem arquivo (link quebrado): a 1.5.1 deixa de fora sem contar.
                Genero::Nenhum => {}
                Genero::Erro => stats.sem_acesso.push(e.caminho.display().to_string()),
            }
        }

        let rel = pasta.strip_prefix(&raiz).map(|r| r.display().to_string()).unwrap_or_default();
        let ordem = em_ordem(&arquivos, |x| x.0.nome.as_str(), false);
        let mut arquivos: Vec<Option<(Entrada, Tipo)>> = arquivos.into_iter().map(Some).collect();
        for i in ordem {
            let (e, tipo) = arquivos[i].take().expect("cada índice uma vez");
            let ext = extensao(&e.nome);
            achados.push(Item { caminho: e.caminho, tipo, raiz: raiz.clone(), pasta_rel: rel.clone(), nome: e.nome, ext, falhou: false });
        }
        if achados.len() - ultimo_aviso >= 200 {
            ultimo_aviso = achados.len();
            progresso(achados.len(), &rel);
        }
        // Pilha: empilha ao contrário para sair na ordem natural (A antes de B).
        for i in em_ordem(&subpastas, |x| x.nome.as_str(), true) {
            pilha.push(std::mem::take(&mut subpastas[i].caminho));
        }
    }
    progresso(achados.len(), "");
    achados
}

/// Varre várias pastas/arquivos e junta tudo, sem repetir o mesmo arquivo.
pub fn varrer_varios(
    caminhos: &[PathBuf],
    cancelado: &dyn Fn() -> bool,
    progresso: &mut dyn FnMut(usize, &str),
    stats: &mut Estatisticas,
) -> Vec<Item> {
    let mut vistos = std::collections::HashSet::new();
    let mut total: Vec<Item> = Vec::new();
    for c in caminhos {
        if cancelado() {
            break;
        }
        let base = total.len();
        let itens = varrer(c, cancelado, &mut |n, p| progresso(base + n, p), stats);
        for item in itens {
            if vistos.insert(normcase(&item.caminho)) {
                total.push(item);
            }
        }
    }
    total
}

/// Atalhos sem callback (testes e ferramentas).
pub fn varrer_simples(raiz: &Path) -> Vec<Item> {
    varrer(raiz, &|| false, &mut |_, _| {}, &mut Estatisticas::default())
}

pub fn varrer_varios_simples(caminhos: &[PathBuf], stats: &mut Estatisticas) -> Vec<Item> {
    varrer_varios(caminhos, &|| false, &mut |_, _| {}, stats)
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn extensao_como_splitext() {
        assert_eq!(extensao("a.JPG"), ".jpg");
        assert_eq!(extensao(".jpg"), "");
        assert_eq!(extensao("..jpg"), "");
        assert_eq!(extensao("a..jpg"), ".jpg");
        assert_eq!(extensao("semext"), "");
        assert_eq!(extensao("a.tar.gz"), ".gz");
        assert_eq!(extensao("arquivo."), ".");
    }
}
