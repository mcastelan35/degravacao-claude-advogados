---
name: degravar
description: Degrava (transcreve integralmente) vídeos e áudios — audiências, reuniões, depoimentos, aulas, áudios de WhatsApp — a partir de link do Google Drive, arquivo ou pasta local (inclusive pastas sincronizadas com a nuvem), entregando documento .md e Word estruturados e um player com legendas e transcrição sincronizada. Use SEMPRE que o usuário pedir para degravar, transcrever, "passar para texto", fazer ata ou resumo de vídeo/áudio, colar um link do Drive com vídeo, mencionar a pasta dos vídeos, pedir para estruturar uma degravação, aplicar a revisão feita no player, corrigir trechos transcritos ou assistir a um vídeo já degravado.
allowed-tools:
  - Bash(uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin *)
  - PowerShell(uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin *)
  - Bash(~/.local/bin/uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin *)
  - PowerShell(& "$env:USERPROFILE\.local\bin\uv.exe" run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin *)
---
<!-- Gerado por ferramentas/empacotar_plugin.py a partir de .claude/skills: não edite aqui. -->

# Degravação de vídeos e áudios

A transcrição roda **localmente** (Whisper via `degravar.py`). O seu papel, Claude, é operar a ferramenta e depois **estruturar** o resultado com rigor — sem inventar nada e sem alterar a transcrição integral.

**Comando base** (`<cmd>` neste texto): `uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin`.
Ele exige o **uv** (astral.sh): sem o uv, nenhum comando roda, mesmo que já exista Python no computador — instale-o primeiro (skill `comecar`, passo 2). Logo depois de instalar o uv, ele ainda não está no PATH desta sessão: use o caminho completo — Windows (PowerShell): `& "$env:USERPROFILE\.local\bin\uv.exe" run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin …`; Mac/Linux: `~/.local/bin/uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin …` — ou peça ao usuário para reiniciar o Claude Code. Se o Claude Code pedir permissão para esses comandos, explique que são a mesma ferramenta e sugira "Sim, e não perguntar de novo".
O código fica no plugin; ambiente, preferências e modelos ficam numa pasta do usuário (`%LOCALAPPDATA%\Degravacao` no Windows, `~/Library/Application Support/Degravacao` no Mac) e as degravações, por padrão, numa pasta só deste computador (Documentos/Degravações, ou a pasta do usuário quando Documentos está no OneDrive/iCloud — a ferramenta diz qual). Os comandos rodam em qualquer pasta. Não existe o atalho de dois cliques nem `python degravar.py` no plugin: quando uma mensagem citar um comando, rode-o com `<cmd>`.

## 1. Primeiro uso e problemas

Se for o primeiro uso neste computador, se o usuário pedir para instalar ou configurar, ou se um comando falhar por falta de ambiente, siga a skill **`comecar`** (diagnóstico → instalar → pastas → teste). `<cmd> diagnostico` mostra a qualquer momento o que está pronto e o próximo passo.

- Pastas: `configurar --mostrar` exibe as atuais; `configurar --entrada` ou `--saida` (sem caminho, abre a janela; rode em segundo plano) troca uma delas. Os originais nunca são movidos. Trocar a pasta das degravações não refaz o que já foi degravado na anterior.
- Se a saída disser que a pasta dos vídeos "não está acessível", o Google Drive/OneDrive não está aberto ou o HD externo está desconectado: diga isso ao usuário antes de qualquer outra coisa.
- Não é preciso ativar ambiente nenhum: `degravar.py` se reexecuta sozinho no ambiente certo.
- Os comandos que recebem o nome de uma degravação aceitam o nome completo ou um trecho único dele e imprimem `Degravação: <slug>` — confira que é a certa. Com mais de uma correspondência, a ferramenta lista as opções em vez de escolher.

## 2. Identificar a entrada

