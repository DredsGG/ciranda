//! Rotação e espelho da foto HEIC em grade (é assim que o iPhone grava), porta da `heif.py` da 1.5.1.
//!
//! O mpv 0.42 monta a grade de blocos, mas não aplica `irot` nem `imir` dela: a foto tirada em pé
//! apareceria deitada. Foto HEIC sem grade ele gira sozinho, então aqui só a grade conta.
//! Lê apenas o cabeçalho do contêiner (ISO/IEC 23008-12) e nunca falha: na dúvida, não muda nada.
//!
//! Igual à 1.5.1 até nos erros: cada leitura fora dos bytes (o `struct.error` e o `IndexError` do
//! Python) e cada falha de arquivo (`OSError`, `ValueError` do `seek`) vira [`Falha`], e a função
//! inteira devolve vazio, como o `try` da 1.5.1 (nunca uma lista pela metade). As leituras dentro
//! da meta são conferidas contra o tamanho da meta inteira, não da caixa: a 1.5.1 lê além do fim
//! da `pitm`, da `ipma` e das propriedades sem reclamar, e aqui também.

use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;

pub const EXTENSOES: [&str; 2] = [".heic", ".heif"];
const LIMITE_META: u64 = 8 * 1024 * 1024;

/// `ext in heif.EXTENSOES` (a extensão já vem em minúsculas, com o ponto).
pub fn eh_heif(ext_minuscula: &str) -> bool {
    EXTENSOES.contains(&ext_minuscula)
}

/// Uma exceção que o `try` da 1.5.1 pega: a função inteira devolve vazio.
struct Falha;

type Res<T> = Result<T, Falha>;

/// `dados[i]`.
fn byte(dados: &[u8], i: usize) -> Res<u8> {
    dados.get(i).copied().ok_or(Falha)
}

/// `struct.unpack_from` big-endian de `N` bytes em `i`.
fn grande<const N: usize>(dados: &[u8], i: usize) -> Res<[u8; N]> {
    let fim = i.checked_add(N).ok_or(Falha)?;
    dados.get(i..fim).and_then(|b| b.try_into().ok()).ok_or(Falha)
}

fn u16_em(dados: &[u8], i: usize) -> Res<u16> {
    grande::<2>(dados, i).map(u16::from_be_bytes)
}

fn u32_em(dados: &[u8], i: usize) -> Res<u32> {
    grande::<4>(dados, i).map(u32::from_be_bytes)
}

fn u64_em(dados: &[u8], i: usize) -> Res<u64> {
    grande::<8>(dados, i).map(u64::from_be_bytes)
}

/// `dados[a:b]` do Python: nunca falha, corta no fim.
fn fatia(dados: &[u8], a: usize, b: usize) -> &[u8] {
    let a = a.min(dados.len());
    &dados[a..b.clamp(a, dados.len())]
}

/// Uma caixa: tipo, início do corpo (depois do cabeçalho) e fim.
type Caixa = ([u8; 4], usize, usize);

/// O gerador `_caixas`: as caixas de `dados[ini:fim]`, uma atrás da outra. Tamanho 1 = 64 bits
/// logo depois do tipo, 0 = até o fim; tamanho torto para a varredura sem erro. Erro mesmo só o
/// tamanho de 64 bits que passa do fim dos bytes (não do `fim`): o `struct.error` da 1.5.1.
struct Caixas<'a> {
    dados: &'a [u8],
    ini: usize,
    fim: usize,
    acabou: bool,
}

fn caixas(dados: &[u8], ini: usize, fim: usize) -> Caixas<'_> {
    Caixas { dados, ini, fim, acabou: false }
}

impl Caixas<'_> {
    fn proxima(&mut self) -> Res<Option<Caixa>> {
        let ini = self.ini;
        if ini.checked_add(8).is_none_or(|f| f > self.fim) {
            return Ok(None);
        }
        let tam32 = u32_em(self.dados, ini)?;
        let tipo = grande::<4>(self.dados, ini + 4)?;
        let (tam, cab) = match tam32 {
            1 => (u64_em(self.dados, ini + 8)?, 16usize),
            0 => ((self.fim - ini) as u64, 8),
            t => (u64::from(t), 8),
        };
        // `ini + tam` no Python não estoura: aqui, estourar é passar do fim.
        let passa = (ini as u64).checked_add(tam).is_none_or(|f| f > self.fim as u64);
        if tam < cab as u64 || passa {
            return Ok(None);
        }
        let fim_caixa = ini + tam as usize;
        self.ini = fim_caixa;
        Ok(Some((tipo, ini + cab, fim_caixa)))
    }
}

