@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Ciranda

if not exist "libmpv-2.dll" (
  echo Falta o arquivo libmpv-2.dll nesta pasta ^(e o motor que toca os videos^).
  echo Peca para a IA gravar de novo a pasta do Ciranda.
  pause
  exit /b 1
)

set "PY="
py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
if not defined PY (
  echo Preciso do Python 3.12. Instalando pelo winget ^(so na primeira vez^)...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
)
if not defined PY (
  echo.
  echo Nao consegui achar o Python 3.12. Feche esta janela e abra de novo; se continuar, instale o Python 3.12 em python.org.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando o ambiente do Ciranda ^(so na primeira vez^)...
  %PY% -m venv .venv || (echo Falhou ao criar o ambiente. & pause & exit /b 1)
)
if not exist ".venv\pronto-1.4.1.txt" (
  echo Instalando o que o Ciranda precisa ^(so na primeira vez, 1 a 3 minutos^)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q || (echo Falhou a instalacao. & pause & exit /b 1)
  echo ok> ".venv\pronto-1.4.1.txt"
)

rem atalho com icone na area de trabalho e na pasta (abre sem a janela preta)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell; $p='%~dp0'; foreach($d in @([Environment]::GetFolderPath('Desktop'), $p)){ $s=$w.CreateShortcut((Join-Path $d 'Ciranda.lnk')); $s.TargetPath=(Join-Path $p 'Ciranda.exe'); $s.WorkingDirectory=$p; $s.IconLocation=(Join-Path $p 'Ciranda.exe')+',0'; $s.Description='Ciranda - feito por Dreds'; $s.Save() }" >nul 2>nul

start "" ".venv\Scripts\pythonw.exe" "%~dp0app.py" %*
exit /b 0