| O usuário forneceu | Comando |
|---|---|
| Link do Google Drive (arquivo ou pasta) | `<cmd> "<link>"` |
| Caminho de arquivo ou de pasta | `<cmd> "<caminho>"` |
| "Os vídeos da pasta", "os novos" | `<cmd> --abrir` (degrava o que houver de novo na pasta configurada) |
| Nada / "quero escolher o vídeo" / arquivo fora da pasta | `<cmd> --escolher --abrir` (abre a janela do sistema para escolher um ou mais arquivos) |
| "Fique vigiando a pasta" | `<cmd> transcrever --monitorar` |

Formatos: praticamente qualquer vídeo ou áudio (MP4, MOV/HEVC do iPhone, WebM, MKV, AVI, WMV, MTS, VOB, 3GP, Opus/OGG do WhatsApp, AMR, WMA…). A ferramenta examina o conteúdo e, se o navegador não tocar o arquivo, gera uma cópia `video.mp4` ou `audio.m4a` na pasta da degravação, só para o player; o original nunca é alterado. Se a saída disser que um arquivo "não tem trilha de áudio", explique que não há fala para degravar; a ferramenta o anota e não tenta de novo (`--refazer` insiste). Para `.arf`/`.wrf` (Webex) e `.zoom`, repasse a instrução de exportar para MP4 no próprio aplicativo. A varredura de uma pasta não entra em subpastas e ignora arquivos que não parecem mídia — a saída avisa o que ficou de fora.

Pastas na nuvem (Google Drive para computador, OneDrive, Dropbox) funcionam como pastas locais. É o melhor caminho para arquivos sigilosos: links públicos do Drive (`"Qualquer pessoa com o link"`) só para material sem dado de cliente. Se um link falhar, explique as duas saídas que a própria mensagem de erro traz.

Se o usuário arrastar um arquivo para o chat, use o caminho que aparecer. Sempre use aspas no caminho/link. Antes de rodar, **pergunte uma única vez**, com a ferramenta `AskUserQuestion` quando ela existir na sessão (botões clicáveis; o usuário pode digitar em "Outro"), e sem bloquear se o usuário não souber:

- em audiências, reuniões e depoimentos: quantas pessoas falam (opções: 2, 3, 4 ou mais, Não sei) → `--num-falantes N` (separa quem fala; com "Não sei", use `--falantes`; em aula ou áudio de uma pessoa só, não separe — `--sem-falantes` vence a preferência configurada);
- se há nomes próprios relevantes — partes, testemunhas, empresas, cidades (opção "Nenhum"; os nomes vêm digitados em "Outro") → `--vocabulario "Nome 1, Nome 2"` (melhora muito a grafia).

Modelo: automático — `large-v3` (máxima precisão) quando há placa NVIDIA que dá conta dele (CUDA pronto, float16 e 6 GB ou mais); `turbo` (bem mais rápido, precisão um pouco menor) nos demais casos, inclusive em placas menores e no processador. Sem placa, gravações longas podem levar tempo da ordem da duração da gravação; não prometa tempos exatos. O usuário pode fixar outro com `configurar --modelo large-v3` ou `--modelo` num comando. Se a saída avisar "placa NVIDIA encontrada, mas faltam as bibliotecas CUDA", rode `<cmd> instalar` de novo (em segundo plano); se o diagnóstico falar em driver antigo, a solução é atualizar o driver da NVIDIA, não reinstalar.

## 3. Rodar a transcrição

Rode o comando **em segundo plano** (transcrições longas passam de 10 minutos; com `--escolher`, a janela também espera o usuário). Fora do terminal, o progresso sai em uma linha a cada 10% (`▶ 40% · decorrido 6 min · restante ~9 min`): não leia a saída repetidamente, espere o aviso de conclusão e, se o usuário perguntar, leia só as últimas linhas. Ao final, a ferramenta informa a pasta da degravação com:

- `<slug>.md` — documento estruturado (ficha técnica, índice, trechos para conferência, transcrição integral com minutagem clicável)
- `<slug>.docx` — o mesmo documento em Word (A4, margens ABNT, páginas numeradas; falantes com as marcas `(?)` e `✎`), pronto para anexar
- `player.html` — vídeo + legendas + transcrição sincronizada (ver passo 7)
- `transcricao.json` — fonte de verdade (frases, tempos, confiança por palavra, forma de onda, revisões)
- `<slug>.txt`, `.srt`, `.vtt` — texto corrido e legendas
- `video.mp4` ou `audio.m4a` — só quando o original não toca no navegador: a cópia que o player usa

