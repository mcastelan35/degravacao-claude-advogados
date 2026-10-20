@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Degravacao - Claude para Advogados

rem Localiza o uv (traz o Python certo, sem administrador) ou um Python 3.11 a 3.14 ja instalado.
set "UV="
where uv >nul 2>&1 && set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "UV=%USERPROFILE%\.cargo\bin\uv.exe"
set "PY="
if defined UV goto checar
for %%V in (3.13 3.12 3.11 3.14) do (
  if not defined PY py -%%V --version >nul 2>&1 && set "PY=py -%%V"
)
if not defined PY python -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1 && set "PY=python"

:checar
rem Instalado de verdade quando o ambiente existe e as dependencias respondem (instalacao interrompida nao passa aqui).
if not exist ".venv\Scripts\python.exe" goto primeira
".venv\Scripts\python.exe" -c "import faster_whisper, sherpa_onnx, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 goto primeira
if not exist ".venv\.instalado" echo instalado antes do marcador> ".venv\.instalado"
goto instalado

:primeira
if not defined UV if not defined PY goto instalar_uv
echo Instalando a ferramenta (primeira vez ou instalacao incompleta). Isso leva alguns minutos...
echo.
if defined UV (
  "%UV%" run --no-project --python 3.12 degravar.py instalar
) else (
  %PY% degravar.py instalar
)
if errorlevel 1 goto erro

:instalado
if not exist "config\preferencias.json" (
  echo.
  echo Escolha a pasta dos videos e onde salvar as degravacoes.
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

:instalar_uv
echo Para instalar, a ferramenta usa o "uv", que traz o Python certo sem pedir administrador.
echo Fonte oficial: https://astral.sh/uv
echo.
choice /C SN /M "Instalar o uv agora"
if errorlevel 2 goto python_manual
powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "UV=%USERPROFILE%\.cargo\bin\uv.exe"
if not defined UV goto python_manual
echo.
goto primeira

:python_manual
echo Instale o Python 3.12 pelo site que vai abrir agora (versao "Windows installer (64-bit)").
echo Na instalacao, marque a opcao "Add python.exe to PATH" e depois de dois cliques aqui de novo.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:erro
echo.
echo Algo deu errado. Copie a mensagem acima e peca ajuda ao Claude.
echo (Se a instalacao foi interrompida, basta dar dois cliques de novo: ela recomeca sozinha.)
pause
exit /b 1
