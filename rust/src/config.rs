//! Ajustes salvos entre uma abertura e outra (`config.json`), porta da `config.py` da 1.5.1.
//!
//! Lê o config da 1.5.x sem perder nada e grava os mesmos bytes que ela gravaria: as chaves na
//! ordem do PADRAO, `json.dump(indent=2, ensure_ascii=False)`, números quebrados no formato do
//! `repr` do Python e `\r\n` no fim das linhas (o modo texto do Python no Windows).
//! Como na 1.5.1, chave que o PADRAO não conhece é descartada na leitura, e o valor de cada
//! chave é guardado como veio (o tipo só é conferido na hora de usar).

use std::path::{Path, PathBuf};

use serde_json::{Map, Value, json};

use crate::fila::{Filtro, Repetir};

/// As chaves e os valores padrão da 1.5.1, na mesma ordem.
pub fn padrao() -> Map<String, Value> {
    let v = json!({
        "volume": 80,
        "mudo": false,
        "aleatorio": true,
        "repetir": "tudo",
        "filtro": "tudo",
        "segundos_foto": 5,
        "painel": true,
        "ultimas_pastas": [],
        "geometria": null,
        "versao_vista": "",
        "idioma": "",
        "aviso_adiado_versao": "",
        "aviso_adiado_ate": 0,
        "novidades_vista": "",
        "tutorial_visto": false,
        "retomar": {},
        "apoio_escolha": "",
    });
    match v {
        Value::Object(m) => m,
        _ => unreachable!(),
    }
}

pub const ARQUIVO: &str = "config.json";

#[derive(Debug, Clone, PartialEq)]
pub struct Config {
    valores: Map<String, Value>,
}

impl Default for Config {
    fn default() -> Self {
        Config { valores: padrao() }
    }
}

impl Config {
    /// `config.carregar()` a partir do texto do arquivo. Texto quebrado (JSON inválido, BOM, não
    /// é objeto) dá o padrão, como na 1.5.1.
    pub fn de_bytes(dados: &[u8]) -> Self {
        let mut cfg = Config::default();
        let Ok(texto) = std::str::from_utf8(dados) else { return cfg };
        if let Ok(Value::Object(salvo)) = serde_json::from_str::<Value>(texto) {
            for (k, v) in salvo {
                if let Some(lugar) = cfg.valores.get_mut(&k) {
                    *lugar = v;
                }
            }
        }
        cfg
    }

    pub fn carregar(pasta: &Path) -> Self {
        match std::fs::read(pasta.join(ARQUIVO)) {
            Ok(d) => Self::de_bytes(&d),
            Err(_) => Config::default(),
        }
    }

    /// Já houve um config nesta pasta (instalação nova ou atualização).
    pub fn existe(pasta: &Path) -> bool {
        pasta.join(ARQUIVO).exists()
    }

    /// O texto que a 1.5.1 gravaria (com `\n`; `salvar` troca por `\r\n`).
    pub fn para_texto(&self) -> String {
        let mut s = String::new();
        escrever(&Value::Object(self.valores.clone()), 0, &mut s);
        s
    }

    /// Os bytes do arquivo, iguais aos da 1.5.1 no Windows.
    pub fn para_bytes(&self) -> Vec<u8> {
        self.para_texto().replace('\n', "\r\n").into_bytes()
    }

    /// Grava num `.tmp` e troca de uma vez (nunca deixa o config pela metade).
    pub fn salvar(&self, pasta: &Path) -> std::io::Result<()> {
        std::fs::create_dir_all(pasta)?;
        let destino = pasta.join(ARQUIVO);
        let tmp = pasta.join(format!("{ARQUIVO}.tmp"));
        std::fs::write(&tmp, self.para_bytes())?;
        std::fs::rename(&tmp, &destino)
    }

    // ---------- leitura com o mesmo sentido que a janela da 1.5.1 dá ----------
    pub fn valor(&self, chave: &str) -> Option<&Value> {
        self.valores.get(chave)
    }

