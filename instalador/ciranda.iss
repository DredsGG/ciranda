; Inno Setup 7: instalador do Ciranda.
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

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"
Name: "menupasta"; Description: "Pôr ""Tocar no Ciranda"" no botão direito das pastas"; GroupDescription: "Explorer:"
Name: "associar"; Description: "Registrar o Ciranda para fotos e vídeos (aparece em ""Abrir com"" e nos Aplicativos padrão)"; GroupDescription: "Explorer:"

[Files]
Source: "..\dist\Ciranda\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Ciranda"; Filename: "{app}\Ciranda.exe"; AppUserModelID: "Dreds.Ciranda"; Comment: "Fotos e vídeos de uma pasta e de todas as subpastas"
Name: "{autodesktop}\Ciranda"; Filename: "{app}\Ciranda.exe"; AppUserModelID: "Dreds.Ciranda"; Tasks: atalho

[Registry]
; botão direito EM CIMA de uma pasta
Root: HKA; Subkey: "Software\Classes\Directory\shell\Ciranda"; ValueType: string; ValueName: ""; ValueData: "Tocar no Ciranda"; Flags: uninsdeletekey; Tasks: menupasta
Root: HKA; Subkey: "Software\Classes\Directory\shell\Ciranda"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Ciranda.exe"; Tasks: menupasta
Root: HKA; Subkey: "Software\Classes\Directory\shell\Ciranda\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Ciranda.exe"" ""%1"""; Tasks: menupasta
; botão direito no ESPAÇO VAZIO dentro de uma pasta
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\Ciranda"; ValueType: string; ValueName: ""; ValueData: "Tocar esta pasta no Ciranda"; Flags: uninsdeletekey; Tasks: menupasta
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\Ciranda"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Ciranda.exe"; Tasks: menupasta
Root: HKA; Subkey: "Software\Classes\Directory\Background\shell\Ciranda\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Ciranda.exe"" ""%V"""; Tasks: menupasta
; fotos e vídeos: ProgIDs, "Abrir com" e Aplicativos padrão (gerado por gerar_associacoes.py)
#include "associacoes.iss"

[Run]
Filename: "{app}\Ciranda.exe"; Description: "Abrir o Ciranda"; Flags: nowait postinstall skipifsilent
; atualização pelo próprio app (/RELANCAR=1 /DE=<versão antiga>): reabre o Ciranda no fim, mesmo em silêncio
Filename: "{app}\Ciranda.exe"; Parameters: "--atualizado-de={param:DE|}"; Flags: nowait; Check: DeveRelancar
Filename: "ms-settings:defaultapps?registeredAppUser=Ciranda"; Description: "Escolher o Ciranda como app padrão de fotos e vídeos (abre as Configurações do Windows)"; Flags: shellexec nowait postinstall skipifsilent unchecked; Tasks: associar

[Code]
function DeveRelancar: Boolean;
begin
  Result := ExpandConstant('{param:RELANCAR|0}') = '1';
end;
