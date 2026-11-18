//! Os textos em Rust contra o que a `textos.py` da 1.5.1 devolve de fato, com a fixture que o
//! próprio Python da 1.5.1 gerou (`ferramentas/gerar_fixtures_textos.py`).

use std::fmt::Display;
use std::path::Path;
use std::sync::{Mutex, MutexGuard};

use ciranda::textos;
use serde_json::Value;

/// O idioma é global (como o `_atual` da 1.5.1) e o `CIRANDA_IDIOMA_SISTEMA` também: os testes que
/// mexem neles rodam um de cada vez.
static TRAVA: Mutex<()> = Mutex::new(());

fn travar() -> MutexGuard<'static, ()> {
    TRAVA.lock().unwrap_or_else(|e| e.into_inner())
}

fn fixture() -> Value {
    let caminho = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests").join("fixtures").join("textos.json");
    serde_json::from_str(&std::fs::read_to_string(caminho).unwrap()).unwrap()
}

fn lista<'a>(v: &'a Value, campo: &str) -> &'a Vec<Value> {
    v[campo].as_array().unwrap_or_else(|| panic!("fixture sem {campo}"))
}

fn texto(v: &Value) -> &str {
    v.as_str().unwrap()
}

/// Os valores do `**kw` como o Rust os passa: inteiro ou texto, cada um pelo `Display`.
enum Valor {
    Int(i64),
    Txt(String),
}

impl Display for Valor {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Valor::Int(n) => n.fmt(f),
            Valor::Txt(s) => s.fmt(f),
        }
    }
}

fn valores(args: &Value) -> Vec<(String, Valor)> {
    args.as_object()
        .unwrap()
        .iter()
        .map(|(k, v)| {
            let valor = match v {
                Value::Number(n) => Valor::Int(n.as_i64().unwrap()),
                Value::String(s) => Valor::Txt(s.clone()),
                outro => panic!("valor inesperado na fixture: {outro}"),
            };
            (k.clone(), valor)
        })
        .collect()
}

fn como_args(v: &[(String, Valor)]) -> Vec<(&str, &dyn Display)> {
    v.iter().map(|(k, x)| (k.as_str(), x as &dyn Display)).collect()
}

/// SAFETY dos `set_var`/`remove_var`: só estes testes mexem na variável, sempre com a `TRAVA`.
fn simular_sistema(valor: Option<&str>) {
    match valor {
        Some(v) => unsafe { std::env::set_var("CIRANDA_IDIOMA_SISTEMA", v) },
        None => unsafe { std::env::remove_var("CIRANDA_IDIOMA_SISTEMA") },
    }
}

#[test]
fn as_mesmas_chaves_na_mesma_ordem() {
    let f = fixture();
    let esperadas: Vec<&str> = lista(&f, "chaves").iter().map(texto).collect();
    assert_eq!(esperadas.len() as u64, f["quantas"].as_u64().unwrap());
    let nossas: Vec<&str> = textos::chaves().collect();
    assert_eq!(nossas.len(), esperadas.len(), "número de chaves diferente da 1.5.1");
    assert_eq!(nossas, esperadas);
    for c in &esperadas {
        assert!(textos::tem(c), "{c}");
    }
    assert!(!textos::tem("chave_que_nao_existe"));
    assert!(!textos::tem("Nada_tocando"));
    assert!(!textos::tem(""));
}

#[test]
fn idiomas_e_nomes() {
    let f = fixture();
    let idiomas: Vec<&str> = lista(&f, "idiomas").iter().map(texto).collect();
    assert_eq!(textos::IDIOMAS.to_vec(), idiomas);
    for i in textos::IDIOMAS {
        assert_eq!(textos::nome(i), texto(&f["nomes"][i]));
    }
    assert_eq!(textos::nome("xx"), "EN");
}

/// Toda chave × idioma: o texto cru e o preenchido, iguais aos da 1.5.1.
#[test]
fn t_igual_a_151_em_toda_chave_e_idioma() {
    let f = fixture();
    let _trava = travar();
    let casos = lista(&f, "t");
    assert_eq!(casos.len(), 3 * f["quantas"].as_u64().unwrap() as usize);
    for c in casos {
        let (chave, idioma) = (texto(&c["chave"]), texto(&c["idioma"]));
        textos::definir(idioma);
        assert_eq!(textos::atual(), idioma);
        assert_eq!(textos::t(chave), texto(&c["cru"]), "{chave} [{idioma}] cru");
        assert_eq!(textos::tf(chave, &[]), texto(&c["cru"]), "{chave} [{idioma}] tf sem valores");
        let v = valores(&c["args"]);
        assert_eq!(textos::tf(chave, &como_args(&v)), texto(&c["formatado"]), "{chave} [{idioma}] formatado");
    }
}