impl Iterator for Caixas<'_> {
    type Item = Res<Caixa>;

    fn next(&mut self) -> Option<Res<Caixa>> {
        if self.acabou {
            return None;
        }
        match self.proxima() {
            Ok(Some(c)) => Some(Ok(c)),
            Ok(None) => {
                self.acabou = true;
                None
            }
            Err(f) => {
                self.acabou = true;
                Some(Err(f))
            }
        }
    }
}

/// `f.read(n)`: até `n` bytes (menos só no fim do arquivo).
fn ler(f: &mut File, n: u64) -> Res<Vec<u8>> {
    let mut v = Vec::new();
    f.by_ref().take(n).read_to_end(&mut v).map_err(|_| Falha)?;
    Ok(v)
}

/// `f.seek(pos)`: o Python recusa (`ValueError`) posição que não cabe num inteiro de 64 bits com sinal.
fn ir(f: &mut File, pos: u64) -> Res<()> {
    if pos > i64::MAX as u64 {
        return Err(Falha);
    }
    f.seek(SeekFrom::Start(pos)).map(|_| ()).map_err(|_| Falha)
}

/// `_ler_meta`: os bytes da caixa meta, que fica no nível de cima do arquivo (no máximo 64 caixas
/// olhadas). `None` e erro dão no mesmo para quem chama: nada a girar.
fn ler_meta(f: &mut File) -> Res<Option<Vec<u8>>> {
    let mut pos: u64 = 0;
    for _ in 0..64 {
        ir(f, pos)?;
        let cab = ler(f, 16)?;
        if cab.len() < 8 {
            return Ok(None);
        }
        let mut tam = u64::from(u32_em(&cab, 0)?);
        let tipo = grande::<4>(&cab, 4)?;
        let mut ini: u64 = 8;
        if tam == 1 {
            tam = u64_em(&cab, 8)?;
            ini = 16;
        }
        if &tipo == b"meta" {
            if tam <= ini || tam > LIMITE_META {
                return Ok(None);
            }
            ir(f, pos.checked_add(ini).ok_or(Falha)?)?;
            return ler(f, tam - ini).map(Some);
        }
        if tam < ini {
            return Ok(None);
        }
        // Passar de 2^64 é o mesmo que passar de 2^63: o próximo `seek` recusa.
        pos = pos.saturating_add(tam);
    }
    Ok(None)
}

/// `_tipo_do_item`: o tipo do item `alvo` na caixa iinf (`dados[ini:fim]`), da primeira infe dele.
fn tipo_do_item(dados: &[u8], ini: usize, fim: usize, alvo: u32) -> Res<Option<&[u8]>> {
    let versao = byte(dados, ini)?;
    let pos = ini + 4 + if versao == 0 { 2 } else { 4 };
    for c in caixas(dados, pos, fim) {
        let (tipo, a, _b) = c?;
        if &tipo != b"infe" {
            continue;
        }
        let v = byte(dados, a)?;
        if v < 2 {
            continue;
        }
        let (item, salto) = if v == 2 {
            (u32::from(u16_em(dados, a + 4)?), a + 8)
        } else {
            (u32_em(dados, a + 4)?, a + 10)
        };
        if item == alvo {
            return Ok(Some(fatia(dados, salto, salto + 4)));
        }
    }
    Ok(None)
}

