@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Ciranda - restaurar de fabrica

echo RESTAURAR DE FABRICA - use quando o Ciranda nao abre ou esta com erro.
echo.
echo Isto apaga:
echo   - os ajustes, a fila e o cache do Ciranda  (%APPDATA%\Ciranda)
echo   - o ambiente instalado do Ciranda          (.venv nesta pasta)
echo Suas fotos e videos NAO sao tocados.
echo Na proxima vez que abrir o Ciranda.exe ele reinstala tudo (1 a 3 minutos).
echo.
echo Feche o Ciranda antes de continuar.
set "RESP="
set /p RESP=Digite S e aperte Enter para restaurar, ou so Enter para cancelar: 
if /i not "%RESP%"=="S" (
  echo Cancelado. Nada foi apagado.
  pause
  exit /b 0
)

rem guarda o erro.txt (serve para descobrir o que deu errado)
if exist "%APPDATA%\Ciranda\erro.txt" copy /y "%APPDATA%\Ciranda\erro.txt" "%~dp0erro-antes-do-reset.txt" >nul

if exist "%APPDATA%\Ciranda" rmdir /s /q "%APPDATA%\Ciranda"
if exist ".venv" rmdir /s /q ".venv"

if exist ".venv" (
  echo.
  echo Nao consegui apagar a pasta .venv: o Ciranda ainda esta aberto?
  echo Feche o Ciranda e rode este arquivo de novo.
  pause
  exit /b 1
)

echo.
echo Pronto. Abra o Ciranda.exe para reinstalar.
pause
