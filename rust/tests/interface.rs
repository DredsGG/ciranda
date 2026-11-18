//! A interface inteira sem janela (REGRA 13): o backend de teste do Slint desenha em memória, o
//! motor é o `MotorFalso` e a plataforma é o `Registro` (nada abre, nada toca, a área de
//! transferência não muda). Cada caso clica nos botões de verdade (`mock_single_click` no centro
//! do elemento), aperta teclas pela janela do Slint e anda com o tempo de mentira.
//!
//! Um processo só (o backend do Slint só pode ser iniciado uma vez): `harness = false`.
//! Imprime "TUDO PASSOU (N verificações)" ou a lista do que falhou.

use std::cell::RefCell;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::Arc;
use std::time::Duration;

use ciranda::config::Config;
use ciranda::fila::Filtro;
use ciranda::motor::{Evento, MotorFalso, Reacao, Valor};
use ciranda::plataforma::Registro;
use ciranda::player::{HEIC_TENTATIVAS, Opcoes, Player};
use ciranda::sessao::Sessao;
use ciranda::textos::{t, tf};
use ciranda::ui::Camada;
use i_slint_backend_testing::{ElementHandle, get_mocked_time, mock_elapsed_time};
use slint::platform::{Key, PointerEventButton, WindowEvent};
use slint::{ComponentHandle, LogicalSize, Model, SharedString};

thread_local! {
    static FALHAS: RefCell<Vec<String>> = const { RefCell::new(Vec::new()) };
    static CONTA: RefCell<usize> = const { RefCell::new(0) };
}

fn conferir(caso: &str, nome: &str, ok: bool, detalhe: impl FnOnce() -> String) {
    CONTA.with(|c| *c.borrow_mut() += 1);
    if !ok {
        let d = detalhe();
        println!("  [FALHOU] {caso}: {nome} — {d}");
        FALHAS.with(|f| f.borrow_mut().push(format!("{caso}: {nome}")));
    }
}

macro_rules! ok {
    ($caso:expr, $nome:expr, $cond:expr) => {
        conferir($caso, $nome, $cond, || String::new())
    };
    ($caso:expr, $nome:expr, $cond:expr, $($d:tt)+) => {
        conferir($caso, $nome, $cond, || format!($($d)+))
    };
}

/// Mídia de mentira (o motor é falso: só o nome e a extensão contam).
fn pasta_de_midia(nome: &str, arquivos: &[&str]) -> PathBuf {
    let base = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("interface").join(nome);
    let _ = std::fs::remove_dir_all(&base);
    for a in arquivos {
        let p = base.join(a);
        std::fs::create_dir_all(p.parent().unwrap()).unwrap();
        std::fs::write(&p, b"x").unwrap();
    }
    base
}

struct Banco {
    caso: &'static str,
    p: Rc<Player>,
    ui: Camada,
    motor: Rc<MotorFalso>,
    reg: Rc<Registro>,
    log: Rc<RefCell<Vec<String>>>,
    dados: PathBuf,
}

impl Banco {
    fn novo(caso: &'static str, cfg: &str, teste: bool) -> Banco {
        let dados = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("interface").join(format!("dados-{caso}"));
        let _ = std::fs::remove_dir_all(&dados);
        std::fs::create_dir_all(&dados).unwrap();
        let ui = Camada::new().unwrap();
        ui.window().set_size(LogicalSize::new(1180.0, 720.0));
        ui.show().unwrap();
        let motor = Rc::new(MotorFalso::novo());
        let reg = Rc::new(Registro::novo());
        let log = Rc::new(RefCell::new(Vec::new()));
        let l = log.clone();
        let sessao = Sessao::nova(Config::de_bytes(cfg.as_bytes()), &dados, Some(7));
        let p = Player::novo(
            ui.clone_strong(),
            motor.clone(),
            reg.clone(),
            sessao,
            Rc::new(|| Duration::from_millis(get_mocked_time())),
            Box::new(move |s: &str| l.borrow_mut().push(s.to_string())),
            Arc::new(|| {}),
            Opcoes { teste, sair_no_fim: false },
        );
        ui.invoke_focar_janela();
        p.reenviar_palco(); // o executável manda o palco ao mostrar a janela
        Banco { caso, p, ui, motor, reg, log, dados }
    }

    /// Lê o correio e os eventos do motor até parar de chegar coisa.
    fn girar(&self) {
        for _ in 0..20 {
            let n = self.p.drenar_correio();
            let tinha = !self.motor.eventos.borrow().is_empty();
            self.p.drenar_motor();
            if n == 0 && !tinha {
                break;
            }
        }
    }

    /// Anda o tempo de mentira em passos de 10 ms (timers do Slint disparam no caminho).
    fn passar(&self, ms: u64) {
        let mut feito = 0;
        while feito < ms {
            let d = (ms - feito).min(10);
            mock_elapsed_time(Duration::from_millis(d));
            self.girar();
            feito += d;
        }
    }

