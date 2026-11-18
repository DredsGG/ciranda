"""Planta um bug conhecido por vez no núcleo e na interface e confere que os testes pegam cada um (os testes não
passam por acaso). Cada bug é desfeito logo depois, mesmo se o teste quebrar no meio.

    python -I rust/ferramentas/bugs_plantados.py <pasta-midia-teste>
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
RUST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIDIA = sys.argv[1]
CARGO = os.path.join(os.environ["USERPROFILE"], ".cargo", "bin", "cargo.exe")

BUGS = [
    ("baralho deixa o último de uma rodada abrir a próxima", "src/fila.rs",
     "            if resto.len() > 1 && resto[0] == ev {", "            if false && resto.len() > 1 && resto[0] == ev {"),
    ("repetir um não repete", "src/fila.rs",
     "        if automatico && self.repetir == Repetir::Um {", "        if false && automatico && self.repetir == Repetir::Um {"),
    ("número compara como texto (foto10 < foto2)", "src/ordem.rs",
     "(Parte::Num(a), Parte::Num(b)) => a.len().cmp(&b.len()).then_with(|| a.cmp(b)),",
     "(Parte::Num(a), Parte::Num(b)) => a.cmp(b),"),
    ("casefold trocado por to_lowercase (ß, Σ...)", "src/ordem.rs",
     "            match DOBRA.binary_search_by_key(&(c as u32), |&(cp, _)| cp) {",
     "            match DOBRA.binary_search_by_key(&(u32::MAX), |&(cp, _)| cp) {"),
    ("config grava LF em vez de CRLF", "src/config.rs",
     "        self.para_texto().replace('\\n', \"\\r\\n\").into_bytes()", "        self.para_texto().into_bytes()"),
    ("config sem a ordem das chaves do PADRAO (chave nova no fim)", "src/config.rs",
     "                if let Some(lugar) = cfg.valores.get_mut(&k) {\n                    *lugar = v;\n                }",
     "                if cfg.valores.contains_key(&k) {\n                    cfg.valores.shift_remove(&k);\n                    cfg.valores.insert(k, v);\n                }"),
    ("varredura não pula pastas de sistema", "src/biblioteca.rs",
     "                    if PASTAS_IGNORADAS.contains(", "                    if false && PASTAS_IGNORADAS.contains("),
    ("arquivos da pasta fora da ordem natural", "src/biblioteca.rs",
     "        let ordem = em_ordem(&arquivos, |x| x.0.nome.as_str(), false);",
     "        let ordem: Vec<usize> = (0..arquivos.len()).rev().collect();"),
    ("arquivo que falha não conta (gira para sempre)", "src/sessao.rs",
     "        self.erros_seguidos += 1;", "        self.erros_seguidos += 0;"),
    ("filtro que esconde tudo não volta para Tudo", "src/sessao.rs",
     "            return self.definir_filtro(Filtro::Tudo);", "            return Passo::NadaComFiltro;"),
    # Os da revisão independente: cada correção tem um teste que a pega.
    ("normcase pelo to_lowercase (Kelvin, sigma final)", "src/biblioteca.rs",
     "    let n = chamar(std::ptr::null_mut(), 0);\n    if n <= 0 {", "    let n = 0;\n    if n <= 0 {"),
    ("abspath sem tirar a barra do fim", "src/biblioteca.rs",
     r"    if (s.ends_with('\\') || s.ends_with('/')) && a.parent().is_some() {",
     r"    if false && (s.ends_with('\\') || s.ends_with('/')) && a.parent().is_some() {"),
    ("classe de erro só com os códigos mais comuns", "src/biblioteca.rs",
     '        2 | 3 | 15 | 18 | 53 | 67 | 161 | 206 => "FileNotFoundError",', '        2 | 3 => "FileNotFoundError",'),
    ("juntar confere repetido na lista que já cresceu", "src/sessao.rs",
     "if !self.pastas_abertas[..antes].contains(c) {", "if !self.pastas_abertas.contains(c) {"),
    ("subpastas sem o desempate estável do reverse=True", "src/biblioteca.rs",
     "        chaves.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));",
     "        chaves.sort_by(|a, b| b.0.cmp(&a.0).then(b.1.cmp(&a.1)));"),
    # Fase 3: a interface e o player (pegos pelo teste sem janela, tests/interface.rs).
    ("HEIC não recarrega: pula na 1ª tentativa", "src/player.rs",
     "        if tentativa >= HEIC_TENTATIVAS {", "        if tentativa >= 1 {"),
    ("espera do HEIC não cresce a cada tentativa", "src/player.rs",
     "HEIC_ESPERA_S + HEIC_PASSO_S * (tentativa - 1) as f64", "HEIC_ESPERA_S + 0.0 * (tentativa - 1) as f64"),
    ("pausa apertada durante a leitura do HEIC se perde", "src/player.rs",
     "            None => self.heic.borrow_mut().pausa_na_leitura.take().unwrap_or(false),", "            None => false,"),
    ("dois cliques no vídeo também pausam", "src/player.rs",
     "        self.t_clique.stop();\n        self.alternar_tela_cheia();", "        self.alternar_tela_cheia();"),
    ("teclas valem com o menu aberto", "src/player.rs",
     "        if (self.ui.get_menu_visivel() || self.ui.get_caixa_visivel()) && acao != Acao::Esc {",
     "        if self.ui.get_caixa_visivel() && acao != Acao::Esc {"),
    ("tecla segurada alterna de novo a cada repetição", "src/player.rs",
     "        if repetida && acao.alterna() {", "        if false && repetida && acao.alterna() {"),
    ("modo teste tira o motor do mudo", "src/player.rs",
     "        if !self.opcoes.teste {\n            let _ = self.motor.por_sim(\"mute\", mudo);",
     "        if true {\n            let _ = self.motor.por_sim(\"mute\", mudo);"),
    ("controles nunca somem na tela cheia", "src/player.rs",
     "            self.ui.set_controles_visiveis(false);\n            self.log(\"controles somem\");",
     "            self.log(\"controles somem\");"),
    ("Shift+clique não pega o intervalo", "src/player.rs",
     "            sel.extend(linhas[de..=ate].iter().copied());", "            sel.insert(linhas[ate]);"),
    ("Ctrl ao soltar não junta", "src/player.rs",
     "        let juntar = self.ctrl_ao_soltar.get() && !self.sessao.borrow().fila.itens.is_empty();",
     "        let juntar = false && !self.sessao.borrow().fila.itens.is_empty();"),
    ("fila escondida com largura 0 estica o palco para fora da tela", "ui/app.slint",
     "                        x: 0;\n                        width: 330px;\n", ""),
    ("HEIC: irot 1 gira para o lado errado", "src/heif.rs",
     '        1 => "transpose=cclock",', '        1 => "transpose=clock",'),
    # Os da revisão independente da fase 3.
    ("fila nova herda a seleção da antiga", "src/player.rs",
     "            self.selecao.borrow_mut().clear();\n            self.ancora.set(None);\n        }\n        let filtro_antes",
     "        }\n        let filtro_antes"),
    ("âncora do Shift fica velha depois de tirar", "src/player.rs",
     "        self.ancora.set(None); // os índices andaram", ""),
    ("a roda passa pela caixa e mexe no volume", "ui/app.slint",
     "        // segura o clique e a roda fora da caixa (é modal, como o QMessageBox da 1.5.1)\n        scroll-event(e) => { accept }",
     "        // segura o clique fora da caixa"),
    ("soltar com a caixa aberta carrega por trás", "src/player.rs",
     "        if self.ui.get_caixa_visivel() || self.dialogo_aberto.get() {", "        if false {"),
    ("teclas valem com a janela de escolher aberta", "src/player.rs",
     "        if self.dialogo_aberto.get() {\n            return true; // a janela de escolher é modal",
     "        if false {\n            return true; // a janela de escolher é modal"),
    ("eof ilegível passa para o próximo", "src/player.rs",
     '        if self.motor.ler_sim("eof-reached") != Some(true) {', '        if self.motor.ler_sim("eof-reached") == Some(false) {'),
    ("Ctrl lido 40 ms depois de soltar", "src/player.rs",
     "        let juntar = self.ctrl_ao_soltar.get() && ", "        let juntar = self.plat.ctrl_apertado() && "),
    ("raiz C:\\ vira \"C:\" no nome da pasta", "src/player.rs",
     "    let base = sem_drive(sem_barra).rsplit(", "    let base = sem_barra.rsplit("),
]


def testes():
    cmds = [
        [CARGO, "test", "--release", "--lib", "--test", "igual_151", "--test", "sessao", "--test", "biblioteca",
         "--test", "heif", "--test", "textos"],
        [CARGO, "test", "--release", "--test", "interface"],
        [CARGO, "test", "--release", "--test", "teste_logica", "--", MIDIA],
    ]
    for c in cmds:
        r = subprocess.run(c, cwd=RUST, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            todas = (r.stdout + r.stderr).splitlines()
            linhas = [l for l in todas if "FALHOU" in l or "panicked" in l] or [l for l in todas if "error" in l]
            return False, (linhas[:2] or ["(sem linha de falha)"])
    return True, []


ok0, _ = testes()
print(f"sem bug: {'passa' if ok0 else 'FALHA (pare: a base precisa passar)'}")
if not ok0:
    sys.exit(1)
pegos = 0
for nome, arq, velho, novo in BUGS:
    p = os.path.join(RUST, arq)
    # O arquivo pode estar com CRLF (autocrlf do git): o bug é plantado com o fim de linha dele e
    # o original volta byte a byte.
    with open(p, "rb") as f:
        original = f.read()
    crlf = b"\r\n" in original
    texto = original.decode("utf-8").replace("\r\n", "\n")
    assert texto.count(velho) == 1, (nome, texto.count(velho))
    com_bug = texto.replace(velho, novo)
    try:
        with open(p, "wb") as f:
            f.write((com_bug.replace("\n", "\r\n") if crlf else com_bug).encode("utf-8"))
        passou, onde = testes()
    finally:
        with open(p, "wb") as f:
            f.write(original)
    pegos += not passou
    print(f"[{'pego' if not passou else 'NÃO PEGO'}] {nome}: {onde[0][:150] if onde else 'os testes passaram com o bug'}")
print(f"{pegos} de {len(BUGS)} bugs plantados pegos")
ok1, _ = testes()
print(f"depois de desfazer tudo: {'passa' if ok1 else 'FALHA'}")
sys.exit(0 if pegos == len(BUGS) and ok1 else 1)
