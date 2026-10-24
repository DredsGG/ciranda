# Third-party notices

Ciranda's own code is under the [MIT License](LICENSE). The release zip also ships one third-party binary, and the first run installs a few Python packages.

## Shipped in the release zip

**`libmpv-2.dll`**, the playback engine.

- Built by [shinchiro/mpv-winbuild-cmake](https://github.com/shinchiro/mpv-winbuild-cmake), release [`20261021`](https://github.com/shinchiro/mpv-winbuild-cmake/releases/tag/20261021): `mpv-dev-x86_64-20261021-git-e471496c56.7z` (x86_64, no AVX2 requirement).
- SHA-256 of the DLL: `04e4d27dc385dc18ddd93fbe69c75e635b864f3c6ec53a9122df54c2f7842f4a`. The release workflow downloads that archive, checks both hashes and copies the DLL unchanged.
- mpv is licensed under the GPL version 2 or later (or LGPL 2.1 or later when built without GPL parts). See [mpv's Copyright file](https://github.com/mpv-player/mpv/blob/master/Copyright). The DLL bundles FFmpeg and other libraries under their own licenses.
- Source: [mpv](https://github.com/mpv-player/mpv) at commit `e471496c56`, and the build scripts with every bundled library version in [mpv-winbuild-cmake](https://github.com/shinchiro/mpv-winbuild-cmake).

## Installed by `RODAR.bat` on first run (from PyPI, not shipped here)

| Package | Version | License |
|---|---|---|
| [PySide6-Essentials](https://pypi.org/project/PySide6-Essentials/) | 6.12.0 | LGPL-3.0, or GPL-2.0 / GPL-3.0 |
| [python-mpv](https://github.com/jaseg/python-mpv) | 1.0.8 | GPL-2.0+ or LGPL-2.1+ (same as libmpv) |
| [Pillow](https://pypi.org/project/pillow/) | 12.3.0 | MIT-CMU |
| [pillow-heif](https://pypi.org/project/pillow-heif/) | 1.8.0 | BSD-3-Clause (bundles libheif, LGPL) |

Check each project for the exact terms.
