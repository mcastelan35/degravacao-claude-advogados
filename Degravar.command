#!/bin/bash
# Dois cliques no Finder: instala na primeira vez, pede as pastas e degrava o que houver de novo.
cd "$(dirname "$0")" || exit 1

pausar() { echo; read -n 1 -s -r -p "Pressione qualquer tecla para fechar."; echo; }
falhou() { echo; echo "Algo deu errado. Copie a mensagem acima e peça ajuda ao Claude."; echo "(Se a instalação foi interrompida, basta dar dois cliques de novo: ela recomeça sozinha.)"; pausar; exit 1; }

# Instalado de verdade quando o ambiente existe e as dependências respondem (instalação interrompida não passa aqui).
instalado() {
  [ -x .venv/bin/python ] && .venv/bin/python -c 'import faster_whisper, sherpa_onnx, imageio_ffmpeg' >/dev/null 2>&1 || return 1
  [ -f .venv/.instalado ] || echo "instalado antes do marcador" > .venv/.instalado
}

if ! instalado; then
  # Primeira vez (ou instalação incompleta). Usa o uv (traz o Python certo, sem senha de administrador) ou um Python 3.11 a 3.14 já instalado.
  UV="$(command -v uv)"
  [ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
  [ -z "$UV" ] && [ -x "$HOME/.cargo/bin/uv" ] && UV="$HOME/.cargo/bin/uv"
  PY=""
  if [ -z "$UV" ]; then
    for c in python3.13 python3.12 python3.11 python3.14 python3; do
      if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)' 2>/dev/null; then
        PY="$c"; break
      fi
    done
  fi
  if [ -z "$UV" ] && [ -z "$PY" ]; then
    echo "Para instalar, a ferramenta usa o uv, que traz o Python certo sem pedir senha de administrador."
    echo "Fonte oficial: https://astral.sh/uv"
    read -r -p "Instalar o uv agora? [S/n] " resposta
    case "$resposta" in
      [nN]*) open "https://www.python.org/downloads/" 2>/dev/null; echo "Instale o Python 3.12 e dê dois cliques aqui de novo."; pausar; exit 1 ;;
    esac
    curl -LsSf https://astral.sh/uv/install.sh | sh || falhou
    UV="$HOME/.local/bin/uv"
  fi
  echo "Instalando a ferramenta (primeira vez ou instalação incompleta). Isso leva alguns minutos..."
  if [ -n "$UV" ]; then
    "$UV" run --no-project --python 3.12 degravar.py instalar || falhou
  else
    "$PY" degravar.py instalar || falhou
  fi
fi

if [ ! -f config/preferencias.json ]; then
  echo; echo "Escolha a pasta dos vídeos e onde salvar as degravações."
  .venv/bin/python degravar.py configurar || { pausar; exit 1; }
fi

echo
if .venv/bin/python degravar.py transcrever --abrir; then
  echo; echo "Pronto."
else
  falhou
fi
pausar
