# Third-party notices

Ciranda's own code is under the [MIT License](LICENSE). The components below ship with it and keep their own licenses. The license texts are in the [`licenses`](licenses) folder. Ciranda does not modify any of them.

## `libmpv-2.dll`, the playback engine

- Official build from the mpv project, version 0.42.0, used unchanged: [`libmpv-v0.42.0-x86_64-w64-mingw32-lgpl.zip`](https://github.com/mpv-player/mpv/releases/download/v0.42.0/libmpv-v0.42.0-x86_64-w64-mingw32-lgpl.zip).
- SHA-256 of the zip: `8e5f77430efc53ef175804ba6618527e3af0448a0dcabf04d3cc72659d1a6fce`.
- SHA-256 of the DLL: `94fb87247732c59915cd59808bc582e843a71c22214b7b6c1e5563aa8149cef4`. The release workflow checks both.
- **mpv** is under the GNU LGPL version 2.1 or later (built with `-Dgpl=false`).
- **FFmpeg**, inside the DLL, is built with `--enable-version3` and without `--enable-gpl`, so it is under the GNU LGPL version 3 or later. The combined DLL follows LGPL version 3 or later.
- Source: [mpv at tag v0.42.0](https://github.com/mpv-player/mpv/tree/v0.42.0) and [FFmpeg at commit baa68e6](https://github.com/FFmpeg/FFmpeg/commit/baa68e68b34e2de912eb7e94342cebd2545f05ed) (`git-2026-11-04-baa68e6`).
- Build recipe: mpv's [`ci/build-mingw64-full.sh`](https://github.com/mpv-player/mpv/blob/v0.42.0/ci/build-mingw64-full.sh), on top of the `ghcr.io/btbn/ffmpeg-builds/win64-lgpl` image from [FFmpeg-Builds](https://github.com/FFmpeg-Builds/FFmpeg-Builds).
- The DLL also statically contains libraries under their own licenses (among them libass, FreeType, HarfBuzz, FriBidi, Fontconfig, libplacebo, dav1d, libaom, libvpx, libwebp, libjxl, Opus, Vorbis, LAME, zlib and libbluray). The list and versions are in the FFmpeg-Builds recipe.
- The DLL is a separate file: you can replace it with another compatible libmpv.

## Python packages

| Package | Version | License used | Source |
|---|---|---|---|
| [PySide6-Essentials](https://pypi.org/project/PySide6-Essentials/), shiboken6 and Qt 6 | 6.12.0 | LGPL-3.0 | [pyside-setup](https://code.qt.io/cgit/pyside/pyside-setup.git/) |
| [python-mpv](https://github.com/jaseg/python-mpv) | 1.0.8 | LGPL-2.1-or-later (dual licensed, GPL-2.0+ not used) | [GitHub](https://github.com/jaseg/python-mpv) |
| [segno](https://pypi.org/project/segno/) | 1.6.6 | BSD-3-Clause (QR code of the Support ♥ card) | [GitHub](https://github.com/heuer/segno) |

The portable zip downloads these from PyPI on first run. The installer ships them.

## Installer only

- **Python 3.12**: PSF-2.0, with the notices of the libraries it includes (`licenses/Python-PSF-2.0.txt`).
- **PyInstaller bootloader** (the installer's `Ciranda.exe`): GPL-2.0-or-later **with the bootloader exception**, which allows distributing the bootloader with any program without GPL restrictions (`licenses/PyInstaller-bootloader-exception.txt`).
