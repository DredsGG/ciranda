; Inno Setup: instalador do Ciranda, em inglês, português e espanhol (segue o idioma do Windows).
; Compilar da raiz:  ISCC.exe /DVersao=1.2.0 instalador\ciranda.iss
; Entrada: dist\Ciranda\ (saída do PyInstaller). Saída: dist\Ciranda-Setup-<versão>.exe

#ifndef Versao
  #define Versao "0.0.0"
#endif

[Setup]
AppId={{4B485C6B-2F3C-4AB5-8B7E-FBCC96A3752A}
AppName=Ciranda
AppVersion={#Versao}
AppVerName=Ciranda {#Versao}
AppPublisher=Dreds
AppPublisherURL=https://github.com/DredsGG
AppSupportURL=https://github.com/DredsGG/ciranda
AppUpdatesURL=https://github.com/DredsGG/ciranda/releases/latest
AppCopyright=feito por Dreds
VersionInfoVersion={#Versao}
; instala só para o usuário: sem pedir administrador
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\Ciranda
DisableProgramGroupPage=yes
DisableWelcomePage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=Ciranda-Setup-{#Versao}
SetupIconFile=..\ui\ciranda.ico
UninstallDisplayIcon={app}\Ciranda.exe
UninstallDisplayName=Ciranda
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; se o Ciranda estiver aberto numa atualização, fecha e reabre
CloseApplications=yes
; avisa o Explorer que as associações mudaram (instalar e desinstalar)
ChangesAssociations=yes
RestartApplications=no

; idioma do instalador = idioma do Windows (pt, es; qualquer outro: inglês, o primeiro da lista)
ShowLanguageDialog=no
LanguageDetectionMethod=uilanguage

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "ptpt"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
en.GrupoAtalhos=Shortcuts:
en.TarefaAtalho=Create a desktop shortcut
en.GrupoExplorer=Explorer:
en.TarefaMenuPasta=Add "Play in Ciranda" when you right-click a folder
en.TarefaAssociar=Register Ciranda for photos and videos (shows up in "Open with" and in Default apps)
en.MenuPasta=Play in Ciranda
en.MenuFundo=Play this folder in Ciranda
en.Comentario=Photos and videos from a folder and every subfolder
en.AbrirCiranda=Open Ciranda
en.EscolherPadrao=Choose Ciranda as the default app for photos and videos (opens Windows Settings)
en.TipoFoto=Photo (Ciranda)
en.TipoVideo=Video (Ciranda)
en.DescricaoApp=Photos and videos from a folder and every subfolder, in one queue
ptbr.GrupoAtalhos=Atalhos:
ptbr.TarefaAtalho=Criar atalho na área de trabalho
ptbr.GrupoExplorer=Explorer:
ptbr.TarefaMenuPasta=Pôr "Tocar no Ciranda" no botão direito das pastas
ptbr.TarefaAssociar=Registrar o Ciranda para fotos e vídeos (aparece em "Abrir com" e nos Aplicativos padrão)
ptbr.MenuPasta=Tocar no Ciranda
ptbr.MenuFundo=Tocar esta pasta no Ciranda
ptbr.Comentario=Fotos e vídeos de uma pasta e de todas as subpastas
ptbr.AbrirCiranda=Abrir o Ciranda
ptbr.EscolherPadrao=Escolher o Ciranda como app padrão de fotos e vídeos (abre as Configurações do Windows)
ptbr.TipoFoto=Foto (Ciranda)
ptbr.TipoVideo=Vídeo (Ciranda)
ptbr.DescricaoApp=Fotos e vídeos de uma pasta e de todas as subpastas, numa fila só
ptpt.GrupoAtalhos=Atalhos:
ptpt.TarefaAtalho=Criar atalho no ambiente de trabalho
ptpt.GrupoExplorer=Explorador:
ptpt.TarefaMenuPasta=Pôr "Tocar no Ciranda" no botão direito das pastas
ptpt.TarefaAssociar=Registar o Ciranda para fotos e vídeos (aparece em "Abrir com" e nas Aplicações predefinidas)
ptpt.MenuPasta=Tocar no Ciranda
ptpt.MenuFundo=Tocar esta pasta no Ciranda
ptpt.Comentario=Fotos e vídeos de uma pasta e de todas as subpastas
ptpt.AbrirCiranda=Abrir o Ciranda
ptpt.EscolherPadrao=Escolher o Ciranda como aplicação predefinida de fotos e vídeos (abre as Definições do Windows)
ptpt.TipoFoto=Foto (Ciranda)
ptpt.TipoVideo=Vídeo (Ciranda)
ptpt.DescricaoApp=Fotos e vídeos de uma pasta e de todas as subpastas, numa fila só
es.GrupoAtalhos=Accesos directos:
es.TarefaAtalho=Crear un acceso directo en el escritorio
es.GrupoExplorer=Explorador:
es.TarefaMenuPasta=Añadir "Reproducir en Ciranda" al clic derecho de las carpetas
es.TarefaAssociar=Registrar Ciranda para fotos y videos (aparece en "Abrir con" y en Aplicaciones predeterminadas)
es.MenuPasta=Reproducir en Ciranda
es.MenuFundo=Reproducir esta carpeta en Ciranda
es.Comentario=Fotos y videos de una carpeta y de todas sus subcarpetas
es.AbrirCiranda=Abrir Ciranda
es.EscolherPadrao=Elegir Ciranda como aplicación predeterminada de fotos y videos (abre la Configuración de Windows)
es.TipoFoto=Foto (Ciranda)
es.TipoVideo=Video (Ciranda)
es.DescricaoApp=Fotos y videos de una carpeta y de todas sus subcarpetas, en una sola cola

[Tasks]
Name: "atalho"; Description: "{cm:TarefaAtalho}"; GroupDescription: "{cm:GrupoAtalhos}"
Name: "menupasta"; Description: "{cm:TarefaMenuPasta}"; GroupDescription: "{cm:GrupoExplorer}"
Name: "associar"; Description: "{cm:TarefaAssociar}"; GroupDescription: "{cm:GrupoExplorer}"

[Files]
Source: "..\dist\Ciranda\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Ciranda"; Filename: "{app}\Ciranda.exe"; AppUserModelID: "Dreds.Ciranda"; Comment: "{cm:Comentario}"
Name: "{autodesktop}\Ciranda"; Filename: "{app}\Ciranda.exe"; AppUserModelID: "Dreds.Ciranda"; Tasks: atalho

[Registry]
; botão direito EM CIMA de uma pasta
Root: HKA; Subkey: "Software\Classes\Directory\shell\Ciranda"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuPasta}"; Flags: uninsdeletekey; Tasks: menupasta
Root: HKA; Subkey: "Software\Classes\Directory\shell\Ciranda"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Ciranda.exe"; Tasks: menupasta
Root: HKA; Subkey: "Software\Classes\Directory\shell\Ciranda\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Ciranda.exe"" ""%1"""; Tasks: menupasta
; botão direito no ESPAÇO VAZIO dentro de uma pasta
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\Ciranda"; ValueType: string; ValueName: ""; ValueData: "{cm:MenuFundo}"; Flags: uninsdeletekey; Tasks: menupasta
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\Ciranda"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Ciranda.exe"; Tasks: menupasta
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\Ciranda\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Ciranda.exe"" ""%V"""; Tasks: menupasta
; fotos e vídeos: ProgIDs, "Abrir com" e Aplicativos padrão (gerado por gerar_associacoes.py)
#include "associacoes.iss"

[Run]
Filename: "{app}\Ciranda.exe"; Description: "{cm:AbrirCiranda}"; Flags: nowait postinstall skipifsilent
; atualização pelo próprio app (/RELANCAR=1 /DE=<versão antiga>): reabre o Ciranda no fim, mesmo em silêncio
Filename: "{app}\Ciranda.exe"; Parameters: "--atualizado-de={param:DE|}"; Flags: nowait; Check: DeveRelancar
Filename: "ms-settings:defaultapps?registeredAppUser=Ciranda"; Description: "{cm:EscolherPadrao}"; Flags: shellexec nowait postinstall skipifsilent unchecked; Tasks: associar

[Code]
function DeveRelancar: Boolean;
begin
  Result := ExpandConstant('{param:RELANCAR|0}') = '1';
end;
