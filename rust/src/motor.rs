//! O motor visto pelo player: o mpv de verdade (`mpv::Mpv`) ou um falso, para testar a
//! interface sem abrir arquivo nenhum (`MotorFalso`).

use std::cell::RefCell;
use std::collections::{HashMap, VecDeque};

/// Um evento do motor já traduzido para Rust.
#[derive(Debug, Clone)]
pub enum Evento {
    InicioArquivo,
    ArquivoCarregado,
    /// `MPV_EVENT_PLAYBACK_RESTART`: o primeiro quadro depois de abrir ou de um seek.
    Reinicio,
    FimArquivo { motivo: i32, erro: i32 },
    Propriedade { id: u64, nome: String, valor: Valor },
    Log { nivel: String, prefixo: String, texto: String },
    FimDoMotor,
    Outro(i32),
}

#[derive(Debug, Clone, PartialEq)]
pub enum Valor {
    Nada,
    Texto(String),
    Sim(bool),
    Inteiro(i64),
    Real(f64),
}

/// `mpv_end_file_reason`: MPV_END_FILE_REASON_ERROR.
pub const FIM_POR_ERRO: i32 = 4;

/// O que o player usa do motor. Tudo na thread da interface.
pub trait Motor {
    fn comando(&self, args: &[&str]) -> Result<(), String>;
    fn por_texto(&self, nome: &str, valor: &str) -> Result<(), String>;
    fn por_sim(&self, nome: &str, valor: bool) -> Result<(), String>;
    fn ler_real(&self, nome: &str) -> Option<f64>;
    fn ler_inteiro(&self, nome: &str) -> Option<i64>;
    fn ler_sim(&self, nome: &str) -> Option<bool>;
    fn ler_texto(&self, nome: &str) -> Option<String>;
    /// Próximo evento sem esperar; `None` quando acabaram.
    fn proximo_evento(&self) -> Option<Evento>;
}

impl Motor for crate::mpv::Mpv {
    fn comando(&self, args: &[&str]) -> Result<(), String> {
        crate::mpv::Mpv::comando(self, args)
    }
    fn por_texto(&self, nome: &str, valor: &str) -> Result<(), String> {
        crate::mpv::Mpv::por_texto(self, nome, valor)
    }
    fn por_sim(&self, nome: &str, valor: bool) -> Result<(), String> {
        crate::mpv::Mpv::por_sim(self, nome, valor)
    }
    fn ler_real(&self, nome: &str) -> Option<f64> {
        crate::mpv::Mpv::ler_real(self, nome)
    }
    fn ler_inteiro(&self, nome: &str) -> Option<i64> {
        crate::mpv::Mpv::ler_inteiro(self, nome)
    }
    fn ler_sim(&self, nome: &str) -> Option<bool> {
        crate::mpv::Mpv::ler_sim(self, nome)
    }
    fn ler_texto(&self, nome: &str) -> Option<String> {
        crate::mpv::Mpv::ler_texto(self, nome)
    }
    fn proximo_evento(&self) -> Option<Evento> {
        crate::mpv::Mpv::proximo_evento(self)
    }
}

/// Como o motor falso reage a um `loadfile`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reacao {
    /// Abre: InicioArquivo, ArquivoCarregado e Reinicio.
    Abre,
    /// Não abre: FimArquivo por erro.
    Falha,
    /// Carrega, mas o quadro nunca aparece (a grade HEIC que trava).
    Trava,
    /// Nada acontece até o teste mandar eventos.
    Calado,
}

/// Motor de mentira para os testes da interface: grava cada comando e cada propriedade, e
/// responde ao `loadfile` com os eventos que o mpv mandaria (veja `Reacao`).
#[derive(Default)]
pub struct MotorFalso {
    pub comandos: RefCell<Vec<Vec<String>>>,
    pub props: RefCell<HashMap<String, String>>,
    pub eventos: RefCell<VecDeque<Evento>>,
    /// Reação por extensão (".mp4"); sem entrada, `Abre`. Nome com "ruim" sempre falha.
    pub reacoes: RefCell<HashMap<String, Reacao>>,
    /// `loadfile` devolve erro na hora (o mpv recusou o comando).
    pub recusar_loadfile: RefCell<bool>,
}