Com `--refazer`, a versão anterior fica guardada em `transcricao-antes-refazer-<data>.json` e a ferramenta diz o que ela tinha (nomes, correções, marcações) e que a nova transcrição não traz.

## 4. Estruturar o documento

Leia o `.md` gerado (em gravações longas, leia a transcrição integral bloco a bloco — nunca resuma a partir de uma leitura parcial). Substitua **apenas** o conteúdo entre `<!-- CLAUDE:ESTRUTURA:INICIO -->` e `<!-- CLAUDE:ESTRUTURA:FIM -->` (mantenha os dois marcadores) por:

```markdown
## Resumo executivo
Texto corrido, objetivo, 1 a 3 parágrafos: do que se trata, quem participa, o que foi decidido/dito de relevante.

## Participantes
| Falante | Papel provável | Base da inferência |
|---|---|---|
| F1 — Juiz(a) | Conduz a audiência | Abre a audiência e concede a palavra (00:00:02) |

## Estrutura de tópicos
- [[00:00:00]](player.html#t=0) **Abertura** — breve descrição
- [[00:04:10]](player.html#t=250) **Depoimento do reclamante** — …

## Pontos de atenção
- [[00:12:31]](player.html#t=751) Fatos, datas, valores, prazos concedidos, confissões, contradições, compromissos assumidos — cada item com minutagem.

## Notas de revisão
- [[00:00:15]](player.html#t=15) "2020 e 4" — provável "2024"; conferir na mídia.
```

Regras inegociáveis:

1. **Nunca altere a seção "Transcrição integral"** ao estruturar. Ela é a degravação literal.
2. **Nada sem lastro.** Todo ponto de atenção e todo tópico tem minutagem real retirada da transcrição. Se algo não foi dito, não entra.
3. **Inferência declarada.** Papéis e nomes dos falantes são inferidos (pela voz e pelo contexto): diga isso e mostre a base. Se não der para inferir, use "Falante não identificado".
4. **Possíveis erros de transcrição vão para "Notas de revisão"**, nunca corrigidos silenciosamente. Considere especialmente os trechos marcados com ⚠️.
5. O link de minutagem segue o formato `[[HH:MM:SS]](player.html#t=SEGUNDOS)`, com segundos inteiros.
6. Se o documento tiver a seção **"Marcações"** (feitas pelo usuário no player), elas indicam o que ele considera relevante: leve-as em conta nos pontos de atenção, sem mudar a categoria que o usuário deu.

Ao terminar, rode `<cmd> regerar <slug>`: o player passa a mostrar a aba "Resumo", a linha do tempo ganha os tópicos (com o sumário clicável) e os pontos de atenção, e o Word é refeito com a estrutura. A saída diz se a seção estruturada foi preservada; se avisar que os marcadores sumiram, reponha-os e estruture de novo.

## 5. Revisão e correções (só quando o usuário pedir)

A fonte de verdade é `transcricao.json`, mas nunca o edite à mão: use os comandos. Há dois caminhos:

**a) Revisão feita pelo usuário no player** (o mais comum). No player, o botão **Revisar** deixa corrigir o texto das frases, trocar o falante de um parágrafo e dar nome aos falantes; as **Marcações** guardam os trechos importantes com categoria e nota. "Exportar revisão" salva `revisao-<slug>.json` em Downloads. Quando o usuário pedir para aplicar a revisão:

