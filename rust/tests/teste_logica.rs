//! Porta do `tests/teste_logica.py` da 1.5.1 (varredura e fila, sem interface), checagem por
//! checagem e na mesma ordem. Rodar:
//!     cargo test --release --test teste_logica [-- <pasta-de-midia-de-teste>]
//! A pasta (do `tests/gerar_midia.py`) é opcional; sem ela, só os testes da fila rodam.
//! Termina com "TUDO PASSOU (N verificações)", como a 1.5.1 (377 sem a pasta, 384 com ela).

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

use ciranda::biblioteca::{Estatisticas, Item, Tipo, varrer_simples, varrer_varios_simples};
use ciranda::fila::{Fila, Filtro, Repetir};
use ciranda::ordem::comparar;

static OK: AtomicUsize = AtomicUsize::new(0);

fn check(cond: bool, msg: &str) {
    if !cond {
        panic!("FALHOU: {msg}");
    }
    OK.fetch_add(1, Ordering::Relaxed);
}

fn item(caminho: &str, tipo: Tipo, raiz: &str, rel: &str, nome: &str, ext: &str) -> Item {
    Item {
        caminho: PathBuf::from(caminho),
        tipo,
        raiz: PathBuf::from(raiz),
        pasta_rel: rel.into(),
        nome: nome.into(),
        ext: ext.into(),
        falhou: false,
    }
}

fn itens_falsos(nf: usize, nv: usize) -> Vec<Item> {
    let mut v: Vec<Item> =
        (0..nf).map(|i| item(&format!("/x/f{i}.jpg"), Tipo::Foto, "/x", "", &format!("f{i}.jpg"), ".jpg")).collect();
    v.extend((0..nv).map(|i| item(&format!("/x/v{i}.mp4"), Tipo::Video, "/x", "sub", &format!("v{i}.mp4"), ".mp4")));
    v
}

fn nome(f: &Fila, i: Option<usize>) -> String {
    i.map(|i| f.itens[i].nome.clone()).unwrap_or_default()
}

fn teste_ordem_natural() {
    let mut nomes = vec!["foto10.jpg", "foto2.jpg", "Foto1.jpg", "a.jpg"];
    nomes.sort_by(|a, b| comparar(a, b));
    check(nomes == ["a.jpg", "Foto1.jpg", "foto2.jpg", "foto10.jpg"], "ordem natural");
}

fn teste_em_ordem_repetir_nada() {
    let mut f = Fila::nova(None);
    f.repetir = Repetir::Nao;
    f.definir_itens(itens_falsos(6, 4));
    let mut vistos = Vec::new();
    let mut it = f.proximo(false);
    while let Some(i) = it {
        vistos.push(f.itens[i].nome.clone());
        it = f.proximo(true);
    }
    check(vistos.len() == 10, "em ordem toca os 10");
    check(vistos[0] == "f0.jpg" && vistos[vistos.len() - 1] == "v3.mp4", "em ordem começa e termina certo");
    check(f.proximo(false).is_none(), "fim sem repetir");
}

fn teste_baralho_sem_repetir() {
    let mut f = Fila::nova(Some(1));
    f.repetir = Repetir::Tudo;
    f.aleatorio = true;
    f.definir_itens(itens_falsos(6, 4));
    for rodada in 0..50 {
        let vistos: HashSet<PathBuf> = (0..10)
            .map(|_| {
                let i = f.proximo(true).unwrap();
                f.itens[i].caminho.clone()
            })
            .collect();
        check(vistos.len() == 10, &format!("rodada {rodada}: cada item uma vez por rodada"));
    }
    // O último de uma rodada não abre a próxima.
    let mut f2 = Fila::nova(Some(7));
    f2.aleatorio = true;
    f2.definir_itens(itens_falsos(3, 0));
    let mut anterior: Option<PathBuf> = None;
    for _ in 0..300 {
        let i = f2.proximo(true).unwrap();
        let c = f2.itens[i].caminho.clone();
        check(Some(&c) != anterior.as_ref(), "nunca o mesmo item duas vezes seguidas");
        anterior = Some(c);
    }
}

