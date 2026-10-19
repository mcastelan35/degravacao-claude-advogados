@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Degravacao - Claude para Advogados

rem Localiza um Python compativel (3.11 a 3.14): primeiro pelo lancador "py", depois "python".
set "PY="
for %%V in (3.13 3.12 3.11 3.14) do (
  if not defined PY py -%%V --version >nul 2>&1 && set "PY=py -%%V"
)
if not defined PY python -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1 && set "PY=python"
if not defined PY goto sem_python

if not exist ".venv\Scripts\python.exe" (
  echo Primeira vez: instalando a ferramenta. Isso leva alguns minutos...
  echo.
  %PY% degravar.py instalar
  if errorlevel 1 goto erro
)

if not exist "config\preferencias.json" (
  echo.
  echo Escolha a pasta onde voce vai colocar os videos.
  ".venv\Scripts\python.exe" degravar.py configurar
  if errorlevel 1 goto erro
)

echo.
".venv\Scripts\python.exe" degravar.py transcrever --abrir
if errorlevel 1 goto erro
echo.
echo Pronto. Pode fechar esta janela.
pause
exit /b 0

:sem_python
echo Nenhum Python compativel (versao 3.11 a 3.14) foi encontrado neste computador.
echo.
where winget >nul 2>&1
if errorlevel 1 goto python_manual
choice /C SN /M "Instalar o Python 3.12 agora"
if errorlevel 2 goto python_manual
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Python instalado. Feche esta janela e de dois cliques em Degravar.bat de novo.
pause
exit /b 0

:python_manual
echo Instale o Python pelo site que vai abrir agora.
echo Na instalacao, marque a opcao "Add python.exe to PATH".
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:erro
echo.
echo Algo deu errado. Copie a mensagem acima e peca ajuda ao Claude.
pause
exit /b 1