1. Rode `<cmd> revisao <slug>` (acha o arquivo mais recente em Downloads; ou passe o caminho como segundo argumento).
2. A ferramenta aplica as correções só onde a frase ainda é a original (avisa os conflitos), guarda o texto original do Whisper, troca falantes, aplica nomes e marcações, lista o que ignorou e regera `.md`, Word, legendas e player, preservando a seção estruturada. Antes, guarda uma cópia `transcricao-antes-revisao-<data>.json`.
3. Se ela recusar o arquivo por ser "de outra versão desta transcrição" (a degravação foi refeita depois da exportação), explique que falantes e marcações cairiam em frases erradas: o usuário deve refazer a revisão no player novo e exportar de novo; `--forcar` só se ele insistir.
4. Relate o resumo que a ferramenta imprimiu e acrescente em "Notas de revisão" uma linha com o que foi corrigido pelo usuário (minutagens), sem reescrever o resto.

**b) Correção pontual pedida no chat.** Para um trecho que o usuário conferiu na mídia: `<cmd> corrigir <slug> <frase> "texto corrigido"`, em que `<frase>` é o índice mostrado por `falantes --listar` ou uma minutagem (`00:12:31` ou segundos). O comando guarda o texto original do Whisper, marca a frase como corrigida (o player e o Word mostram isso) e regera tudo. Registre a correção em "Notas de revisão".

Nunca edite a transcrição integral direto no `.md`: seria sobrescrita no próximo `regerar` e ficaria divergente do player.

## 6. Falantes (separação pela voz + revisão do Claude)

A separação automática (`--falantes` / `--num-falantes N`) roda localmente, sem conta nem chave, e rotula cada frase como F1, F2… Ela é **aproximada**. No teste de referência (audiência por videoconferência, 9 min, áudio comprimido) acertou cerca de 78% das frases: 86% das não marcadas e só metade das marcadas com **(?)** (frases curtas, trocas rápidas). Em sequências rápidas de pergunta e resposta, a acústica pode colar vários turnos num só falante, e vozes de quem fala pouco (ex.: juiz) podem se fundir com outra.

Para degravação já existente sem falantes: `<cmd> falantes <slug> --separar [--num-falantes N]`. Atenção: `--separar` (ou `--num-falantes` sozinho) refaz a separação do zero e descarta nomes e atribuições corrigidas — a ferramenta guarda uma cópia e avisa. Numa degravação já revisada, prefira `--atribuir`.

**Depois de separar, faça sempre a revisão** (antes de estruturar):

1. `<cmd> falantes <slug> --listar` — mostra cada frase com índice, minutagem, falante e marcas (`?` a conferir, `✎` revista).
2. Leia **todas** as frases e identifique os papéis (quem conduz, quem pergunta, quem responde).
3. Corrija **apenas** atribuições que o sentido torna inequívocas: pergunta atribuída a quem está respondendo, resposta atribuída a quem pergunta, sequência de turnos colada num só falante. Use `--atribuir 108=F1 --atribuir 110-111=F1` (vários na mesma chamada). Para uma pessoa que a acústica fundiu com outra (ex.: juiz), crie um rótulo novo: `--atribuir 0=F3`.
4. Na dúvida, **não corrija**: o "(?)" fica para o usuário conferir ouvindo no player.
5. Nomeie: `--nomear F1="Juiz(a)" --nomear F2="Preposto — Fulano"`. Use nomes só quando ditos na gravação ou informados pelo usuário; senão, o papel.
6. Na estruturação (passo 4), "Participantes" usa esses rótulos, e "Notas de revisão" informa quantas atribuições foram revistas pelo sentido e quais trechos seguem incertos.

A separação acústica original fica guardada em `falante_acustico` no `transcricao.json`; as frases revistas aparecem com ✎ no `.md`, no Word e no player, e o `.txt`, o Word e as legendas já saem com o nome de quem fala (formato de ata), com `(?)` nas atribuições a conferir.

## 7. Reproduzir

Ofereça abrir o player no navegador: `<cmd> assistir <slug>` (ou `--em <segundos>` para abrir num ponto específico). Recursos que vale mencionar ao usuário, conforme a necessidade:

