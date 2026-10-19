# Degravação com Claude — Claude para Advogados

Transforme vídeos e áudios — audiências, depoimentos, reuniões com clientes, aulas, áudios de WhatsApp — em **degravação integral** com minutagem, organizada em um documento Markdown e acompanhada de um **player** em que você assiste ao vídeo com o texto sincronizado.

- **Entrada:** link do Google Drive (arquivo ou pasta), arquivo no computador ou a pasta `entrada/`.
- **Transcrição:** Whisper rodando **no seu computador** — o vídeo não é enviado para nenhum serviço.
- **Estrutura:** o Claude lê a degravação e preenche resumo executivo, participantes, tópicos com minutagem, pontos de atenção e notas de revisão — sem tocar no texto integral.
- **Reprodução:** `player.html` com clique-para-ir, busca, legenda, velocidade e atalhos de teclado.

---

## 1. Requisitos

- **Python 3.10 a 3.13** — no Windows, instale pelo [python.org](https://www.python.org/downloads/) marcando *"Add python.exe to PATH"*.
- **Claude Code** (aba *Code* do app Claude Desktop, ou terminal) para o fluxo conversacional.
- Espaço em disco para o modelo: ~3 GB (`large-v3`) ou ~1,6 GB (`turbo`), baixado uma única vez.
- *Opcional:* [ffmpeg](https://ffmpeg.org/download.html), apenas para converter formatos que o navegador não reproduz (`.mkv`, `.avi`, `.wmv`…). A transcrição funciona sem ele.

## 2. Instalação

```bash
git clone https://github.com/mcastelan35/degravacao-claude-advogados.git
cd degravacao-claude-advogados
python degravar.py instalar
```

> No Windows, se `python` não for reconhecido, use `py degravar.py instalar`.
> Para já deixar o modelo baixado: `python degravar.py instalar --baixar-modelo large-v3`.

## 3. Uso com o Claude (recomendado)

Abra a pasta do projeto no Claude Code e peça em linguagem natural:

> Degrava esse vídeo: https://drive.google.com/file/d/…/view
>
> Degrava os vídeos da pasta entrada. As partes são Maria Souza e Construtora Alfa.
>
> Estrutura a degravação audiencia-03-05
>
> Gera a versão com falantes da audiencia-03-05
>
> Abre o vídeo da audiência no minuto 12

O Claude segue a skill [`degravar`](.claude/skills/degravar/SKILL.md): instala o que faltar, roda a transcrição, estrutura o documento e abre o player.

## 4. Uso direto pelo terminal

```bash
python degravar.py "https://drive.google.com/file/d/ID/view"     # arquivo do Drive
python degravar.py "https://drive.google.com/drive/folders/ID"   # pasta inteira do Drive
python degravar.py "C:\Gravações\audiencia.mp4"                  # arquivo local
python degravar.py "C:\Gravações"                                # todos os vídeos de uma pasta
python degravar.py                                               # tudo que estiver em entrada/
python degravar.py transcrever --monitorar                       # vigia entrada/ continuamente

python degravar.py assistir                 # abre o player da última degravação
python degravar.py assistir audiencia --em 754
python degravar.py listar                   # todas as degravações e se já foram estruturadas
python degravar.py regerar <nome>           # refaz .md e player após corrigir o transcricao.json
```

Opções úteis de `transcrever`:

| Opção | Para quê |
|---|---|
| `--modelo turbo` | várias vezes mais rápido que o padrão, precisão um pouco menor |
| `--vocabulario "Fulano, Beltrana, Umuarama"` | melhora a grafia de nomes das partes e termos do caso |
| `--idioma ""` | detecta o idioma automaticamente (padrão: português) |
| `--refazer` | degrava de novo algo já processado |
| `--copiar-video` | copia o arquivo local para a pasta de saída (pasta autocontida) |

### Google Drive

O link precisa estar compartilhado como **"Qualquer pessoa com o link"**. Para arquivos sigilosos que não devem ser compartilhados, instale o **Google Drive para computador** e informe o caminho da pasta sincronizada (ex.: `"G:\Meu Drive\Audiências"`) — funciona como pasta local.

### Pasta `entrada/`

Funciona como caixa de entrada: coloque os vídeos ali e rode `python degravar.py`. Cada arquivo processado é **movido** para a sua pasta em `saida/`, então o que sobra em `entrada/` é o que ainda falta degravar.

## 5. O que é gerado

Cada mídia gera `saida/<nome>/`:

| Arquivo | Conteúdo |
|---|---|
| `<nome>.md` | ficha técnica, resumo/estrutura (preenchidos pelo Claude), índice por minutagem, trechos para conferência e **transcrição integral** com minutagem clicável |
| `player.html` | vídeo + transcrição sincronizada; abre com dois cliques, sem internet |
| `transcricao.json` | fonte de verdade: frases, tempos, confiança por palavra |
| `<nome>.txt` | texto corrido, para colar em peças |
| `<nome>.srt` / `.vtt` | legendas (VLC, YouTube, editores de vídeo) |
| o vídeo | quando veio do Drive ou da pasta `entrada/` |

## 6. Precisão

| Modelo | Precisão | Velocidade | Download |
|---|---|---|---|
| `large-v3` (padrão) | máxima | lenta em CPU | ~3 GB |
| `turbo` | muito próxima | várias vezes mais rápida | ~1,6 GB |
| `medium` / `small` | menor | rápidas | 1,5 GB / 0,5 GB |

Com placa de vídeo NVIDIA (CUDA), a transcrição é muitas vezes mais rápida; sem ela, roda em CPU automaticamente.

Para melhorar o resultado:

- Informe nomes próprios com `--vocabulario` e mantenha termos recorrentes em [`config/vocabulario.txt`](config/vocabulario.txt).
- Trechos com baixa confiança aparecem com ⚠️ no `.md` e com sublinhado ondulado no player — confira-os na mídia.
- Corrija erros editando o `txt` do trecho em `transcricao.json` e rodando `regerar` (ou peça ao Claude).

## 7. Limitações — leia antes de usar em processo

- **Transcrição automática é apoio, não prova.** Para citação em peça ou juntada aos autos, confira os trechos na mídia original.
- **Não há separação automática de vozes.** A identificação de falantes é feita pelo Claude a partir do contexto e vem sempre marcada como inferência.
- Música de fundo, vozes sobrepostas e áudio de baixa qualidade reduzem a precisão.

## 8. Privacidade (LGPD)

- O vídeo e o áudio são processados **somente no seu computador**.
- Quando você pede ao Claude para estruturar, apenas o **texto** da degravação é lido pelo Claude, nas condições da sua conta.
- `entrada/` e `saida/` estão no `.gitignore`: suas gravações nunca vão para o GitHub, mesmo que você faça um fork.

## 9. Problemas comuns

| Sintoma | Solução |
|---|---|
| `Dependências ausentes` | rode `python degravar.py instalar` |
| Falha no link do Drive | compartilhe como "Qualquer pessoa com o link" ou use a pasta do Google Drive para computador |
| Player não toca o vídeo | formato não suportado pelo navegador: instale o ffmpeg e rode com `--refazer`, ou selecione o arquivo no aviso do próprio player |
| Muito lento | use `--modelo turbo`; feche outros programas pesados |
| Nomes escritos errado | `--vocabulario "Nome Completo, Outro Nome"` |
