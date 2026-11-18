//! A heif.rs contra a heif.py da 1.5.1: para cada arquivo de `tests/fixtures/heif/` (HEIC de
//! verdade do `gerar_heic.py`, cortados, com bytes trocados, com caixas de tamanho 0 e de 64 bits,
//! montados à mão e coisas que nem são HEIC), o mesmo filtro e a mesma lista que o Python da 1.5.1
//! deu (`tests/fixtures/heif.json`, do `ferramentas/gerar_fixtures_heif.py`).

use std::path::{Path, PathBuf};

use ciranda::heif::{EXTENSOES, eh_heif, filtro_de_giro, transformacoes_da_grade};

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests").join("fixtures")
}

#[test]
fn heif_igual_a_151() {
    let json: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(fixtures().join("heif.json")).unwrap()).unwrap();
    let casos = json["casos"].as_object().unwrap();
    assert!(casos.len() >= 1000, "faltam fixtures: {}", casos.len());
    let dir = fixtures().join("heif");
    let mut no_disco: Vec<String> =
        std::fs::read_dir(&dir).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()).collect();
    no_disco.sort();
    let mut no_json: Vec<String> = casos.keys().cloned().collect();
    no_json.sort();
    assert_eq!(no_disco, no_json, "a pasta e o heif.json não batem");

    let mut verificacoes = 0usize;
    let mut com_giro = 0usize;
    let mut erros = Vec::new();
    for (nome, esperado) in casos {
        let p = dir.join(nome);
        let filtro = esperado["filtro"].as_str().unwrap();
        let partes: Vec<&str> = esperado["partes"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
        let r_filtro = filtro_de_giro(&p);
        let r_partes = transformacoes_da_grade(&p);
        if r_filtro != filtro {
            erros.push(format!("{nome}: filtro {r_filtro:?}, a 1.5.1 dá {filtro:?}"));
        }
        if r_partes != partes {
            erros.push(format!("{nome}: partes {r_partes:?}, a 1.5.1 dá {partes:?}"));
        }
        verificacoes += 2;
        com_giro += usize::from(!partes.is_empty());
    }
    assert!(com_giro >= 100, "poucas fixtures com giro ou espelho: {com_giro}");

    // Caminho que não existe e pasta: nada a girar (o OSError do open da 1.5.1).
    let tmp = std::env::temp_dir().join(format!("ciranda-heif-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(tmp.join("pasta.heic")).unwrap();
    for p in [tmp.join("nao-existe.heic"), tmp.join("pasta.heic"), tmp.clone()] {
        if !filtro_de_giro(&p).is_empty() || !transformacoes_da_grade(&p).is_empty() {
            erros.push(format!("{}: deveria dar vazio", p.display()));
        }
        verificacoes += 2;
    }
    let _ = std::fs::remove_dir_all(&tmp);

    // `ext in heif.EXTENSOES`: só as duas, em minúsculas e com o ponto.
    for (ext, sim) in
        [(".heic", true), (".heif", true), (".HEIC", false), ("heic", false), (".avif", false), ("", false)]
    {
        if eh_heif(ext) != sim {
            erros.push(format!("eh_heif({ext:?}) deveria ser {sim}"));
        }
        verificacoes += 1;
    }
    assert_eq!(EXTENSOES, [".heic", ".heif"]);
    verificacoes += 1;

    assert!(erros.is_empty(), "{} de {verificacoes} verificações FALHARAM:\n{}", erros.len(), erros.join("\n"));
    println!("heif: {verificacoes} verificações ({} fixtures, {com_giro} com giro ou espelho)", casos.len());
}
