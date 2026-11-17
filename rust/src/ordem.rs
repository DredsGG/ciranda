//! Ordem "natural" (foto2 < foto10), igual à `chave_natural` da 1.5.1:
//! `[(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"(\d+)", texto.casefold())]`.
//!
//! O `casefold` e o `\d` vêm das tabelas do Python 3.12 (`unicode_py.rs`), então a ordem é a mesma
//! até para ß, letras gregas e dígitos de outros alfabetos.

use std::cmp::Ordering;

use crate::unicode_py::{DIGITOS, DOBRA};

/// `str.casefold()` do Python.
pub fn dobrar(texto: &str) -> String {
    let mut s = String::with_capacity(texto.len());
    for c in texto.chars() {
        if c.is_ascii() {
            s.push(c.to_ascii_lowercase());
        } else {
            match DOBRA.binary_search_by_key(&(c as u32), |&(cp, _)| cp) {
                Ok(i) => s.push_str(DOBRA[i].1),
                Err(_) => s.push(c),
            }
        }
    }
    s
}

/// Valor de um caractere que o `\d` do Python aceita (`None` se não aceita).
pub fn digito(c: char) -> Option<u32> {
    let cp = c as u32;
    if c.is_ascii_digit() {
        return Some(cp - '0' as u32);
    }
    if cp < 0x80 {
        return None;
    }
    let i = DIGITOS.partition_point(|&(a, _)| a <= cp);
    let (a, b) = *DIGITOS.get(i.checked_sub(1)?)?;
    (cp <= b).then(|| cp - a)
}

/// Um pedaço da chave. Número vem antes de texto na mesma posição (o 0 e o 1 da tupla do Python).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Parte {
    /// Algarismos ASCII do valor, sem zeros à esquerda ("" é o zero): compara pelo valor, de
    /// qualquer tamanho, como o `int` do Python.
    Num(String),
    Texto(String),
}

impl Ord for Parte {
    fn cmp(&self, o: &Self) -> Ordering {
        match (self, o) {
            (Parte::Num(a), Parte::Num(b)) => a.len().cmp(&b.len()).then_with(|| a.cmp(b)),
            (Parte::Num(_), Parte::Texto(_)) => Ordering::Less,
            (Parte::Texto(_), Parte::Num(_)) => Ordering::Greater,
            // String compara byte a byte em UTF-8, que é a mesma ordem dos códigos (como o Python).
            (Parte::Texto(a), Parte::Texto(b)) => a.cmp(b),
        }
    }
}
impl PartialOrd for Parte {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}

/// Chave da ordem natural. Como o `re.split` com grupo, começa e termina com texto (às vezes
/// vazio) e alterna texto e número.
pub fn chave_natural(texto: &str) -> Vec<Parte> {
    let dobrado = dobrar(texto);
    let mut partes = Vec::new();
    let mut txt = String::new();
    let mut num = String::new();
    let mut em_numero = false;
    for c in dobrado.chars() {
        match digito(c) {
            Some(v) => {
                if !em_numero {
                    partes.push(Parte::Texto(std::mem::take(&mut txt)));
                    em_numero = true;
                }
                if !(num.is_empty() && v == 0) {
                    num.push(char::from_digit(v, 10).unwrap_or('0'));
                }
            }
            None => {
                if em_numero {
                    partes.push(Parte::Num(std::mem::take(&mut num)));
                    em_numero = false;
                }
                txt.push(c);
            }
        }
    }
    if em_numero {
        partes.push(Parte::Num(num));
    }
    partes.push(Parte::Texto(txt));
    partes
}

/// Compara dois nomes na ordem natural.
pub fn comparar(a: &str, b: &str) -> Ordering {
    chave_natural(a).cmp(&chave_natural(b))
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn chave_igual_ao_python() {
        // re.split(r"(\d+)", "10a") == ['', '10', 'a']
        assert_eq!(
            chave_natural("10a"),
            vec![Parte::Texto("".into()), Parte::Num("10".into()), Parte::Texto("a".into())]
        );
        assert_eq!(chave_natural("a"), vec![Parte::Texto("a".into())]);
        assert_eq!(chave_natural("007"), vec![Parte::Texto("".into()), Parte::Num("7".into()), Parte::Texto("".into())]);
        assert_eq!(dobrar("Straße ΣΑΣ"), "strasse σασ");
        assert_eq!(digito('٣'), Some(3)); // dígito árabe-índico
        assert_eq!(digito('²'), None); // sobrescrito não é \d
    }
}
