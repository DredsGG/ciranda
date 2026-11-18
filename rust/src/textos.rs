//! Textos da interface em português, inglês e espanhol, porta da `textos.py` da 1.5.1 (regra 13).
//!
//! `t("chave")` devolve o texto no idioma atual; `tf("chave", &[("n", &3)])` também preenche os
//! campos `{nome}`, como o `t("chave", n=3)` da 1.5.1 (`str.format(**kw)`). A tabela
//! (`textos_tabela.rs`) sai do próprio `textos.py` da 1.5.1 por `ferramentas/gerar_textos.py`:
//! texto novo entra lá, já nos três idiomas, e a tabela é gerada de novo.
//! Idioma: o escolhido no seletor PT · EN · ES (config "idioma"); se nunca escolheu, o do Windows
//! (pt-*, es-*; qualquer outro vira inglês).
//!
//! Onde a porta difere da 1.5.1, de propósito:
//! - chave desconhecida devolve a própria chave (a 1.5.1 levanta `KeyError`); em debug, `debug_assert!`;
//! - campo sem valor (ou `{`/`}` sozinho) fica no texto como está (a 1.5.1 levanta `KeyError` ou
//!   `ValueError`); em debug, `debug_assert!`;
//! - `idioma_do_sistema` não tem o passo do Qt (`QLocale.system().uiLanguages()`): depois do Windows
//!   vai direto para o `LANG`. No Windows o Qt só seria consultado se a API do Windows falhasse;
//! - `nome()` de idioma desconhecido dá "EN" (o `NOMES[idioma]` da 1.5.1 levanta `KeyError`).

use std::collections::HashMap;
use std::fmt::{Display, Write};
use std::sync::OnceLock;
use std::sync::atomic::{AtomicU8, Ordering};

#[path = "textos_tabela.rs"]
mod tabela;
use tabela::TABELA;

pub const IDIOMAS: [&str; 3] = ["pt", "en", "es"];
const NOMES: [&str; 3] = ["PT", "EN", "ES"];
/// Posição do inglês em `IDIOMAS`: o idioma de reserva e o texto de reserva (`trio[1]`).
const INGLES: usize = 1;

/// O `_atual` da 1.5.1: 0 = ainda não definido (o `""` de lá); 1..=3 = posição em `IDIOMAS` + 1.
static ATUAL: AtomicU8 = AtomicU8::new(0);

fn posicao(idioma: &str) -> Option<usize> {
    IDIOMAS.iter().position(|i| *i == idioma)
}

fn guardar(posicao: usize) -> u8 {
    posicao as u8 + 1
}

/// O rótulo do seletor: "PT", "EN" ou "ES".
pub fn nome(idioma: &str) -> &'static str {
    NOMES[posicao(idioma).unwrap_or(INGLES)]
}

/// O `str.isspace()` do Python: o `White_Space` do Unicode (o `char::is_whitespace`) mais os
/// separadores de arquivo, grupo, registro e unidade (U+001C a U+001F).
fn espaco_py(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// pt-BR → pt, es-419 → es, en-US → en; qualquer outro → en (como o `normalizar` da 1.5.1).
pub fn normalizar(codigo: &str) -> &'static str {
    let c = codigo.trim_matches(espaco_py).to_lowercase().replace('_', "-");
    for i in IDIOMAS {
        if c == i || c.strip_prefix(i).is_some_and(|resto| resto.starts_with('-')) {
            return i;
        }
    }
    "en"
}

