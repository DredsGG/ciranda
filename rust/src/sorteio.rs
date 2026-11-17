//! Gerador de números aleatórios da fila (o `random.Random` da 1.5.1).
//!
//! xoshiro256** com a semente espalhada pelo SplitMix64 (os dois de domínio público, de
//! Blackman e Vigna). Sem semente, parte do relógio e de um contador. Não precisa ser
//! criptográfico: só embaralha a fila. A sequência não é a do Python (outra semente, outro
//! gerador); os testes conferem as propriedades (cada item uma vez por rodada etc.), não a ordem.

use std::sync::atomic::{AtomicU64, Ordering};

pub struct Sorteio {
    s: [u64; 4],
}

fn splitmix(x: &mut u64) -> u64 {
    *x = x.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *x;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

impl Sorteio {
    pub fn com_semente(semente: u64) -> Self {
        let mut x = semente;
        let s = [splitmix(&mut x), splitmix(&mut x), splitmix(&mut x), splitmix(&mut x)];
        Sorteio { s }
    }

    /// Semente do relógio + contador (duas filas criadas no mesmo instante não saem iguais).
    pub fn novo() -> Self {
        static CONTA: AtomicU64 = AtomicU64::new(0);
        let t = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0);
        let n = CONTA.fetch_add(1, Ordering::Relaxed);
        Self::com_semente(t ^ n.wrapping_mul(0xA24B_AED4_963E_E407) ^ (std::process::id() as u64) << 32)
    }

    pub fn proximo_u64(&mut self) -> u64 {
        let s = &mut self.s;
        let r = s[1].wrapping_mul(5).rotate_left(7).wrapping_mul(9);
        let t = s[1] << 17;
        s[2] ^= s[0];
        s[3] ^= s[1];
        s[1] ^= s[2];
        s[0] ^= s[3];
        s[2] ^= t;
        s[3] = s[3].rotate_left(45);
        r
    }

    /// Inteiro uniforme em `0..n` (n > 0), sem viés (rejeita a sobra, como o `_randbelow`).
    pub fn abaixo(&mut self, n: usize) -> usize {
        assert!(n > 0, "abaixo(0)");
        let n = n as u64;
        let zona = u64::MAX - (u64::MAX % n);
        loop {
            let x = self.proximo_u64();
            if x < zona {
                return (x % n) as usize;
            }
        }
    }

    /// `randrange(a, b)`: em `a..b`.
    pub fn faixa(&mut self, a: usize, b: usize) -> usize {
        a + self.abaixo(b - a)
    }

    /// `randint(a, b)`: em `a..=b`.
    pub fn entre(&mut self, a: usize, b: usize) -> usize {
        a + self.abaixo(b - a + 1)
    }

    /// `random.shuffle`: Fisher-Yates do fim para o começo.
    pub fn embaralhar<T>(&mut self, v: &mut [T]) {
        for i in (1..v.len()).rev() {
            let j = self.abaixo(i + 1);
            v.swap(i, j);
        }
    }
}
