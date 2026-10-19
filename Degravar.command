#!/bin/bash
# Dois cliques no Finder: instala na primeira vez, pede a pasta e degrava o que houver de novo.
cd "$(dirname "$0")" || exit 1

pausar() { echo; read -n 1 -s -r -p "Pressione qualquer tecla para fechar."; echo; }

PY=""
for c in python3.13 python3.12 python3.11 python3.14 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Nenhum Python compatível (versão 3.11 a 3.14) foi encontrado."
  echo "Instale pelo site que vai abrir agora e depois dê dois cliques aqui de novo."
  open "https://www.python.org/downloads/" 2>/dev/null
  pausar; exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Primeira vez: instalando a ferramenta. Isso leva alguns minutos..."
  "$PY" degravar.py instalar || { echo "Algo deu errado. Copie a mensagem acima e peça ajuda ao Claude."; pausar; exit 1; }
fi

if [ ! -f config/preferencias.json ]; then
  echo; echo "Escolha a pasta onde você vai colocar os vídeos."
  .venv/bin/python degravar.py configurar || { pausar; exit 1; }
fi

echo
if .venv/bin/python degravar.py transcrever --abrir; then
  echo; echo "Pronto."
else
  echo; echo "Algo deu errado. Copie a mensagem acima e peça ajuda ao Claude."
fi
pausar