/// Idioma da interface do Windows (`GetUserPreferredUILanguages`), já normalizado.
/// `CIRANDA_IDIOMA_SISTEMA` (testes: simula o sistema em outro idioma) vem antes de tudo; se o
/// Windows não responder, vale o `LANG` (sem o que vem depois do ponto) e, sem ele, inglês.
pub fn idioma_do_sistema() -> &'static str {
    if let Some(forcado) = std::env::var_os("CIRANDA_IDIOMA_SISTEMA").filter(|f| !f.is_empty()) {
        return normalizar(&forcado.to_string_lossy());
    }
    if let Some(primeiro) = primeiro_idioma_do_windows() {
        return normalizar(&primeiro);
    }
    // A 1.5.1 tenta o QLocale do Qt aqui; sem Qt, vai direto para o LANG.
    let lang = std::env::var_os("LANG").map_or_else(|| "en".to_string(), |l| l.to_string_lossy().into_owned());
    normalizar(lang.split('.').next().unwrap_or_default())
}

/// O primeiro da lista de idiomas de interface preferidos do usuário (ex.: "pt-BR").
#[cfg(windows)]
fn primeiro_idioma_do_windows() -> Option<String> {
    use windows_sys::Win32::Globalization::{GetUserPreferredUILanguages, MUI_LANGUAGE_NAME};
    let (mut quantos, mut tamanho) = (0u32, 0u32);
    // SAFETY: os ponteiros são de variáveis locais; o buffer nulo só pede o tamanho.
    let nulo = std::ptr::null_mut();
    if unsafe { GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, &mut quantos, nulo, &mut tamanho) } == 0 {
        return None;
    }
    let mut buf = vec![0u16; tamanho as usize];
    // SAFETY: `buf` tem os `tamanho` u16 que a primeira chamada pediu.
    if unsafe { GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, &mut quantos, buf.as_mut_ptr(), &mut tamanho) } == 0 {
        return None;
    }
    // Lista de nomes separados por \0 (e terminada por \0\0): vale o primeiro.
    let usado = &buf[..(tamanho as usize).min(buf.len())];
    let primeiro = usado.split(|&u| u == 0).next().unwrap_or_default();
    (!primeiro.is_empty()).then(|| String::from_utf16_lossy(primeiro))
}

#[cfg(not(windows))]
fn primeiro_idioma_do_windows() -> Option<String> {
    None
}

/// Troca o idioma dos textos. Fora de `IDIOMAS` (inclusive "PT" ou "pt-BR"), inglês.
pub fn definir(idioma: &str) {
    ATUAL.store(guardar(posicao(idioma).unwrap_or(INGLES)), Ordering::Relaxed);
}

/// O idioma dos textos agora; se ninguém definiu ainda, o do sistema (e ele fica valendo).
pub fn atual() -> &'static str {
    let mut v = ATUAL.load(Ordering::Relaxed);
    if v == 0 {
        let do_sistema = guardar(posicao(idioma_do_sistema()).unwrap_or(INGLES));
        // Se outra thread definiu o idioma enquanto isso, vale o dela.
        v = match ATUAL.compare_exchange(0, do_sistema, Ordering::Relaxed, Ordering::Relaxed) {
            Ok(_) => do_sistema,
            Err(outro) => outro,
        };
    }
    IDIOMAS[v as usize - 1]
}

/// Escolhe o idioma ao abrir: o salvo no seletor (config "idioma"), se for um de `IDIOMAS`;
/// senão, o do sistema.
pub fn iniciar(idioma_salvo: Option<&str>) -> &'static str {
    let escolhido = match idioma_salvo.and_then(posicao) {
        Some(p) => IDIOMAS[p],
        None => idioma_do_sistema(),
    };
    definir(escolhido);
    escolhido
}

fn indice() -> &'static HashMap<&'static str, usize> {
    static INDICE: OnceLock<HashMap<&'static str, usize>> = OnceLock::new();
    INDICE.get_or_init(|| TABELA.iter().enumerate().map(|(i, (chave, _))| (*chave, i)).collect())
}

/// A chave existe na tabela.
pub fn tem(chave: &str) -> bool {
    indice().contains_key(chave)
}

/// Todas as chaves, na ordem da tabela `T` da 1.5.1.
pub fn chaves() -> impl Iterator<Item = &'static str> {
    TABELA.iter().map(|(chave, _)| *chave)
}

