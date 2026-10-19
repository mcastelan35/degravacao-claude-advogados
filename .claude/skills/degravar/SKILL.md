---
name: degravar
description: Degrava (transcreve integralmente) vídeos e áudios — audiências, reuniões, depoimentos, aulas, áudios de WhatsApp — a partir de link do Google Drive, arquivo ou pasta local, entregando documento .md estruturado e player com transcrição sincronizada. Use SEMPRE que o usuário pedir para degravar, transcrever, "passar para texto", fazer ata ou resumo de vídeo/áudio, colar um link do Drive com vídeo, mencionar a pasta entrada/, pedir para estruturar uma degravação existente, corrigir trechos transcritos ou assistir/reproduzir um vídeo já degravado.
---

# Degravação de vídeos e áudios

A transcrição roda **localmente** (Whisper via `degravar.py`). O seu papel, Claude, é operar a ferramenta e depois **estruturar** o resultado com rigor — sem inventar nada e sem alterar a transcrição integral.

## 1. Preparar o ambiente (só na primeira vez)

- Se não existir a pasta `.venv/` na raiz do repositório, rode `python degravar.py instalar` (no Windows, se `python` não existir, use `py`). Demora alguns minutos.
- Não é preciso ativar a venv: `degravar.py` se reexecuta sozinho com o Python da `.venv`.

## 2. Identificar a entrada

| O usuário forneceu | Comando |
|---|---|
| Link do Google Drive (arquivo ou pasta) | `python degravar.py "<link>"` |
| Caminho de arquivo ou de pasta | `python degravar.py "<caminho>"` |
| Nada / "os vídeos da pasta" | `python degravar.py` (processa `entrada/`) |
| "Fique vigiando a pasta" | `python degravar.py transcrever --monitorar` |

Sempre use aspas no caminho/link. Antes de rodar, **pergunte uma única vez** (sem bloquear se o usuário não souber) se há nomes próprios relevantes — partes, testemunhas, empresas, cidades — e passe-os em `--vocabulario "Nome 1, Nome 2"`. Isso melhora muito a grafia de nomes.

Modelo: o padrão é `large-v3` (mais preciso). Para gravações longas em computador sem placa de vídeo NVIDIA, avise que o processamento pode levar tempo da ordem da duração da gravação (depende da máquina) e ofereça `--modelo turbo` (bem mais rápido, precisão ligeiramente menor). Não prometa tempos exatos.

Se o link do Drive falhar, explique as duas saídas que a própria mensagem de erro traz: compartilhar como "Qualquer pessoa com o link" ou usar a pasta sincronizada do Google Drive para computador.

## 3. Rodar a transcrição

Rode o comando **em segundo plano** (transcrições longas passam de 10 minutos) e acompanhe a saída. Ao final, a ferramenta informa a pasta `saida/<slug>/` com:

- `<slug>.md` — documento estruturado (ficha técnica, índice, trechos para conferência, transcrição integral com minutagem clicável)
- `player.html` — vídeo + transcrição sincronizada
- `transcricao.json` — fonte de verdade (segmentos, tempos, confiança por palavra)
- `<slug>.txt`, `.srt`, `.vtt` — texto corrido e legendas

## 4. Estruturar o documento

Leia o `.md` gerado (em gravações longas, leia a transcrição integral bloco a bloco — nunca resuma a partir de uma leitura parcial). Substitua **apenas** o conteúdo entre `<!-- CLAUDE:ESTRUTURA:INICIO -->` e `<!-- CLAUDE:ESTRUTURA:FIM -->` (mantenha os dois marcadores) por:

```markdown
## Resumo executivo
Texto corrido, objetivo, 1 a 3 parágrafos: do que se trata, quem participa, o que foi decidido/dito de relevante.

## Participantes
| Falante | Papel provável | Base da inferência |
|---|---|---|
| Falante 1 | Juiz(a) | Abre a audiência e concede a palavra (00:00:02) |

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
3. **Inferência declarada.** Falantes e papéis são inferidos pelo contexto (o Whisper não separa vozes): diga isso e mostre a base. Se não der para inferir, use "Falante não identificado".
4. **Possíveis erros de transcrição vão para "Notas de revisão"**, nunca corrigidos silenciosamente. Considere especialmente os trechos marcados com ⚠️.
5. O link de minutagem segue o formato `[[HH:MM:SS]](player.html#t=SEGUNDOS)`, com segundos inteiros.

## 5. Correções na transcrição (só quando o usuário pedir)

A fonte de verdade é `transcricao.json`. Para corrigir um trecho que o usuário conferiu na mídia:

1. Edite o campo `txt` do segmento correspondente em `saida/<slug>/transcricao.json` (localize pelo `ini`).
2. Rode `python degravar.py regerar <slug>` — o `.md`, as legendas e o player são refeitos e a seção estruturada é preservada.
3. Registre a correção em "Notas de revisão" (o que mudou e em qual minutagem).

Nunca edite a transcrição integral direto no `.md`: seria sobrescrita no próximo `regerar` e ficaria divergente do player.

## 6. Versão com falantes (opcional, sob pedido)

Se o usuário pedir a degravação "com falantes" (formato de ata/termo de audiência), gere um arquivo **separado** `saida/<slug>/<slug>-falantes.md`, com cada fala precedida do rótulo inferido (`**JUIZ(A):**`, `**ADVOGADO(A) DO RECLAMANTE:**` …) e a minutagem, reproduzindo o texto literal da transcrição. No topo, deixe claro que a atribuição de falantes é inferida e precisa de conferência. O arquivo original não é alterado.

## 7. Reproduzir

Ofereça abrir o player: `python degravar.py assistir <slug>` (ou `--em <segundos>` para abrir num ponto específico). No player: clique em qualquer frase para ir ao trecho; espaço pausa; ← → voltam/avançam 5 s; há busca e controle de velocidade. Se o vídeo foi movido, o próprio player permite selecionar o arquivo.

`python degravar.py listar` mostra todas as degravações e se já foram estruturadas.

## Lembretes ao usuário

- A transcrição automática é ferramenta de apoio: para uso em peça ou juntada aos autos, os trechos citados devem ser conferidos na mídia original.
- Vídeos e degravações ficam em `entrada/` e `saida/`, que não vão para o Git (podem conter dados pessoais — LGPD).
