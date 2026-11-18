//! Núcleo da Ciranda em Rust: varredura, ordem natural, fila, config, a sessão que decide o que
//! tocar (fase 2) e o player com a interface (fase 3). O player fala com o motor e com o Windows
//! só por traços (`motor::Motor`, `plataforma::Plataforma`): os testes usam falsos e nada aparece.

pub mod biblioteca;
pub mod config;
pub mod fila;
pub mod heif;
pub mod modo_teste;
pub mod motor;
pub mod mpv;
pub mod ordem;
pub mod plataforma;
pub mod player;
pub mod sessao;
pub mod sistema;
pub mod sorteio;
pub mod textos;
/// A interface gerada de `ui/app.slint`.
pub mod ui {
    slint::include_modules!();
}
mod unicode_py;

pub use unicode_py::VERSAO_UNICODE;
