"""Gera instalador/associacoes.iss: registra o Ciranda para fotos e vídeos no Windows
(aparece em "Abrir com" e em Configurações > Aplicativos padrão > Ciranda).
O Windows não deixa app nenhum virar padrão sozinho: o usuário escolhe uma vez.
Tudo é apagado na desinstalação (uninsdeletekey / uninsdeletevalue)."""
import os

FOTOS = [".jpg", ".jpeg", ".jfif", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff",
         ".heic", ".heif", ".avif"]
VIDEOS = [".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mpg",
          ".mpeg", ".ts", ".mts", ".m2ts", ".3gp", ".ogv"]
CAP = r"Software\Dreds\Ciranda\Capabilities"
T = "Tasks: associar"


def progid(nome, descricao):
    base = rf"Software\Classes\{nome}"
    return [
        f'Root: HKA; Subkey: "{base}"; ValueType: string; ValueName: ""; ValueData: "{descricao}"; Flags: uninsdeletekey; {T}',
        f'Root: HKA; Subkey: "{base}\\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{{app}}\\Ciranda.exe,0"; {T}',
        f'Root: HKA; Subkey: "{base}\\shell\\open"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Ciranda"; {T}',
        f'Root: HKA; Subkey: "{base}\\shell\\open\\command"; ValueType: string; ValueName: ""; ValueData: """{{app}}\\Ciranda.exe"" ""%1"""; {T}',
    ]


linhas = ["; GERADO por instalador/gerar_associacoes.py: não editar à mão", ""]
linhas += progid("Ciranda.Foto", "{cm:TipoFoto}") + progid("Ciranda.Video", "{cm:TipoVideo}")
linhas += [
    f'Root: HKA; Subkey: "{CAP}"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Ciranda"; Flags: uninsdeletekey; {T}',
    f'Root: HKA; Subkey: "{CAP}"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "{{cm:DescricaoApp}}"; {T}',
    f'Root: HKA; Subkey: "{CAP}"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: "{{app}}\\Ciranda.exe,0"; {T}',
    f'Root: HKA; Subkey: "Software\\Dreds"; Flags: uninsdeletekeyifempty; {T}',
    f'Root: HKA; Subkey: "Software\\Dreds\\Ciranda"; Flags: uninsdeletekey; {T}',
    f'Root: HKA; Subkey: "Software\\RegisteredApplications"; ValueType: string; ValueName: "Ciranda"; ValueData: "{CAP}"; Flags: uninsdeletevalue; {T}',
    f'Root: HKA; Subkey: "Software\\Classes\\Applications\\Ciranda.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Ciranda"; Flags: uninsdeletekey; {T}',
    f'Root: HKA; Subkey: "Software\\Classes\\Applications\\Ciranda.exe\\shell\\open\\command"; ValueType: string; ValueName: ""; ValueData: """{{app}}\\Ciranda.exe"" ""%1"""; {T}',
]
for exts, pid in ((FOTOS, "Ciranda.Foto"), (VIDEOS, "Ciranda.Video")):
    for e in exts:
        linhas += [
            f'Root: HKA; Subkey: "Software\\Classes\\{e}\\OpenWithProgids"; ValueType: string; ValueName: "{pid}"; ValueData: ""; Flags: uninsdeletevalue; {T}',
            f'Root: HKA; Subkey: "{CAP}\\FileAssociations"; ValueType: string; ValueName: "{e}"; ValueData: "{pid}"; {T}',
            f'Root: HKA; Subkey: "Software\\Classes\\Applications\\Ciranda.exe\\SupportedTypes"; ValueType: string; ValueName: "{e}"; ValueData: ""; {T}',
        ]
destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "associacoes.iss")
with open(destino, "w", encoding="utf-8-sig", newline="\r\n") as f:
    f.write("\n".join(linhas) + "\n")
print(f"{len(FOTOS)} fotos + {len(VIDEOS)} vídeos -> {destino}")
