#!/usr/bin/env python3
"""Empacota a ferramenta como plugin do Claude Code (o repositório é plugin e marketplace, como o Radar).

    python ferramentas/empacotar_plugin.py

Gera, a partir das skills do projeto (.claude/skills — a fonte da verdade, não edite as cópias):
  - skills/<nome>/SKILL.md      versão do plugin: o comando base passa a ser o uv + ${CLAUDE_PLUGIN_ROOT}
  - .claude-plugin/plugin.json  e  .claude-plugin/marketplace.json
  - dist/degravacao-<versão>.plugin   arquivo para enviar ao claude.ai (Personalizar › Plugins)

Marcadores nas skills: o bloco COMANDO é trocado pelo comando do plugin; blocos REPO saem da versão do
plugin; blocos PLUGIN (escritos dentro de um comentário HTML, invisíveis no repositório) entram nela.

Quem já instalou só recebe código novo quando a versão muda: suba `__version__` em degravacao/__init__.py
a cada publicação.

Instalação pelo GitHub, no Claude Code (precisa do Git):
    /plugin marketplace add mcastelan35/degravacao-claude-advogados
    /plugin install degravacao@degravacao-claude-advogados
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from degravacao import __version__  # noqa: E402

NOME = "degravacao"
MARKETPLACE = "degravacao-claude-advogados"
AUTOR = {"name": "Marcos Vilas Boas", "url": "https://www.instagram.com/advvilasboas/"}
SITE = "https://github.com/mcastelan35/degravacao-claude-advogados"
DESCRICAO = ("Degravação de audiências, depoimentos e reuniões para advogados: transcrição integral local (Whisper), "
             "separação de falantes, player com legendas, marcações e revisão, e documento em Word. "
             "Os vídeos não saem do computador.")
PALAVRAS = ["degravação", "transcrição", "audiência", "whisper", "legendas", "advocacia", "jurídico"]

# `--plugin` avisa ao script que ele roda como plugin (dados e degravações em pastas do usuário), mesmo que o
# cache de plugins do Claude Code esteja num lugar fora do padrão.
SCRIPT = '"${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin'
CMD = f"uv run --no-project --python 3.12 {SCRIPT}"
UV_WINDOWS = f'& "$env:USERPROFILE\\.local\\bin\\uv.exe" run --no-project --python 3.12 {SCRIPT}'
UV_UNIX = f"~/.local/bin/uv run --no-project --python 3.12 {SCRIPT}"
COMANDO_PLUGIN = (
    f"**Comando base** (`<cmd>` neste texto): `{CMD}`.\n"
    "Ele exige o **uv** (astral.sh): sem o uv, nenhum comando roda, mesmo que já exista Python no computador — "
    "instale-o primeiro (skill `comecar`, passo 2). Logo depois de instalar o uv, ele ainda não está no PATH desta "
    f"sessão: use o caminho completo — Windows (PowerShell): `{UV_WINDOWS} …`; Mac/Linux: `{UV_UNIX} …` — ou peça ao "
    "usuário para reiniciar o Claude Code. Se o Claude Code pedir permissão para esses comandos, explique que são a "
    "mesma ferramenta e sugira \"Sim, e não perguntar de novo\".\n"
    "O código fica no plugin; ambiente, preferências e modelos ficam numa pasta do usuário "
    "(`%LOCALAPPDATA%\\Degravacao` no Windows, `~/Library/Application Support/Degravacao` no Mac) e as degravações, por "
    "padrão, numa pasta só deste computador (Documentos/Degravações, ou a pasta do usuário quando Documentos está no "
    "OneDrive/iCloud — a ferramenta diz qual). Os comandos rodam em qualquer pasta. Não existe o atalho de dois cliques "
    "nem `python degravar.py` no plugin: quando uma mensagem citar um comando, rode-o com `<cmd>`."
)
PERMISSOES = [f"Bash({CMD} *)", f"PowerShell({CMD} *)", f"Bash({UV_UNIX} *)", f"PowerShell({UV_WINDOWS} *)"]

# Incluídos no .plugin (o resto do repositório — testes, atalhos .bat, saídas — fica de fora).
ARQUIVOS = ["degravar.py", "degravacao", "config/vocabulario.txt", "requirements.txt", "requirements-gpu.txt",
            "README.md", ".claude-plugin", "skills"]


def skill_do_plugin(texto: str) -> str:
    texto = texto.replace("python degravar.py", "<cmd>")   # antes do bloco COMANDO, que cita o comando do repositório
    texto = re.sub(r"<!-- COMANDO:INICIO -->.*?<!-- COMANDO:FIM -->", lambda _: COMANDO_PLUGIN, texto, flags=re.S)
    texto = re.sub(r"<!-- REPO:INICIO -->.*?<!-- REPO:FIM -->\n?", "", texto, flags=re.S)
    texto = re.sub(r"<!-- PLUGIN:INICIO[^\n]*\n(.*?)\nPLUGIN:FIM -->", lambda m: m.group(1), texto, flags=re.S)
    cab, corpo = texto.split("\n---\n", 1)          # frontmatter: libera o comando da ferramenta durante a skill
    cab += "\nallowed-tools:\n" + "".join(f"  - {p}\n" for p in PERMISSOES)
    return cab.rstrip("\n") + "\n---\n" + corpo


def main() -> int:
    for origem in sorted((RAIZ / ".claude" / "skills").glob("*/SKILL.md")):
        destino = RAIZ / "skills" / origem.parent.name / "SKILL.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        aviso = "<!-- Gerado por ferramentas/empacotar_plugin.py a partir de .claude/skills: não edite aqui. -->\n"
        texto = skill_do_plugin(origem.read_text(encoding="utf-8"))
        cab, corpo = texto.split("\n---\n", 1)
        destino.write_bytes((cab + "\n---\n" + aviso + corpo).encode("utf-8"))
        print(f"✓ {destino.relative_to(RAIZ)}")

    plugin = {"name": NOME, "version": __version__, "description": DESCRICAO, "author": AUTOR, "homepage": SITE,
              "repository": SITE, "keywords": PALAVRAS}
    mercado = {"name": MARKETPLACE, "owner": AUTOR,
               "metadata": {"description": "Degravação para advogados no Claude Code.", "version": __version__},
               "plugins": [{"name": NOME, "source": "./", "description": DESCRICAO, "version": __version__,
                            "author": AUTOR, "homepage": SITE, "category": "legal", "keywords": PALAVRAS}]}
    pasta = RAIZ / ".claude-plugin"
    pasta.mkdir(exist_ok=True)
    for nome, dados in (("plugin.json", plugin), ("marketplace.json", mercado)):
        (pasta / nome).write_bytes((json.dumps(dados, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        print(f"✓ .claude-plugin/{nome}")

    saida = RAIZ / "dist" / f"{NOME}-{__version__}.plugin"
    saida.parent.mkdir(exist_ok=True)
    if saida.exists():
        print(f"⚠ dist/{saida.name} já existia: se o código mudou desde a última publicação, suba __version__ em "
              "degravacao/__init__.py — quem já instalou só recebe a versão nova.")
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for item in ARQUIVOS:
            caminho = RAIZ / item
            for arq in [caminho] if caminho.is_file() else sorted(caminho.rglob("*")):
                if arq.is_file() and "__pycache__" not in arq.parts:
                    z.write(arq, arq.relative_to(RAIZ).as_posix())
    print(f"✓ {saida.relative_to(RAIZ)} ({saida.stat().st_size / 1e3:.0f} KB) — versão {__version__}, para enviar ao claude.ai")
    return 0


if __name__ == "__main__":
    for _f in (sys.stdout, sys.stderr):
        try:
            _f.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    sys.exit(main())