#[test]
fn formatar_igual_ao_str_format() {
    let f = fixture();
    for c in lista(&f, "formato") {
        let v = valores(&c["args"]);
        let modelo = texto(&c["modelo"]);
        assert_eq!(textos::formatar(modelo, &como_args(&v)), texto(&c["esperado"]), "{modelo:?}");
    }
}

#[test]
fn traducao_vazia_cai_no_ingles() {
    let f = fixture();
    for c in lista(&f, "escolha") {
        let t: Vec<&str> = lista(c, "trio").iter().map(texto).collect();
        let trio = [t[0], t[1], t[2]];
        let idioma = texto(&c["idioma"]);
        assert_eq!(textos::escolher(&trio, idioma), texto(&c["esperado"]), "{trio:?} [{idioma}]");
    }
}

#[test]
fn normalizar_igual_a_151() {
    let f = fixture();
    let casos = lista(&f, "normalizar");
    assert!(casos.len() >= 90);
    for c in casos {
        let entrada = texto(&c[0]);
        assert_eq!(textos::normalizar(entrada), texto(&c[1]), "normalizar({entrada:?})");
    }
}

#[test]
fn idioma_do_sistema_simulado() {
    let f = fixture();
    let _trava = travar();
    for c in lista(&f, "sistema") {
        let v = texto(&c[0]);
        simular_sistema(Some(v));
        assert_eq!(textos::idioma_do_sistema(), texto(&c[1]), "CIRANDA_IDIOMA_SISTEMA={v:?}");
    }
    // Vazio conta como ausente (o `if forcado` da 1.5.1): vale o Windows, que dá um dos três.
    simular_sistema(Some(""));
    assert!(textos::IDIOMAS.contains(&textos::idioma_do_sistema()));
    simular_sistema(None);
}

#[test]
fn iniciar_e_definir_iguais_a_151() {
    let f = fixture();
    let _trava = travar();
    for c in lista(&f, "iniciar") {
        simular_sistema(Some(texto(&c["sistema"])));
        let salvo = c["salvo"].as_str();
        let r = textos::iniciar(salvo);
        assert_eq!(r, texto(&c["esperado"]), "iniciar({salvo:?}) com o sistema {}", c["sistema"]);
        assert_eq!(textos::atual(), r);
    }
    simular_sistema(None);
    for c in lista(&f, "definir") {
        textos::definir(texto(&c[0]));
        assert_eq!(textos::atual(), texto(&c[1]), "definir({:?})", c[0]);
    }
}

/// O idioma vale para todas as threads e não se corrompe com várias trocando ao mesmo tempo.
#[test]
fn idioma_global_entre_threads() {
    let _trava = travar();
    std::thread::scope(|s| {
        for i in 0..8 {
            s.spawn(move || {
                for _ in 0..2000 {
                    textos::definir(textos::IDIOMAS[i % 3]);
                    assert!(textos::IDIOMAS.contains(&textos::atual()));
                    assert!(!textos::t("nada_tocando").is_empty());
                }
            });
        }
    });
    textos::definir("es");
    let outra = std::thread::spawn(|| (textos::atual(), textos::t("nada_tocando"))).join().unwrap();
    assert_eq!(outra, ("es", "Nada en reproducción".to_string()));
}

/// Chave desconhecida: a 1.5.1 levanta KeyError; aqui volta a própria chave (só em release, porque
/// em debug o `debug_assert!` avisa do erro de programação).
#[cfg(not(debug_assertions))]
#[test]
fn chave_desconhecida_devolve_a_chave() {
    let _trava = travar();
    assert_eq!(textos::t("chave_que_nao_existe"), "chave_que_nao_existe");
    assert_eq!(textos::tf("outra_que_nao_existe", &[("n", &1)]), "outra_que_nao_existe");
    // Campo sem valor fica como está (a 1.5.1 levantaria KeyError).
    assert_eq!(textos::formatar("{n} de {total}", &[("n", &1)]), "1 de {total}");
}
