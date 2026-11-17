//! Núcleo da Ciranda em Rust (fase 2): varredura, ordem natural, fila, config e a sessão que
//! decide o que tocar. Nada aqui abre janela, toca som ou depende do motor: tudo é testado sem
//! interface (`cargo test`).

pub mod biblioteca;
pub mod config;
pub mod fila;
pub mod modo_teste;
pub mod ordem;
pub mod sessao;
pub mod sorteio;
mod unicode_py;

pub use unicode_py::VERSAO_UNICODE;
