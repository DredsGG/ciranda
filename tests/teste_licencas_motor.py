"""1.5.1: falha se faltar o texto de licença de alguma biblioteca compilada dentro do libmpv-2.dll.
Confere a lista de licenses/motor contra a receita (instalador/gerar_licencas_motor.py), as tabelas dos
avisos, o empacotamento (Setup e zip) e, se a DLL estiver na pasta, a configuração do FFmpeg dentro dela.
    python testes/teste_licencas_motor.py
"""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "instalador"))
import gerar_licencas_motor as G  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    assert cond, msg
    n += 1


MOTOR = os.path.join(RAIZ, "licenses", "motor")
lista = {}
with open(os.path.join(MOTOR, "LISTA.tsv"), encoding="utf-8") as f:
    for linha in f.read().splitlines()[1:]:
        c = linha.split("\t")
        lista[c[0]] = c
nomes = [lib[0] for lib in G.LIBS]
ok(sorted(lista) == sorted(nomes), f"LISTA.tsv diferente da receita: {set(nomes) ^ set(lista)}")

COPYRIGHT = re.compile(r"copyright|\(c\)|©|permission is hereby granted|public license|licensed under|apache license", re.I)
for nome in nomes:
    arq = os.path.join(MOTOR, f"{nome}.txt")
    ok(os.path.isfile(arq), f"falta licenses/motor/{nome}.txt")
    texto = open(arq, encoding="utf-8").read()
    corpo = texto.split("=====", 1)[-1]
    ok("=====" in texto and len(corpo) > 200, f"{nome}: sem o texto da licença")
    ok(COPYRIGHT.search(corpo), f"{nome}: sem aviso de copyright nem texto de licença reconhecível")
    ok(not re.search(r"^tree [0-9a-f]{40}:", texto, re.M), f"{nome}: listagem de pasta no lugar do texto de licença")
    ok(lista[nome][2] and lista[nome][3].startswith("http"), f"{nome}: sem licença ou link do código-fonte")

crates = open(os.path.join(MOTOR, "subrandr-crates.txt"), encoding="utf-8").read()
ok(crates.count("### ") > 100, "subrandr-crates.txt incompleto")

md = open(os.path.join(RAIZ, "THIRD-PARTY-NOTICES.md"), encoding="utf-8").read()
txt = open(os.path.join(RAIZ, "AVISOS-DE-TERCEIROS.txt"), encoding="utf-8").read()
tab_md = md[md.index("<!-- motor:inicio -->"):md.index("<!-- motor:fim -->")]
tab_txt = txt[txt.index("[tabela do motor: início]"):txt.index("[tabela do motor: fim]")]
for nome in nomes:
    ok(f"| {nome}" in tab_md, f"{nome} fora da tabela do THIRD-PARTY-NOTICES.md")
    ok(re.search(rf"^   {re.escape(nome)}\s", tab_txt, re.M), f"{nome} fora da tabela do AVISOS-DE-TERCEIROS.txt")
ok("zvbi" in txt and "GPL" in txt and os.path.isfile(os.path.join(RAIZ, "licenses", "GPL-2.0.txt")), "aviso do zvbi (GPL-2) sumiu")

iss = open(os.path.join(RAIZ, "instalador", "ciranda.iss"), encoding="utf-8").read()
ok(re.search(r'Source: "\.\.\\licenses\\\*".*recursesubdirs', iss), "o Setup não leva licenses\\ com as subpastas")
wf_arq = next(p for p in (os.path.join(RAIZ, "instalador", "release.yml"),  # pasta do PC
                          os.path.join(RAIZ, ".github", "workflows", "release.yml")) if os.path.isfile(p))  # repositório
wf = open(wf_arq, encoding="utf-8").read()
ok("cp -r licenses" in wf, "o zip portátil não leva licenses/")