    /// Troca o valor de uma chave do PADRAO (chave desconhecida é ignorada, como na leitura).
    pub fn definir(&mut self, chave: &str, v: Value) {
        if let Some(lugar) = self.valores.get_mut(chave) {
            *lugar = v;
        }
    }

    /// `bool(cfg[chave])` do Python.
    pub fn sim(&self, chave: &str) -> bool {
        verdadeiro(self.valores.get(chave).unwrap_or(&Value::Null))
    }

    /// `int(cfg[chave])` do Python; o que o Python recusaria dá o padrão.
    pub fn inteiro(&self, chave: &str) -> i64 {
        self.valores.get(chave).and_then(inteiro_py).or_else(|| padrao().get(chave).and_then(inteiro_py)).unwrap_or(0)
    }

    pub fn texto(&self, chave: &str) -> String {
        match self.valores.get(chave) {
            Some(Value::String(s)) => s.clone(),
            _ => String::new(),
        }
    }

    pub fn volume(&self) -> i64 {
        self.inteiro("volume")
    }
    pub fn mudo(&self) -> bool {
        self.sim("mudo")
    }
    pub fn aleatorio(&self) -> bool {
        self.sim("aleatorio")
    }
    pub fn segundos_foto(&self) -> i64 {
        self.inteiro("segundos_foto")
    }
    pub fn painel(&self) -> bool {
        self.sim("painel")
    }

    /// Valor fora da lista volta para "tudo" (a janela da 1.5.1 faz o mesmo).
    pub fn repetir(&self) -> Repetir {
        Repetir::de_nome(&self.texto("repetir")).unwrap_or(Repetir::Tudo)
    }
    pub fn filtro(&self) -> Filtro {
        Filtro::de_nome(&self.texto("filtro")).unwrap_or(Filtro::Tudo)
    }

    /// As pastas do "Continuar" (só os textos; quem usa confere se ainda existem).
    pub fn ultimas_pastas(&self) -> Vec<PathBuf> {
        match self.valores.get("ultimas_pastas") {
            Some(Value::Array(v)) => v.iter().filter_map(|x| x.as_str()).map(PathBuf::from).collect(),
            _ => Vec::new(),
        }
    }

    pub fn definir_aleatorio(&mut self, v: bool) {
        self.definir("aleatorio", Value::Bool(v));
    }
    pub fn definir_repetir(&mut self, r: Repetir) {
        self.definir("repetir", Value::String(r.nome().into()));
    }
    pub fn definir_filtro(&mut self, f: Filtro) {
        self.definir("filtro", Value::String(f.nome().into()));
    }
    pub fn definir_ultimas_pastas(&mut self, pastas: &[PathBuf]) {
        let v = pastas.iter().take(5000).map(|p| Value::String(p.to_string_lossy().into_owned())).collect();
        self.definir("ultimas_pastas", Value::Array(v));
    }
}

/// Verdade do Python: `None`, `False`, 0, "", [] e {} são falsos.
fn verdadeiro(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().map(|f| f != 0.0).unwrap_or(true),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// `int(v)` do Python para os tipos do JSON (número quebrado corta para o zero; texto só se for
/// um inteiro escrito; o resto o Python recusaria).
fn inteiro_py(v: &Value) -> Option<i64> {
    match v {
        Value::Bool(b) => Some(*b as i64),
        Value::Number(n) => n.as_i64().or_else(|| n.as_f64().filter(|f| f.is_finite()).map(|f| f.trunc() as i64)),
        Value::String(s) => s.trim().replace('_', "").parse().ok(),
        _ => None,
    }
}

// ---------- json.dump(indent=2, ensure_ascii=False) ----------

fn escrever(v: &Value, nivel: usize, s: &mut String) {
    match v {
        Value::Null => s.push_str("null"),
        Value::Bool(b) => s.push_str(if *b { "true" } else { "false" }),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                s.push_str(&i.to_string());
            } else if let Some(u) = n.as_u64() {
                s.push_str(&u.to_string());
            } else {
                s.push_str(&repr_float(n.as_f64().unwrap_or(0.0)));
            }
        }
        Value::String(t) => texto_json(t, s),
        Value::Array(a) => {
            if a.is_empty() {
                s.push_str("[]");
                return;
            }
            s.push('[');
            for (i, x) in a.iter().enumerate() {
                s.push_str(if i == 0 { "\n" } else { ",\n" });
                recuo(nivel + 1, s);
                escrever(x, nivel + 1, s);
            }
            s.push('\n');
            recuo(nivel, s);
            s.push(']');
        }
        Value::Object(o) => {
            if o.is_empty() {
                s.push_str("{}");
                return;
            }
            s.push('{');
            for (i, (k, x)) in o.iter().enumerate() {
                s.push_str(if i == 0 { "\n" } else { ",\n" });
                recuo(nivel + 1, s);
                texto_json(k, s);
                s.push_str(": ");
                escrever(x, nivel + 1, s);
            }
            s.push('\n');
            recuo(nivel, s);
            s.push('}');
        }
    }
}

