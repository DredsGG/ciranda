"""Textos de licença do que está compilado dentro do libmpv-2.dll (mpv 0.42.0, build oficial LGPL).

Rodar quando o motor mudar (precisa de git e internet; nada baixado é executado, só os arquivos de
licença são lidos):
    python instalador/gerar_licencas_motor.py <pasta-de-cache>
Grava licenses/motor/<biblioteca>.txt (um por biblioteca, com o aviso de copyright dela),
licenses/motor/subrandr-crates.txt, licenses/motor/LISTA.tsv e a tabela entre as marcas de
AVISOS-DE-TERCEIROS.txt e THIRD-PARTY-NOTICES.md.

De onde vem a lista: a configuração do FFmpeg gravada dentro da DLL, o ci/build-mingw64-full.sh da
tag v0.42.0 do mpv e a receita FFmpeg-Builds no último commit antes do build do mpv (c63bb308,
2026-11-04), que fixa o commit de cada biblioteca. O que o mpv baixa sem versão fixa (LuaJIT,
libsixel, libarchive, subrandr, mujs) está no commit da data do build: é dedução, marcada na lista.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "licenses", "motor")
FB = "receita FFmpeg-Builds c63bb308"
MPV = "ci/build-mingw64-full.sh do mpv v0.42.0"
DATA = "na data do build (2026-11-04), dedução"

# nome, repositório, commit ou tag, origem, licença usada (SPDX), observação
LIBS = [
    ("mpv", "https://github.com/mpv-player/mpv.git", "v0.42.0", "o motor", "LGPL-2.1-or-later", "compilado com -Dgpl=false"),
    ("FFmpeg", "https://github.com/FFmpeg/FFmpeg.git", "baa68e68b34e2de912eb7e94342cebd2545f05ed", MPV, "LGPL-3.0-or-later", "--enable-version3, sem --enable-gpl"),
    ("libiconv", "https://git.savannah.gnu.org/git/libiconv.git", "b5a1735e02bf", FB, "LGPL-2.1-or-later", ""),
    ("zlib", "https://github.com/madler/zlib.git", "9d314c341b2c", FB, "Zlib", ""),
    ("fribidi", "https://github.com/fribidi/fribidi.git", "d2f3e1f4946e", FB, "LGPL-2.1-or-later", ""),
    ("gmp", "https://github.com/BtbN/gmplib.git", "5c3e9a9d52b6", FB, "LGPL-3.0-or-later", "licença dupla LGPL-3+ ou GPL-2+; usada a LGPL"),
    ("libogg", "https://github.com/xiph/ogg.git", "06a5e0262cdc", FB, "BSD-3-Clause", ""),
    ("libpng", "https://github.com/glennrp/libpng.git", "0b0876829d77", FB, "libpng-2.0", ""),
    ("libxml2", "https://github.com/GNOME/libxml2.git", "c79c9612fcc7", FB, "MIT", ""),
    ("openssl", "https://github.com/openssl/openssl.git", "openssl-3.6.5", FB, "Apache-2.0", ""),
    ("xz", "https://github.com/tukaani-project/xz.git", "299eb5c3f597", FB, "0BSD", "liblzma; as ferramentas GPL do xz não entram"),
    ("brotli", "https://github.com/google/brotli.git", "2e2bcf17ae71", FB, "MIT", ""),
    ("freetype", "https://gitlab.freedesktop.org/freetype/freetype.git", "4ba7c3d82ab8", FB, "FTL", "licença dupla FTL ou GPL-2; usada a FTL"),
    ("fontconfig", "https://gitlab.freedesktop.org/fontconfig/fontconfig.git", "b25ffeabd15b", FB, "HPND-sell-variant", ""),
    ("harfbuzz", "https://github.com/harfbuzz/harfbuzz.git", "75d8ac5d2313", FB, "MIT-Modern-Variant", "\"Old MIT\""),
    ("lcms2", "https://github.com/mm2/Little-CMS.git", "1112313b3784", FB, "MIT", ""),
    ("libsamplerate", "https://github.com/libsndfile/libsamplerate.git", "0844c208f683", FB, "BSD-2-Clause", "dependência do SDL2"),
    ("libudfread", "https://code.videolan.org/videolan/libudfread.git", "b0bc6957e7e0", FB, "LGPL-2.1-or-later", ""),
    ("libunibreak", "https://github.com/adah1972/libunibreak.git", "f8172fe771ef", FB, "Zlib", ""),
    ("libvorbis", "https://github.com/xiph/vorbis.git", "1b75110b5a27", FB, "BSD-3-Clause", ""),
    ("OpenCL-Headers", "https://github.com/KhronosGroup/OpenCL-Headers.git", "82f60316cc142e7b21dc1d8983b26de18858fbd9", FB, "Apache-2.0", ""),
    ("OpenCL-ICD-Loader", "https://github.com/KhronosGroup/OpenCL-ICD-Loader.git", "5192c84f8059e5f703e5452929b613f9487f6e4c", FB, "Apache-2.0", ""),
    ("vmaf", "https://github.com/Netflix/vmaf.git", "f712fa7564fe", FB, "BSD-2-Clause-Patent", ""),
    ("libsvm", "https://github.com/cjlin1/libsvm.git", "v324", "copiado dentro do vmaf (libvmaf/src/svm.cpp, LIBSVM_VERSION 324)", "BSD-3-Clause", ""),
    ("xxhash", "https://github.com/Cyan4973/xxHash.git", "61fd0fece2eb", FB, "BSD-2-Clause", ""),
    ("zstd", "https://github.com/facebook/zstd.git", "49cf51799ea0", FB, "BSD-3-Clause", "licença dupla BSD ou GPL-2; usada a BSD"),
    ("Vulkan-Headers", "https://github.com/KhronosGroup/Vulkan-Headers.git", "v1.4.366", FB, "Apache-2.0 OR MIT", ""),
    ("Vulkan-Shim-Loader", "https://github.com/BtbN/Vulkan-Shim-Loader.git", "65b3936528cd", FB, "MIT", ""),
    ("shaderc", "https://github.com/google/shaderc.git", "2737994b552137a85545f956e303d620e6ff232c", FB, "Apache-2.0", ""),
    ("glslang", "https://github.com/KhronosGroup/glslang.git", "73b25650df6dc4545966674531e6b7cc8f5d2407", "DEPS do shaderc", "BSD-3-Clause AND MIT AND Apache-2.0", "o analisador gerado pelo Bison tem a exceção do Bison"),
    ("SPIRV-Tools", "https://github.com/KhronosGroup/SPIRV-Tools.git", "71f287f18ed78d496e724fbfb1c3feae3a2af75a", "DEPS do shaderc", "Apache-2.0", ""),
    ("SPIRV-Headers", "https://github.com/KhronosGroup/SPIRV-Headers.git", "fbf86836a9b1", FB, "MIT", ""),
    ("SPIRV-Cross", "https://github.com/KhronosGroup/SPIRV-Cross.git", "300681bbcb83", FB, "Apache-2.0", ""),
    ("AMF", "https://github.com/GPUOpen-LibrariesAndSDKs/AMF.git", "57ee0cfb0e1a", FB, "MIT", "só cabeçalhos"),
    ("aom", "https://aomedia.googlesource.com/aom", "9ace39e02a34", FB, "BSD-2-Clause", "+ licença de patentes AOMedia 1.0"),
    ("chromaprint", "https://github.com/acoustid/chromaprint.git", "3b38c100022b", FB, "MIT AND LGPL-2.1-or-later", "FFT pelo kissfft (BSD-3), não pelo FFTW"),
    ("dav1d", "https://code.videolan.org/videolan/dav1d.git", "b8b2d726b4b7", FB, "BSD-2-Clause", ""),
    ("nv-codec-headers", "https://github.com/FFmpeg/nv-codec-headers.git", "f2053071ea93", FB, "MIT", "só cabeçalhos; texto do cabeçalho dos arquivos"),
    ("game-music-emu", "https://github.com/libgme/game-music-emu.git", "f68963b1de06", FB, "LGPL-2.1-or-later", "emulador YM2612 Nuked (padrão, LGPL); o MAME (GPL) não é usado"),
    ("kvazaar", "https://github.com/ultravideo/kvazaar.git", "1f11f9ae33ef", FB, "BSD-3-Clause", ""),
    ("LCEVCdec", "https://github.com/v-novaltd/LCEVCdec.git", "741fb7c869cf", FB, "BSD-3-Clause-Clear", ""),
    ("aribb24", "https://github.com/nkoriyama/aribb24.git", "5e9be272f96e", FB, "LGPL-3.0-or-later", ""),
    ("libaribcaption", "https://github.com/xqq/libaribcaption.git", "37dde0f32652", FB, "MIT", ""),
    ("libass", "https://github.com/libass/libass.git", "f61db567e659", FB, "ISC", ""),
    ("libbluray", "https://code.videolan.org/videolan/libbluray.git", "f33a738fd7bb", FB, "LGPL-2.1-or-later", "os .jar do BD-J não vão no pacote"),
    ("libpsl", "https://github.com/rockdaboot/libpsl.git", "620d51d13351", FB, "MIT", ""),
    ("nghttp2", "https://github.com/nghttp2/nghttp2.git", "3baf9561e09f", FB, "MIT", ""),
    ("nghttp3", "https://github.com/ngtcp2/nghttp3.git", "ac11a456eb9d", FB, "MIT", ""),
    ("ngtcp2", "https://github.com/ngtcp2/ngtcp2.git", "20da63db12a3", FB, "MIT", ""),
    ("curl", "https://github.com/curl/curl.git", "bc677a8f16a5", FB, "curl", ""),
    ("libjxl", "https://github.com/libjxl/libjxl.git", "e47d2a2b5bb418f2947ce07f36cb048861db3820", FB, "BSD-3-Clause", "+ concessão de patentes"),
    ("highway", "https://github.com/google/highway.git", "457c891775a7397bdb0376bb1031e6e027af1c48", "submódulo do libjxl", "Apache-2.0 OR BSD-3-Clause", ""),
    ("LAME", "https://svn.code.sf.net/p/lame/svn/trunk/lame", "7113", FB, "LGPL-2.0-or-later", "repositório SVN, revisão 7113"),
    ("opus", "https://github.com/xiph/opus.git", "a8b2545eec71", FB, "BSD-3-Clause", ""),
    ("libplacebo", "https://code.videolan.org/videolan/libplacebo.git", "275f7dea27924cdd34ab2e6c20e448b6bc4fab65", FB, "LGPL-2.1-or-later", ""),
    ("glad", "https://github.com/Dav1dde/glad.git", "73db193f853e2ee079bf3ca8a64aa2eaf6459043", "submódulo do libplacebo", "MIT AND Apache-2.0", ""),
    ("fast_float", "https://github.com/fastfloat/fast_float.git", "97b54ca9e75f5303507699d27c6b4f4efe4641a1", "submódulo do libplacebo", "Apache-2.0 OR BSL-1.0 OR MIT", ""),
    ("mbedtls", "https://github.com/Mbed-TLS/mbedtls.git", "v4.2.0", FB, "Apache-2.0", "licença dupla Apache-2.0 ou GPL-2+; usada a Apache"),
    ("tf-psa-crypto", "https://github.com/Mbed-TLS/TF-PSA-Crypto.git", "73c5da561c8e5253db7b1fb440eda86fde8d8024", "submódulo do mbedtls", "Apache-2.0", "licença dupla Apache-2.0 ou GPL-2+; usada a Apache"),
    ("librist", "https://code.videolan.org/rist/librist.git", "47ad5513d1aa", FB, "BSD-2-Clause", ""),
    ("libssh", "https://gitlab.com/libssh/libssh-mirror.git", "9de02f3d01ba", FB, "LGPL-2.1-or-later", ""),
    ("theora", "https://github.com/xiph/theora.git", "28fd5ec77f0a", FB, "BSD-3-Clause", ""),
    ("libvpx", "https://chromium.googlesource.com/webm/libvpx", "900b2a52b69e", FB, "BSD-3-Clause", "+ concessão de patentes"),
    ("libwebp", "https://chromium.googlesource.com/webm/libwebp", "1844042d1ca7", FB, "BSD-3-Clause", "+ concessão de patentes"),
    ("libzmq", "https://github.com/zeromq/libzmq.git", "46493370217a", FB, "MPL-2.0", ""),
    ("lv2", "https://github.com/lv2/lv2.git", "3c57dae600a5", FB, "ISC", ""),
    ("serd", "https://github.com/drobilla/serd.git", "b621b0bc790d", FB, "ISC", ""),
    ("zix", "https://github.com/drobilla/zix.git", "17d632393f5a", FB, "ISC", ""),
    ("sord", "https://github.com/drobilla/sord.git", "4b5232bb91e7", FB, "ISC", ""),
    ("sratom", "https://github.com/lv2/sratom.git", "9e8ee84eed50", FB, "ISC", ""),
    ("lilv", "https://github.com/lv2/lilv.git", "4b8f30055fa5", FB, "ISC", ""),
    ("libvpl", "https://github.com/intel/libvpl.git", "674d015bcb29", FB, "MIT", ""),
    ("openapv", "https://github.com/AcademySoftwareFoundation/openapv.git", "b4ff69856b4c", FB, "BSD-3-Clause", ""),
    ("opencore-amr", "https://git.code.sf.net/p/opencore-amr/code", "7dba8c322384", FB, "Apache-2.0", ""),
    ("openh264", "https://github.com/cisco/openh264.git", "1bca62311e44", FB, "BSD-2-Clause", ""),
    ("openjpeg", "https://github.com/uclouvain/openjpeg.git", "8314119b067c", FB, "BSD-2-Clause", ""),
    ("libopenmpt", "https://github.com/OpenMPT/openmpt.git", "3ee3c8000b45", FB, "BSD-3-Clause", "sem mpg123"),
    ("SDL2", "https://github.com/libsdl-org/SDL.git", "8acf7cfc0f88", FB, "Zlib", ""),
    ("snappy", "https://github.com/google/snappy.git", "946606459314", FB, "BSD-3-Clause", ""),
    ("soxr", "https://git.code.sf.net/p/soxr/code", "945b592b7047", FB, "LGPL-2.1-or-later", ""),
    ("srt", "https://github.com/Haivision/srt.git", "9f2390232a82", FB, "MPL-2.0", ""),
    ("SVT-AV1", "https://github.com/AOMediaCodec/SVT-AV1.git", "ad11d76a6c9c", FB, "BSD-3-Clause-Clear", "+ licença de patentes AOMedia 1.0"),
    ("twolame", "https://github.com/njh/twolame.git", "6fced852d4d5", FB, "LGPL-2.1-or-later", ""),
    ("uavs3d", "https://github.com/uavs3/uavs3d.git", "0e20d2c29185", FB, "BSD-3-Clause", ""),
    ("libva", "https://github.com/intel/libva.git", "f052e984e0c8bf10784198cc311b23c567b1367f", FB, "MIT", ""),
    ("vapoursynth", "https://github.com/vapoursynth/vapoursynth.git", "R81", FB, "LGPL-2.1-or-later", "só cabeçalhos; a biblioteca é carregada em tempo de execução e não vem junto"),
    ("vvenc", "https://github.com/fraunhoferhhi/vvenc.git", "0e7508b811bb", FB, "BSD-3-Clause-Clear", ""),
    ("zimg", "https://github.com/sekrit-twc/zimg.git", "67e0603271c080e22c8429856dd4a8a56587e61e", FB, "WTFPL", ""),
    ("graphengine", "https://github.com/sekrit-twc/graphengine.git", "cb5b2ce13384ec2491f0c37256ea210034799f69", "submódulo do zimg", "WTFPL", ""),
    ("zvbi", "https://github.com/zapping-vbi/zvbi", "34bb6f660c5c1bacd4a66cc7b22311e4ca3c1ab5", FB, "GPL-2.0-only AND LGPL-2.0-or-later",
     "⚠️ GPL: src/packet-830.c e src/pdc.c são GPL-2 e entram na biblioteca; o FFmpeg não lista o libzvbi como GPL"),
    ("mingw-w64", "https://git.code.sf.net/p/mingw-w64/mingw-w64.git", "7213d719fe34", FB, "ZPL-2.1 AND MIT AND public-domain", "runtime do compilador"),
    ("mingw-std-threads", "https://github.com/meganz/mingw-std-threads.git", "c931bac289dd", FB, "BSD-2-Clause", ""),
    ("LuaJIT", "https://github.com/LuaJIT/LuaJIT.git", "ea9eb7edb5eac4a9d175d74523db34fac0fa5180", f"{MPV}, ramo v2.1 {DATA}", "MIT", ""),
    ("libsixel", "https://github.com/saitoha/libsixel.git", "ca31d6a2d2d69eaed4b2be40f69c305380948e8f", f"{MPV}, master {DATA}", "MIT", ""),
    ("libarchive", "https://github.com/libarchive/libarchive.git", "d56567180f781878eecf5b9af7155cc6de6c2de2", f"{MPV}, master {DATA}", "BSD-2-Clause", ""),
    ("uchardet", "https://gitlab.freedesktop.org/uchardet/uchardet.git", "v0.0.8", MPV, "MPL-1.1 OR LGPL-2.1-or-later", "tripla com GPL-2+; usada MPL/LGPL"),
    ("subrandr", "https://github.com/afishhh/subrandr.git", "a41311bb5e382abcc47ef141e2ea1098d22a8d58", f"{MPV}, master {DATA}", "MPL-2.0", "crates Rust em subrandr-crates.txt"),
    ("mujs", "https://codeberg.org/ccxvii/mujs.git", "1.3.8", f"{MPV}, wrapdb {DATA}", "ISC", ""),
    ("cppwinrt", "https://github.com/microsoft/cppwinrt.git", "2.0.250303.1", MPV, "MIT", "cabeçalhos gerados"),
    ("gcc-runtime", "https://github.com/gcc-mirror/gcc.git", "releases/gcc-16.2.0", "compilador (libgcc, libstdc++)", "GPL-3.0-or-later WITH GCC-exception-3.1",
     "a exceção de runtime libera a distribuição do programa compilado"),
    ("rust-std", "https://github.com/rust-lang/rust.git", "1.99.1", "biblioteca padrão do Rust (subrandr)", "MIT OR Apache-2.0",
     "a DLL traz caminhos /rustc/58cf8f9c35b3..., o commit da tag 1.99.1"),
]
NOME_LIC = re.compile(r"^(licen[cs]e|copying|copyright|notice|unlicense|patents?)", re.I)
FIXOS = {"gcc-runtime": ["COPYING3", "COPYING.RUNTIME"], "rust-std": ["LICENSE-MIT", "LICENSE-APACHE", "COPYRIGHT"],
         "nv-codec-headers": ["include/ffnvcodec/dynlink_loader.h"]}
SO_RAIZ = {"mpv", "FFmpeg", "libsvm"}  # o aviso deles está na raiz; o resto da árvore são partes deles mesmos
# avisos que só existem no cabeçalho do arquivo-fonte (código de terceiros copiado para dentro do projeto)
CABECALHOS = {"vmaf": ["libvmaf/src/feature/third_party/xiph/psnr_hvs.c"]}
IGNORAR = {"license-checker.cfg"}
# código embutido em subpastas (third_party etc.) também tem aviso; teste, documentação e exemplo não entram na DLL
FORA = re.compile(r"(^|/)(tests?|testdata|test_data|testing|unittests?|fuzz\w*|docs?|examples?|samples?|demos?|"
                  r"\.github|bench\w*|tools?)(/|$)", re.I)


def _git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, timeout=900)


def _svn(lib):
    """LAME vive num SVN: lê o COPYING da revisão pela página do SourceForge."""
    nome, url, ref = lib[:3]
    bruto = f"https://sourceforge.net/p/lame/svn/{ref}/tree/trunk/lame/COPYING?format=raw"
    texto = urllib.request.urlopen(urllib.request.Request(bruto, headers={"User-Agent": "ciranda-licencas"}), timeout=60).read()
    return nome, f"r{ref}", [("COPYING", texto.decode("utf-8", "replace"))]


def buscar(cache, lib):
    nome, url, ref = lib[:3]
    if url.startswith("https://svn."):
        return _svn(lib)
    d = os.path.join(cache, "git", nome)
    os.makedirs(d, exist_ok=True)
    if not os.path.isdir(os.path.join(d, ".git")):
        _git("init", "-q", d)
        _git("remote", "add", "o", url, cwd=d)
    alvo = _git("rev-parse", "--verify", "-q", ref + "^{commit}", cwd=d).stdout.decode().strip()
    if not alvo:
        if _git("fetch", "-q", "--depth", "1", "--filter=blob:none", "o", ref, cwd=d).returncode == 0:
            alvo = _git("rev-parse", "FETCH_HEAD", cwd=d).stdout.decode().strip()
        else:  # servidor que não aceita commit curto: busca tudo, sem conteúdo
            _git("fetch", "-q", "--filter=blob:none", "--tags", "o", cwd=d)
            alvo = _git("rev-parse", "--verify", "-q", ref + "^{commit}", cwd=d).stdout.decode().strip()
    if not alvo:
        raise SystemExit(f"{nome}: não achei {ref} em {url}")
    if nome in FIXOS:
        arqs = FIXOS[nome]
    else:
        todos = _git("ls-tree", "-r", "--name-only", alvo, cwd=d).stdout.decode().splitlines()
        arqs = []
        for caminho in todos:
            partes = caminho.split("/")
            if nome in SO_RAIZ and len(partes) > 1 and not NOME_LIC.match(partes[0]):
                continue
            # o arquivo se chama LICENSE/COPYING/..., ou está dentro de uma pasta com esse nome (licenses/fmt/...)
            if not any(NOME_LIC.match(p) for p in partes) or partes[-1] in IGNORAR or FORA.search(caminho):
                continue
            arqs.append(caminho)
    textos = []
    for f in sorted(arqs, key=lambda c: (c.count("/"), c.lower())):
        t = _git("show", f"{alvo}:{f}", cwd=d)
        if t.returncode == 0 and t.stdout.strip() and not t.stdout.startswith(b"tree "):
            texto = t.stdout.decode("utf-8", "replace")
            if nome == "nv-codec-headers":  # só o aviso do cabeçalho
                texto = texto[:texto.index("*/") + 2]
            textos.append((f, texto))
    for f in CABECALHOS.get(nome, []):
        t = _git("show", f"{alvo}:{f}", cwd=d).stdout.decode("utf-8", "replace")
        textos.append((f + " (cabeçalho)", t[:t.index("*/") + 2]))
    if not textos:
        raise SystemExit(f"{nome}: nenhum texto de licença")
    return nome, alvo, textos


def crates(cache, sha):
    d = os.path.join(cache, "git", "subrandr")
    lock = _git("show", f"{sha}:Cargo.lock", cwd=d).stdout.decode()
    pacotes = re.findall(r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"\nsource = "registry', lock)
    saida = []
    for n, v in pacotes:
        arq = os.path.join(cache, "crates", f"{n}-{v}.crate")
        os.makedirs(os.path.dirname(arq), exist_ok=True)
        cab = {"User-Agent": "ciranda-licencas (github.com/DredsGG/ciranda)"}
        if not os.path.exists(arq):
            with open(arq, "wb") as f:
                f.write(urllib.request.urlopen(urllib.request.Request(
                    f"https://static.crates.io/crates/{n}/{n}-{v}.crate", headers=cab), timeout=60).read())
        lic, textos = None, []
        with tarfile.open(arq, mode="r:gz") as tf:
            for m in tf.getmembers():
                partes = m.name.split("/")
                if m.isfile() and len(partes) == 2:
                    if NOME_LIC.match(partes[1]):
                        textos.append((partes[1], tf.extractfile(m).read().decode("utf-8", "replace")))
                    elif partes[1] == "Cargo.toml":
                        achou = re.search(r'^license\s*=\s*"([^"]+)"', tf.extractfile(m).read().decode("utf-8", "replace"), re.M)
                        lic = achou.group(1) if achou else None
        saida.append((n, v, lic, textos))
    return saida


def escrever(resultados, lista_crates):
    os.makedirs(DESTINO, exist_ok=True)
    for f in os.listdir(DESTINO):
        os.remove(os.path.join(DESTINO, f))
    linhas = ["biblioteca\tversao\tlicenca\tfonte\torigem\tobservacao"]
    info = {lib[0]: lib for lib in LIBS}
    for nome, sha, textos in resultados:
        _, url, ref, origem, spdx, obs = info[nome]
        versao = ref if not re.fullmatch(r"[0-9a-f]{12,40}", ref) else sha[:12]
        fonte = f"{url} @ {sha}"
        corpo = [f"Biblioteca: {nome}", f"Versão: {versao} (commit {sha})", f"Licença: {spdx}", f"Fonte: {url}",
                 f"Origem: {origem}"] + ([f"Observação: {obs}"] if obs else []) + [""]
        for arq, texto in textos:
            corpo += [f"===== {arq} =====", texto.rstrip(), ""]
        with open(os.path.join(DESTINO, f"{nome}.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(corpo) + "\n")
        linhas.append("\t".join([nome, versao, spdx, fonte, origem, obs]))
    vistos = {}
    corpo = ["Crates Rust do subrandr (Cargo.lock no commit usado). Inclui crates de outras plataformas que não",
             "entram na DLL de Windows; a lista é maior que o necessário de propósito.", ""]
    for n, v, lic, textos in lista_crates:
        corpo.append(f"### {n} {v}  licença: {lic or '⚠️ não declarada no Cargo.toml'}")
        for arq, texto in textos:
            chave = texto.strip()
            if chave in vistos:
                corpo.append(f"{arq}: mesmo texto de {vistos[chave]}")
            else:
                vistos[chave] = f"{n} {v} ({arq})"
                corpo += [f"===== {arq} =====", texto.rstrip()]
        if not textos:
            corpo.append("(o pacote não traz arquivo de licença; vale a licença declarada acima)")
        corpo.append("")
    with open(os.path.join(DESTINO, "subrandr-crates.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(corpo) + "\n")
    with open(os.path.join(DESTINO, "LISTA.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(linhas) + "\n")
    _tabelas(resultados)


def _tabelas(resultados):
    info = {lib[0]: lib for lib in LIBS}
    md = ["| Library | Version | License | Source |", "|---|---|---|---|"]
    txt = []
    for nome, sha, _ in resultados:
        _, url, ref, _origem, spdx, obs = info[nome]
        versao = ref if not re.fullmatch(r"[0-9a-f]{12,40}", ref) else sha[:12]
        nota = " ⚠️" if "⚠️" in obs else ""
        md.append(f"| {nome}{nota} | `{versao}` | {spdx} | {url} |")
        txt.append(f"   {nome:20} {versao:22} {spdx}{nota}\n   {'':20} {url}")
    _trocar(os.path.join(RAIZ, "THIRD-PARTY-NOTICES.md"), "<!-- motor:inicio -->", "<!-- motor:fim -->", "\n".join(md))
    _trocar(os.path.join(RAIZ, "AVISOS-DE-TERCEIROS.txt"), "[tabela do motor: início]", "[tabela do motor: fim]", "\n".join(txt))


def _trocar(arquivo, ini, fim, conteudo):
    with open(arquivo, encoding="utf-8") as f:
        t = f.read()
    a, b = t.index(ini) + len(ini), t.index(fim)
    with open(arquivo, "w", encoding="utf-8", newline="\n") as f:
        f.write(t[:a] + "\n" + conteudo + "\n" + t[b:])


if __name__ == "__main__":
    cache = sys.argv[1]
    with ThreadPoolExecutor(8) as ex:
        resultados = list(ex.map(lambda lib: buscar(cache, lib), LIBS))
    sha_sub = dict((n, s) for n, s, _ in resultados)["subrandr"]
    escrever(resultados, crates(cache, sha_sub))
    print(f"{len(resultados)} bibliotecas e os crates do subrandr em {DESTINO}")
