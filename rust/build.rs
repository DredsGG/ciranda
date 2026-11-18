fn main() {
    // fluent-dark: a barra de rolagem da ListView no tema escuro.
    // with_debug_info: os nomes dos elementos ficam no código gerado, para o teste sem janela
    // (`tests/interface.rs`) achar cada botão pelo id. Não muda nada na tela.
    let cfg = slint_build::CompilerConfiguration::new().with_style("fluent-dark".into()).with_debug_info(true);
    slint_build::compile_with_config("ui/app.slint", cfg).expect("ui/app.slint");
}
