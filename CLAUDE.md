# Degravação — Claude para Advogados

Ferramenta que recebe vídeos/áudios (link do Google Drive, arquivo ou pasta), transcreve integralmente com Whisper **local** e entrega um `.md` estruturado + `player.html` com transcrição sincronizada.

## Como operar

Para qualquer pedido de degravação, transcrição, estruturação ou reprodução, siga a skill `.claude/skills/degravar/SKILL.md`.

Comandos (todos pelo ponto de entrada único, que se reexecuta na `.venv` automaticamente):

```bash
python degravar.py instalar                 # 1ª vez
python degravar.py "<link Drive | arquivo | pasta>" [--modelo turbo] [--vocabulario "Nome, Nome"]
python degravar.py                          # processa entrada/
python degravar.py transcrever --monitorar  # vigia entrada/
python degravar.py assistir [slug] [--em SEG]
python degravar.py listar
python degravar.py regerar <slug>           # refaz .md/legendas/player a partir do transcricao.json
```

## Estrutura

- `degravar.py` — CLI.
- `degravacao/fontes.py` — Drive (gdown), arquivos e pastas.
- `degravacao/transcricao.py` — faster-whisper; divide segmentos em frases pelos tempos das palavras e marca baixa confiança.
- `degravacao/documento.py` — `.md`, `.srt`, `.vtt`, `.txt`. A seção entre `<!-- CLAUDE:ESTRUTURA:INICIO/FIM -->` é do Claude e é preservada pelo `regerar`.
- `degravacao/player.py` — `player.html` autocontido (dados embutidos, sem servidor).
- `config/vocabulario.txt` — termos jurídicos passados ao Whisper como `hotwords`.

## Regras

- Nunca alterar a transcrição integral ao estruturar; correções só via `transcricao.json` + `regerar`, a pedido do usuário.
- Nunca commitar conteúdo de `entrada/` ou `saida/` (dados de clientes — LGPD).
- `av<17` está fixado de propósito: o PyAV 17+ quebra o `faster-whisper` 1.2.