    /// Espera a varredura (thread de verdade) terminar.
    fn esperar_varredura(&self) {
        for _ in 0..500 {
            self.girar();
            if !self.p.lendo() {
                break;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        self.girar();
    }

    fn el(&self, id: &str) -> Option<ElementHandle> {
        ElementHandle::find_by_element_id(&self.ui, id).next()
    }

    fn clicar(&self, id: &str) -> bool {
        match self.el(id) {
            Some(e) => {
                e.mock_single_click(PointerEventButton::Left);
                self.girar();
                true
            }
            None => {
                ok!(self.caso, &format!("achou {id}"), false, "elemento não existe");
                false
            }
        }
    }

    fn rotulo(&self, r: &str) -> Vec<ElementHandle> {
        ElementHandle::find_by_accessible_label(&self.ui, r).filter(|e| e.type_name().as_deref() != Some("Text")).collect()
    }

    /// Clica na linha de menu (ou botão) com este rótulo.
    fn clicar_rotulo(&self, r: &str) -> bool {
        let v = self.rotulo(r);
        match v.last() {
            Some(e) => {
                e.mock_single_click(PointerEventButton::Left);
                self.girar();
                true
            }
            None => {
                ok!(self.caso, &format!("achou o rótulo {r:?}"), false, "não existe");
                false
            }
        }
    }

    fn tecla(&self, texto: &str) {
        let t: SharedString = texto.into();
        self.ui.window().dispatch_event(WindowEvent::KeyPressed { text: t.clone() });
        self.ui.window().dispatch_event(WindowEvent::KeyReleased { text: t });
        self.girar();
    }

    fn tecla_k(&self, k: Key) {
        self.tecla(&SharedString::from(k));
    }

    fn com(&self, modif: Key, texto: &str) {
        let m: SharedString = modif.into();
        self.ui.window().dispatch_event(WindowEvent::KeyPressed { text: m.clone() });
        self.tecla(texto);
        self.ui.window().dispatch_event(WindowEvent::KeyReleased { text: m });
    }

    fn abrir(&self, pasta: &Path) {
        self.reg.responder_pasta(Some(pasta.to_path_buf()));
        // Tela de início: o botão grande; com fila: a pílula Abrir da fila.
        self.clicar(if self.ui.get_vazio() { "Vazio::b-abrir" } else { "Camada::p-abrir" });
        self.esperar_varredura();
    }

    fn carregados(&self) -> Vec<String> {
        self.motor
            .carregados()
            .iter()
            .map(|c| Path::new(c).file_name().unwrap().to_string_lossy().into_owned())
            .collect()
    }
    fn ultimo(&self) -> String {
        self.carregados().last().cloned().unwrap_or_default()
    }
    fn tem_log(&self, s: &str) -> bool {
        self.log.borrow().iter().any(|l| l.contains(s))
    }
    fn cmd(&self, s: &str) -> bool {
        self.motor.linhas().iter().any(|l| l == s)
    }
    fn pausado(&self) -> bool {
        self.motor.prop("pause").as_deref() == Some("yes")
    }
    fn nomes_da_lista(&self) -> Vec<String> {
        let m = self.ui.get_fila();
        (0..m.row_count()).map(|i| m.row_data(i).unwrap().nome.to_string()).collect()
    }
}

impl Drop for Banco {
    fn drop(&mut self) {
        let _ = self.ui.hide();
    }
}

const CFG_ORDEM: &str = r#"{"aleatorio": false, "repetir": "tudo", "segundos_foto": 5, "volume": 50}"#;

fn caso_inicio_e_barra() {
    let caso = "barra";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    ok!(caso, "começa na tela de início", b.ui.get_vazio());
    ok!(caso, "barra diz nada tocando", b.ui.get_nome() == t("nada_tocando"), "{}", b.ui.get_nome());
    ok!(caso, "fila vazia no resumo", b.ui.get_resumo() == t("fila_vazia"));
    ok!(caso, "sem Continuar sem histórico", b.ui.get_continuar_txt().is_empty());

    let pasta = pasta_de_midia("barra", &["a1.jpg", "a2.jpg", "b.mp4", "sub/c.png"]);
    b.abrir(&pasta);
    let pedidos = b.reg.pedidos_de("escolher-pasta");
    ok!(caso, "Abrir pasta pede a janela de escolher (só registrada)", pedidos.len() == 1, "{pedidos:?}");
    ok!(caso, "tocou o primeiro na ordem natural", b.carregados() == ["a1.jpg"], "{:?}", b.carregados());
    ok!(caso, "saiu da tela de início", !b.ui.get_vazio());
    ok!(caso, "nome na barra", b.ui.get_nome() == "a1.jpg");
    ok!(caso, "info com a posição", b.ui.get_info().contains(&tf("n_de_total", &[("n", &1), ("total", &4)])), "{}", b.ui.get_info());
    ok!(caso, "título da janela", *b.reg.titulo_atual.borrow() == "a1.jpg — Ciranda", "{}", b.reg.titulo_atual.borrow());
    ok!(caso, "contagem da fila", b.ui.get_contagem() == "4");
    ok!(caso, "lista com os 4", b.nomes_da_lista() == ["a1.jpg", "a2.jpg", "b.mp4", "c.png"], "{:?}", b.nomes_da_lista());
    ok!(caso, "resumo com fotos e vídeos", b.ui.get_resumo().contains(&tf("resumo", &[("fila", &"4"), ("fotos", &"3"), ("videos", &"1")])));
    ok!(caso, "botão mostra pausar", b.ui.get_tocando());
    let cfg = Config::carregar(&b.dados);
    ok!(caso, "Continuar salvo no config", cfg.ultimas_pastas() == [pasta.clone()], "{:?}", cfg.ultimas_pastas());

    b.clicar("Camada::b-play");
    ok!(caso, "play pausa", b.pausado() && !b.ui.get_tocando());
    b.clicar("Camada::b-play");
    ok!(caso, "play despausa", !b.pausado() && b.ui.get_tocando());
    b.clicar("Camada::b-prox");
    ok!(caso, "próximo", b.ultimo() == "a2.jpg", "{:?}", b.carregados());
    b.clicar("Camada::b-ant");
    ok!(caso, "anterior", b.ultimo() == "a1.jpg");
    b.clicar("Camada::b-alea");
    ok!(caso, "aleatório liga", b.ui.get_aleatorio() && b.p.sessao.borrow().fila.aleatorio);
    ok!(caso, "aleatório avisa por cima do vídeo", b.cmd(&format!("show-text {} 1300 1", t("osd_aleatorio"))));
    b.clicar("Camada::b-alea");
    ok!(caso, "aleatório desliga", !b.ui.get_aleatorio());
    b.clicar("Camada::b-rep");
    ok!(caso, "repetir: tudo → um", b.ui.get_repetir() == "um");
    b.clicar("Camada::b-rep");
    ok!(caso, "repetir: um → não", b.ui.get_repetir() == "nao");
    b.clicar("Camada::b-rep");
    ok!(caso, "repetir: não → tudo", b.ui.get_repetir() == "tudo");
    b.clicar("Camada::b-vol");
    ok!(caso, "mudo liga (motor e tela)", b.ui.get_mudo() && b.motor.prop("mute").as_deref() == Some("yes"));
    b.clicar("Camada::b-vol");
    ok!(caso, "mudo desliga", !b.ui.get_mudo() && b.motor.prop("mute").as_deref() == Some("no"));
    b.clicar("Camada::b-painel");
    ok!(caso, "fila esconde", !b.ui.get_painel_visivel());
    b.clicar("Camada::b-painel");
    ok!(caso, "fila volta", b.ui.get_painel_visivel());
    b.clicar("Camada::b-painel");
    b.clicar("Camada::b-esq");
    ok!(caso, "clique no nome mostra a fila escondida", b.ui.get_painel_visivel() && b.tem_log("botão: mostrar-na-fila"));

    // Filtros da fila lateral.
    b.clicar("Camada::f-videos");
    ok!(caso, "filtro Vídeos toca o vídeo", b.ultimo() == "b.mp4" && b.ui.get_filtro() == "videos");
    ok!(caso, "lista só com o vídeo", b.nomes_da_lista() == ["b.mp4"], "{:?}", b.nomes_da_lista());
    b.clicar("Camada::f-fotos");
    ok!(caso, "filtro Fotos sai do vídeo", b.ultimo() == "a1.jpg" && b.nomes_da_lista().len() == 3);
    b.clicar("Camada::f-tudo");
    ok!(caso, "filtro Tudo continua na foto", b.ultimo() == "a1.jpg" && b.nomes_da_lista().len() == 4);
    let cfg_tela = b.p.sessao.borrow().cfg.para_texto();
    ok!(caso, "filtro guardado no config", cfg_tela.contains("\"filtro\": \"tudo\""));
}

fn caso_foto_e_tempo() {
    let caso = "foto";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    let pasta = pasta_de_midia("foto", &["1.jpg", "2.jpg", "3.jpg"]);
    b.abrir(&pasta);
    b.passar(4900);
    ok!(caso, "foto ainda na tela aos 4,9 s", b.carregados() == ["1.jpg"], "{:?}", b.carregados());
    ok!(caso, "barra da foto anda", b.ui.get_progresso() > 0.9, "{}", b.ui.get_progresso());
    ok!(caso, "tempo da foto na barra", b.ui.get_tempo_txt() == "0:04" && b.ui.get_total_txt() == "0:05", "{} {}", b.ui.get_tempo_txt(), b.ui.get_total_txt());
    b.passar(200);
    ok!(caso, "passa aos 5 s", b.ultimo() == "2.jpg", "{:?}", b.carregados());
    ok!(caso, "busca desligada em foto", !b.ui.get_busca_ativa());
    b.passar(2000);
    b.tecla(" ");
    b.passar(10_000);
    ok!(caso, "pausada a foto não passa", b.ultimo() == "2.jpg");
    b.tecla(" ");
    b.passar(2700);
    ok!(caso, "despausada continua de onde parou (falta 3 s)", b.ultimo() == "2.jpg", "{:?}", b.carregados());
    b.passar(400);
    ok!(caso, "e passa", b.ultimo() == "3.jpg", "{:?}", b.carregados());

    // Menu do tempo da foto.
    b.clicar("Camada::p-foto");
    ok!(caso, "menu do tempo abre", b.ui.get_menu_visivel());
    let itens: Vec<String> = { let m = b.ui.get_menu_itens(); (0..m.row_count()).map(|i| m.row_data(i).unwrap().texto.to_string()).collect() };
    ok!(caso, "9 tempos prontos e Outro tempo", ["2 s", "3 s", "5 s", "8 s", "10 s", "15 s", "20 s", "30 s", "1 min"].iter().all(|x| itens.iter().any(|i| i == x)) && itens.iter().any(|i| *i == t("outro_tempo")), "{itens:?}");
    b.clicar_rotulo("10 s");
    ok!(caso, "10 s escolhido", !b.ui.get_menu_visivel() && b.ui.get_foto_longo().contains("10 s"), "{}", b.ui.get_foto_longo());
    ok!(caso, "aviso do tempo", b.cmd(&format!("show-text {} 1300 1", tf("osd_cada_foto", &[("v", &10)]))));
    b.clicar("Camada::p-foto");
    b.clicar_rotulo(&t("outro_tempo"));
    ok!(caso, "Outro tempo abre a caixa com número", b.ui.get_caixa_visivel() && b.ui.get_caixa_numero() && b.ui.get_caixa_valor() == "10");
    b.ui.set_caixa_valor("42".into());
    b.clicar_rotulo("OK");
    ok!(caso, "42 s pela caixa", !b.ui.get_caixa_visivel() && b.ui.get_foto_longo().contains("42 s"), "{}", b.ui.get_foto_longo());
    b.clicar("Camada::p-foto");
    let outro = tf("outro_tempo_agora", &[("tempo", &"42 s")]);
    ok!(caso, "o menu mostra o tempo fora da lista", b.rotulo(&outro).len() == 1, "{outro:?} {:?}", { let m = b.ui.get_menu_itens(); (0..m.row_count()).map(|i| m.row_data(i).unwrap().texto.to_string()).collect::<Vec<_>>() });
    b.tecla_k(Key::Escape);
    ok!(caso, "Esc fecha o menu", !b.ui.get_menu_visivel());
    b.tecla("+");
    ok!(caso, "+ soma 1 s", b.ui.get_foto_curto().starts_with("43 s"), "{}", b.ui.get_foto_curto());
    b.tecla("-");
    b.tecla("-");
    ok!(caso, "- tira 1 s", b.ui.get_foto_curto().starts_with("41 s"));
    let cfg = b.p.sessao.borrow().cfg.segundos_foto();
    ok!(caso, "tempo no config", cfg == 41, "{cfg}");

    // Repetir um: a foto fica, a barra mostra ∞.
    b.tecla("r");
    let antes = b.carregados().len();
    b.passar(60_000);
    ok!(caso, "repetir um segura a foto", b.ui.get_repetir() == "um" && b.ui.get_total_txt() == "∞" && b.carregados().len() == antes, "{} {:?}", b.ui.get_total_txt(), b.carregados());
}

fn caso_video() {
    let caso = "video";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    let pasta = pasta_de_midia("video", &["a.mp4", "b.mkv", "c.gif"]);
    b.abrir(&pasta);
    ok!(caso, "vídeo sem repetir um toca uma vez", b.cmd("set loop-file no"));
    b.motor.definir("duration", "100");
    b.motor.definir("time-pos", "25");
    b.passar(150);
    ok!(caso, "tempo e total na barra", b.ui.get_tempo_txt() == "0:25" && b.ui.get_total_txt() == "1:40", "{} {}", b.ui.get_tempo_txt(), b.ui.get_total_txt());
    ok!(caso, "barra de busca na posição", (b.ui.get_progresso() - 0.25).abs() < 0.01 && b.ui.get_busca_ativa());
    b.clicar("Camada::t-total");
    b.passar(150);
    ok!(caso, "clique no total mostra o que falta", b.ui.get_total_txt() == "-1:15", "{}", b.ui.get_total_txt());
    b.el("Camada::busca-barra").unwrap().mock_single_click(PointerEventButton::Left);
    b.girar();
    ok!(caso, "clique na barra de busca vai para o meio", b.motor.linhas().iter().any(|l| l.starts_with("seek 50") && l.ends_with("absolute-percent")), "{:?}", b.motor.linhas().iter().filter(|l| l.starts_with("seek")).collect::<Vec<_>>());
    b.tecla_k(Key::RightArrow);
    ok!(caso, "→ pula 5 s", b.cmd("seek 5 relative"));
    b.com(Key::Shift, &SharedString::from(Key::LeftArrow));
    ok!(caso, "Shift+← volta 30 s", b.cmd("seek -30 relative"));
    b.clicar("Camada::b-ant");
    ok!(caso, "anterior com mais de 3 s volta ao começo", b.cmd("seek 0 absolute") && b.carregados().len() == 1);
    // Fim natural do vídeo.
    b.passar(400);
    b.motor.definir("eof-reached", "yes");
    b.motor.emitir(Evento::Propriedade { id: 2, nome: "eof-reached".into(), valor: Valor::Sim(true) });
    b.girar();
    ok!(caso, "fim do vídeo passa para o próximo", b.ultimo() == "b.mkv", "{:?}", b.carregados());
    b.tecla("n");
    ok!(caso, "GIF anima em laço", b.ultimo() == "c.gif" && b.motor.linhas().iter().rev().find(|l| l.starts_with("set loop-file")).map(|s| s.as_str()) == Some("set loop-file inf"));
    b.tecla("r");
    b.tecla("p");
    ok!(caso, "vídeo em repetir um fica em laço", b.ultimo() == "b.mkv" && b.motor.linhas().iter().rev().find(|l| l.starts_with("set loop-file")).map(|s| s.as_str()) == Some("set loop-file inf"));

    // Volume pela roda e pelas setas.
    let v0 = b.ui.get_volume();
    b.tecla_k(Key::UpArrow);
    ok!(caso, "↑ sobe o volume", b.ui.get_volume() == v0 + 5 && b.motor.prop("volume") == Some((v0 + 5).to_string()));
    b.tecla_k(Key::DownArrow);
    b.tecla_k(Key::DownArrow);
    ok!(caso, "↓ desce", b.ui.get_volume() == v0 - 5);
    ok!(caso, "aviso de volume por cima do vídeo", b.cmd(&format!("show-text {} 1300 1", tf("osd_volume", &[("v", &(v0 - 5))]))));
    if let Some(palco) = b.el("Camada::tela") {
        palco.scroll(0.0, 120.0);
        b.girar();
        ok!(caso, "roda no vídeo sobe o volume", b.ui.get_volume() == v0, "{}", b.ui.get_volume());
    } else {
        ok!(caso, "achou o palco", false);
    }
    b.tecla("m");
    ok!(caso, "M deixa mudo", b.ui.get_mudo());
    b.tecla_k(Key::UpArrow);
    ok!(caso, "subir o volume tira do mudo (como a 1.5.1)", !b.ui.get_mudo());
}

fn caso_palco_e_tela_cheia() {
    let caso = "tela-cheia";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    let pasta = pasta_de_midia("tela", &["a.mp4", "b.mp4"]);
    b.abrir(&pasta);
    let palco = b.reg.palco.get();
    ok!(caso, "o vídeo vai para o palco (sem a fila e a barra)", palco.2 > 600 && palco.2 < 1180 && palco.3 > 400 && palco.3 < 720, "{palco:?}");
    let tela = b.el("Camada::tela").unwrap();
    tela.mock_single_click(PointerEventButton::Left);
    b.passar(100);
    ok!(caso, "um clique ainda não pausa (espera o segundo)", !b.pausado());
    b.passar(200);
    ok!(caso, "um clique no vídeo pausa depois de 230 ms", b.pausado());
    b.passar(600); // longe do clique anterior (senão o Windows já conta como duplo)
    tela.mock_single_click(PointerEventButton::Left);
    tela.mock_single_click(PointerEventButton::Left);
    b.girar();
    b.passar(300);
    ok!(caso, "dois cliques: tela cheia, sem pausar de novo", b.reg.em_tela_cheia_registrada() && b.pausado(), "{:?} pausado={} {:?}", b.reg.pedidos_de("tela-cheia"), b.pausado(), b.motor.linhas().iter().filter(|l| l.contains("pause")).collect::<Vec<_>>());
    ok!(caso, "a fila some na tela cheia", !b.ui.get_painel_visivel() && b.ui.get_tela_cheia());
    let palco_cheio = b.reg.palco.get();
    ok!(caso, "na tela cheia o vídeo cabe na janela", palco_cheio.1 + palco_cheio.3 <= 720 && palco_cheio.2 == 1180, "{palco_cheio:?}");
    b.passar(2600);
    ok!(caso, "controles somem em 2,5 s", !b.ui.get_controles_visiveis());
    b.girar();
    let palco_sem_barra = b.reg.palco.get();
    ok!(caso, "sem a barra o vídeo cresce", palco_sem_barra.3 > palco_cheio.3, "{palco_cheio:?} → {palco_sem_barra:?}");
    b.reg.cursor_pos.set(Some((10, 10)));
    b.passar(200);
    ok!(caso, "mexer o mouse traz os controles", b.ui.get_controles_visiveis());
    b.reg.cursor_na_barra.set(true);
    b.passar(3000);
    ok!(caso, "mouse parado sobre a barra: ficam", b.ui.get_controles_visiveis());
    b.reg.cursor_na_barra.set(false);
    b.passar(2600);
    ok!(caso, "saiu da barra: somem", !b.ui.get_controles_visiveis());
    b.tecla("l");
    ok!(caso, "L mostra a fila na tela cheia", b.ui.get_painel_visivel());
    b.tecla("l");
    b.tecla_k(Key::Escape);
    ok!(caso, "Esc sai da tela cheia", !b.ui.get_tela_cheia() && !b.reg.em_tela_cheia_registrada());
    ok!(caso, "a fila volta como estava", b.ui.get_painel_visivel() && b.ui.get_controles_visiveis());
    let cfg = b.p.sessao.borrow().cfg.painel();
    ok!(caso, "fila na tela cheia não mexe no config", cfg);
    b.tecla("f");
    ok!(caso, "F entra", b.ui.get_tela_cheia());
    b.tecla("e");
    ok!(caso, "E sai da tela cheia e mostra no Explorer (só registrado)", !b.ui.get_tela_cheia() && b.reg.pedidos_de("explorer").len() == 1, "{:?}", b.reg.pedidos_de("explorer"));
    b.tecla_k(Key::Return);
    ok!(caso, "Enter alterna a tela cheia", b.ui.get_tela_cheia());
    b.tecla_k(Key::F11);
    ok!(caso, "F11 alterna", !b.ui.get_tela_cheia());
    // Menu do vídeo (botão direito).
    tela.mock_single_click(PointerEventButton::Right);
    b.girar();
    ok!(caso, "botão direito abre o menu do vídeo", b.ui.get_menu_visivel() && b.ui.get_menu_jeito() == "ponteiro");
    b.tecla("n");
    ok!(caso, "com menu aberto as teclas não valem", b.carregados().len() == 1);
    b.clicar_rotulo(&t("proximo"));
    ok!(caso, "Próximo pelo menu do vídeo", b.ultimo() == "b.mp4" && !b.ui.get_menu_visivel());
    tela.mock_single_click(PointerEventButton::Right);
    b.girar();
    b.clicar_rotulo(&t("tela_cheia"));
    ok!(caso, "Tela cheia pelo menu", b.ui.get_tela_cheia());
    tela.mock_single_click(PointerEventButton::Right);
    b.girar();
    ok!(caso, "na tela cheia o menu diz Sair", b.rotulo(&t("sair_tela_cheia")).len() == 1);
    b.clicar_rotulo(&t("sair_tela_cheia"));
    ok!(caso, "e sai", !b.ui.get_tela_cheia());
}

fn caso_menus_e_limpar() {
    let caso = "menus";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    b.clicar("Camada::b-pastas");
    ok!(caso, "menu de pastas abre sem fila", b.ui.get_menu_visivel());
    let explorer = b.rotulo(&t("mostrar_explorer"));
    ok!(caso, "sem arquivo, Mostrar no Explorer apagado", explorer.len() == 1 && explorer[0].accessible_enabled() == Some(false), "{} {:?}", explorer.len(), explorer.iter().map(|e| (e.accessible_enabled(), e.type_name(), e.id())).collect::<Vec<_>>());
    for k in ["procurar_atualizacao", "como_usar", "restaurar"] {
        let e = b.rotulo(&t(k));
        ok!(caso, &format!("{k}: aparece apagado (fases 4 e 5)"), e.len() == 1 && e[0].accessible_enabled() == Some(false), "{} {:?}", e.len(), e.iter().map(|e| (e.accessible_enabled(), e.type_name(), e.id())).collect::<Vec<_>>());
    }
    b.clicar_rotulo(&t("como_usar"));
    ok!(caso, "linha apagada não faz nada", b.ui.get_menu_visivel());
    let pasta_menus = pasta_de_midia("menus", &["x.jpg", "y.mp4"]);
    b.reg.responder_pasta(Some(pasta_menus.clone()));
    b.clicar_rotulo(&t("abrir_pasta"));
    b.esperar_varredura();
    ok!(caso, "Abrir pasta pelo menu", b.ultimo() == "x.jpg");
    b.reg.responder_arquivos(vec![pasta_de_midia("menus2", &["z.png"]).join("z.png")]);
    b.clicar("Camada::b-pastas");
    b.clicar_rotulo(&t("abrir_arquivos"));
    b.esperar_varredura();
    ok!(caso, "Abrir arquivos troca a fila", b.ultimo() == "z.png" && b.nomes_da_lista() == ["z.png"]);
    let ult = b.p.sessao.borrow().cfg.ultimas_pastas();
    ok!(caso, "arquivos soltos não mexem no Continuar", ult == [pasta_menus.clone()], "{ult:?}");
    b.clicar("Camada::b-pastas");
    let cont = tf("continuar_1", &[("n", &1)]);
    ok!(caso, "Continuar no menu", b.rotulo(&cont).len() == 1);
    b.clicar_rotulo(&cont);
    b.esperar_varredura();
    ok!(caso, "Continuar reabre a última pasta", b.nomes_da_lista() == ["x.jpg", "y.mp4"]);
    b.reg.responder_pasta(Some(pasta_de_midia("menus3", &["w.jpg"])));
    b.clicar("Camada::p-juntar");
    b.esperar_varredura();
    ok!(caso, "Juntar pasta soma sem trocar o que toca", b.nomes_da_lista().len() == 3 && b.ultimo() == "x.jpg", "{:?}", b.nomes_da_lista());
    ok!(caso, "Juntar pede a janela com o título certo", b.reg.pedidos_de("escolher-pasta").last().is_some_and(|p| p.contains(&t("dlg_adicionar_pasta"))));
    b.clicar("Camada::b-pastas");
    b.clicar_rotulo(&t("mostrar_explorer"));
    ok!(caso, "Mostrar no Explorer (registrado, nada abre)", b.reg.pedidos_de("explorer").len() == 1);

    // Limpar fila pela pílula.
    b.clicar("Camada::p-limpar");
    ok!(caso, "pílula Limpar abre o menu", b.ui.get_menu_visivel());
    b.motor.esquecer_comandos();
    b.clicar_rotulo(&t("limpar_fila"));
    ok!(caso, "Limpar fila volta à tela de início", b.ui.get_vazio() && b.nomes_da_lista().is_empty() && b.cmd("stop"));
    ok!(caso, "título volta", *b.reg.titulo_atual.borrow() == "Ciranda");
    ok!(caso, "Continuar continua lá", !b.ui.get_continuar_txt().is_empty());
    // Limpar tudo: pergunta antes.
    b.clicar("Camada::p-limpar");
    b.clicar_rotulo(&t("limpar_tudo"));
    ok!(caso, "Limpar tudo pergunta", b.ui.get_caixa_visivel() && b.ui.get_caixa_texto() == t("limpar_tudo_confirma"));
    b.tecla_k(Key::Escape);
    ok!(caso, "Esc é Não", !b.ui.get_caixa_visivel() && !b.ui.get_continuar_txt().is_empty());
    b.clicar("Camada::p-limpar");
    b.clicar_rotulo(&t("limpar_tudo"));
    b.clicar_rotulo(&t("sim"));
    ok!(caso, "Sim limpa o Continuar", b.ui.get_continuar_txt().is_empty() && b.ui.get_status() == t("limpos"));
    let cfg = Config::carregar(&b.dados);
    ok!(caso, "e grava o config", cfg.ultimas_pastas().is_empty());
}

fn caso_lista() {
    let caso = "lista";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    let pasta = pasta_de_midia("lista", &["a.jpg", "b.jpg", "c.jpg", "d.jpg", "sub/e.mp4"]);
    b.abrir(&pasta);
    let linha = |n: &str| b.rotulo(n).into_iter().next().unwrap();
    linha("b.jpg").mock_single_click(PointerEventButton::Left);
    b.girar();
    let sel = |b: &Banco| { let m = b.ui.get_fila(); (0..m.row_count()).filter(|&i| m.row_data(i).unwrap().selecionada).map(|i| m.row_data(i).unwrap().nome.to_string()).collect::<Vec<_>>() };
    ok!(caso, "clique seleciona", sel(&b) == ["b.jpg"], "{:?}", sel(&b));
    ok!(caso, "clique não toca", b.carregados().len() == 1);
    let m: SharedString = Key::Shift.into();
    b.ui.window().dispatch_event(WindowEvent::KeyPressed { text: m.clone() });
    linha("d.jpg").mock_single_click(PointerEventButton::Left);
    b.ui.window().dispatch_event(WindowEvent::KeyReleased { text: m });
    b.girar();
    ok!(caso, "Shift+clique pega o intervalo", sel(&b) == ["b.jpg", "c.jpg", "d.jpg"], "{:?}", sel(&b));
    let m: SharedString = Key::Control.into();
    b.ui.window().dispatch_event(WindowEvent::KeyPressed { text: m.clone() });
    linha("c.jpg").mock_single_click(PointerEventButton::Left);
    b.ui.window().dispatch_event(WindowEvent::KeyReleased { text: m });
    b.girar();
    ok!(caso, "Ctrl+clique tira um", sel(&b) == ["b.jpg", "d.jpg"], "{:?}", sel(&b));
    linha("c.jpg").mock_single_click(PointerEventButton::Left);
    linha("c.jpg").mock_single_click(PointerEventButton::Left);
    b.girar();
    ok!(caso, "dois cliques tocam", b.ultimo() == "c.jpg", "{:?}", b.carregados());
    let atual = { let m = b.ui.get_fila(); (0..m.row_count()).filter(|&i| m.row_data(i).unwrap().atual).map(|i| m.row_data(i).unwrap().nome.to_string()).collect::<Vec<_>>() };
    ok!(caso, "a linha atual é a que toca", atual == ["c.jpg"], "{atual:?}");
    ok!(caso, "pasta da linha (subpasta)", b.ui.get_fila().row_data(4).unwrap().pasta == "sub");

    // Menu da lista.
    linha("a.jpg").mock_single_click(PointerEventButton::Right);
    b.girar();
    ok!(caso, "botão direito abre o menu da lista", b.ui.get_menu_visivel() && sel(&b) == ["a.jpg"]);
    b.clicar_rotulo(&t("copiar_caminho"));
    let copiado = b.reg.area_de_transferencia.borrow().clone();
    ok!(caso, "Copiar caminho (registrado, a área de transferência do Windows não muda)", copiado == Some(pasta.join("a.jpg").to_string_lossy().into_owned()), "{copiado:?}");
    linha("a.jpg").mock_single_click(PointerEventButton::Right);
    b.girar();
    b.clicar_rotulo(&t("mostrar_explorer"));
    ok!(caso, "Mostrar no Explorer da linha", b.reg.pedidos_de("explorer").last().is_some_and(|p| p.ends_with("a.jpg")));
    linha("a.jpg").mock_single_click(PointerEventButton::Right);
    b.girar();
    b.clicar_rotulo(&t("tocar_agora"));
    ok!(caso, "Tocar agora", b.ultimo() == "a.jpg");
    // Tirar dois, um deles tocando.
    linha("a.jpg").mock_single_click(PointerEventButton::Left);
    let m: SharedString = Key::Control.into();
    b.ui.window().dispatch_event(WindowEvent::KeyPressed { text: m.clone() });
    linha("b.jpg").mock_single_click(PointerEventButton::Left);
    b.ui.window().dispatch_event(WindowEvent::KeyReleased { text: m });
    linha("b.jpg").mock_single_click(PointerEventButton::Right);
    b.girar();
    ok!(caso, "Tirar 2 da fila no menu", b.rotulo(&tf("tirar_n_da_fila", &[("n", &2)])).len() == 1);
    b.clicar_rotulo(&tf("tirar_n_da_fila", &[("n", &2)]));
    ok!(caso, "tirou os 2 e tocou o próximo", b.nomes_da_lista() == ["c.jpg", "d.jpg", "e.mp4"] && b.ultimo() == "c.jpg", "{:?} {:?}", b.nomes_da_lista(), b.carregados());

    // Busca.
    let campo = b.rotulo(&t("buscar_fila")).into_iter().find(|e| e.accessible_role() == Some(i_slint_backend_testing::AccessibleRole::TextInput));
    ok!(caso, "campo de busca existe", campo.is_some());
    if let Some(c) = campo {
        c.set_accessible_value("SUB");
        b.girar();
        ok!(caso, "busca filtra pelo nome e pasta, sem diferença de maiúsculas", b.nomes_da_lista() == ["e.mp4"], "{:?}", b.nomes_da_lista());
        c.set_accessible_value("");
        b.girar();
        ok!(caso, "busca vazia mostra tudo", b.nomes_da_lista().len() == 3);
    }
    b.tecla("l");
    ok!(caso, "L esconde a fila", !b.ui.get_painel_visivel());
    b.com(Key::Control, "f");
    ok!(caso, "Ctrl+F mostra a fila escondida", b.ui.get_painel_visivel() && b.tem_log("tecla na camada: Buscar"));
    // Tirar tudo: volta à tela de início.
    b.ui.invoke_focar_janela();
    for _ in 0..3 {
        let primeira = b.nomes_da_lista()[0].clone();
        linha(&primeira).mock_single_click(PointerEventButton::Right);
        b.girar();
        b.clicar_rotulo(&t("tirar_da_fila"));
    }
    ok!(caso, "tirar o último volta à tela de início", b.ui.get_vazio() && b.nomes_da_lista().is_empty());
}

fn caso_falhas_e_heic() {
    let caso = "heic";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    let pasta = pasta_de_midia("heic", &["1.heic", "2-ruim.mp4", "3.heic", "4.jpg"]);
    b.motor.reacoes.borrow_mut().insert(".heic".into(), Reacao::Abre);
    b.abrir(&pasta);
    ok!(caso, "HEIC lido o giro e carregado", b.ultimo() == "1.heic");
    ok!(caso, "seek 0 depois do file-loaded", b.cmd("seek 0 absolute+exact"));
    b.passar(200); // o vigia olha a cada 50 ms e a barra anda a cada 100 ms
    ok!(caso, "HEIC apareceu: o tempo começa a contar", b.ui.get_progresso() > 0.0, "{}", b.ui.get_progresso());
    b.passar(4900);
    ok!(caso, "o ruim é tentado", b.carregados().iter().any(|c| c == "2-ruim.mp4"));
    b.passar(100);
    b.esperar_varredura(); // o próximo é HEIC: o cabeçalho é lido numa thread de verdade
    ok!(caso, "o ruim é marcado e pulado", b.ultimo() == "3.heic" && b.tem_log("não abriu: "), "{:?}", b.carregados());
    let falhou = { let m = b.ui.get_fila(); (0..m.row_count()).any(|i| { let l = m.row_data(i).unwrap(); l.nome == "2-ruim.mp4" && l.falhou }) };
    ok!(caso, "a linha do ruim fica marcada", falhou);
    ok!(caso, "o resumo conta o que não abriu", b.ui.get_resumo().contains(&t("um_nao_abriu")));

    // HEIC que trava: recarrega até 5 vezes, com espera crescente; o tempo da foto não conta.
    let c = Banco::novo("heic-trava", CFG_ORDEM, false);
    c.motor.reacoes.borrow_mut().insert(".heic".into(), Reacao::Trava);
    c.abrir(&pasta_de_midia("heic-trava", &["1.heic", "2.jpg"]));
    // Instante de cada recarga, contado do primeiro loadfile (o vigia olha a cada 50 ms).
    let t0 = get_mocked_time();
    let ate = |c: &Banco, ms: u64| {
        let agora = get_mocked_time() - t0;
        if ms > agora {
            c.passar(ms - agora);
        }
    };
    let mut quando = 0u64;
    for tentativa in 1..=HEIC_TENTATIVAS as u64 {
        let espera = 1500 + 1000 * (tentativa - 1);
        quando += espera;
        ate(&c, quando - 100);
        ok!("heic-trava", &format!("tentativa {tentativa}: ainda esperando"), c.carregados().len() == tentativa as usize, "{:?}", c.carregados());
        ok!("heic-trava", &format!("tentativa {tentativa}: tempo da foto parado"), c.ui.get_progresso() == 0.0, "{}", c.ui.get_progresso());
        ate(&c, quando + 120);
        if tentativa < HEIC_TENTATIVAS as u64 {
            ok!("heic-trava", &format!("recarrega depois de {:.1} s", espera as f64 / 1000.0), c.carregados().len() == tentativa as usize + 1, "{:?}", c.carregados());
        }
    }
    c.passar(100);
    ok!("heic-trava", "na 5ª pula como arquivo que não abriu", c.ultimo() == "2.jpg" && c.tem_log("HEIC não apareceu em 5 tentativas: pulando"), "{:?}", c.carregados());
    let falhou = { let m = c.ui.get_fila(); (0..m.row_count()).any(|i| { let l = m.row_data(i).unwrap(); l.nome == "1.heic" && l.falhou }) };
    ok!("heic-trava", "e o HEIC fica marcado na fila", falhou);
    // Pausa enquanto lê o cabeçalho vale para o HEIC (não para o arquivo anterior).
    let d = Banco::novo("heic-pausa", CFG_ORDEM, false);
    d.motor.reacoes.borrow_mut().insert(".heic".into(), Reacao::Abre);
    d.abrir(&pasta_de_midia("heic-pausa", &["0.jpg", "1.heic"]));
    d.p.proximo();
    d.tecla(" "); // ainda lendo o giro (a thread não foi lida)
    d.esperar_varredura();
    d.passar(60);
    ok!("heic-pausa", "pausa no meio da leitura vale para o HEIC", d.ultimo() == "1.heic" && d.pausado(), "{:?}", d.carregados());
    d.passar(10_000);
    ok!("heic-pausa", "e o tempo não anda", d.ultimo() == "1.heic");

    // Nada abre.
    let e = Banco::novo("nada-abre", CFG_ORDEM, false);
    e.abrir(&pasta_de_midia("nada-abre", &["a-ruim.mp4", "b-ruim.mkv"]));
    e.passar(300);
    ok!("nada-abre", "tenta os dois e para", e.carregados().len() == 2 && e.ui.get_info() == t("nenhum_abriu") && !e.ui.get_tocando(), "{:?} {}", e.carregados(), e.ui.get_info());
}

fn caso_teclas() {
    let caso = "teclas";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    b.reg.responder_pasta(None);
    b.com(Key::Control, "o");
    ok!(caso, "Ctrl+O abre a janela de pasta", b.reg.pedidos_de("escolher-pasta").len() == 1);
    b.tecla(" ");
    ok!(caso, "Espaço sem fila abre a janela de pasta (como a 1.5.1)", b.reg.pedidos_de("escolher-pasta").len() == 2);
    b.abrir(&pasta_de_midia("teclas", &["a.jpg", "b.jpg", "c.mp4"]));
    let antes = b.carregados().len();
    b.com(Key::Shift, "N");
    ok!(caso, "Shift+N não é atalho (Qt: letra só sem Shift)", b.carregados().len() == antes);
    b.tecla("N");
    ok!(caso, "N com Caps Lock é atalho (como no Qt)", b.ultimo() == "b.jpg");
    b.tecla("p");
    b.tecla_k(Key::PageDown);
    ok!(caso, "PgDown é próximo", b.ultimo() == "b.jpg");
    b.tecla_k(Key::PageUp);
    ok!(caso, "PgUp é anterior", b.ultimo() == "a.jpg");
    b.tecla("k");
    ok!(caso, "K pausa", b.pausado());
    b.ui.window().dispatch_event(WindowEvent::KeyPressed { text: " ".into() });
    for _ in 0..3 {
        b.ui.window().dispatch_event(WindowEvent::KeyPressRepeated { text: " ".into() });
    }
    b.ui.window().dispatch_event(WindowEvent::KeyReleased { text: " ".into() });
    b.girar();
    ok!(caso, "Espaço segurado alterna uma vez só", !b.pausado());
    b.tecla("s");
    ok!(caso, "S aleatório", b.ui.get_aleatorio());
    b.tecla("3");
    ok!(caso, "3 só vídeos", b.ui.get_filtro() == "videos" && b.ultimo() == "c.mp4");
    b.tecla("2");
    ok!(caso, "2 só fotos", b.ui.get_filtro() == "fotos");
    b.tecla("1");
    ok!(caso, "1 tudo", b.ui.get_filtro() == "tudo");
    b.reg.responder_pasta(Some(pasta_de_midia("teclas2", &["z.jpg"])));
    b.ui.window().dispatch_event(WindowEvent::KeyPressed { text: Key::Control.into() });
    b.ui.window().dispatch_event(WindowEvent::KeyPressed { text: Key::Shift.into() });
    b.tecla("O");
    b.ui.window().dispatch_event(WindowEvent::KeyReleased { text: Key::Shift.into() });
    b.ui.window().dispatch_event(WindowEvent::KeyReleased { text: Key::Control.into() });
    b.esperar_varredura();
    ok!(caso, "Ctrl+Shift+O junta pasta", b.nomes_da_lista().len() == 4, "{:?}", b.nomes_da_lista());
    let antes = b.carregados().len();
    ok!(caso, "teclas de mídia (mandadas pelo executável)", b.p.tecla("midia-proximo", false, false, false, false, "camada") && b.carregados().len() == antes + 1);
    b.p.tecla("midia-anterior", false, false, false, false, "camada");
    ok!(caso, "tecla de mídia anterior", b.carregados().len() == antes + 2);
    ok!(caso, "Alt+N não é atalho", !b.p.tecla("n", false, false, true, false, "camada"));
}

fn caso_modo_teste_e_largura() {
    let caso = "modo-teste";
    let b = Banco::novo(caso, r#"{"mudo": false}"#, true);
    b.motor.definir("mute", "yes");
    b.abrir(&pasta_de_midia("modo-teste", &["a.mp4"]));
    b.clicar("Camada::b-vol");
    b.clicar("Camada::b-vol");
    b.tecla("m");
    let mexeu = b.motor.linhas().iter().any(|l| l.starts_with("set mute"));
    ok!(caso, "no modo de teste o motor nunca sai do mudo", !mexeu && b.motor.prop("mute").as_deref() == Some("yes"));
    ok!(caso, "mas a pessoa vê o estado dela", b.ui.get_mudo());
    b.tecla("f");
    ok!(caso, "tela cheia só registrada", b.tem_log("tela cheia: não aplicada no modo teste (pedido true)"));

    // Barra responsiva: abaixo de 1080 px o volume vira só o ícone e o tempo da foto encurta.
    let larga = b.el("Camada::volume").is_some();
    b.ui.window().set_size(LogicalSize::new(1000.0, 700.0));
    b.passar(20);
    ok!(caso, "larga: tem o controle de volume", larga);
    ok!(caso, "estreita: sem o controle de volume", b.el("Camada::volume").is_none() && !b.ui.get_larga());
    let pil = b.el("Camada::p-foto").and_then(|e| e.accessible_label()).unwrap_or_default();
    ok!(caso, "estreita: tempo da foto curto", pil == b.ui.get_foto_curto(), "{pil}");
}

fn caso_arrastar() {
    let caso = "arrastar";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    let solte = |b: &Banco| ElementHandle::find_by_accessible_label(&b.ui, &t("solte_para_tocar")).count();
    ok!(caso, "parado: a tela de início diz arraste aqui", solte(&b) == 0);
    b.p.arrastando(true);
    ok!(caso, "arrastando: a tela de início diz Solte para tocar", b.ui.get_arrastando() && solte(&b) == 1, "{}", solte(&b));
    let pasta = pasta_de_midia("arrastar", &["a.jpg", "b.jpg"]);
    b.p.soltar(vec![pasta.join("a.jpg")]);
    b.p.soltar(vec![pasta.join("b.jpg")]);
    b.passar(50);
    b.esperar_varredura();
    ok!(caso, "os soltos juntos viram uma fila", b.nomes_da_lista() == ["a.jpg", "b.jpg"] && !b.ui.get_arrastando(), "{:?}", b.nomes_da_lista());
    let outra = pasta_de_midia("arrastar2", &["c.jpg"]);
    b.reg.ctrl.set(true);
    b.p.soltar(vec![outra]);
    b.passar(50);
    b.esperar_varredura();
    ok!(caso, "Ctrl ao soltar junta", b.nomes_da_lista().len() == 3 && b.ultimo() == "a.jpg");
    b.reg.ctrl.set(false);
    b.p.soltar(vec![pasta.clone()]);
    b.passar(50);
    b.esperar_varredura();
    ok!(caso, "sem Ctrl troca a fila", b.nomes_da_lista().len() == 2);
}

/// Os achados da revisão independente da fase 3, cada um com o cenário que ela rodou.
fn caso_revisao() {
    let caso = "revisao";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    let sel = |b: &Banco| { let m = b.ui.get_fila(); (0..m.row_count()).filter(|&i| m.row_data(i).unwrap().selecionada).map(|i| m.row_data(i).unwrap().nome.to_string()).collect::<Vec<_>>() };
    let linha = |b: &Banco, n: &str| b.rotulo(n).into_iter().next().unwrap();
    b.abrir(&pasta_de_midia("rev-1", &["a.jpg", "b.jpg", "c.jpg"]));
    linha(&b, "b.jpg").mock_single_click(PointerEventButton::Left);
    b.girar();
    b.reg.responder_pasta(Some(pasta_de_midia("rev-2", &["p.jpg", "q.jpg", "r.jpg"])));
    b.clicar("Camada::p-abrir");
    b.esperar_varredura();
    ok!(caso, "fila nova não herda a seleção da antiga", b.nomes_da_lista() == ["p.jpg", "q.jpg", "r.jpg"] && sel(&b).is_empty(), "{:?}", sel(&b));

    // Menu da lista aberto quando a varredura troca a fila: fecha, nada é tirado.
    b.p.carregar(vec![pasta_de_midia("rev-3", &["x.jpg", "y.jpg", "z.jpg"])], false);
    linha(&b, "q.jpg").mock_single_click(PointerEventButton::Right);
    ok!(caso, "menu da lista aberto (antes de ler o correio)", b.ui.get_menu_visivel());
    b.esperar_varredura();
    ok!(caso, "a fila trocou: o menu da lista fecha", !b.ui.get_menu_visivel() && b.nomes_da_lista() == ["x.jpg", "y.jpg", "z.jpg"]);

    // Âncora do Shift depois de tirar.
    b.abrir(&pasta_de_midia("rev-4", &["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"]));
    linha(&b, "c.jpg").mock_single_click(PointerEventButton::Right);
    b.girar();
    b.clicar_rotulo(&t("tirar_da_fila"));
    let m: SharedString = Key::Shift.into();
    b.ui.window().dispatch_event(WindowEvent::KeyPressed { text: m.clone() });
    linha(&b, "e.jpg").mock_single_click(PointerEventButton::Left);
    b.ui.window().dispatch_event(WindowEvent::KeyReleased { text: m });
    b.girar();
    ok!(caso, "Shift+clique depois de tirar não usa a âncora velha", sel(&b) == ["e.jpg"], "{:?}", sel(&b));

    // A roda com a caixa ou o menu abertos não mexe no volume.
    b.abrir(&pasta_de_midia("rev-5", &["v.mp4", "w.jpg"]));
    let v0 = b.ui.get_volume();
    let tela = b.el("Camada::tela").unwrap();
    b.clicar("Camada::p-foto");
    b.clicar_rotulo(&t("outro_tempo"));
    ok!(caso, "caixa do tempo aberta", b.ui.get_caixa_visivel());
    tela.scroll(0.0, 120.0);
    b.girar();
    ok!(caso, "roda com a caixa aberta não mexe no volume", b.ui.get_volume() == v0, "{} → {}", v0, b.ui.get_volume());
    b.tecla_k(Key::Escape);
    b.clicar("Camada::p-foto");
    tela.scroll(0.0, 120.0);
    b.girar();
    ok!(caso, "roda com o menu aberto não mexe no volume", b.ui.get_volume() == v0, "{} → {}", v0, b.ui.get_volume());
    b.tecla_k(Key::Escape);
    tela.scroll(0.0, 120.0);
    b.girar();
    ok!(caso, "sem nada aberto, a roda mexe", b.ui.get_volume() == v0 + 5);

    // Soltar com a caixa "Limpar tudo?" aberta não carrega nada por trás.
    b.clicar("Camada::p-limpar");
    b.clicar_rotulo(&t("limpar_tudo"));
    ok!(caso, "caixa Limpar tudo aberta", b.ui.get_caixa_visivel());
    b.p.soltar(vec![pasta_de_midia("rev-6", &["novo.jpg"])]);
    b.passar(60);
    b.esperar_varredura();
    ok!(caso, "soltar com a caixa aberta é ignorado", b.nomes_da_lista() == ["v.mp4", "w.jpg"] && b.tem_log("solto ignorado"), "{:?}", b.nomes_da_lista());
    b.clicar_rotulo(&t("nao"));

    // O aviso diz "acabou", mas reler o eof-reached falha: não é fim (a 1.5.1 relê e ignora).
    b.motor.props.borrow_mut().remove("eof-reached");
    b.passar(400);
    let antes = b.carregados().len();
    b.motor.emitir(Evento::Propriedade { id: 2, nome: "eof-reached".into(), valor: Valor::Sim(true) });
    b.girar();
    ok!(caso, "eof ilegível não passa para o próximo", b.carregados().len() == antes && b.ultimo() == "v.mp4", "{:?}", b.carregados());

    // Ctrl vale no instante em que soltou, não 40 ms depois.
    b.reg.ctrl.set(true);
    b.p.soltar(vec![pasta_de_midia("rev-7", &["k.jpg"])]);
    b.reg.ctrl.set(false);
    b.passar(60);
    b.esperar_varredura();
    ok!(caso, "Ctrl solto antes dos 40 ms ainda junta", b.nomes_da_lista() == ["v.mp4", "w.jpg", "k.jpg"], "{:?}", b.nomes_da_lista());

    // Nome da pasta como o basename da 1.5.1.
    use ciranda::player::nome_da_pasta;
    for (cam, esperado) in [
        ("C:\\", "C:\\"),
        ("C:\\Fotos\\", "Fotos"),
        ("D:\\Fotos\\2024", "2024"),
        ("\\\\srv\\share\\", "\\\\srv\\share\\"),
        ("\\\\srv\\share\\Viagem", "Viagem"),
    ] {
        let n = nome_da_pasta(Path::new(cam));
        ok!(caso, &format!("nome da pasta {cam:?}"), n == esperado, "{n:?}");
    }
}

/// A janela de escolher pasta é modal e não para o player (o Qt roda os timers durante o
/// diálogo; o Rust abre o diálogo numa thread e a resposta volta pelo correio).
fn caso_dialogo() {
    let caso = "dialogo";
    let b = Banco::novo(caso, CFG_ORDEM, false);
    b.abrir(&pasta_de_midia("dialogo", &["1.jpg", "2.jpg", "3.jpg"]));
    b.reg.segurar_escolha.set(true);
    b.clicar("Camada::p-abrir");
    ok!(caso, "a janela de escolher abriu", b.reg.pedidos_de("escolher-pasta").len() == 2);
    b.passar(5200);
    ok!(caso, "com a janela aberta a foto passa no tempo", b.ultimo() == "2.jpg", "{:?}", b.carregados());
    let antes = b.carregados().len();
    b.tecla("n");
    ok!(caso, "com a janela aberta as teclas não valem", b.carregados().len() == antes);
    b.p.abrir_pasta();
    ok!(caso, "não abre uma segunda janela", b.reg.pedidos_de("escolher-pasta").len() == 2);
    b.p.soltar(vec![pasta_de_midia("dialogo-solto", &["s.jpg"])]);
    b.passar(60);
    ok!(caso, "soltar com a janela aberta é ignorado", b.nomes_da_lista().len() == 3);
    b.reg.responder_pasta(Some(pasta_de_midia("dialogo-2", &["n1.jpg", "n2.jpg"])));
    ok!(caso, "a pessoa escolheu", b.reg.responder_agora());
    b.esperar_varredura();
    ok!(caso, "a resposta chega pelo correio e troca a fila", b.nomes_da_lista() == ["n1.jpg", "n2.jpg"] && b.ultimo() == "n1.jpg", "{:?}", b.nomes_da_lista());
    b.tecla("n");
    ok!(caso, "fechada a janela, as teclas voltam", b.ultimo() == "n2.jpg");
    b.clicar("Camada::p-abrir");
    b.reg.responder_pasta(None);
    b.reg.responder_agora();
    b.girar();
    ok!(caso, "cancelar não muda nada", b.nomes_da_lista() == ["n1.jpg", "n2.jpg"] && b.tem_log("escolha cancelada"));
}

trait TelaCheiaRegistrada {
    fn em_tela_cheia_registrada(&self) -> bool;
}
impl TelaCheiaRegistrada for Registro {
    fn em_tela_cheia_registrada(&self) -> bool {
        use ciranda::plataforma::Plataforma;
        self.em_tela_cheia()
    }
}

fn main() {
    i_slint_backend_testing::init_no_event_loop();
    let _ = Filtro::Tudo;
    let casos: [(&str, fn()); 9] = [
        ("barra", caso_inicio_e_barra),
        ("foto", caso_foto_e_tempo),
        ("video", caso_video),
        ("tela-cheia", caso_palco_e_tela_cheia),
        ("menus", caso_menus_e_limpar),
        ("lista", caso_lista),
        ("heic", caso_falhas_e_heic),
        ("teclas", caso_teclas),
        ("modo-teste", caso_modo_teste_e_largura),
    ];
    for (nome, f) in casos {
        println!("{nome}");
        f();
    }
    println!("arrastar");
    caso_arrastar();
    println!("revisao");
    caso_revisao();
    println!("dialogo");
    caso_dialogo();
    let n = CONTA.with(|c| *c.borrow());
    let falhas = FALHAS.with(|f| f.borrow().clone());
    if falhas.is_empty() {
        println!("TUDO PASSOU ({n} verificações)");
    } else {
        println!("{} de {n} FALHARAM:", falhas.len());
        for f in &falhas {
            println!("  {f}");
        }
        std::process::exit(1);
    }
}
