---
name: comecar
description: Primeiros passos da degravação — instala tudo (mesmo sem Python no computador), escolhe a pasta dos vídeos (local ou na nuvem, como Google Drive e OneDrive), testa com uma audiência fictícia e mostra o player. Use quando o usuário estiver começando ou disser "quero começar", "instala", "configura", "primeiro uso", "como uso isso", "não está funcionando", quando o diagnóstico acusar pendências, ou antes da primeira degravação neste computador.
allowed-tools:
  - Bash(uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin *)
  - PowerShell(uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin *)
  - Bash(~/.local/bin/uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin *)
  - PowerShell(& "$env:USERPROFILE\.local\bin\uv.exe" run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin *)
---
<!-- Gerado por ferramentas/empacotar_plugin.py a partir de .claude/skills: não edite aqui. -->

# Primeiros passos

Objetivo: numa conversa só, o advogado sai com a ferramenta instalada, as pastas escolhidas e uma degravação de teste aberta no navegador. Fale em linguagem simples, sem jargão técnico, e uma etapa por vez. Faça as perguntas com a ferramenta `AskUserQuestion` (botões clicáveis), quando ela existir na sessão.

**Comando base** (`<cmd>` neste texto): `uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin`.
Ele exige o **uv** (astral.sh): sem o uv, nenhum comando roda, mesmo que já exista Python no computador — instale-o primeiro (skill `comecar`, passo 2). Logo depois de instalar o uv, ele ainda não está no PATH desta sessão: use o caminho completo — Windows (PowerShell): `& "$env:USERPROFILE\.local\bin\uv.exe" run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin …`; Mac/Linux: `~/.local/bin/uv run --no-project --python 3.12 "${CLAUDE_PLUGIN_ROOT}/degravar.py" --plugin …` — ou peça ao usuário para reiniciar o Claude Code. Se o Claude Code pedir permissão para esses comandos, explique que são a mesma ferramenta e sugira "Sim, e não perguntar de novo".
O código fica no plugin; ambiente, preferências e modelos ficam numa pasta do usuário (`%LOCALAPPDATA%\Degravacao` no Windows, `~/Library/Application Support/Degravacao` no Mac) e as degravações, por padrão, numa pasta só deste computador (Documentos/Degravações, ou a pasta do usuário quando Documentos está no OneDrive/iCloud — a ferramenta diz qual). Os comandos rodam em qualquer pasta. Não existe o atalho de dois cliques nem `python degravar.py` no plugin: quando uma mensagem citar um comando, rode-o com `<cmd>`.

## 1. Diagnóstico

Rode `<cmd> diagnostico`. É rápido. Resuma em duas ou três linhas o que já está pronto e o que falta, e siga só os passos do que faltar. Se estiver tudo pronto, vá direto ao passo 4.
No plugin, o comando exige o uv: se a resposta for "uv não é reconhecido" (ou "command not found"), faça primeiro o passo 2 e repita o diagnóstico.

## 2. Instalar (se o diagnóstico pedir)

- Avise antes que leva alguns minutos e baixa, uma vez só:
  - ~300 MB de programas;
  - mais ~2 GB se houver placa NVIDIA, o que deixa a transcrição muitas vezes mais rápida;
  - o modelo de transcrição (1,6 a 3 GB) na primeira degravação.
  Depois disso, as gravações só saem do computador se o usuário pedir um artefato com mídia (o texto da degravação é lido por você, Claude, quando ele pede estruturação ou revisão).
- Se faltar o **uv** — no plugin, sempre que o comando base não rodar; no repositório, quando não houver Python 3.11–3.14 —, proponha instalá-lo: ele traz o Python certo sem pedir administrador. Explique que é o instalador oficial (astral.sh) e só rode depois da confirmação:
  - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  Na mesma conversa o uv ainda não está no PATH: chame-o pelo caminho completo — Windows (PowerShell): `& "$env:USERPROFILE\.local\bin\uv.exe" run --no-project --python 3.12 …`; Mac: `~/.local/bin/uv run --no-project --python 3.12 …` — ou peça ao usuário para reiniciar o Claude Code. Se o Claude Code pedir permissão para esses comandos, diga que é a mesma ferramenta e sugira "Sim, e não perguntar de novo".
  - Windows com processador Snapdragon (ARM64): só o uv serve; ele instala um Python x64, que roda emulado.
