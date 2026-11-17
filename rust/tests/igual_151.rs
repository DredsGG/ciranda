//! O núcleo em Rust contra o que a 1.5.1 faz de fato, com as fixtures que o próprio Python da
//! 1.5.1 gerou (`ferramentas/gerar_fixtures.py`).

use std::path::{Path, PathBuf};

use ciranda::biblioteca::em_ordem;
use ciranda::config::Config;
use ciranda::ordem::chave_natural;

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests").join("fixtures")
}

/// Para cada caso, `carregar()` + `salvar()` em Rust grava os mesmos bytes que a 1.5.1 gravou.
#[test]
fn config_le_e_grava_igual_a_151() {
    let dir = fixtures().join("config");
    let mut saidas: Vec<PathBuf> = std::fs::read_dir(&dir)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.to_string_lossy().ends_with(".saida.json"))
        .collect();
    saidas.sort();
    assert!(saidas.len() >= 14, "faltam fixtures: {}", saidas.len());
    let tmp = std::env::temp_dir().join(format!("ciranda-cfg-{}", std::process::id()));
    for saida in &saidas {
        let nome = saida.file_name().unwrap().to_string_lossy().replace(".saida.json", "");
        let esperado = std::fs::read(saida).unwrap();
        let entrada = dir.join(format!("{nome}.entrada.json"));
        // O caminho que o app faz: arquivo na pasta → carregar → salvar → bytes no disco.
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(&tmp).unwrap();
        if entrada.exists() {
            std::fs::copy(&entrada, tmp.join("config.json")).unwrap();
        }
        let cfg = Config::carregar(&tmp);
        cfg.salvar(&tmp).unwrap();
        let gravado = std::fs::read(tmp.join("config.json")).unwrap();
        assert!(
            gravado == esperado,
            "{nome}: diferente da 1.5.1\n--- 1.5.1 ---\n{}\n--- Rust ---\n{}",
            String::from_utf8_lossy(&esperado),
            String::from_utf8_lossy(&gravado)
        );
        assert!(!tmp.join("config.json.tmp").exists(), "{nome}: sobrou o .tmp");
        // Ler de novo o que foi gravado não muda nada (ida e volta).
        assert_eq!(Config::de_bytes(&gravado).para_bytes(), esperado, "{nome}: ida e volta");
    }
    let _ = std::fs::remove_dir_all(&tmp);
}

/// O sentido que a janela da 1.5.1 dá a valores tortos (bool(), int(), lista fora do padrão).
#[test]
fn config_valores_tortos_como_a_151() {
    let dir = fixtures().join("config");
    let c = Config::de_bytes(&std::fs::read(dir.join("06-tipos-errados.entrada.json")).unwrap());
    assert_eq!(c.volume(), 70); // int("70")
    assert!(!c.aleatorio()); // bool(0)
    assert_eq!(c.repetir(), ciranda::fila::Repetir::Tudo); // "sempre" não existe
    assert_eq!(c.filtro(), ciranda::fila::Filtro::Tudo); // null
    assert!(c.ultimas_pastas().is_empty()); // texto em vez de lista
    assert!(!c.mudo()); // bool([])
    let r = Config::de_bytes(&std::fs::read(dir.join("03-realista.entrada.json")).unwrap());
    assert_eq!(r.volume(), 65);
    assert_eq!(r.segundos_foto(), 12);
    assert!(r.mudo() && !r.aleatorio() && !r.painel());
    assert_eq!(r.ultimas_pastas().len(), 3);
}

/// 2.991 nomes difíceis (ß, Σ, dígitos de outros alfabetos, zeros à esquerda, números gigantes,
/// empates): a mesma ordem da `chave_natural` da 1.5.1, inclusive nos empates (sort estável).
#[test]
fn ordem_natural_igual_a_151() {
    let texto = std::fs::read_to_string(fixtures().join("ordem.json")).unwrap();
    let v: serde_json::Value = serde_json::from_str(&texto).unwrap();
    let nomes: Vec<String> = v["nomes"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_string()).collect();
    assert_eq!(nomes.len(), 2991);
    // O `em_ordem` é o que a varredura usa: crescente para os arquivos, decrescente (e estável,
    // como o sorted(reverse=True)) para as subpastas que vão para a pilha.
    for (campo, decrescente) in [("ordem", false), ("ordem_decrescente", true)] {
        let esperado: Vec<usize> = v[campo].as_array().unwrap().iter().map(|x| x.as_u64().unwrap() as usize).collect();
        assert_eq!(esperado.len(), nomes.len(), "{campo} completo na fixture");
        let idx = em_ordem(&nomes, |s| s.as_str(), decrescente);
        assert_eq!(idx.len(), esperado.len());
        if let Some(p) = idx.iter().zip(&esperado).position(|(a, b)| a != b) {
            panic!(
                "{campo}, posição {p}: Rust {:?}, 1.5.1 {:?}",
                &idx[p.saturating_sub(2)..(p + 3).min(idx.len())].iter().map(|&i| &nomes[i]).collect::<Vec<_>>(),
                &esperado[p.saturating_sub(2)..(p + 3).min(idx.len())].iter().map(|&i| &nomes[i]).collect::<Vec<_>>()
            );
        }
    }
    // E a chave sozinha, como a `chave_natural` da 1.5.1.
    let mut idx: Vec<usize> = (0..nomes.len()).collect();
    idx.sort_by_cached_key(|&i| (chave_natural(&nomes[i]), i));
    let esperado: Vec<usize> = v["ordem"].as_array().unwrap().iter().map(|x| x.as_u64().unwrap() as usize).collect();
    assert_eq!(idx, esperado);
}
