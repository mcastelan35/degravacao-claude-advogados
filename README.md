# Degravação com Claude — Claude para Advogados

Transforme vídeos e áudios — audiências, depoimentos, reuniões com clientes, aulas, áudios de WhatsApp — em **degravação integral** com minutagem, organizada em um documento Markdown e acompanhada de um **player** em que você assiste ao vídeo com o texto sincronizado.

- **Entrada:** uma pasta do seu computador que você escolhe uma vez (pode ser a pasta sincronizada do Google Drive), um link do Google Drive ou um arquivo avulso.
- **Transcrição:** Whisper rodando **no seu computador** — o vídeo não é enviado para nenhum serviço.
- **Falantes:** separação de quem fala pela voz, também local e **sem conta ou chave**, revisada pelo Claude pelo sentido da conversa.
- **Estrutura:** o Claude lê a degravação e preenche resumo executivo, participantes, tópicos com minutagem, pontos de atenção e notas de revisão — sem tocar no texto integral.
- **Reprodução:** `player.html` com clique-para-ir, busca, legenda, velocidade e atalhos de teclado.

---

## 1. Requisitos

- **Python 3.11 a 3.14** (recomendado 3.12), instalado pelo [python.org](https://www.python.org/downloads/). No Windows, marque *"Add python.exe to PATH"* na instalação. Se faltar, o atalho do Windows oferece instalar sozinho.
- **Claude Code** (aba *Code* do app Claude Desktop), para o uso conversacional. O uso por dois cliques dispensa.
- Espaço em disco para o modelo: ~3 GB (`large-v3`) ou ~1,6 GB (`turbo`), baixado uma única vez.

## 2. Instalação e uso em dois cliques (sem terminal)

1. Nesta página do GitHub, clique em **Code → Download ZIP** e extraia a pasta onde quiser (por exemplo, em Documentos).
2. Dê dois cliques em **`Degravar.bat`** (Windows) ou **`Degravar.command`** (Mac).
   - Na primeira vez, ele instala a ferramenta (alguns minutos) e abre uma janela para você **escolher a pasta dos vídeos**.
   - No Mac, se aparecer o aviso de segurança, clique com o botão direito no arquivo e escolha **Abrir**.
3. Daí em diante, o uso é sempre o mesmo: **coloque os vídeos na pasta e dê dois cliques em `Degravar`**. Ele degrava só o que ainda não foi degravado e, ao terminar, abre o player.

Os resultados ficam numa subpasta **`Degravações`** dentro da pasta que você escolheu, uma pasta por vídeo. **Os vídeos originais nunca são movidos nem alterados.** Para trocar a pasta, o modelo ou ligar a separação de falantes, use **`Configurar.bat`** / **`Configurar.command`**.

A primeira degravação demora mais, porque baixa o modelo de transcrição (~3 GB), uma única vez.

> **Dica:** escolha como pasta dos vídeos uma pasta do **Google Drive para computador** (ex.: `G:\Meu Drive\Degravações`). Assim você sobe o vídeo pelo celular ou pelo navegador e ele já aparece no computador para ser degravado.

### Instalação pelo terminal (opcional)

```bash
git clone https://github.com/mcastelan35/degravacao-claude-advogados.git
cd degravacao-claude-advogados
python degravar.py instalar
python degravar.py configurar          # abre a janela para escolher a pasta dos vídeos
```

> No Windows, se `python` não for reconhecido, use `py`. Para escolher a pasta sem janela: `python degravar.py configurar --entrada "C:\Gravações"`.

## 3. Uso com o Claude (recomendado)

Abra a pasta do projeto no Claude Code e peça em linguagem natural:

> Degrava esse vídeo: https://drive.google.com/file/d/…/view
>
> Degrava os vídeos da pasta entrada. As partes são Maria Souza e Construtora Alfa.
>
> Degrava essa audiência separando os falantes: são 3 pessoas (juiz, advogada e testemunha).
>
> Estrutura a degravação audiencia-03-05
>
> Gera a versão com falantes da audiencia-03-05
>
> Abre o vídeo da audiência no minuto 12

Na primeira vez, basta pedir **"instala e configura a degravação"**: o Claude instala tudo e abre no seu computador a janela para escolher a pasta dos vídeos.

O Claude segue a skill [`degravar`](.claude/skills/degravar/SKILL.md): instala o que faltar, roda a transcrição, estrutura o documento e abre o player.

## 4. Uso direto pelo terminal

```bash
python degravar.py "https://drive.google.com/file/d/ID/view"     # arquivo do Drive
python degravar.py "https://drive.google.com/drive/folders/ID"   # pasta inteira do Drive
python degravar.py "C:\Gravações\audiencia.mp4"                  # arquivo local
python degravar.py "C:\Gravações"                                # todos os vídeos de uma pasta
python degravar.py                                               # o que houver de novo na pasta escolhida
python degravar.py transcrever --monitorar                       # vigia a pasta continuamente
python degravar.py configurar --mostrar                          # mostra pastas e preferências

python degravar.py assistir                 # abre o player da última degravação
python degravar.py assistir audiencia --em 754
python degravar.py listar                   # todas as degravações e se já foram estruturadas
python degravar.py regerar <nome>           # refaz .md e player após corrigir o transcricao.json
python degravar.py falantes <nome> --separar --num-falantes 3   # separa falantes de degravação já feita
python degravar.py falantes <nome> --listar                     # frases com o falante atribuído
python degravar.py falantes <nome> --atribuir 12=F2 --nomear F1="Juiz(a)"
```

Opções úteis de `transcrever`:

| Opção | Para quê |
|---|---|
| `--modelo turbo` | várias vezes mais rápido que o padrão, precisão um pouco menor |
| `--vocabulario "Fulano, Beltrana, Umuarama"` | melhora a grafia de nomes das partes e termos do caso |
| `--num-falantes 3` | separa quem fala, sabendo quantas pessoas são (mais confiável) |
| `--falantes` | separa quem fala sem informar quantas pessoas são |
| `--idioma ""` | detecta o idioma automaticamente (padrão: português) |
| `--refazer` | degrava de novo algo já processado |
| `--copiar-video` | copia o arquivo local para a pasta de saída (pasta autocontida) |

### Google Drive

O link precisa estar compartilhado como **"Qualquer pessoa com o link"**. Para arquivos sigilosos que não devem ser compartilhados, instale o **Google Drive para computador** e informe o caminho da pasta sincronizada (ex.: `"G:\Meu Drive\Audiências"`) — funciona como pasta local.

### Pasta dos vídeos

Depois de `configurar`, `python degravar.py` degrava o que houver de novo na pasta escolhida e grava os resultados em `Degravações/`, sem mexer nos originais. Sem configuração, vale a pasta interna `entrada/` do repositório, que funciona como caixa de entrada: cada vídeo degravado é **movido** para `saida/`.

## 5. O que é gerado

Cada mídia gera `saida/<nome>/`:

| Arquivo | Conteúdo |
|---|---|
| `<nome>.md` | ficha técnica, resumo/estrutura (preenchidos pelo Claude), índice por minutagem, trechos para conferência e **transcrição integral** com minutagem clicável |
| `player.html` | vídeo + transcrição sincronizada; abre com dois cliques, sem internet |
| `transcricao.json` | fonte de verdade: frases, tempos, confiança por palavra |
| `<nome>.txt` | texto corrido, para colar em peças (com o nome de quem fala, se houver separação) |
| `<nome>.srt` / `.vtt` | legendas (VLC, YouTube, editores de vídeo) |
| o vídeo | quando veio do Drive ou da pasta `entrada/` |

## 6. Precisão

| Modelo | Precisão | Velocidade | Download |
|---|---|---|---|
| `large-v3` (padrão) | máxima | lenta em CPU | ~3 GB |
| `turbo` | muito próxima | várias vezes mais rápida | ~1,6 GB |
| `medium` / `small` | menor | rápidas | 1,5 GB / 0,5 GB |

Com placa de vídeo NVIDIA (CUDA), a transcrição é muitas vezes mais rápida; sem ela, roda em CPU automaticamente. Referência: numa máquina de 4 núcleos sem placa de vídeo, o `large-v3` levou cerca de 2x a duração da gravação (9 min de audiência em ~18 min).

Para melhorar o resultado:

- Informe nomes próprios com `--vocabulario` e mantenha termos recorrentes em [`config/vocabulario.txt`](config/vocabulario.txt).
- Trechos com baixa confiança aparecem com ⚠️ no `.md` e com sublinhado ondulado no player — confira-os na mídia.
- Corrija erros editando o `txt` do trecho em `transcricao.json` e rodando `regerar` (ou peça ao Claude).

## 7. Separação de falantes

Com `--falantes` ou `--num-falantes N`, cada frase recebe um rótulo (F1, F2…) definido pela **voz**. A separação roda no seu computador, com modelos abertos baixados do GitHub no primeiro uso (~33 MB: segmentação pyannote 3.0, licença MIT, e WeSpeaker, licença Apache 2.0). **Não exige conta no Hugging Face nem chave de API.**

Em seguida o Claude revisa pelo **sentido**: corrige perguntas atribuídas a quem responde (e vice-versa), separa quem a acústica juntou e dá nome a cada falante. Toda atribuição revista fica marcada com ✎, e a separação original continua guardada no `transcricao.json`.

Resultado medido numa audiência real por videoconferência (9 min, áudio comprimido, 3 participantes), comparando com um gabarito de quem fala montado pela leitura do conteúdo:

| | Acerto por frase |
|---|---|
| Separação pela voz, geral | ~78% |
| Frases sem marcação | ~86% |
| Frases marcadas com **(?)** (curtas, trocas rápidas) | ~50% |

Na prática: a voz acerta bem as falas longas, erra nas respostas curtas ("Sim", "Também") e em sequências rápidas de pergunta e resposta, e pode juntar quem fala pouco (como o juiz) com outra pessoa. Por isso a revisão do Claude é parte do fluxo e as marcas **(?)** devem ser conferidas ouvindo no player. A separação levou ~1,2 min para os 9 min de áudio.

## 8. Ver dentro do Claude (artefato)

O player local abre no navegador do computador. Para assistir **dentro do Claude** ou mandar o link a alguém, peça ao Claude: **"publica a degravação X como artefato"**. Ele gera uma página com o vídeo, a transcrição sincronizada, a busca, o resumo, os tópicos e a ficha técnica, e publica no claude.ai.

- O artefato aceita arquivos de até 15 MB, então a mídia é recomprimida: vídeos curtos saem com imagem (até cerca de 10 minutos), gravações mais longas só com o áudio e, no limite, só com a transcrição.
- **Atenção à privacidade:** o artefato é privado por padrão (só você abre até compartilhar pelo menu da página), mas a mídia e o texto **saem do seu computador** e vão para o claude.ai. Use para aulas e conteúdo público; para audiências e reuniões com clientes, prefira o player local ou publique só a transcrição (`--sem-video`).
- Pelo terminal: `python degravar.py artefato <nome> --titulo "Título"` prepara a página e a mídia; a publicação é feita pelo Claude.

## 9. Limitações — leia antes de usar em processo

- **Transcrição automática é apoio, não prova.** Para citação em peça ou juntada aos autos, confira os trechos na mídia original.
- **Falantes são atribuição aproximada**, mesmo depois da revisão do Claude, que não ouve o áudio: confira as marcas (?) e ✎ antes de atribuir uma fala a alguém em peça.
- Música de fundo, vozes sobrepostas e áudio de baixa qualidade reduzem a precisão.

## 10. Privacidade (LGPD)

- O vídeo e o áudio são processados **somente no seu computador** — transcrição e separação de falantes. Só saem dele se você pedir um artefato (seção 8).
- Quando você pede ao Claude para estruturar, apenas o **texto** da degravação é lido pelo Claude, nas condições da sua conta.
- `entrada/` e `saida/` estão no `.gitignore`: suas gravações nunca vão para o GitHub, mesmo que você faça um fork.

## 11. Problemas comuns

| Sintoma | Solução |
|---|---|
| `Dependências ausentes` | dê dois cliques em `Degravar` ou rode `python degravar.py instalar` |
| Janela de escolha da pasta não abriu | rode `python degravar.py configurar --entrada "CAMINHO DA PASTA"` |
| Falha no link do Drive | compartilhe como "Qualquer pessoa com o link" ou use a pasta do Google Drive para computador |
| Player não toca o vídeo | o vídeo foi movido ou o formato não é suportado: rode de novo com `--refazer` (a ferramenta converte `.mkv`, `.avi`, `.wmv` etc.) ou selecione o arquivo no aviso do próprio player |
| Muito lento | use `--modelo turbo`; feche outros programas pesados |
| Nomes escritos errado | `--vocabulario "Nome Completo, Outro Nome"` |
| Falantes trocados | informe `--num-falantes`; peça ao Claude a revisão de falantes; corrija com `falantes --atribuir` |