fn teste_aleatorio_distribui() {
    let mut c: HashMap<String, usize> = HashMap::new();
    for s in 0..400 {
        let mut f = Fila::nova(Some(s));
        f.aleatorio = true;
        f.definir_itens(itens_falsos(6, 4));
        let i = f.proximo(false);
        *c.entry(nome(&f, i)).or_default() += 1;
    }
    let menor = c.values().copied().min().unwrap_or(0);
    check(c.len() == 10 && menor > 15, &format!("primeiro item varia: {c:?}"));
}

fn teste_repetir_um() {
    let mut f = Fila::nova(None);
    f.repetir = Repetir::Um;
    f.definir_itens(itens_falsos(6, 4));
    let a = f.proximo(false);
    check(f.proximo(true) == a, "repetir um repete no automático");
    check(f.proximo(false) != a, "botão próximo sai do repetir um");
}

fn teste_filtro() {
    let mut f = Fila::nova(None);
    f.definir_itens(itens_falsos(6, 4));
    f.proximo(false); // f0
    check(!f.definir_filtro(Filtro::Videos), "foto atual sai com filtro vídeos");
    check(f.len() == 4, "só vídeos");
    let i = f.proximo(false).unwrap();
    check(f.itens[i].tipo == Tipo::Video, "próximo é vídeo");
    check(f.definir_filtro(Filtro::Tudo), "vídeo atual fica com filtro tudo");
    check(f.len() == 10, "volta tudo");
}

fn teste_alternar_aleatorio_mantem_atual() {
    let mut f = Fila::nova(Some(3));
    f.definir_itens(itens_falsos(6, 4));
    let mut atual = None;
    for _ in 0..4 {
        atual = f.proximo(false);
    }
    f.definir_aleatorio(true);
    check(f.indice_atual() == atual && f.posicao().0 == 1, "ligar aleatório mantém o atual no topo");
    f.definir_aleatorio(false);
    check(f.indice_atual() == atual && f.posicao().0 == 4, "desligar volta para a posição dele");
}

fn teste_anterior_e_ir_para() {
    let mut f = Fila::nova(None);
    f.repetir = Repetir::Tudo;
    f.definir_itens(itens_falsos(6, 4));
    f.proximo(false);
    let a = f.anterior();
    check(nome(&f, a) == "v3.mp4", "anterior no começo com repetir tudo vai pro fim");
    let b = f.ir_para(2);
    check(nome(&f, b) == "f2.jpg", "ir para");
    let c = f.proximo(false);
    check(nome(&f, c) == "f3.jpg", "segue do escolhido");
}

fn teste_falhou_pula() {
    let mut f = Fila::nova(None);
    let mut its = itens_falsos(3, 0);
    its[1].falhou = true;
    f.definir_itens(its);
    let a = f.proximo(false);
    let b = f.proximo(false);
    check([nome(&f, a), nome(&f, b)] == ["f0.jpg", "f2.jpg"], "pula o que falhou");
    for i in f.itens.iter_mut() {
        i.falhou = true;
    }
    check(f.proximo(false).is_none(), "tudo falhou -> None, sem laço infinito");
}

fn teste_adicionar_e_remover() {
    let mut f = Fila::nova(Some(2));
    f.aleatorio = true;
    f.definir_itens(itens_falsos(4, 0));
    let a = f.proximo(false).unwrap();
    let a_nome = f.itens[a].nome.clone();
    let novos: Vec<Item> =
        (0..5).map(|i| item(&format!("/y/n{i}.jpg"), Tipo::Foto, "/y", "", &format!("n{i}.jpg"), ".jpg")).collect();
    f.adicionar(novos);
    check(f.indice_atual() == Some(a) && f.len() == 9, "adicionar não troca o atual");
    let resto: Vec<String> = (0..8).map(|_| { let i = f.proximo(true); nome(&f, i) }).collect();
    let unicos: HashSet<&String> = resto.iter().collect();
    check(unicos.len() == 8 && !resto.contains(&a_nome), "novos entram no resto da rodada");
    let atual = f.indice_atual().unwrap();
    f.remover(&[atual]);
    check(f.len() == 8 && f.proximo(false).is_some(), "remover o atual segue a fila");
}

