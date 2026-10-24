@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Ciranda - menu do botao direito

set "CHAVE=HKCU\Software\Classes\Directory\shell\Ciranda"
set "CHAVE_FUNDO=HKCU\Software\Classes\Directory\Background\shell\Ciranda"
set "EXE=%~dp0Ciranda.exe"
set "PYW=%~dp0.venv\Scripts\pythonw.exe"
set "APP=%~dp0app.py"
set "ICO=%~dp0Ciranda.exe"

reg query "%CHAVE%" >nul 2>nul
if not errorlevel 1 (
  echo O "Tocar no Ciranda" ja esta no menu do botao direito.
  choice /c SN /m "Quer TIRAR do menu"
  if errorlevel 2 exit /b 0
  reg delete "%CHAVE%" /f >nul
  reg delete "%CHAVE_FUNDO%" /f >nul 2>nul
  echo Tirado.
  pause
  exit /b 0
)

if not exist "%PYW%" (
  echo Abra o Ciranda.exe uma vez antes ^(ele instala o que falta^).
  pause
  exit /b 1
)

rem botao direito EM CIMA de uma pasta
reg add "%CHAVE%" /ve /d "Tocar no Ciranda" /f >nul
reg add "%CHAVE%" /v Icon /d "%ICO%" /f >nul
reg add "%CHAVE%\command" /ve /d "\"%EXE%\" \"%%1\"" /f >nul
rem botao direito no ESPACO VAZIO dentro de uma pasta
reg add "%CHAVE_FUNDO%" /ve /d "Tocar esta pasta no Ciranda" /f >nul
reg add "%CHAVE_FUNDO%" /v Icon /d "%ICO%" /f >nul
reg add "%CHAVE_FUNDO%\command" /ve /d "\"%EXE%\" \"%%V\"" /f >nul

echo Pronto. Clique com o botao direito numa pasta: "Tocar no Ciranda".
echo No Windows 11 ele fica em "Mostrar mais opcoes" ^(ou Shift + botao direito^).
echo Para tirar do menu, rode este arquivo de novo.
pause