/// `_propriedades_do_item`: índices (a partir de 1) das propriedades ligadas ao item, conforme a
/// caixa ipma que começa em `ini`. Como na 1.5.1, o fim da caixa não conta: lê até onde a contagem
/// mandar, e só para com erro no fim dos bytes.
fn propriedades_do_item(dados: &[u8], ini: usize, alvo: u32) -> Res<Vec<usize>> {
    let versao = byte(dados, ini)?;
    // `int.from_bytes(dados[ini + 1:ini + 4], "big")`: com menos de 3 bytes, o `n` logo abaixo já falha.
    let flags = fatia(dados, ini + 1, ini + 4).iter().fold(0u32, |f, &b| (f << 8) | u32::from(b));
    let n = u32_em(dados, ini + 4)?;
    let mut pos = ini + 8;
    let mut achou = Vec::new();
    for _ in 0..n {
        let item;
        if versao < 1 {
            item = u32::from(u16_em(dados, pos)?);
            pos += 2;
        } else {
            item = u32_em(dados, pos)?;
            pos += 4;
        }
        let qtd = byte(dados, pos)?;
        pos += 1;
        for _ in 0..qtd {
            let idx;
            if flags & 1 != 0 {
                idx = usize::from(u16_em(dados, pos)? & 0x7FFF);
                pos += 2;
            } else {
                idx = usize::from(byte(dados, pos)? & 0x7F);
                pos += 1;
            }
            if item == alvo {
                achou.push(idx);
            }
        }
    }
    Ok(achou)
}

/// irot: 90 graus anti-horários x valor.
fn giro(valor: u8) -> &'static str {
    match valor {
        1 => "transpose=cclock",
        2 => "hflip,vflip",
        _ => "transpose=clock",
    }
}

/// imir, conferido contra o libheif.
fn espelho(valor: u8) -> &'static str {
    if valor == 0 { "vflip" } else { "hflip" }
}

/// O filtro de vídeo que põe a grade em pé (giro e espelho, na ordem do arquivo), ou "" se não
/// precisa. Tem que ser filtro: o video-rotate do mpv não chega na grade já montada.
pub fn filtro_de_giro(caminho: &Path) -> String {
    let partes = transformacoes_da_grade(caminho);
    if partes.is_empty() { String::new() } else { format!("lavfi=[{}]", partes.join(",")) }
}

/// `_transformacoes_da_grade`: os filtros, na ordem do arquivo; vazio em qualquer erro.
pub fn transformacoes_da_grade(caminho: &Path) -> Vec<&'static str> {
    transformacoes(caminho).unwrap_or_default()
}

fn transformacoes(caminho: &Path) -> Res<Vec<&'static str>> {
    let meta = {
        let mut f = File::open(caminho).map_err(|_| Falha)?;
        ler_meta(&mut f)?
    };
    let Some(meta) = meta.filter(|m| !m.is_empty()) else { return Ok(Vec::new()) };
    let (mut primario, mut iinf, mut iprp) = (None, None, None);
    for c in caixas(&meta, 4, meta.len()) {
        let (tipo, a, b) = c?;
        match &tipo {
            b"pitm" => {
                primario = Some(if byte(&meta, a)? == 0 { u32::from(u16_em(&meta, a + 4)?) } else { u32_em(&meta, a + 4)? });
            }
            b"iinf" => iinf = Some((a, b)),
            b"iprp" => iprp = Some((a, b)),
            _ => {}
        }
    }
    let (Some(primario), Some(iinf), Some(iprp)) = (primario, iinf, iprp) else { return Ok(Vec::new()) };
    if tipo_do_item(&meta, iinf.0, iinf.1, primario)? != Some(b"grid".as_slice()) {
        return Ok(Vec::new());
    }
    let mut props: Vec<([u8; 4], usize)> = Vec::new();
    let mut ipma = None;
    for c in caixas(&meta, iprp.0, iprp.1) {
        let (tipo, a, b) = c?;
        match &tipo {
            b"ipco" => props = caixas(&meta, a, b).map(|c| c.map(|(t, x, _y)| (t, x))).collect::<Res<_>>()?,
            b"ipma" => ipma = Some(a),
            _ => {}
        }
    }
    let Some(ipma) = ipma else { return Ok(Vec::new()) };
    let mut partes = Vec::new();
    for idx in propriedades_do_item(&meta, ipma, primario)? {
        if !(1..=props.len()).contains(&idx) {
            continue;
        }
        let (tipo, pos) = props[idx - 1];
        if &tipo == b"irot" && byte(&meta, pos)? & 3 != 0 {
            partes.push(giro(byte(&meta, pos)? & 3));
        } else if &tipo == b"imir" {
            partes.push(espelho(byte(&meta, pos)? & 1));
        }
    }
    Ok(partes)
}