fn recuo(nivel: usize, s: &mut String) {
    for _ in 0..nivel {
        s.push_str("  ");
    }
}

/// Texto JSON como o Python com `ensure_ascii=False`: só aspas, barra e controles são escapados.
fn texto_json(t: &str, s: &mut String) {
    s.push('"');
    for c in t.chars() {
        match c {
            '"' => s.push_str("\\\""),
            '\\' => s.push_str("\\\\"),
            '\n' => s.push_str("\\n"),
            '\r' => s.push_str("\\r"),
            '\t' => s.push_str("\\t"),
            '\u{8}' => s.push_str("\\b"),
            '\u{c}' => s.push_str("\\f"),
            c if (c as u32) < 0x20 => s.push_str(&format!("\\u{:04x}", c as u32)),
            c => s.push(c),
        }
    }
    s.push('"');
}

/// `repr(float)` do Python: os menores dígitos que voltam ao mesmo número; notação com expoente
/// quando o ponto cairia antes de 4 zeros ou depois de 16 dígitos; ".0" no inteiro.
pub fn repr_float(x: f64) -> String {
    if x.is_nan() {
        return "NaN".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "Infinity".into() } else { "-Infinity".into() };
    }
    let sinal = if x.is_sign_negative() { "-" } else { "" };
    let e = format!("{:e}", x.abs()); // "1.2345e3": menores dígitos que voltam ao número
    let (mant, exp) = e.split_once('e').expect("formato {:e}");
    let exp: i32 = exp.parse().expect("expoente");
    let digitos: String = mant.chars().filter(|c| *c != '.').collect();
    let digitos = if x == 0.0 { "0".to_string() } else { digitos };
    let decpt = exp + 1; // valor = 0.DIGITOS × 10^decpt
    let n = digitos.len() as i32;
    if x != 0.0 && (decpt <= -4 || decpt > 16) {
        let resto = &digitos[1..];
        let m = if resto.is_empty() { digitos[..1].to_string() } else { format!("{}.{resto}", &digitos[..1]) };
        let ee = decpt - 1;
        return format!("{sinal}{m}e{}{:02}", if ee < 0 { '-' } else { '+' }, ee.abs());
    }
    let corpo = if x == 0.0 {
        "0.0".to_string()
    } else if decpt <= 0 {
        format!("0.{}{digitos}", "0".repeat((-decpt) as usize))
    } else if decpt >= n {
        format!("{digitos}{}.0", "0".repeat((decpt - n) as usize))
    } else {
        format!("{}.{}", &digitos[..decpt as usize], &digitos[decpt as usize..])
    };
    format!("{sinal}{corpo}")
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn repr_igual_ao_python() {
        for (x, r) in [
            (5.0, "5.0"),
            (0.1, "0.1"),
            (1763400000.123456, "1763400000.123456"),
            (1e16, "1e+16"),
            (1234567890123456.0, "1234567890123456.0"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (1.5e-7, "1.5e-07"),
            (-0.0, "-0.0"),
            (0.0, "0.0"),
            (123.456, "123.456"),
            (1e22, "1e+22"),
            (2.5e300, "2.5e+300"),
        ] {
            assert_eq!(repr_float(x), r, "{x}");
        }
    }
}
