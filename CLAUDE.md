# Degravação — Claude para Advogados

Ferramenta que recebe vídeos/áudios (link do Google Drive, arquivo ou pasta), transcreve integralmente com Whisper **local** e entrega um `.md` estruturado, o mesmo documento em Word e um `player.html` com legendas e transcrição sincronizada.

## Como operar

Para qualquer pedido de degravação, transcrição, estruturação ou reprodução, siga a skill `.claude/skills/degravar/SKILL.md`; para o primeiro uso, `.claude/skills/comecar/SKILL.md`.

Comandos (todos pelo ponto de entrada único, que se reexecuta na `.venv` automaticamente):

```bash
python degravar.py diagnostico              # o que está pronto e o próximo passo (roda sem nada instalado)
python degravar.py instalar                 # 1ª vez (ou instalação interrompida: recomeça sozinha)
python degravar.py configurar [--entrada PASTA] [--saida PASTA] [--mostrar]  # grava config/preferencias.json
python degravar.py "<link Drive | arquivo | pasta>" [--modelo turbo] [--vocabulario "Nome, Nome"] [--num-falantes N] [--sem-falantes]
python degravar.py [--abrir]                # degrava o que houver de novo na pasta configurada (ou entrada/)
python degravar.py transcrever --monitorar  # vigia a pasta
python degravar.py exemplo                  # audiência fictícia com a voz do sistema (modelo turbo)
python degravar.py assistir [slug] [--em SEG]
python degravar.py listar
python degravar.py regerar <slug>           # refaz .md/Word/legendas/player a partir do transcricao.json
python degravar.py falantes <slug> [--separar] [--listar] [--atribuir 12=F2] [--nomear F1="Juiz(a)"]
python degravar.py corrigir <slug> <frase|HH:MM:SS> "texto"   # correção pontual, guardando o original do Whisper
python degravar.py revisao <slug> [arquivo] [--forcar]        # aplica a revisão exportada pelo player
python degravar.py artefato <slug> [--titulo T] [--sem-video] [--sem-marcacoes]  # página (+ mídia ≤15 MB) para artefato
```

## Estrutura

- `degravar.py` — CLI. `MODO_PLUGIN` vem do argumento `--plugin` (a skill do plugin sempre o passa) ou da pasta de plugins do Claude Code; nele, dados ficam em `%LOCALAPPDATA%\Degravacao` / `~/Library/Application Support/Degravacao` e as degravações numa pasta local (Documentos, ou a pasta do usuário se Documentos está na nuvem). `DEGRAVAR_DADOS` sobrepõe a pasta de dados (testes).
- `Degravar.bat` / `Degravar.command` — atalho de dois cliques (instala, configura e degrava); `Configurar.*` reabre a configuração. Consideram instalado quando as dependências importam no Python da `.venv` (o marcador `.venv/.instalado`, gravado no fim de uma instalação completa, diz ao `instalar` que não há nada a recriar; `# sem-gpu` nele registra a instalação sem CUDA). `.bat` em CRLF (`.gitattributes`), sem acentos.
- `degravacao/fontes.py` — Drive (gdown; cada download numa subpasta com o id, para nomes repetidos não se sobrescreverem), arquivos e pastas (sem subpastas; avisa o que ignorou).
- `degravacao/midia.py` — exame pelo conteúdo (PyAV: contêiner, codecs, pixel, capa ≠ vídeo, stream sem decodificador) e a cópia que o navegador toca: `video.mp4`/`audio.m4a` na pasta da degravação, com nome curto por causa do limite de 260 caracteres do Windows. O original nunca é alterado; sem trilha de áudio, recusa (`ErroMidia.definitivo` → `config/ignorados.json`).
- `degravacao/transcricao.py` — faster-whisper; divide segmentos em frases pelos tempos das palavras e marca baixa confiança. `gpu_para_large_v3()` decide o modelo automático (float16 e ≥6 GB); no Linux as bibliotecas CUDA também vêm do pip.
- `degravacao/falantes.py` — diarização local (sherpa-onnx; modelos do GitHub em `modelos/`, sem conta/chave). Frase recebe o falante majoritário; curtas/ambíguas ficam `falante_incerto`.
- `degravacao/documento.py` — `.md`, `.srt`, `.vtt`, `.txt`. A seção entre `<!-- CLAUDE:ESTRUTURA:INICIO/FIM -->` é do Claude e é preservada pelo `regerar`; `secao_estruturada()` é o único juiz de "pendente" (`MARCA_PENDENTE`). `partes_legenda` devolve o índice da frase em cada legenda.
- `degravacao/word.py` — `.docx` escrito à mão (OOXML, compatibilidade 15), com as marcas `(?)`/`✎` dos falantes.
- `degravacao/player.py` + `degravacao/pagina/` — `player.html` autocontido (dados embutidos, sem servidor); no modo artefato, sem URL do Drive e sem o texto original das frases corrigidas.
- `degravacao/artefato.py` — página para artefato: mídia recomprimida para ≤15 MB sem metadados (vídeo → só áudio → sem mídia), com o motivo na ficha; `--sem-video` = nenhuma mídia.
- `degravacao/nuvem.py` — pastas de nuvem (unidade inteira do Google Drive, OneDrive e bibliotecas do SharePoint pelo registro, Dropbox, iCloud), Documentos e Downloads.
- `ferramentas/empacotar_plugin.py` — gera `skills/`, `.claude-plugin/` e `dist/*.plugin` a partir de `.claude/skills` (fonte da verdade). Blocos `COMANDO`/`REPO`/`PLUGIN` nas skills.
- `config/vocabulario.txt` — termos jurídicos passados ao Whisper como `hotwords`.

## Regras

- Nunca alterar a transcrição integral ao estruturar; correções só pelos comandos `corrigir` e `revisao` (guardam `txt_whisper`), a pedido do usuário. Nunca editar `transcricao.json` à mão.
- Revisão de falantes só via `falantes --atribuir` (preserva `falante_acustico` e marca ✎); corrigir apenas o que o sentido torna inequívoco. `--separar`/`--num-falantes` numa degravação já revisada descarta nomes e correções (guarda cópia `transcricao-antes-*.json` e avisa).
- Todo `transcricao.json` é gravado de forma atômica (`gravar_json`); `--refazer` e `revisao` guardam cópia antes.
- Nunca commitar conteúdo de `entrada/` ou `saida/` nem `config/preferencias.json`, `config/ignorados.json` (dados de clientes e caminhos locais — LGPD).
- Pasta configurada pelo usuário: os originais nunca são movidos; o já degravado é pulado pela chave `arquivo:<caminho>` (inclusive nas saídas anteriores, `saidas_anteriores`). Só a `entrada/` interna move os vídeos para a saída.
- `av<17` está fixado de propósito: o PyAV 17+ quebra o `faster-whisper` 1.2.
- Artefato só com aviso de que texto, marcações e (salvo `--sem-video`) a mídia saem do computador; gravação com dados de clientes exige confirmação expressa.
- A cada publicação do plugin, subir `__version__` em `degravacao/__init__.py` e rodar `python ferramentas/empacotar_plugin.py`: quem já instalou só recebe a versão nova.