/// O texto de um trio (português, inglês, espanhol) para o idioma: o `trio[idx] or trio[1]` da
/// 1.5.1 (tradução vazia cai no inglês). Idioma fora de `IDIOMAS` conta como inglês.
pub fn escolher<'a>(trio: &[&'a str; 3], idioma: &str) -> &'a str {
    match trio[posicao(idioma).unwrap_or(INGLES)] {
        "" => trio[INGLES],
        txt => txt,
    }
}

/// O texto da chave no idioma atual, sem preencher nada (como o `t("chave")` da 1.5.1, que
/// também deixa um `{n}` ou `{{` do modelo como está).
pub fn t(chave: &str) -> String {
    tf(chave, &[])
}

/// O texto da chave no idioma atual com os campos preenchidos: `tf("n_de_total", &[("n", &3),
/// ("total", &10)])` é o `t("n_de_total", n=3, total=10)` da 1.5.1. Sem nenhum valor, devolve o
/// modelo cru (o `if kw` de lá); valor que o modelo não usa é ignorado.
pub fn tf(chave: &str, args: &[(&str, &dyn Display)]) -> String {
    let Some(&i) = indice().get(chave) else {
        debug_assert!(false, "chave de texto desconhecida: {chave:?}");
        return chave.to_string();
    };
    let txt = escolher(&TABELA[i].1, atual());
    if args.is_empty() { txt.to_string() } else { formatar(txt, args) }
}

/// O `modelo.format(**args)` do Python para o que a tabela usa: campos `{nome}` (o valor sai pelo
/// `Display`, que para texto e inteiro é o `str()` do Python), `{{` → `{` e `}}` → `}`.
/// O gerador da tabela confere que nenhum modelo usa mais que isso (`{0}`, `{x:>5}`, `{x!r}`...).
pub fn formatar(modelo: &str, args: &[(&str, &dyn Display)]) -> String {
    let mut saida = String::with_capacity(modelo.len() + 16);
    let mut resto = modelo;
    while let Some(p) = resto.find(['{', '}']) {
        saida.push_str(&resto[..p]);
        let chave = if resto.as_bytes()[p] == b'{' { '{' } else { '}' };
        let depois = &resto[p + 1..];
        if let Some(apos) = depois.strip_prefix(chave) {
            saida.push(chave);
            resto = apos;
            continue;
        }
        if chave == '{'
            && let Some(fim) = depois.find('}')
        {
            let campo = &depois[..fim];
            if !campo.contains('{')
                && let Some((_, valor)) = args.iter().find(|(nome, _)| *nome == campo)
            {
                let _ = write!(saida, "{valor}");
                resto = &depois[fim + 1..];
                continue;
            }
        }
        // Campo sem valor ou chave sozinha: a 1.5.1 levantaria erro; aqui o texto fica como está.
        debug_assert!(false, "modelo de texto que a 1.5.1 não formataria: {modelo:?}");
        saida.push(chave);
        resto = depois;
    }
    saida.push_str(resto);
    saida
}

#[cfg(test)]
mod testes {
    use super::*;

    /// Este é o único teste da biblioteca que mexe no idioma global: antes de qualquer
    /// `definir`, o idioma é o do sistema, e ele fica guardado.
    #[test]
    fn sem_definir_vale_o_do_sistema() {
        assert_eq!(ATUAL.load(Ordering::Relaxed), 0);
        let sistema = idioma_do_sistema();
        assert_eq!(atual(), sistema);
        assert_eq!(ATUAL.load(Ordering::Relaxed), guardar(posicao(sistema).unwrap()));
        definir("es");
        assert_eq!(atual(), "es");
        definir("PT");
        assert_eq!(atual(), "en");
    }

    #[test]
    fn tabela_sem_chave_repetida() {
        assert_eq!(indice().len(), TABELA.len());
    }
}
