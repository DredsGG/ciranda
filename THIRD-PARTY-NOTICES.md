# Third-party notices

Ciranda's own code is under the [MIT License](LICENSE). The components below ship with it and keep their own licenses. The texts of the licenses named in each item are in the [`licenses`](licenses) folder. Ciranda does not modify any of them.

## `libmpv-2.dll`, the playback engine

- Official build from the mpv project, version 0.42.0, used unchanged: [`libmpv-v0.42.0-x86_64-w64-mingw32-lgpl.zip`](https://github.com/mpv-player/mpv/releases/download/v0.42.0/libmpv-v0.42.0-x86_64-w64-mingw32-lgpl.zip).
- SHA-256 of the zip: `8e5f77430efc53ef175804ba6618527e3af0448a0dcabf04d3cc72659d1a6fce`.
- SHA-256 of the DLL: `94fb87247732c59915cd59808bc582e843a71c22214b7b6c1e5563aa8149cef4`. The release workflow checks both.
- **mpv** is under the GNU LGPL version 2.1 or later (built with `-Dgpl=false`).
- **FFmpeg**, inside the DLL, is built with `--enable-version3` and without `--enable-gpl`, so it is under the GNU LGPL version 3 or later.
- **Heads-up: the official DLL also contains zvbi** (a teletext decoder Ciranda never uses). Two of its files, `src/packet-830.c` and `src/pdc.c`, are under the GNU GPL version 2. FFmpeg does not list libzvbi as a GPL library, so it ends up in mpv's "LGPL" build. As long as mpv ships the DLL this way, Ciranda's package is not entirely free of GPL code (`licenses/GPL-2.0.txt`). FFmpeg-Builds removed zvbi from its LGPL variants on 2026-11-07 ([commit 162691525a43](https://github.com/FFmpeg-Builds/FFmpeg-Builds/commit/162691525a43), after mpv 0.42.0 was built); Ciranda will switch DLLs once mpv publishes an official libmpv built after that.
- Source: [mpv at tag v0.42.0](https://github.com/mpv-player/mpv/tree/v0.42.0) and [FFmpeg at commit baa68e6](https://github.com/FFmpeg/FFmpeg/commit/baa68e68b34e2de912eb7e94342cebd2545f05ed) (`git-2026-11-04-baa68e6`).
- Build recipe: mpv's [`ci/build-mingw64-full.sh`](https://github.com/mpv-player/mpv/blob/v0.42.0/ci/build-mingw64-full.sh), on top of the `win64-lgpl` image from [FFmpeg-Builds at c63bb308](https://github.com/FFmpeg-Builds/FFmpeg-Builds/tree/c63bb308a1de656b425c132a8102f8fd5389afc5), the last recipe commit before mpv's build (2026-11-04), which pins every library's commit. What mpv clones without a pinned version (LuaJIT, libsixel, libarchive, subrandr, mujs) is listed at its commit on the build date: that part is inferred.
- The DLL is a separate file: you can replace it with another compatible libmpv.

### Libraries compiled into the DLL

Each library's license text, with its copyright notice, is in `licenses/motor/<library>.txt`; subrandr's Rust crates are in `licenses/motor/subrandr-crates.txt`; the full list with commits is `licenses/motor/LISTA.tsv`.

<!-- motor:inicio -->
| Library | Version | License | Source |
|---|---|---|---|
| mpv | `v0.42.0` | LGPL-2.1-or-later | https://github.com/mpv-player/mpv.git |
| FFmpeg | `baa68e68b34e` | LGPL-3.0-or-later | https://github.com/FFmpeg/FFmpeg.git |
| libiconv | `b5a1735e02bf` | LGPL-2.1-or-later | https://git.savannah.gnu.org/git/libiconv.git |
| zlib | `9d314c341b2c` | Zlib | https://github.com/madler/zlib.git |
| fribidi | `d2f3e1f4946e` | LGPL-2.1-or-later | https://github.com/fribidi/fribidi.git |
| gmp | `5c3e9a9d52b6` | LGPL-3.0-or-later | https://github.com/BtbN/gmplib.git |
| libogg | `06a5e0262cdc` | BSD-3-Clause | https://github.com/xiph/ogg.git |
| libpng | `0b0876829d77` | libpng-2.0 | https://github.com/glennrp/libpng.git |
| libxml2 | `c79c9612fcc7` | MIT | https://github.com/GNOME/libxml2.git |
| openssl | `openssl-3.6.5` | Apache-2.0 | https://github.com/openssl/openssl.git |
| xz | `299eb5c3f597` | 0BSD | https://github.com/tukaani-project/xz.git |
| brotli | `2e2bcf17ae71` | MIT | https://github.com/google/brotli.git |
| freetype | `4ba7c3d82ab8` | FTL | https://gitlab.freedesktop.org/freetype/freetype.git |
| fontconfig | `b25ffeabd15b` | HPND-sell-variant | https://gitlab.freedesktop.org/fontconfig/fontconfig.git |
| harfbuzz | `75d8ac5d2313` | MIT-Modern-Variant | https://github.com/harfbuzz/harfbuzz.git |
| lcms2 | `1112313b3784` | MIT | https://github.com/mm2/Little-CMS.git |
| libsamplerate | `0844c208f683` | BSD-2-Clause | https://github.com/libsndfile/libsamplerate.git |
| libudfread | `b0bc6957e7e0` | LGPL-2.1-or-later | https://code.videolan.org/videolan/libudfread.git |
| libunibreak | `f8172fe771ef` | Zlib | https://github.com/adah1972/libunibreak.git |
| libvorbis | `1b75110b5a27` | BSD-3-Clause | https://github.com/xiph/vorbis.git |
| OpenCL-Headers | `82f60316cc14` | Apache-2.0 | https://github.com/KhronosGroup/OpenCL-Headers.git |
| OpenCL-ICD-Loader | `5192c84f8059` | Apache-2.0 | https://github.com/KhronosGroup/OpenCL-ICD-Loader.git |
| vmaf | `f712fa7564fe` | BSD-2-Clause-Patent | https://github.com/Netflix/vmaf.git |
| xxhash | `61fd0fece2eb` | BSD-2-Clause | https://github.com/Cyan4973/xxHash.git |
| zstd | `49cf51799ea0` | BSD-3-Clause | https://github.com/facebook/zstd.git |
| Vulkan-Headers | `v1.4.366` | Apache-2.0 OR MIT | https://github.com/KhronosGroup/Vulkan-Headers.git |
| Vulkan-Shim-Loader | `65b3936528cd` | MIT | https://github.com/BtbN/Vulkan-Shim-Loader.git |
| shaderc | `2737994b5521` | Apache-2.0 | https://github.com/google/shaderc.git |
| glslang | `73b25650df6d` | BSD-3-Clause AND MIT AND Apache-2.0 | https://github.com/KhronosGroup/glslang.git |
| SPIRV-Tools | `71f287f18ed7` | Apache-2.0 | https://github.com/KhronosGroup/SPIRV-Tools.git |
| SPIRV-Headers | `fbf86836a9b1` | MIT | https://github.com/KhronosGroup/SPIRV-Headers.git |
| SPIRV-Cross | `300681bbcb83` | Apache-2.0 | https://github.com/KhronosGroup/SPIRV-Cross.git |
| AMF | `57ee0cfb0e1a` | MIT | https://github.com/GPUOpen-LibrariesAndSDKs/AMF.git |
| aom | `9ace39e02a34` | BSD-2-Clause | https://aomedia.googlesource.com/aom |
| chromaprint | `3b38c100022b` | MIT AND LGPL-2.1-or-later | https://github.com/acoustid/chromaprint.git |
| dav1d | `b8b2d726b4b7` | BSD-2-Clause | https://code.videolan.org/videolan/dav1d.git |
| nv-codec-headers | `f2053071ea93` | MIT | https://github.com/FFmpeg/nv-codec-headers.git |
| game-music-emu | `f68963b1de06` | LGPL-2.1-or-later | https://github.com/libgme/game-music-emu.git |
| kvazaar | `1f11f9ae33ef` | BSD-3-Clause | https://github.com/ultravideo/kvazaar.git |
| LCEVCdec | `741fb7c869cf` | BSD-3-Clause-Clear | https://github.com/v-novaltd/LCEVCdec.git |
| aribb24 | `5e9be272f96e` | LGPL-3.0-or-later | https://github.com/nkoriyama/aribb24.git |
| libaribcaption | `37dde0f32652` | MIT | https://github.com/xqq/libaribcaption.git |
| libass | `f61db567e659` | ISC | https://github.com/libass/libass.git |
| libbluray | `f33a738fd7bb` | LGPL-2.1-or-later | https://code.videolan.org/videolan/libbluray.git |
| libpsl | `620d51d13351` | MIT | https://github.com/rockdaboot/libpsl.git |
| nghttp2 | `3baf9561e09f` | MIT | https://github.com/nghttp2/nghttp2.git |
| nghttp3 | `ac11a456eb9d` | MIT | https://github.com/ngtcp2/nghttp3.git |
| ngtcp2 | `20da63db12a3` | MIT | https://github.com/ngtcp2/ngtcp2.git |
| curl | `bc677a8f16a5` | curl | https://github.com/curl/curl.git |
| libjxl | `e47d2a2b5bb4` | BSD-3-Clause | https://github.com/libjxl/libjxl.git |
| highway | `457c891775a7` | Apache-2.0 OR BSD-3-Clause | https://github.com/google/highway.git |
| LAME | `7113` | LGPL-2.0-or-later | https://svn.code.sf.net/p/lame/svn/trunk/lame |
| opus | `a8b2545eec71` | BSD-3-Clause | https://github.com/xiph/opus.git |
| libplacebo | `275f7dea2792` | LGPL-2.1-or-later | https://code.videolan.org/videolan/libplacebo.git |
| glad | `73db193f853e` | MIT AND Apache-2.0 | https://github.com/Dav1dde/glad.git |
| fast_float | `97b54ca9e75f` | Apache-2.0 OR BSL-1.0 OR MIT | https://github.com/fastfloat/fast_float.git |
| mbedtls | `v4.2.0` | Apache-2.0 | https://github.com/Mbed-TLS/mbedtls.git |
| tf-psa-crypto | `73c5da561c8e` | Apache-2.0 | https://github.com/Mbed-TLS/TF-PSA-Crypto.git |
| librist | `47ad5513d1aa` | BSD-2-Clause | https://code.videolan.org/rist/librist.git |
| libssh | `9de02f3d01ba` | LGPL-2.1-only | https://gitlab.com/libssh/libssh-mirror.git |
| theora | `28fd5ec77f0a` | BSD-3-Clause | https://github.com/xiph/theora.git |
| libvpx | `900b2a52b69e` | BSD-3-Clause | https://chromium.googlesource.com/webm/libvpx |
| libwebp | `1844042d1ca7` | BSD-3-Clause | https://chromium.googlesource.com/webm/libwebp |
| libzmq | `46493370217a` | MPL-2.0 | https://github.com/zeromq/libzmq.git |
| lv2 | `3c57dae600a5` | ISC | https://github.com/lv2/lv2.git |
| serd | `b621b0bc790d` | ISC | https://github.com/drobilla/serd.git |
| zix | `17d632393f5a` | ISC | https://github.com/drobilla/zix.git |
| sord | `4b5232bb91e7` | ISC | https://github.com/drobilla/sord.git |
| sratom | `9e8ee84eed50` | ISC | https://github.com/lv2/sratom.git |
| lilv | `4b8f30055fa5` | ISC | https://github.com/lv2/lilv.git |
| libvpl | `674d015bcb29` | MIT | https://github.com/intel/libvpl.git |
| openapv | `b4ff69856b4c` | BSD-3-Clause | https://github.com/AcademySoftwareFoundation/openapv.git |
| opencore-amr | `7dba8c322384` | Apache-2.0 | https://git.code.sf.net/p/opencore-amr/code |
| openh264 | `1bca62311e44` | BSD-2-Clause | https://github.com/cisco/openh264.git |
| openjpeg | `8314119b067c` | BSD-2-Clause | https://github.com/uclouvain/openjpeg.git |
| libopenmpt | `3ee3c8000b45` | BSD-3-Clause | https://github.com/OpenMPT/openmpt.git |
| SDL2 | `8acf7cfc0f88` | Zlib | https://github.com/libsdl-org/SDL.git |
| snappy | `946606459314` | BSD-3-Clause | https://github.com/google/snappy.git |
| soxr | `945b592b7047` | LGPL-2.1-or-later | https://git.code.sf.net/p/soxr/code |
| srt | `9f2390232a82` | MPL-2.0 | https://github.com/Haivision/srt.git |
| SVT-AV1 | `ad11d76a6c9c` | BSD-3-Clause-Clear | https://github.com/AOMediaCodec/SVT-AV1.git |
| twolame | `6fced852d4d5` | LGPL-2.1-or-later | https://github.com/njh/twolame.git |
| uavs3d | `0e20d2c29185` | BSD-3-Clause | https://github.com/uavs3/uavs3d.git |
| libva | `f052e984e0c8` | MIT | https://github.com/intel/libva.git |
| vapoursynth | `R81` | LGPL-2.1-or-later | https://github.com/vapoursynth/vapoursynth.git |
| vvenc | `0e7508b811bb` | BSD-3-Clause-Clear | https://github.com/fraunhoferhhi/vvenc.git |
| zimg | `67e0603271c0` | WTFPL | https://github.com/sekrit-twc/zimg.git |
| graphengine | `cb5b2ce13384` | WTFPL | https://github.com/sekrit-twc/graphengine.git |
| zvbi ⚠️ | `34bb6f660c5c` | GPL-2.0-only AND LGPL-2.0-or-later | https://github.com/zapping-vbi/zvbi |
| mingw-w64 | `7213d719fe34` | ZPL-2.1 AND MIT AND public-domain | https://git.code.sf.net/p/mingw-w64/mingw-w64.git |
| mingw-std-threads | `c931bac289dd` | BSD-2-Clause | https://github.com/meganz/mingw-std-threads.git |
| LuaJIT | `ea9eb7edb5ea` | MIT | https://github.com/LuaJIT/LuaJIT.git |
| libsixel | `ca31d6a2d2d6` | MIT | https://github.com/saitoha/libsixel.git |
| libarchive | `d56567180f78` | BSD-2-Clause | https://github.com/libarchive/libarchive.git |
| uchardet | `v0.0.8` | MPL-1.1 OR LGPL-2.1-or-later | https://gitlab.freedesktop.org/uchardet/uchardet.git |
| subrandr | `a41311bb5e38` | MPL-2.0 | https://github.com/afishhh/subrandr.git |
| mujs | `1.3.8` | ISC | https://codeberg.org/ccxvii/mujs.git |
| cppwinrt | `2.0.250303.1` | MIT | https://github.com/microsoft/cppwinrt.git |
| gcc-runtime | `releases/gcc-16.2.0` | GPL-3.0-or-later WITH GCC-exception-3.1 | https://github.com/gcc-mirror/gcc.git |
| rust-std ⚠️ | `main` | MIT OR Apache-2.0 | https://github.com/rust-lang/rust.git |
<!-- motor:fim -->

## Python packages

| Package | Version | License used | Source |
|---|---|---|---|
| [PySide6-Essentials](https://pypi.org/project/PySide6-Essentials/), shiboken6 and Qt 6 | 6.12.0 | LGPL-3.0 | [pyside-setup](https://code.qt.io/cgit/pyside/pyside-setup.git/) |
| [python-mpv](https://github.com/jaseg/python-mpv) | 1.0.8 | LGPL-2.1-or-later (dual licensed, GPL-2.0+ not used) | [GitHub](https://github.com/jaseg/python-mpv) |
| [segno](https://pypi.org/project/segno/) | 1.6.6 | BSD-3-Clause (QR code of the Support ♥ card) | [GitHub](https://github.com/heuer/segno) |

The portable zip downloads these from PyPI on first run. The installer ships them.

## Installer only

- **Python 3.12**: PSF-2.0 (`licenses/Python-PSF-2.0.txt`).
- **OpenSSL 3** (libssl and libcrypto, shipped with Python and PySide6): Apache-2.0 (`licenses/Apache-2.0.txt`).
- **PyInstaller bootloader** (the installer's `Ciranda.exe`): GPL-2.0-or-later **with the bootloader exception**, which allows distributing the bootloader with any program without GPL restrictions (`licenses/PyInstaller-bootloader-exception.txt`).
