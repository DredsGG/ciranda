//! Varre pastas com o núcleo em Rust e grava o resultado em JSON (para comparar com a 1.5.1).
//!     cargo run --release --example varrer -- <saida.json> <pasta ou arquivo>...

use std::path::PathBuf;
use std::time::Instant;

use ciranda::biblioteca::{Estatisticas, varrer_varios};
use serde_json::{Value, json};

fn main() {
    let mut args = std::env::args_os().skip(1);
    let saida = PathBuf::from(args.next().expect("uso: varrer <saida.json> <caminhos>..."));
    let caminhos: Vec<PathBuf> = args.map(PathBuf::from).collect();
    let mut stats = Estatisticas::default();
    let t0 = Instant::now();
    let itens = varrer_varios(&caminhos, &|| false, &mut |_, _| {}, &mut stats);
    let segundos = t0.elapsed().as_secs_f64();
    let lista: Vec<Value> = itens
        .iter()
        .map(|i| {
            json!([i.caminho.to_string_lossy(), i.tipo.nome(), i.raiz.to_string_lossy(), i.pasta_rel, i.nome, i.ext])
        })
        .collect();
    let ignorados: serde_json::Map<String, Value> = stats.ignorados.iter().map(|(k, v)| (k.clone(), json!(v))).collect();
    let v = json!({
        "segundos": segundos,
        "itens": lista,
        "pastas_lidas": stats.pastas_lidas,
        "ignorados": ignorados,
        "sem_acesso": stats.sem_acesso,
        "puladas": stats.puladas,
    });
    std::fs::write(&saida, serde_json::to_vec(&v).unwrap()).unwrap();
    println!("{} itens, {} pastas lidas, {segundos:.3} s", itens.len(), stats.pastas_lidas);
}
