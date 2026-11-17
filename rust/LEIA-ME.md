# Ciranda em Rust: fase 1 (prova técnica)

Só a prova do arranjo de janelas. Nenhum recurso da 1.x foi portado ainda; a 1.5.1 (Python) continua sendo a Ciranda de verdade.

## O arranjo

- **Hospedeira** (`src/hospedeira.rs`): janela Win32 normal, com a barra de título do Windows (escura). O mpv desenha o vídeo numa janela filha dela (`wid`, `vo=gpu-next`, `hwdec=auto-safe` → d3d11va sem cópia).
- **Camada** (`ui/app.slint`): janela Slint de topo, sem borda, transparente com alfa por pixel (winit + femtovg), *owned* pela hospedeira. Fica sempre colada na área cliente; o Windows a mantém por cima da dona, esconde junto ao minimizar e a deixa fora da barra de tarefas e do Alt+Tab.
- **Motor** (`src/mpv.rs`): ligação própria e fina com o `libmpv-2.dll` por `libloading`, escrita a partir do `include/mpv/client.h` da v0.42.0 (ISC). Nada de crate LGPL compilada dentro.
- Teclas funcionam com o foco em qualquer das duas janelas (Slint `FocusScope` na camada, `WM_KEYDOWN` na hospedeira). Tecla segurada não fica alternando (Espaço, F, Enter, Esc); Ctrl/Alt + tecla não é atalho. Arrastar do Explorer chega pela camada (evento do winit) ou pela barra de título (`WM_DROPFILES`).
- A interface só repinta quando uma propriedade muda (relógio da barra 4×/s), nunca a cada quadro de vídeo.
- Alt+F4 em qualquer das duas janelas fecha o app inteiro. A barra de título fica acesa com o foco na camada e apaga quando outro app vem para a frente.
- Tela cheia: controles somem 2,5 s depois do último movimento do mouse, menos com o mouse parado sobre a barra.

## Montar e rodar

```
cargo build --release
copy <libmpv-2.dll oficial LGPL 0.42> target\release\
target\release\ciranda-prova.exe [pasta ou arquivos]
```

A prova confere o sha256 da DLL antes de carregar (`94fb87247732c59915cd59808bc582e843a71c22214b7b6c1e5563aa8149cef4`, a mesma da 1.5.1) e se recusa a abrir com outra: outro build (GPL, por exemplo) mudaria a licença do conjunto. O erro vai para `%APPDATA%\Ciranda-rust-prova\erro.txt`.

Log em `%APPDATA%\Ciranda-rust-prova\prova.log` (nunca usa `%APPDATA%\Ciranda`).

Teclas: Espaço, ← → (5 s; Shift: 30 s; na foto troca de foto), F / Enter / F11 (tela cheia), Esc, N, P. Duplo clique: tela cheia. Botão direito: menu.

## Medir

- `medir/medir.py`: prova contra a 1.5.1 instalada, mesmos arquivos, mesma posição de janela. Séries: `mpv` (quadros perdidos e atrasados, hwdec, CPU interna), `cpu` (Get-Counter e memória), `quadro` (tempo até o 1º quadro na tela), `composicao` (CPU do dwm.exe e uso da GPU, com linha de base sem app).
- `medir/mpv_151.py`: lê o mpv da 1.5.1 a partir do código-fonte dela (o exe instalado não deixa).
- `medir/interface.py`: clique e tecla reais (SendInput), alinhamento das janelas, menu, quadro, teclas nas duas janelas, tecla segurada, barra de título, tela cheia (pelo retângulo, não pelo log), Alt+F4, fotos; prints só da janela do app.
- `medir/arrastar.py` + `medir/fonte_arrasto.ps1`: arrasto OLE real (CF_HDROP, o formato do Explorer) de uma janelinha WinForms até a prova, com mouse real.
- Variáveis da prova: `CIRANDA_PROVA_MEDIR=<saida.json>`, `CIRANDA_PROVA_SEGUNDOS`, `CIRANDA_PROVA_AQUECER`, `CIRANDA_PROVA_SAIR`. A janela de medição é uma só por processo.

## Licenças

`cargo deny check licenses sources` com `deny.toml`: só MIT, Apache-2.0, BSD, ISC, Zlib, Unicode-3.0 e Slint Royalty-free 2.0; BSL-1.0 só para `clipboard-win` e `error-code` (que o Slint puxa); só crates.io (git ou outro registro derruba). A `libmpv-2.dll` fica fora do `cargo deny` (é carregada em tempo de execução): quem a garante é a conferência do sha256 acima. O Slint Royalty-free exige o `AboutSlint` numa tela "Sobre" e o selo na página do projeto: entra na fase 4.

## Ficou para a fase 2

Ordem natural dos nomes (hoje é por nome, sem maiúsculas), varredura recursiva, giro do HEIC do iPhone (`irot`, que a 1.5.1 faz no `heif.py`) e a rede de segurança de recarga do HEIC em grade.
