#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "A ferramenta ainda não foi instalada. Dê dois cliques em Degravar.command primeiro."
else
  .venv/bin/python degravar.py configurar
fi
echo; read -n 1 -s -r -p "Pressione qualquer tecla para fechar."; echo
