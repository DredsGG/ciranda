//! Caminhos e varredura contra a 1.5.1: `normcase`, `abspath` e a classe de erro tirados do
//! Python 3.12 (`tests/fixtures/caminhos.json`, do `ferramentas/gerar_fixtures.py`), e pastas de
//! sistema puladas numa árvore de verdade.

use std::path::{Path, PathBuf};

use ciranda::biblioteca::{
    Estatisticas, PASTAS_IGNORADAS, absoluto, classe_do_erro, normcase, varrer_simples, varrer_varios_simples,
};

fn fixture() -> serde_json::Value {
    let p = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests").join("fixtures").join("caminhos.json");
    serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap()
}

fn pares(v: &serde_json::Value) -> Vec<(String, String)> {
    v.as_array().unwrap().iter().map(|x| (x[0].as_str().unwrap().into(), x[1].as_str().unwrap().into())).collect()
}

struct Pasta(PathBuf);
impl Drop for Pasta {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn pasta(nome: &str) -> Pasta {
    let p = std::env::temp_dir().join(format!("ciranda-biblioteca-{nome}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&p);
    std::fs::create_dir_all(&p).unwrap();
    Pasta(p)
}

#[test]
fn normcase_igual_ao_python() {
    let casos = pares(&fixture()["normcase"]);
    assert!(casos.len() >= 15);
    for (entrada, esperado) in casos {
        assert_eq!(normcase(Path::new(&entrada)), esperado, "normcase({entrada:?})");
    }
}

#[test]
fn abspath_igual_ao_python() {
    let casos = pares(&fixture()["abspath"]);
    assert!(casos.len() >= 10);
    for (entrada, esperado) in casos {
        assert_eq!(absoluto(Path::new(&entrada)), PathBuf::from(&esperado), "abspath({entrada:?})");
    }
}

#[test]
fn classe_do_erro_igual_ao_python() {
    let f = fixture();
    let tabela = f["erros_nao_oserror"].as_object().unwrap();
    assert!(tabela.len() > 50);
    for w in 0..20000u32 {
        let esperado = tabela.get(&w.to_string()).and_then(|v| v.as_str()).unwrap_or("OSError");
        assert_eq!(classe_do_erro(w), esperado, "winerror {w}");
    }
}

/// O que os bugs plantados mostraram que faltava: pasta de sistema (comparada sem maiúsculas)
/// fica de fora e vai para "puladas"; uma pasta comum do lado entra.
#[test]
fn pastas_de_sistema_puladas() {
    let d = pasta("ignoradas");
    let mut esperadas = Vec::new();
    for (n, nome) in PASTAS_IGNORADAS.iter().enumerate() {
        // Metade em maiúsculas, como o Windows mostra ($RECYCLE.BIN, System Volume Information).
        let nome = if n % 2 == 0 { nome.to_uppercase() } else { nome.to_string() };
        let p = d.0.join(&nome);
        std::fs::create_dir_all(&p).unwrap();
        std::fs::write(p.join("dentro.jpg"), b"").unwrap();
        esperadas.push(p);
    }
    std::fs::create_dir_all(d.0.join("Comum")).unwrap();
    std::fs::write(d.0.join("Comum").join("fica.jpg"), b"").unwrap();
    let mut stats = Estatisticas::default();
    let its = varrer_varios_simples(&[d.0.clone()], &mut stats);
    let nomes: Vec<&str> = its.iter().map(|i| i.nome.as_str()).collect();
    assert_eq!(nomes, vec!["fica.jpg"]);
    let mut puladas: Vec<PathBuf> = stats.puladas.iter().map(PathBuf::from).collect();
    puladas.sort();
    esperadas.sort();
    assert_eq!(puladas, esperadas);
}

/// K (sinal Kelvin) e k são dois arquivos no NTFS; o normcase do Python não junta os dois, então
/// os dois entram na fila. A mesma pasta escrita em maiúsculas e minúsculas (grego) entra uma vez só.
#[test]
fn kelvin_e_grego_como_a_151() {
    let d = pasta("kelvin");
    std::fs::write(d.0.join("\u{212A}.jpg"), b"").unwrap();
    std::fs::write(d.0.join("k.jpg"), b"").unwrap();
    assert_eq!(varrer_simples(&d.0).len(), 2);

    let maiusc = d.0.join("ΦΩΤΟΣ");
    std::fs::create_dir_all(&maiusc).unwrap();
    std::fs::write(maiusc.join("a.jpg"), b"").unwrap();
    let minusc = d.0.join("φωτοσ"); // o NTFS acha a mesma pasta
    assert!(minusc.is_dir());
    let its = varrer_varios_simples(&[maiusc, minusc], &mut Estatisticas::default());
    assert_eq!(its.len(), 1, "a mesma pasta duas vezes não repete arquivo");
}