- **legendas sobre o vídeo**, com o nome de quem fala, também em tela cheia (C); **janela flutuante** (P) que leva vídeo e legenda para assistir enquanto escreve a peça;
- **forma de onda** colorida por falante na linha do tempo, com tópicos, pontos de atenção, marcações e trechos a conferir; passar o mouse mostra o que foi dito ali;
- transcrição com **destaque palavra a palavra**; dois cliques numa palavra levam ao instante exato; **sumário** de tópicos clicável;
- **selecionar um trecho** permite copiá-lo como citação — `“texto” (Falante, 00:12:31–00:12:48)` — ou **marcá-lo** (Relevante, Favorável, Desfavorável, Contradição, Conferir), com nota; a aba **Marcações** reúne tudo e copia de uma vez;
- filtros por falante, "A conferir" e "Marcados"; busca sem acento com anterior/próxima; "Próximo a conferir" (N), "Repetir frase" (R), "Pular silêncios longos" e "Voltar 2 s ao retomar" nas preferências;
- **Revisar** (passo 5a), Exportar (Word, PDF pela impressão, texto, legendas), tema claro/escuro, tamanho do texto, layouts e atalhos (tecla ?). O player lembra onde o usuário parou e guarda no navegador o que ainda não foi exportado.

Se o vídeo foi movido, o próprio player permite selecionar o arquivo. `<cmd> listar` mostra todas as degravações e se já foram estruturadas.

## 8. Ver dentro do Claude: publicar como artefato (opcional)

Use quando o usuário quiser assistir dentro do Claude ou compartilhar a degravação por link, e a ferramenta de artefatos estiver disponível na sessão.

1. **Privacidade antes de tudo.** Publicar envia ao claude.ai a transcrição, a estrutura, as marcações e notas feitas no player (`--sem-marcacoes` as deixa de fora) e, salvo `--sem-video`, a gravação (vídeo recomprimido, ou só o áudio quando o vídeo não cabe). `--sem-video` publica só o texto: nenhuma mídia, nem o áudio, sai do computador. O artefato é privado por padrão (só o dono abre até compartilhar), mas sai do computador. Antes de publicar, diga isso ao usuário. Se a gravação envolver cliente, audiência, processo ou dado pessoal, só publique com confirmação expressa e ofereça a alternativa `--sem-video` ou manter tudo local.
2. Estruture a degravação antes (passo 4): a aba "Resumo" da página vem dessa seção do `.md`.
3. Rode `<cmd> artefato <slug> --titulo "<título legível>"` (com `--sem-video` e/ou `--sem-marcacoes` conforme o combinado). A página é a mesma do player local, sem impressão, sem revisão e sem arquivos para baixar, que o artefato não permite. Ele grava `<pasta da degravação>/artefato/index.html` e, se houver mídia, `artefato/midia/midia.*` (até 15 MB: vídeo; se não couber, só o áudio; acima disso, só a transcrição — a página diz o motivo) e imprime os caminhos.
4. Publique com a ferramenta de artefatos: `file_path` = o `index.html` impresso; `files` = `{"midia/<nome do arquivo>": "<caminho da mídia impresso>"}` (omita quando não houver mídia); `icon` = `"video"`; `description` = uma frase sobre a gravação. Para atualizar uma publicação feita antes, passe o `url` dela e, se a nova versão não leva a mídia (ou leva outra), liste os arquivos do artefato e passe `"midia/<arquivo antigo>": null` para remover a anterior — senão ela continua hospedada.
5. Entregue o link dizendo que é privado e que, para outra pessoa abrir, é preciso compartilhar pelo menu da página.

## Lembretes ao usuário

- A transcrição automática é ferramenta de apoio: para uso em peça ou juntada aos autos, os trechos citados devem ser conferidos na mídia original.
- Vídeo e áudio ficam no computador do usuário (ou na pasta da nuvem que ele escolheu) e só saem dali se ele pedir um artefato com mídia (passo 8). O **texto** da degravação é lido por você, Claude, quando ele pede estruturação, revisão de falantes ou correções — ou seja, vai para a conta do Claude dele, nas condições dessa conta; se perguntarem, diga isso com clareza. As degravações podem conter dados pessoais (LGPD).
