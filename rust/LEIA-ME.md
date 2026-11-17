# Ciranda em Rust: fase 2 (núcleo) sobre a prova da fase 1

A 1.5.1 (Python) continua sendo a Ciranda de verdade. Aqui: a prova do arranjo de janelas (fase 1) e o núcleo portado da 1.5.1 (fase 2).

## O núcleo (biblioteca `ciranda`, `src/lib.rs`)

Nada no núcleo abre janela, toca som ou depende do motor: tudo roda em `cargo test`.

- `biblioteca.rs`: porta da `biblioteca.py`. Varre em qualquer profundidade (pilha, sem recursão), arquivos da pasta antes das subpastas, mesmas listas de formatos e de pastas puladas, junções e links conferidos pelo destino real (o `realpath` não estrito do Python 3.12), sem repetir arquivo. Lê cada pasta com `FindFirstFileExW`, como o `os.scandir`. Caminho longo ganha `\\?\` (funciona sem o LongPathsEnabled).
- `ordem.rs` + `unicode_py.rs`: ordem natural igual à `chave_natural` da 1.5.1, com o `casefold` e o `\d` tirados do próprio Python 3.12 (Unicode 15.0) por `ferramentas/gerar_tabelas_unicode.py`.
- `fila.rs` + `sorteio.rs`: porta da `fila.py` (baralho, repetir nada/tudo/um, filtro, falhos, juntar, tirar). O sorteio é xoshiro256** próprio (a sequência não é a do Python; as propriedades são).
- `config.rs`: lê o `config.json` da 1.5.x e grava os mesmos bytes que ela (ordem das chaves, `indent=2`, `ensure_ascii=False`, `repr` dos números, CRLF no fim das linhas). Chave desconhecida some na leitura, como na 1.5.1.
- `sessao.rs`: o que a `janela.py` decide tocar (abrir/juntar, varredura pronta, próximo/anterior, fim de foto e vídeo, arquivo que falha, nenhum abriu, filtro que esconde tudo).
- `modo_teste.rs`: `DREDS_TESTE=1`.

## Testes do núcleo

```
cargo test --release                                    # tudo (unidade, igual_151, sessao, teste_logica sem pasta)
cargo test --release --test teste_logica -- <pasta>     # com a pasta do tests/gerar_midia.py: 384 checagens
python -I rust/ferramentas/gerar_fixtures.py            # refaz as fixtures com o Python da 1.5.1
python -I rust/ferramentas/comparar_varredura.py <varrer.exe> <saida.json> [pastas]   # 1.5.1 × Rust, item por item, com tempo
python -I rust/medir/teste_invisivel.py <ciranda-prova.exe> <pasta-midia-teste>       # app em DREDS_TESTE=1
```

- `tests/teste_logica.rs`: porta do `teste_logica.py`, checagem por checagem (377 sem a pasta, 384 com ela; os mesmos números da 1.5.1).
- `tests/igual_151.rs`: config (14 casos, bytes iguais aos da 1.5.1) e ordem natural (2.991 nomes difíceis, mesma ordem crescente e decrescente, inclusive nos empates).
- `tests/biblioteca.rs`: `normcase`, `abspath` e a classe de erro de cada código do Windows (0 a 19.999) iguais aos do Python 3.12 (`tests/fixtures/caminhos.json`); pastas de sistema puladas; K (Kelvin) e k são dois arquivos; a mesma pasta em grego maiúsculo e minúsculo entra uma vez.
- `tests/sessao.rs`: as decisões da janela, sem janela.
- `ferramentas/bugs_plantados.py <pasta-midia-teste>`: planta 15 bugs conhecidos, um por vez, e confere que os testes pegam cada um.
- `medir/teste_invisivel.py`: o app inteiro em `DREDS_TESTE=1` (sem janela, `vo=null`, `ao=null`, `mute`), teclas por `PostMessage` para a hospedeira oculta. Vigia de janela visível e de foco pelos eventos do Windows (`SetWinEventHook`) e a cada 100 ms. A única isenta é a auxiliar do winit ("Winit Thread Event Target": 16×16, em camadas, transparente, sem conteúdo; o winit a marca visível só para receber `WM_PAINT`, e o DWM não a mostra).

## Modo de teste (REGRA 13)

`DREDS_TESTE=1`: a hospedeira nasce e fica oculta, a camada Slint não é mostrada, o mpv roda com `vo=null`, `ao=null` e `mute=yes`, tela cheia vira só log, nada chama `SetForegroundWindow`. `CIRANDA_DADOS=<pasta>` troca a pasta de dados (recusa `%APPDATA%\Ciranda` e o que fica dentro dela, também por junção, nome curto 8.3, `\\?\` ou barra no fim), `CIRANDA_SAIR_NO_FIM=1` fecha quando a fila acaba, `CIRANDA_TESTE_LIMITE_S` (padrão 120) é o limite de tempo.

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

Log e `config.json` em `%APPDATA%\Ciranda-rust-prova\` (nunca usa `%APPDATA%\Ciranda`; o app se recusa). Rodando de dentro do app Claude (pacote MSIX), o Windows redireciona esse `%APPDATA%` para `%LOCALAPPDATA%\Packages\Claude_…\LocalCache\Roaming`.

Teclas: Espaço, ← → (5 s; Shift: 30 s; na foto troca de foto), F / Enter / F11 (tela cheia), Esc, N, P (vídeo com mais de 3 s volta ao começo), S (aleatório), R (repetir), 1 / 2 / 3 (tudo / fotos / vídeos). Duplo clique: tela cheia. Botão direito: menu. Soltar com Ctrl junta à fila sem parar o que toca.

## Medir

- `medir/medir.py`: prova contra a 1.5.1 instalada, mesmos arquivos, mesma posição de janela. Séries: `mpv` (quadros perdidos e atrasados, hwdec, CPU interna), `cpu` (Get-Counter e memória), `quadro` (tempo até o 1º quadro na tela), `composicao` (CPU do dwm.exe e uso da GPU, com linha de base sem app).
- `medir/mpv_151.py`: lê o mpv da 1.5.1 a partir do código-fonte dela (o exe instalado não deixa).
- `medir/interface.py`: clique e tecla reais (SendInput), alinhamento das janelas, menu, quadro, teclas nas duas janelas, tecla segurada, barra de título, tela cheia (pelo retângulo, não pelo log), Alt+F4, fotos; prints só da janela do app.
- `medir/arrastar.py` + `medir/fonte_arrasto.ps1`: arrasto OLE real (CF_HDROP, o formato do Explorer) de uma janelinha WinForms até a prova, com mouse real.
- Variáveis da prova: `CIRANDA_PROVA_MEDIR=<saida.json>`, `CIRANDA_PROVA_SEGUNDOS`, `CIRANDA_PROVA_AQUECER`, `CIRANDA_PROVA_SAIR`. A janela de medição é uma só por processo.

## Licenças

`cargo deny check licenses sources` com `deny.toml`: só MIT, Apache-2.0, BSD, ISC, Zlib, Unicode-3.0 e Slint Royalty-free 2.0; BSL-1.0 só para `clipboard-win` e `error-code` (que o Slint puxa); só crates.io (git ou outro registro derruba). A `libmpv-2.dll` fica fora do `cargo deny` (é carregada em tempo de execução): quem a garante é a conferência do sha256 acima. O Slint Royalty-free exige o `AboutSlint` numa tela "Sobre" e o selo na página do projeto: entra na fase 4.

## Fica para a fase 3 (player completo)

Barra em 3 zonas, fila lateral, busca, OSD, menus, demais teclas, giro do HEIC do iPhone (`irot`/`imir`, que a 1.5.1 faz no `heif.py`) e a recarga do HEIC em grade, interface no backend de teste do Slint.
