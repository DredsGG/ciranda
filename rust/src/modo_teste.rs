//! Modo de teste invisível e mudo (REGRA 13): `DREDS_TESTE=1`.
//!
//! Ligado, o app não mostra janela nenhuma, não toca som (mpv com `ao=null`, `mute=yes` e
//! `vo=null`), não pega o foco e não mexe no mouse. Processos filhos herdam a variável.

/// `DREDS_TESTE=1` no ambiente.
pub fn ligado() -> bool {
    std::env::var_os("DREDS_TESTE").is_some_and(|v| v == "1")
}
