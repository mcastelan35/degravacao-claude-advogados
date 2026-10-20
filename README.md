# Degravação com Claude — Claude para Advogados

Plugin desenvolvido por **Marcos Vilas Boas** — [Fale comigo](https://www.instagram.com/advvilasboas/) (Instagram @advvilasboas).

Transforme vídeos e áudios — audiências, depoimentos, reuniões com clientes, aulas, áudios de WhatsApp — em **degravação integral** com minutagem, organizada em um documento Markdown e acompanhada de um **player** em que você assiste ao vídeo com o texto sincronizado.

- **Entrada:** uma pasta do seu computador que você escolhe uma vez (pode ser a pasta sincronizada do Google Drive), um link do Google Drive ou um arquivo avulso.
- **Transcrição:** Whisper rodando **no seu computador** — o vídeo não é enviado para nenhum serviço.
- **Falantes:** separação de quem fala pela voz, também local e **sem conta ou chave**, revisada pelo Claude pelo sentido da conversa.
- **Estrutura:** o Claude lê a degravação e preenche resumo executivo, participantes, tópicos com minutagem, pontos de atenção e notas de revisão — sem tocar no texto integral.
- **Reprodução:** um player no navegador com legendas sobre o vídeo, forma de onda colorida por falante, destaque palavra a palavra, **marcações** jurídicas, **revisão** do texto, citação com minutagem, janela flutuante e atalhos — e o documento também em **Word**.

---

## 1. Comece aqui

Você precisa só do **app Claude** com a aba **Code** (Claude Code), em Windows 10/11 (x64) ou macOS, e de uns 6 GB livres. **Não precisa instalar Python nem nada antes**: o Claude cuida disso. (Só a instalação pelo GitHub, no caminho A, usa o **Git**; sem ele, use o arquivo `.plugin` ou o ZIP.)

### A. Como plugin do Claude (recomendado)

1. Adicione o plugin **Degravação**, de um destes jeitos:
   - no Claude Code, digite os dois comandos (precisa do Git instalado; no Windows, [Git for Windows](https://git-scm.com/download/win)):
     ```
     /plugin marketplace add mcastelan35/degravacao-claude-advogados
     /plugin install degravacao@degravacao-claude-advogados
     ```
   - ou envie o arquivo `degravacao-<versão>.plugin` (publicado na seção **Releases** do GitHub, ou enviado pelo autor; quem tem o código gera o seu com `python ferramentas/empacotar_plugin.py`) em **claude.ai › Personalizar › Plugins**; ele aparece sozinho no Claude Code.
2. Abra a aba **Code** em qualquer pasta e digite **`/degravacao:comecar`**, ou só "quero começar a degravar".
3. O Claude confere o computador, instala o que falta (sem pedir senha de administrador), pergunta onde ficam os vídeos — já mostrando suas pastas do Google Drive, OneDrive ou Dropbox —, testa com uma audiência fictícia de 40 segundos e abre o player.

Daí em diante, é só pedir: **"degrava os vídeos novos"**. Se o Claude Code pedir permissão para rodar um comando da ferramenta, responda "Sim, e não perguntar de novo". Para receber as versões novas: no Claude Code, `/plugin` › **Marketplaces** › atualizar (ou ligue a atualização automática ali); pelo terminal, `claude plugin update degravacao@degravacao-claude-advogados`.

### B. Abrindo a pasta do projeto no Claude Code

Nesta página do GitHub, clique em **Code › Download ZIP** e extraia num caminho curto (ex.: `C:\Degravacao`). Abra essa pasta na aba **Code** e diga **"quero começar"**: o Claude segue a mesma skill [`comecar`](.claude/skills/comecar/SKILL.md). Os comandos da ferramenta já vêm liberados em [`.claude/settings.json`](.claude/settings.json), então o Claude não pede permissão a cada passo.

### C. Em dois cliques, sem o Claude

Dê dois cliques em **`Degravar.bat`** (Windows) ou **`Degravar.command`** (Mac). Na primeira vez ele instala a ferramenta — se o computador não tiver Python, oferece instalar o **uv**, que traz o Python certo sem pedir administrador — e abre as janelas para escolher as pastas. Depois, é só pôr os vídeos na pasta e dar dois cliques de novo. **`Configurar`** troca as pastas. Se a instalação for interrompida (rede, janela fechada), dê dois cliques de novo: ela recomeça sozinha.

No Mac, o arquivo baixado da internet vem com o aviso de segurança: no macOS 15 ou mais novo, abra **Ajustes do Sistema › Privacidade e Segurança** e clique em **Abrir Mesmo Assim**; em versões anteriores, botão direito › **Abrir**. Em Windows com processador Snapdragon (ARM64), a instalação só funciona pelo uv (ele traz um Python x64, que roda emulado).

### Onde ficam os vídeos

- **Pasta na nuvem** (Google Drive para computador, inclusive drives compartilhados; OneDrive e bibliotecas do SharePoint; Dropbox): você envia o vídeo pelo celular ou pelo navegador e ele aparece no computador para ser degravado. Nesse caso, as degravações ficam por padrão numa pasta **só deste computador** — Documentos/Degravações ou, se a sua pasta Documentos estiver no OneDrive/iCloud, a pasta do seu usuário; a ferramenta mostra qual e avisa quando a pasta escolhida é sincronizada —, porque têm dados de clientes. Para compartilhá-las com a equipe pela nuvem, escolha outra pasta.
- **Pasta deste computador:** as degravações ficam numa subpasta `Degravações` ao lado dos vídeos. A ferramenta lê só a pasta escolhida (não as subpastas) e avisa o que deixou de fora.
- **Os vídeos originais nunca são movidos nem alterados.**

A primeira degravação demora mais, porque baixa o modelo de transcrição (1,6 a 3 GB), uma única vez. `python degravar.py diagnostico` mostra a qualquer momento o que está pronto e o próximo passo.

## 2. No dia a dia, com o Claude

Peça em linguagem natural:

> Degrava os vídeos novos.
>
> Degrava esse vídeo: https://drive.google.com/file/d/…/view
>
> Degrava essa audiência separando os falantes: são 3 pessoas (juiz, advogada e testemunha). As partes são Maria Souza e Construtora Alfa.
>
> Estrutura a degravação audiencia-03-05
>
> Aplique a revisão da degravação audiencia-03-05
>
> Abre o vídeo da audiência no minuto 12

O Claude segue a skill [`degravar`](.claude/skills/degravar/SKILL.md): roda a transcrição em segundo plano, estrutura o documento (resumo, participantes, tópicos, pontos de atenção) e abre o player.

## 3. Revisão e marcações no player

- **Marcar:** selecione um trecho e escolha a cor — *Relevante*, *Favorável*, *Desfavorável*, *Contradição* ou *Conferir* — ou tecle `M` durante a reprodução. Na aba **Marcações**, acrescente notas e copie tudo como citações para a peça.
- **Revisar:** o botão **Revisar** deixa corrigir o texto de qualquer frase, trocar o falante de um parágrafo e dar nome aos falantes. Tudo fica guardado no navegador até você clicar em **Exportar revisão**.
- **Aplicar:** peça ao Claude **"aplique a revisão"** (ou `python degravar.py revisao <nome>`). O documento, o Word, as legendas e o player são refeitos com as correções e as marcações; o texto original do Whisper continua guardado para conferência, e uma cópia da versão anterior fica na pasta. O que você editar no player depois de exportar não se perde: ele continua guardado no navegador até a próxima exportação.
- **Corrigir uma frase pelo chat:** "corrija a frase do minuto 12:31: …" — o Claude usa `python degravar.py corrigir <nome> 00:12:31 "texto"`, que também guarda o original.

## 4. Uso direto pelo terminal

```bash
python degravar.py "https://drive.google.com/file/d/ID/view"     # arquivo do Drive
python degravar.py "https://drive.google.com/drive/folders/ID"   # pasta inteira do Drive
python degravar.py "C:\Gravações\audiencia.mp4"                  # arquivo local
python degravar.py "C:\Gravações"                                # todos os vídeos de uma pasta
python degravar.py                                               # o que houver de novo na pasta escolhida
python degravar.py --escolher                                    # abre a janela para escolher os arquivos
python degravar.py transcrever --monitorar                       # vigia a pasta continuamente
python degravar.py configurar --mostrar                          # mostra pastas e preferências
python degravar.py configurar --saida                            # escolhe outra pasta para as degravações

python degravar.py assistir                 # abre o player da última degravação
python degravar.py assistir audiencia --em 754
python degravar.py listar                   # todas as degravações e se já foram estruturadas
python degravar.py regerar <nome>           # refaz .md, Word, legendas e player a partir do transcricao.json
python degravar.py revisao <nome>           # aplica a revisão exportada pelo player
python degravar.py corrigir <nome> 00:12:31 "texto certo"   # corrige uma frase (minutagem, 751s, ou o índice de `falantes --listar`), guardando o original
python degravar.py diagnostico              # o que está pronto e o próximo passo
python degravar.py exemplo                  # testa com uma audiência fictícia
python degravar.py falantes <nome> --separar --num-falantes 3   # separa falantes de degravação já feita (descarta revisões; guarda cópia)
python degravar.py falantes <nome> --listar                     # frases com o falante atribuído
python degravar.py falantes <nome> --atribuir 12=F2 --nomear F1="Juiz(a)"
python degravar.py artefato <nome> --sem-video --sem-marcacoes  # página para artefato só com o texto
```

Os comandos aceitam o nome completo da degravação ou um trecho único dele; com mais de uma correspondência, listam as opções.

Opções úteis de `transcrever`:

| Opção | Para quê |
|---|---|
| `--modelo turbo` / `large-v3` | força um modelo (padrão automático: `large-v3` com placa NVIDIA que dá conta dele, `turbo` nos demais casos) |
| `--vocabulario "Fulano, Beltrana, Umuarama"` | melhora a grafia de nomes das partes e termos do caso |
| `--num-falantes 3` | separa quem fala, sabendo quantas pessoas são (mais confiável) |
| `--falantes` / `--sem-falantes` | separa quem fala sem informar quantas pessoas são / não separa (aula, uma pessoa só), mesmo que seja o padrão configurado |
| `--idioma ""` | detecta o idioma automaticamente (padrão: português) |
| `--refazer` | degrava de novo algo já processado (a versão anterior fica guardada em `transcricao-antes-refazer-<data>.json`) |
| `--copiar-video` | copia o arquivo local para a pasta de saída (pasta autocontida) |

### Google Drive

O link precisa estar compartilhado como **"Qualquer pessoa com o link"**. Para arquivos sigilosos que não devem ser compartilhados, instale o **Google Drive para computador** e informe o caminho da pasta sincronizada (ex.: `"G:\Meu Drive\Audiências"`) — funciona como pasta local.

### Formatos aceitos

- **Vídeo:** MP4, MOV (inclusive HEVC do iPhone), WebM, MKV, AVI, WMV/ASF, FLV, MPG/MPEG, VOB (DVD), TS/MTS/M2TS (filmadoras), 3GP, OGV, MXF, DV, RM/RMVB e DAV (gravadores de câmeras de segurança).
- **Áudio:** MP3, M4A, WAV, AIFF, CAF, OGG e Opus (WhatsApp), AMR, WMA, FLAC, AAC, AC3 e WebM/WEBA.

A ferramenta olha o **conteúdo** do arquivo, não só a extensão:

- o que o navegador já toca é usado como está;
- um vídeo H.264 em outro contêiner (MKV, FLV, MTS) só troca de contêiner, em segundos;
- o resto (HEVC do iPhone, WMV, AVI, MPEG-2, WebM só de áudio…) é convertido para `video.mp4` ou `audio.m4a` na pasta da degravação, usando a placa NVIDIA se houver. A cópia de vídeo fica com até 720 linhas e serve só para o player; **o original não é alterado**;
- um arquivo sem trilha de áudio é recusado com aviso e anotado para não ser tentado de novo (`--refazer` insiste).

Gravações do Webex (`.arf`, `.wrf`) e do Zoom ainda não convertidas (`.zoom`) estão em formato fechado e precisam ser exportadas para MP4 no próprio aplicativo; a ferramenta avisa quando encontra uma.

### Pasta dos vídeos

Depois de `configurar`, `python degravar.py` degrava o que houver de novo na pasta escolhida (sem entrar em subpastas), sem mexer nos originais. Trocar a pasta das degravações não refaz o que já foi degravado na anterior. Sem configuração (só na pasta do projeto), vale a pasta interna `entrada/`, que funciona como caixa de entrada: cada vídeo degravado é **movido** para `saida/`.

## 5. O que é gerado

Cada mídia gera uma pasta `<nome>/` dentro da pasta das degravações:

| Arquivo | Conteúdo |
|---|---|
| `<nome>.md` | ficha técnica, resumo/estrutura (preenchidos pelo Claude), índice por minutagem, trechos para conferência, marcações e **transcrição integral** com minutagem clicável |
| `<nome>.docx` | o mesmo documento em **Word**: A4, margens ABNT, páginas numeradas, trechos a conferir com sublinhado ondulado, falantes com as marcas `(?)` e `✎` |
| `player.html` | vídeo + legendas + transcrição sincronizada, resumo, marcações e ficha técnica; abre com dois cliques, sem internet (detalhes abaixo) |
| `transcricao.json` | fonte de verdade: frases, tempos, confiança por palavra, forma de onda, revisões (nunca edite à mão: use `corrigir`, `falantes` e `revisao`) |
| `<nome>.txt` | texto corrido, para colar em peças (com o nome de quem fala, se houver separação) |
| `<nome>.srt` / `.vtt` | legendas de até duas linhas (VLC, YouTube, editores de vídeo) |
| `video.mp4` / `audio.m4a` | só quando o original não toca no navegador: a cópia que o player usa |
| o vídeo | quando veio do Drive ou da pasta `entrada/` |

### O player

- **Legendas sobre o vídeo**, com o nome de quem fala, também em tela cheia (`C`), em três tamanhos. A **janela flutuante** (`P`) leva o vídeo com a legenda para um canto da tela enquanto você escreve a peça (Chrome e Edge).
- **Forma de onda** na linha do tempo, colorida por falante, com marcas de tópicos, pontos de atenção, marcações e trechos a conferir. Passe o mouse para ler o que foi dito ali; clique ou arraste para ir.
- **Transcrição** com a palavra dita sublinhada; dois cliques numa palavra levam ao instante exato. **Sumário** dos tópicos no alto, com o tópico atual destacado.
- **Citação e marcações:** selecione um trecho para copiar `“texto” (Falante, 00:12:31–00:12:48)` ou marcá-lo por categoria (seção 3).
- **Conferência:** *Próximo a conferir* (`N`), *Repetir frase* (`R`), filtros por falante, *A conferir* e *Marcados*, palavras duvidosas com sublinhado ondulado.
- **Busca** que ignora acentos, com anterior/próxima (`Enter` / `Shift+Enter`) e marcas na linha do tempo.
- **Preferências:** tema claro ou escuro, tamanho do texto, layouts (lado a lado, vídeo grande, só texto), pular silêncios longos, voltar 2 s ao retomar. O player lembra onde você parou.
- **Exportar:** Word, PDF (pela impressão), texto, legendas, e copiar a transcrição ou as marcações. Atalhos: tecla `?`.

## 6. Precisão

| Modelo | Precisão | Velocidade | Download |
|---|---|---|---|
| `large-v3` (padrão com placa NVIDIA que dá conta: float16 e 6 GB ou mais) | máxima | lenta em CPU | ~3 GB |
| `turbo` (padrão sem placa, ou com placa menor) | muito próxima | várias vezes mais rápida | ~1,6 GB |
| `medium` / `small` | menor | rápidas | 1,5 GB / 0,5 GB |

Com placa de vídeo NVIDIA (CUDA), a transcrição é muitas vezes mais rápida; sem ela, roda em CPU automaticamente. No Windows e no Linux, `python degravar.py instalar` (ou o primeiro `Degravar.bat`) detecta a placa e instala as bibliotecas CUDA sozinho (~2 GB, uma vez; `--sem-gpu` pula). Placas pequenas ou antigas (menos de 6 GB, sem float16) ficam com o `turbo`, que também roda na placa. Referências:

- numa máquina de 4 núcleos sem placa de vídeo, o `large-v3` levou cerca de 2x a duração da gravação (9 min de audiência em ~18 min);
- com `turbo`, 11,4 min de áudio levaram 12 s numa GeForce RTX 5050 (8 GB) e 93 s na CPU da mesma máquina.

Para melhorar o resultado:

- Informe nomes próprios com `--vocabulario` e mantenha termos recorrentes em [`config/vocabulario.txt`](config/vocabulario.txt).
- Trechos com baixa confiança aparecem com ⚠️ no `.md` e com sublinhado ondulado no player — confira-os na mídia.
- Corrija erros no próprio player (**Revisar**) e peça ao Claude para aplicar a revisão.

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

O player local abre no navegador do computador. Para assistir **dentro do Claude** ou mandar o link a alguém, peça ao Claude: **"publica a degravação X como artefato"**. Ele publica no claude.ai a mesma página do player (legendas, forma de onda, filtros, citação, marcações, resumo e ficha técnica). Ficam de fora a impressão, a revisão e os arquivos para baixar, que o artefato não permite; marcações feitas na página publicada ficam só no navegador de quem as fez.

- O artefato aceita arquivos de até 15 MB, então a mídia é recomprimida (sem os metadados do original, como a localização do celular): vídeos curtos saem com imagem (até cerca de 10 minutos), gravações mais longas só com o áudio e, no limite, só com a transcrição — a página diz o motivo.
- **Atenção à privacidade:** o artefato é privado por padrão (só você abre até compartilhar pelo menu da página), mas a mídia, o texto, a estrutura e as **marcações com suas notas** saem do seu computador e vão para o claude.ai. Use para aulas e conteúdo público; para audiências e reuniões com clientes, prefira o player local ou publique só a transcrição: `--sem-video` não envia mídia nenhuma (nem o áudio) e `--sem-marcacoes` deixa as marcações de fora. O link do Drive de origem nunca entra na página.
- Pelo terminal: `python degravar.py artefato <nome> --titulo "Título"` prepara a página e a mídia; a publicação é feita pelo Claude. Ao republicar sem a mídia, o Claude remove a anterior do artefato.

## 9. Limitações — leia antes de usar em processo

- **Transcrição automática é apoio, não prova.** Para citação em peça ou juntada aos autos, confira os trechos na mídia original.
- **Falantes são atribuição aproximada**, mesmo depois da revisão do Claude, que não ouve o áudio: confira as marcas (?) e ✎ antes de atribuir uma fala a alguém em peça.
- Música de fundo, vozes sobrepostas e áudio de baixa qualidade reduzem a precisão.

## 10. Privacidade (LGPD)

- O vídeo e o áudio são processados **somente no seu computador** — transcrição e separação de falantes. Só saem dele se você pedir um artefato com mídia (seção 8).
- Quando você pede ao Claude para estruturar, revisar falantes ou corrigir, o **texto** da degravação é lido pelo Claude — ou seja, vai para a sua conta do Claude, nas condições dela. Se preferir que nem o texto saia, use a ferramenta só pelos atalhos de dois cliques ou pelo terminal.
- Com os vídeos numa pasta da nuvem, as degravações ficam por padrão numa pasta só deste computador (fora do OneDrive/iCloud, mesmo que a sua pasta Documentos esteja neles): só sobem para a nuvem se você escolher. `diagnostico` e `configurar` dizem se a pasta das degravações é sincronizada.
- `entrada/` e `saida/` estão no `.gitignore`: suas gravações nunca vão para o GitHub, mesmo que você faça um fork.

## 11. Problemas comuns

| Sintoma | Solução |
|---|---|
| Não sei o que falta | `python degravar.py diagnostico` (ou peça ao Claude "quero começar") |
| `Dependências ausentes` ou instalação interrompida | dê dois cliques em `Degravar` ou rode `python degravar.py instalar` (recomeça do zero sozinho) |
| `Command 'git' not found` ao adicionar o marketplace | instale o [Git for Windows](https://git-scm.com/download/win), ou use o arquivo `.plugin` / o ZIP (seção 1) |
| "caminho longo demais para o Windows" | mova a pasta da ferramenta para mais perto da raiz (ex.: `C:\Degravacao`) |
| "A pasta dos vídeos não está acessível" | abra o Google Drive/OneDrive ou conecte o HD externo; ou `configurar --entrada` para outra pasta |
| Janela de escolha da pasta não abriu | rode `python degravar.py configurar --entrada "CAMINHO DA PASTA"` |
| Falha no link do Drive | compartilhe como "Qualquer pessoa com o link" ou use a pasta do Google Drive para computador |
| Player não toca o vídeo | o vídeo foi movido: selecione o arquivo no aviso do próprio player. No Windows, caminhos com mais de 260 caracteres não abrem: escolha uma pasta de degravações mais curta (`configurar --saida`) e rode `regerar`. Degravações feitas antes da conversão automática de formatos: rode de novo com `--refazer` |
| "não tem trilha de áudio" | o arquivo é só imagem (ex.: gravação de tela sem som); não há fala para degravar, e ele não será tentado de novo |
| Placa NVIDIA não usada ("driver antigo") | atualize o driver da NVIDIA (nvidia.com/drivers); reinstalar não resolve |
| Windows com Snapdragon (ARM64) | instale pelo uv (seção 1, caminho C): as bibliotecas só existem para x64 |
| "revisão exportada de outra versão" | a degravação foi refeita depois da exportação: refaça a revisão no player novo (ou `revisao --forcar`, por sua conta) |
| Muito lento | use `--modelo turbo`; feche outros programas pesados |
| Nomes escritos errado | `--vocabulario "Nome Completo, Outro Nome"` |
| Falantes trocados | peça ao Claude a revisão de falantes; corrija com `falantes --atribuir`. Separar de novo (`--separar`/`--num-falantes`) descarta a revisão feita (fica uma cópia) |
