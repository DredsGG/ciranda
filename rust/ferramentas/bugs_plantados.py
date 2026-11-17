"""Planta um bug conhecido por vez no núcleo e confere que os testes pegam cada um (os testes não
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
]


def testes():
    cmds = [
        [CARGO, "test", "--release", "--lib", "--test", "igual_151", "--test", "sessao", "--test", "biblioteca"],
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
    original = open(p, encoding="utf-8").read()
    assert original.count(velho) == 1, (nome, original.count(velho))
    try:
        open(p, "w", encoding="utf-8").write(original.replace(velho, novo))
        passou, onde = testes()
    finally:
        open(p, "w", encoding="utf-8").write(original)
    pegos += not passou
    print(f"[{'pego' if not passou else 'NÃO PEGO'}] {nome}: {onde[0][:150] if onde else 'os testes passaram com o bug'}")
print(f"{pegos} de {len(BUGS)} bugs plantados pegos")
ok1, _ = testes()
print(f"depois de desfazer tudo: {'passa' if ok1 else 'FALHA'}")
sys.exit(0 if pegos == len(BUGS) and ok1 else 1)