impl MotorFalso {
    pub fn novo() -> Self {
        let m = MotorFalso::default();
        m.props.borrow_mut().insert("pause".into(), "no".into());
        m.props.borrow_mut().insert("volume".into(), "80".into());
        m.props.borrow_mut().insert("mute".into(), "no".into());
        m
    }
    pub fn emitir(&self, e: Evento) {
        self.eventos.borrow_mut().push_back(e);
    }
    pub fn definir(&self, nome: &str, valor: &str) {
        self.props.borrow_mut().insert(nome.into(), valor.into());
    }
    pub fn prop(&self, nome: &str) -> Option<String> {
        self.props.borrow().get(nome).cloned()
    }
    /// Os comandos gravados, cada um como "a b c".
    pub fn linhas(&self) -> Vec<String> {
        self.comandos.borrow().iter().map(|c| c.join(" ")).collect()
    }
    pub fn esquecer_comandos(&self) {
        self.comandos.borrow_mut().clear();
    }
    /// Quantos `loadfile` já recebeu.
    pub fn carregados(&self) -> Vec<String> {
        self.comandos.borrow().iter().filter(|c| c.first().is_some_and(|x| x == "loadfile")).map(|c| c[1].clone()).collect()
    }
    fn mudou(&self, nome: &str, valor: Valor) {
        if matches!(nome, "pause" | "eof-reached") {
            self.emitir(Evento::Propriedade { id: 0, nome: nome.into(), valor });
        }
    }
}

impl Motor for MotorFalso {
    fn comando(&self, args: &[&str]) -> Result<(), String> {
        self.comandos.borrow_mut().push(args.iter().map(|s| s.to_string()).collect());
        match args.first().copied() {
            Some("loadfile") => {
                if *self.recusar_loadfile.borrow() {
                    return Err("loadfile recusado (motor falso)".into());
                }
                let caminho = args.get(1).copied().unwrap_or_default();
                self.definir("path", caminho);
                self.definir("eof-reached", "no");
                self.definir("time-pos", "0");
                let ext = std::path::Path::new(caminho)
                    .extension()
                    .map(|e| format!(".{}", e.to_string_lossy().to_lowercase()))
                    .unwrap_or_default();
                let reacao = if caminho.to_lowercase().contains("ruim") {
                    Reacao::Falha
                } else {
                    self.reacoes.borrow().get(&ext).copied().unwrap_or(Reacao::Abre)
                };
                // HEIC: a faixa de vídeo e o tamanho na tela (o player confere se batem).
                let heic = matches!(ext.as_str(), ".heic" | ".heif");
                if heic {
                    for (k, v) in [("track-list/count", "1"), ("track-list/0/type", "video"), ("track-list/0/selected", "yes"),
                        ("track-list/0/demux-w", "4"), ("track-list/0/demux-h", "3")]
                    {
                        self.definir(k, v);
                    }
                    let (w, h) = if reacao == Reacao::Abre { ("3", "4") } else { ("0", "0") };
                    self.definir("dwidth", w);
                    self.definir("dheight", h);
                }
                match reacao {
                    Reacao::Abre => {
                        self.emitir(Evento::InicioArquivo);
                        self.emitir(Evento::ArquivoCarregado);
                        self.emitir(Evento::Reinicio);
                    }
                    Reacao::Falha => {
                        self.emitir(Evento::InicioArquivo);
                        self.emitir(Evento::FimArquivo { motivo: FIM_POR_ERRO, erro: -13 });
                    }
                    Reacao::Trava => {
                        self.emitir(Evento::InicioArquivo);
                        self.emitir(Evento::ArquivoCarregado);
                    }
                    Reacao::Calado => {}
                }
            }
            Some("stop") => {
                self.props.borrow_mut().remove("path");
            }
            Some("seek") => {
                self.emitir(Evento::Reinicio);
            }
            _ => {}
        }
        Ok(())
    }
    fn por_texto(&self, nome: &str, valor: &str) -> Result<(), String> {
        self.comandos.borrow_mut().push(vec!["set".into(), nome.into(), valor.into()]);
        self.definir(nome, valor);
        Ok(())
    }
    fn por_sim(&self, nome: &str, valor: bool) -> Result<(), String> {
        self.comandos.borrow_mut().push(vec!["set".into(), nome.into(), if valor { "yes" } else { "no" }.into()]);
        let antes = self.ler_sim(nome);
        self.definir(nome, if valor { "yes" } else { "no" });
        if antes != Some(valor) {
            self.mudou(nome, Valor::Sim(valor));
        }
        Ok(())
    }
    fn ler_real(&self, nome: &str) -> Option<f64> {
        self.prop(nome)?.parse().ok()
    }
    fn ler_inteiro(&self, nome: &str) -> Option<i64> {
        self.prop(nome)?.parse().ok()
    }
    fn ler_sim(&self, nome: &str) -> Option<bool> {
        match self.prop(nome)?.as_str() {
            "yes" => Some(true),
            "no" => Some(false),
            _ => None,
        }
    }
    fn ler_texto(&self, nome: &str) -> Option<String> {
        self.prop(nome)
    }
    fn proximo_evento(&self) -> Option<Evento> {
        self.eventos.borrow_mut().pop_front()
    }
}