fn teste_varredura(pasta: &Path) {
    let its = varrer_simples(pasta);
    let nomes: Vec<String> = its
        .iter()
        .map(|i| {
            let j = if i.pasta_rel.is_empty() { i.nome.clone() } else { format!("{}\\{}", i.pasta_rel, i.nome) };
            j.replace('\\', "/")
        })
        .collect();
    check(nomes.iter().any(|n| n == ".oculta/nao-deve-aparecer.mp4"), "pasta oculta também entra (abre tudo)");
    check(nomes.len() >= 2 && nomes[..2] == ["abertura.mp4", "capa.jpg"], &format!("arquivos da raiz primeiro: {:?}", &nomes[..3.min(nomes.len())]));
    let i2 = nomes.iter().position(|n| n == "2024 Praia/Dia 1/foto2.jpg").expect("foto2");
    let i10 = nomes.iter().position(|n| n == "2024 Praia/Dia 1/foto10.jpg").expect("foto10");
    check(i2 < i10, "foto2 antes de foto10");
    check(its.len() == 16, &format!("16 arquivos de mídia achados, achou {}: {nomes:?}", its.len()));
    check(its.iter().filter(|i| i.tipo == Tipo::Video).count() == 7, "7 vídeos (inclui o corrompido e o da pasta oculta)");
    let dup = varrer_varios_simples(&[pasta.to_path_buf(), pasta.join("Aniversário")], &mut Estatisticas::default());
    check(dup.len() == 16, "pasta dentro de pasta não duplica");
    let um = varrer_simples(&pasta.join("capa.jpg"));
    check(um.len() == 1 && um[0].tipo == Tipo::Foto, "arquivo solto");
}

/// 84 pastas soltas (como arrastar 84 pastas de uma vez), cada uma com arquivos na raiz e 3
/// níveis de subpasta, mais lixo de outros tipos.
fn teste_muitas_pastas() {
    let base = std::env::temp_dir().join(format!("ciranda-84-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&base);
    let mut raizes = Vec::new();
    for k in 0..84 {
        let r = base.join(format!("Pasta {k:02}"));
        let fundo = r.join("a").join("b").join("c");
        std::fs::create_dir_all(&fundo).unwrap();
        for n in ["x.jpg", "y.MP4", "z.HEIC", "leia.txt", "desktop.ini"] {
            std::fs::write(r.join(n), b"").unwrap();
        }
        std::fs::write(fundo.join("fundo.mov"), b"").unwrap();
        raizes.push(r);
    }
    let mut stats = Estatisticas::default();
    let its = varrer_varios_simples(&raizes, &mut stats);
    check(its.len() == 84 * 4, &format!("84 pastas: esperado {}, achou {}", 84 * 4, its.len()));
    let pastas: HashSet<PathBuf> = its.iter().filter_map(|i| i.caminho.parent().map(Path::to_path_buf)).collect();
    check(pastas.len() == 84 * 2, "pastas com mídia contadas");
    check(stats.pastas_lidas == 84 * 4, &format!("pastas lidas {}", stats.pastas_lidas));
    check(stats.ignorados.get(".txt") == Some(&84) && stats.ignorados.get(".ini") == Some(&84), "outros tipos contados");
    // Profundidade grande, sem estourar a pilha.
    let fundo = base.join("fundo");
    let mut p = fundo.clone();
    for _ in 0..400 {
        p = p.join("d");
    }
    match std::fs::create_dir_all(&p) {
        Ok(()) => {
            std::fs::write(p.join("lá-no-fundo.jpg"), b"").unwrap();
            check(varrer_simples(&fundo).len() == 1, "400 níveis de subpasta");
        }
        // Caminho longo demais para o sistema de arquivos: pula, como na 1.5.1, mas avisa.
        Err(e) => println!("AVISO: 400 níveis de subpasta não testado ({e})"),
    }
    let _ = std::fs::remove_dir_all(&base);
}

fn main() {
    // `cargo test` passa as próprias opções (--nocapture, filtros): só vale um caminho que exista.
    let pasta = std::env::args().skip(1).map(PathBuf::from).find(|p| p.is_dir());
    teste_ordem_natural();
    teste_em_ordem_repetir_nada();
    teste_baralho_sem_repetir();
    teste_aleatorio_distribui();
    teste_repetir_um();
    teste_filtro();
    teste_alternar_aleatorio_mantem_atual();
    teste_anterior_e_ir_para();
    teste_falhou_pula();
    teste_adicionar_e_remover();
    teste_muitas_pastas();
    if let Some(p) = &pasta {
        teste_varredura(p);
    }
    println!("TUDO PASSOU ({} verificações)", OK.load(Ordering::Relaxed));
}