# a DLL de verdade: toda biblioteca ligada na configuração do FFmpeg tem texto
POR_OPCAO = {
    "iconv": "libiconv", "zlib": "zlib", "libxml2": "libxml2", "libvmaf": "vmaf", "fontconfig": "fontconfig",
    "libharfbuzz": "harfbuzz", "libfreetype": "freetype", "libfribidi": "fribidi", "lcms2": "lcms2", "vulkan": "Vulkan-Shim-Loader",
    "libdav1d": "dav1d", "libvorbis": "libvorbis", "gmp": "gmp", "lzma": "xz", "liblcevc-dec": "LCEVCdec", "opencl": "OpenCL-ICD-Loader",
    "amf": "AMF", "libaom": "aom", "chromaprint": "chromaprint", "ffnvcodec": "nv-codec-headers", "libgme": "game-music-emu",
    "libkvazaar": "kvazaar", "libaribb24": "aribb24", "libaribcaption": "libaribcaption", "libass": "libass", "libbluray": "libbluray",
    "libcurl": "curl", "libjxl": "libjxl", "libmp3lame": "LAME", "libopus": "opus", "libplacebo": "libplacebo", "librist": "librist",
    "libssh": "libssh", "libtheora": "theora", "libvpx": "libvpx", "libwebp": "libwebp", "libzmq": "libzmq", "lv2": "lilv",
    "libvpl": "libvpl", "liboapv": "openapv", "libopencore-amrnb": "opencore-amr", "libopencore-amrwb": "opencore-amr",
    "libopenh264": "openh264", "libopenjpeg": "openjpeg", "libopenmpt": "libopenmpt", "sdl2": "SDL2", "libsnappy": "snappy",
    "libsoxr": "soxr", "libsrt": "srt", "libsvtav1": "SVT-AV1", "libtwolame": "twolame", "libuavs3d": "uavs3d", "vaapi": "libva",
    "vapoursynth": "vapoursynth", "libvvenc": "vvenc", "libzimg": "zimg", "libzvbi": "zvbi", "libshaderc": "shaderc",
}
SISTEMA = {"pthreads", "schannel", "cuda-llvm", "version3", "static"}
dll = os.path.join(RAIZ, "libmpv-2.dll")
if os.path.isfile(dll):
    dados = open(dll, "rb").read()
    conf = re.search(rb"--prefix=/opt/ffbuild [^\0]+", dados).group(0).decode()
    ligadas = set(re.findall(r"--enable-([a-z0-9-]+)", conf)) - SISTEMA
    desligadas = set(re.findall(r"--disable-([a-z0-9-]+)", conf))
    for opcao in sorted(ligadas - desligadas):
        alvo = POR_OPCAO.get(opcao)
        ok(alvo is not None, f"--enable-{opcao} na DLL sem biblioteca correspondente no teste")
        ok(alvo in nomes, f"--enable-{opcao}: falta {alvo} em licenses/motor")
    # e as dependências do próprio mpv ("List of enabled features" gravada na DLL)
    POR_RECURSO = {"iconv": "libiconv", "javascript": "mujs", "lcms2": "lcms2", "libarchive": "libarchive", "libass": "libass",
                   "libbluray": "libbluray", "libcurl": "curl", "libplacebo": "libplacebo", "luajit": "LuaJIT",
                   "shaderc": "shaderc", "sixel": "libsixel", "spirv-cross": "SPIRV-Cross", "subrandr": "subrandr",
                   "uchardet": "uchardet", "vaapi": "libva", "vapoursynth": "vapoursynth", "vulkan": "Vulkan-Shim-Loader",
                   "zimg": "zimg", "zlib": "zlib", "amf": "AMF", "ffnvcodec": "nv-codec-headers", "win32-smtc": "cppwinrt",
                   "ffmpeg": "FFmpeg"}
    recursos = set(re.search(rb"List of enabled features: ([^\n\0]+)", dados).group(1).decode().split())
    for r in sorted(recursos & set(POR_RECURSO)):
        ok(POR_RECURSO[r] in nomes, f"mpv com {r}: falta {POR_RECURSO[r]} em licenses/motor")
    print(f"DLL conferida: {len(ligadas - desligadas)} opções --enable do FFmpeg e {len(recursos & set(POR_RECURSO))} "
          f"dependências do mpv")
else:
    print("(sem libmpv-2.dll na pasta: conferência contra a DLL pulada)")
print(f"LICENCAS MOTOR PASSOU ({n} checagens)")
