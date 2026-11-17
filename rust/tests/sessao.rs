//! A sessão (o que a janela da 1.5.1 decide tocar), sem janela nem motor.

use std::path::{Path, PathBuf};

use ciranda::biblioteca::{Estatisticas, Item, Tipo, varrer_varios_simples};
use ciranda::config::Config;
use ciranda::fila::{Filtro, Repetir};
use ciranda::sessao::{Passo, Sessao};

fn item(n: &str, tipo: Tipo) -> Item {
    let ext = if tipo == Tipo::Foto { ".jpg" } else { ".mp4" };
    Item {
        caminho: PathBuf::from(format!("/x/{n}{ext}")),
        tipo,
        raiz: "/x".into(),
        pasta_rel: String::new(),
        nome: format!("{n}{ext}"),
        ext: ext.into(),
        falhou: false,
    }
}

struct Pasta(PathBuf);
impl Drop for Pasta {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn pasta(nome: &str) -> Pasta {
    let p = std::env::temp_dir().join(format!("ciranda-sessao-{nome}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&p);
    std::fs::create_dir_all(&p).unwrap();
    Pasta(p)
}

fn sessao(dados: &Path, cfg: &str) -> Sessao {
    Sessao::nova(Config::de_bytes(cfg.as_bytes()), dados, Some(5))
}

#[test]
fn modos_vem_do_config() {
    let d = pasta("modos");
    let s = sessao(&d.0, r#"{"aleatorio": false, "repetir": "um", "filtro": "videos"}"#);
    assert!(!s.fila.aleatorio);
    assert_eq!(s.fila.repetir, Repetir::Um);
    assert_eq!(s.fila.filtro, Filtro::Videos);
    // Sem config: o padrão da 1.5.1 (aleatório ligado, repetir tudo, tudo).
    let s = Sessao::nova(Config::default(), &d.0, None);
    assert!(s.fila.aleatorio && s.fila.repetir == Repetir::Tudo && s.fila.filtro == Filtro::Tudo);
}

#[test]
fn falhas_seguidas_param_quando_nada_abre() {
    let d = pasta("falhas");
    let mut s = sessao(&d.0, r#"{"aleatorio": false, "repetir": "tudo"}"#);
    s.pastas_abertas = vec![d.0.clone()];
    let p = s.varredura_pronta(vec![item("a", Tipo::Video), item("b", Tipo::Video), item("c", Tipo::Video)], false);
    assert_eq!(p, Passo::Tocar(0));
    assert_eq!(s.arquivo_falhou(), Passo::PularFalho);
    assert_eq!(s.pular_falho(), Passo::Tocar(1));
    assert_eq!(s.arquivo_falhou(), Passo::PularFalho);
    assert_eq!(s.pular_falho(), Passo::Tocar(2));
    assert_eq!(s.arquivo_falhou(), Passo::NenhumAbriu, "3 falhas seguidas numa fila de 3: para");
    assert!(s.fim_da_fila);
    assert!(s.fila.itens.iter().all(|i| i.falhou));
}

#[test]
fn falha_no_meio_pula_e_o_fim_natural_zera_a_conta() {
    let d = pasta("meio");
    let mut s = sessao(&d.0, r#"{"aleatorio": false, "repetir": "nao"}"#);
    let p = s.varredura_pronta(vec![item("a", Tipo::Video), item("b", Tipo::Video), item("c", Tipo::Video)], false);
    assert_eq!(p, Passo::Tocar(0));
    assert_eq!(s.arquivo_falhou(), Passo::PularFalho); // a falhou
    assert_eq!(s.pular_falho(), Passo::Tocar(1));
    assert_eq!(s.video_acabou(), Passo::Tocar(2)); // b tocou até o fim: conta zera
    assert_eq!(s.arquivo_falhou(), Passo::PularFalho);
    assert_eq!(s.pular_falho(), Passo::FimDaFila, "c falha no fim, sem repetir: fim da fila");
    // Tocar/pausar no fim da fila recomeça (pulando o que falhou).
    assert_eq!(s.tocar_sem_item(), Some(Passo::Tocar(1)));
}

#[test]
fn foto_unica_fica_na_tela() {
    let d = pasta("foto");
    let mut s = sessao(&d.0, r#"{"aleatorio": false, "repetir": "tudo"}"#);
    assert_eq!(s.varredura_pronta(vec![item("f", Tipo::Foto)], false), Passo::Tocar(0));
    assert_eq!(s.foto_acabou(), Passo::Nada, "uma foto só, repetir tudo: fica");
    s.ciclar_repetir(); // tudo → um
    s.ciclar_repetir(); // um → nao
    assert_eq!(s.fila.repetir, Repetir::Nao);
    assert_eq!(s.foto_acabou(), Passo::FimDaFila);
}

#[test]
fn filtro_que_esconde_tudo_volta_para_tudo() {
    let d = pasta("filtro");
    let mut s = sessao(&d.0, r#"{"aleatorio": false, "filtro": "videos"}"#);
    let p = s.varredura_pronta(vec![item("f1", Tipo::Foto), item("f2", Tipo::Foto)], false);
    assert_eq!(p, Passo::Tocar(0), "pasta só de fotos com filtro Vídeos: volta para Tudo e toca");
    assert_eq!(s.fila.filtro, Filtro::Tudo);
    assert_eq!(s.cfg.filtro(), Filtro::Tudo);
    // Filtro Vídeos agora: nada passa.
    assert_eq!(s.definir_filtro(Filtro::Videos), Passo::NadaComFiltro);
    assert_eq!(s.item, None);
    assert_eq!(s.definir_filtro(Filtro::Videos), Passo::Nada, "mesmo filtro: nada muda");
    assert_eq!(s.definir_filtro(Filtro::Fotos), Passo::Tocar(0));
}

#[test]
fn juntar_nao_para_o_que_toca_e_abrir_troca() {
    let d = pasta("juntar");
    let a = d.0.join("A");
    let b = d.0.join("B");
    std::fs::create_dir_all(&a).unwrap();
    std::fs::create_dir_all(&b).unwrap();
    for (p, n) in [(&a, "1.jpg"), (&a, "2.jpg"), (&b, "3.mp4")] {
        std::fs::write(p.join(n), b"").unwrap();
    }
    let dados = d.0.join("dados");
    let mut s = sessao(&dados, r#"{"aleatorio": false}"#);
    let carga = s.preparar_carga(&[a.clone(), d.0.join("nao-existe")], false).unwrap();
    assert_eq!(carga.caminhos, vec![a.clone()], "caminho que não existe fica de fora");
    assert!(!carga.juntar);
    let its = varrer_varios_simples(&carga.caminhos, &mut Estatisticas::default());
    assert_eq!(s.varredura_pronta(its, carga.juntar), Passo::Tocar(0));
    // Continuar salvo no config, no disco.
    assert_eq!(Config::carregar(&dados).ultimas_pastas(), vec![a.clone()]);

    let carga = s.preparar_carga(&[b.clone()], true).unwrap();
    assert!(carga.juntar);
    let its = varrer_varios_simples(&carga.caminhos, &mut Estatisticas::default());
    assert_eq!(s.varredura_pronta(its, carga.juntar), Passo::Juntou);
    assert_eq!(s.item, Some(0), "o que toca continua");
    assert_eq!(s.fila.len(), 3);
    assert_eq!(s.pastas_abertas, vec![a.clone(), b.clone()]);
    assert_eq!(Config::carregar(&dados).ultimas_pastas(), vec![a.clone(), b.clone()]);

    // Abrir (sem juntar) troca a fila inteira.
    let carga = s.preparar_carga(&[b.clone()], false).unwrap();
    let its = varrer_varios_simples(&carga.caminhos, &mut Estatisticas::default());
    assert_eq!(s.varredura_pronta(its, carga.juntar), Passo::Tocar(0));
    assert_eq!(s.fila.len(), 1);
    assert_eq!(s.fila.itens[0].nome, "3.mp4");

    // Pasta sem mídia não mexe na fila.
    let vazia = d.0.join("vazia");
    std::fs::create_dir_all(&vazia).unwrap();
    let carga = s.preparar_carga(&[vazia], false).unwrap();
    let its = varrer_varios_simples(&carga.caminhos, &mut Estatisticas::default());
    assert_eq!(s.varredura_pronta(its, carga.juntar), Passo::NenhumaMidia);
    assert_eq!(s.fila.len(), 1);
}

#[test]
fn alternar_aleatorio_e_repetir_vao_para_o_config() {
    let d = pasta("modos2");
    let mut s = sessao(&d.0, r#"{"aleatorio": false, "repetir": "tudo"}"#);
    s.varredura_pronta((0..5).map(|i| item(&format!("v{i}"), Tipo::Video)).collect(), false);
    s.proximo(false);
    let atual = s.fila.indice_atual();
    assert!(s.alternar_aleatorio());
    assert_eq!(s.fila.indice_atual(), atual, "ligar o aleatório mantém o atual");
    assert!(s.cfg.aleatorio());
    assert_eq!(s.ciclar_repetir(), Repetir::Um);
    assert_eq!(s.cfg.repetir(), Repetir::Um);
    s.salvar().unwrap();
    let lido = Config::carregar(&d.0);
    assert!(lido.aleatorio() && lido.repetir() == Repetir::Um);
}

#[test]
fn linhas_do_log_iguais_as_da_151() {
    let d = pasta("log");
    let mut s = sessao(&d.0, "{}");
    s.pastas_abertas = vec![d.0.clone()];
    let mut st = Estatisticas { pastas_lidas: 3, ..Default::default() };
    for e in [".txt", ".ini", ".txt"] {
        *st.ignorados.entry(e.into()).or_insert(0) += 1;
    }
    st.puladas.push("X\\$RECYCLE.BIN".into());
    let l = s.linhas_da_varredura(&[item("a", Tipo::Foto)], &st);
    assert_eq!(l[0], "varredura: 1 pastas abertas, 3 pastas lidas, 1 fotos/vídeos, 3 arquivos de outros tipos");
    assert_eq!(l[1], "  outros tipos (não são foto/vídeo): .txt 2, .ini 1");
    assert_eq!(l[2], "  pulada: X\\$RECYCLE.BIN");
}

/// O próximo depois de um arquivo que falha é escolhido quando os 50 ms passam (como o QTimer da
/// 1.5.1): um filtro trocado nesse meio-tempo já vale.
#[test]
fn pular_falho_usa_o_filtro_de_agora() {
    let d = pasta("pular");
    let mut s = sessao(&d.0, r#"{"aleatorio": false, "repetir": "nao"}"#);
    let p = s.varredura_pronta(vec![item("a", Tipo::Foto), item("b", Tipo::Video), item("c", Tipo::Foto)], false);
    assert_eq!(p, Passo::Tocar(0));
    assert_eq!(s.arquivo_falhou(), Passo::PularFalho);
    s.fila.definir_filtro(Filtro::Fotos); // a tecla 2 chega antes dos 50 ms
    assert_eq!(s.pular_falho(), Passo::Tocar(2), "o vídeo b já não aparece");
}

/// Juntar confere os repetidos contra a lista de antes (1.5.1: `c not in self.pastas_abertas`
/// com a lista velha), e caminho com barra no fim vira o mesmo do abspath.
#[test]
fn juntar_repetido_e_barra_no_fim_como_a_151() {
    let d = pasta("juntar2");
    let (a, b) = (d.0.join("A"), d.0.join("B"));
    for p in [&a, &b] {
        std::fs::create_dir_all(p).unwrap();
        std::fs::write(p.join("x.jpg"), b"").unwrap();
    }
    let dados = d.0.join("dados");
    let mut s = sessao(&dados, r#"{"aleatorio": false}"#);
    let com_barra = PathBuf::from(format!("{}\\", a.display()));
    let carga = s.preparar_carga(&[com_barra], false).unwrap();
    // Como texto: a igualdade de Path ignora a barra do fim, a 1.5.1 (que compara texto) não.
    assert_eq!(carga.caminhos[0].as_os_str(), a.as_os_str(), "barra do fim sai, como no os.path.abspath");
    let its = varrer_varios_simples(&carga.caminhos, &mut Estatisticas::default());
    s.varredura_pronta(its, false);
    let texto = std::fs::read_to_string(dados.join("config.json")).unwrap();
    let esperado = serde_json::to_string(&a.display().to_string()).unwrap();
    assert!(texto.contains(&format!("    {esperado}\r\n")), "Continuar gravado sem a barra: {texto}");
    s.preparar_carga(&[b.clone(), b.clone(), a.clone()], true).unwrap();
    assert_eq!(s.pastas_abertas, vec![a.clone(), b.clone(), b.clone()]);
}