- Rode `<cmd> instalar` **em segundo plano** e espere o aviso de conclusão, sem ler a saída repetidamente. Se a instalação for interrompida (rede, janela fechada), basta rodar `instalar` de novo: ela recomeça do zero sozinha.

## 3. Escolher as pastas

Pergunte, com botões, onde ficarão os vídeos. As opções são:
- as pastas de nuvem que o diagnóstico listou (ex.: "Google Drive (G:\)", "OneDrive");
- "Uma pasta deste computador";
- "Ainda não sei".

- **Pasta na nuvem:**
  1. Explique em uma frase que os vídeos enviados pelo celular ou pelo navegador aparecem ali sozinhos. Se o Drive estiver no modo "só na nuvem", a primeira leitura de cada vídeo o baixa.
  2. Sugira uma subpasta própria (ex.: `Audiências`) e crie-a se o usuário concordar. A ferramenta lê só a pasta escolhida, não as subpastas dela (e avisa quando há vídeos em subpastas).
  3. Rode `<cmd> configurar --entrada "CAMINHO"`.
  4. A ferramenta imprime onde as degravações vão ficar e se a pasta é "só neste computador" ou sincronizada. Com vídeos na nuvem, o padrão é uma pasta **local** (Documentos/Degravações, ou a pasta do usuário quando Documentos está no OneDrive/iCloud), porque as degravações têm dados de clientes. Diga isso ao usuário e pergunte se prefere outra pasta, por exemplo para compartilhar com a equipe. Se sim, use `configurar --saida "CAMINHO"`, ou `configurar --saida` em segundo plano para abrir a janela.
- **Pasta deste computador:** rode `<cmd> configurar` em segundo plano. Abrem as janelas do sistema, que podem ficar atrás de outras; no Windows, procure na barra de tarefas.
- **Ainda não sei:** pule. Dá para escolher depois, e arquivos avulsos podem ser degravados com `<cmd> --escolher`.

Se a pasta das degravações ficar fora da pasta em que o Claude Code está aberto, avise que o usuário pode digitar `/add-dir "<pasta das degravações>"` uma vez: assim o Claude lê os documentos sem pedir permissão a cada vez.

## 4. Testar

Pergunte: "Quer ver funcionando agora, com uma audiência fictícia de 40 segundos?"
- Se sim, rode `<cmd> exemplo` em segundo plano. Ele grava o áudio com a voz do computador, degrava e abre o player no navegador. Na primeira vez, também baixa o modelo turbo de transcrição (1,6 GB).
- Se o usuário preferir, teste com um vídeo curto dele: `<cmd> --escolher --abrir`.

Com o player aberto, mostre três coisas:
1. Clicar numa frase leva àquele momento da gravação.
2. Selecionar um trecho permite copiá-lo como citação com minutagem ou marcá-lo (relevante, favorável, contradição…).
3. As legendas aparecem no vídeo, também em tela cheia, e a janela flutuante deixa assistir enquanto escreve a peça.

## 5. Fechar

Explique o dia a dia em três linhas:
- coloque os vídeos na pasta e diga **"degrava os vídeos novos"**, ou arraste um arquivo para o chat;
- **"estrutura a degravação"** gera resumo, participantes, tópicos e pontos de atenção;
- no player, **Revisar** corrige o texto e os falantes, e **Exportar revisão** salva o arquivo; depois, peça **"aplique a revisão"**. Uma frase isolada também se corrige pelo chat ("corrija a frase do minuto 12: …").

Daí em diante, siga a skill `degravar`.
