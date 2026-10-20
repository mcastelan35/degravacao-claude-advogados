"""Gera o documento .md estruturado, o texto corrido e as legendas (.srt/.vtt)."""

from __future__ import annotations

import html
import math
import re
from datetime import datetime
from pathlib import Path

from .falantes import nome as nome_falante
from .util import duracao_por_extenso, minutagem

PAUSA_NOVO_PARAGRAFO = 2.0     # segundos de silêncio que abrem novo parágrafo
TAMANHO_PARAGRAFO = 550        # caracteres a partir dos quais o parágrafo fecha no fim da frase
TAMANHO_MAXIMO = 1200
LEGENDA_LINHA = 42             # caracteres por linha de legenda (duas linhas por legenda, padrão usual)

CATEGORIAS = {"relevante": "Relevante", "favoravel": "Favorável", "desfavoravel": "Desfavorável",
              "contradicao": "Contradição", "conferir": "Conferir"}   # marcações feitas no player

MARCA_CLAUDE_INI = "<!-- CLAUDE:ESTRUTURA:INICIO -->"
MARCA_CLAUDE_FIM = "<!-- CLAUDE:ESTRUTURA:FIM -->"
TITULO_ESTRUTURA = "## Resumo e estrutura"
# Começo da primeira linha da seção ainda não estruturada (o resto cita o slug). A seção só conta
# como pendente quando COMEÇA por ela: um "_Pendente._" no meio do texto do Claude não a apaga.
MARCA_PENDENTE = "_Pendente. No Claude Code, peça:"


def estrutura_pendente(trecho: str) -> bool:
    """Se o trecho da seção (com ou sem os marcadores e o título) ainda é SÓ o aviso padrão.

    Estrutura escrita abaixo do aviso (sem apagá-lo) conta como estrutura."""
    t = trecho.strip()
    if t.startswith(MARCA_CLAUDE_INI):
        t = t[len(MARCA_CLAUDE_INI):].strip()
    if t.startswith(TITULO_ESTRUTURA):
        t = t[len(TITULO_ESTRUTURA):].strip()
    if not t.startswith(MARCA_PENDENTE):
        return False
    resto = t.split("\n", 1)[1] if "\n" in t else ""   # o aviso ocupa uma linha só
    return not resto.strip()


def paragrafos(segmentos: list[dict]) -> list[dict]:
    """Agrupa frases em parágrafos legíveis, sem alterar o texto. Troca de falante abre parágrafo."""
    saida: list[dict] = []
    atual: dict | None = None
    for s in segmentos:
        if atual is not None:
            pausa = s["ini"] - atual["fim"]
            tamanho = sum(len(segmentos[i]["txt"]) for i in atual["segs"])
            fim_frase = segmentos[atual["segs"][-1]]["txt"].rstrip().endswith((".", "?", "!", "…"))
            troca = s.get("falante") != atual["falante"]
            if troca or pausa >= PAUSA_NOVO_PARAGRAFO or (tamanho >= TAMANHO_PARAGRAFO and fim_frase) or tamanho >= TAMANHO_MAXIMO:
                saida.append(atual)
                atual = None
        if atual is None:
            atual = {"ini": s["ini"], "fim": s["fim"], "segs": [], "falante": s.get("falante")}
        atual["segs"].append(s["i"])
        atual["fim"] = s["fim"]
    if atual:
        saida.append(atual)
    return saida


def _tamanho_bloco(duracao: float) -> int:
    if duracao <= 10 * 60:
        return 2 * 60
    if duracao <= 60 * 60:
        return 5 * 60
    return 10 * 60


def blocos(pars: list[dict], duracao: float) -> list[list[dict]]:
    passo = _tamanho_bloco(duracao)
    grupos: list[list[dict]] = []
    limite = -1.0
    for p in pars:
        if p["ini"] >= limite:
            grupos.append([])
            limite = (p["ini"] // passo + 1) * passo
        grupos[-1].append(p)
    return grupos


def _texto(p: dict, segs: list[dict]) -> str:
    return " ".join(segs[i]["txt"].strip() for i in p["segs"])


def _link(seg: float) -> str:
    return f"[[{minutagem(seg)}]](player.html#t={int(seg)})"


def falante_revisto(s: dict) -> bool:
    """Frase cujo falante foi trocado depois da separação automática (só quando há o acústico guardado)."""
    return bool(s.get("falante_acustico")) and s.get("falante") != s.get("falante_acustico")


def marcas_falante(p: dict, segs: list[dict]) -> str:
    """Marcas do rótulo do parágrafo: ' (?)' = todas as frases com atribuição acústica incerta; ' ✎' = alguma revista.

    A mesma regra vale para o .md, o .txt e o Word."""
    incerto = all(segs[i].get("falante_incerto") for i in p["segs"])
    revisto = any(falante_revisto(segs[i]) for i in p["segs"])
    return (" (?)" if incerto else "") + (" ✎" if revisto else "")


def _rotulo(p: dict, segs: list[dict], dados: dict) -> str:
    if not p.get("falante"):
        return ""
    return f"**{nome_falante(dados, p['falante'])}**{marcas_falante(p, segs)}: "


def trechos_conferencia(pars: list[dict], segs: list[dict]) -> list[tuple[float, str]]:
    """(início, texto) de cada trecho de baixa confiança: frases duvidosas consecutivas do mesmo parágrafo."""
    itens: list[tuple[float, str]] = []
    for p in pars:
        corrida: list[int] = []
        for i in [*p["segs"], None]:
            if i is not None and segs[i].get("baixa_confianca"):
                corrida.append(i)
                continue
            if corrida:
                itens.append((segs[corrida[0]]["ini"], " ".join(segs[k]["txt"].strip() for k in corrida)))
                corrida = []
    return itens


def _numero(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def marcacoes_validas(dados: dict) -> list[dict]:
    """Marcações do transcricao.json saneadas, na ordem da gravação.

    Índices inteiros dentro do intervalo, tempos numéricos (ou os das frases), categoria conhecida,
    nota e texto como texto. O que não bate é ignorado em vez de quebrar a geração."""
    segs = dados["segmentos"]
    saida = []
    for m in dados.get("marcacoes") or []:
        if not isinstance(m, dict):
            continue
        de, ate = m.get("de"), m.get("ate")
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (de, ate)) or not (0 <= de <= ate < len(segs)):
            continue
        ini = _numero(m.get("ini"))
        fim = _numero(m.get("fim"))
        texto = m.get("texto") if isinstance(m.get("texto"), str) else ""
        nota = m.get("nota") if isinstance(m.get("nota"), str) else ""
        saida.append({
            "id": m.get("id") if isinstance(m.get("id"), (str, int)) else None,
            "de": de, "ate": ate,
            "ini": ini if ini is not None else segs[de]["ini"],
            "fim": fim if fim is not None else segs[ate]["fim"],
            "cat": m.get("cat") if m.get("cat") in CATEGORIAS else "relevante",
            "texto": " ".join(texto.split()) or " ".join(segs[k]["txt"].strip() for k in range(de, ate + 1)),
            "nota": " ".join(nota.split()),
        })
    return sorted(saida, key=lambda m: (m["ini"], m["de"]))


def resumo_revisao(dados: dict) -> str:
    """Totais das revisões aplicadas pelo player (`python degravar.py revisao`)."""
    segs = dados["segmentos"]
    corrigidas = sum(1 for x in segs if x.get("corrigido"))
    revistas = sum(1 for x in segs if falante_revisto(x))
    try:
        ultima = datetime.fromisoformat(dados["revisoes"][-1]["em"]).strftime("%d/%m/%Y %H:%M")
    except (KeyError, IndexError, TypeError, ValueError):
        ultima = "data desconhecida"
    marcas = len(marcacoes_validas(dados))
    plural = lambda n, um, varios: f"{n} {um if n == 1 else varios}"  # noqa: E731
    return (f"{plural(corrigidas, 'frase corrigida', 'frases corrigidas')} · "
            f"{plural(revistas, 'frase com falante revisto', 'frases com falante revisto')} · "
            f"{plural(marcas, 'marcação', 'marcações')} · em {ultima}")


def gerar_markdown(dados: dict, titulo: str) -> str:
    segs = dados["segmentos"]
    pars = paragrafos(segs)
    grupos = blocos(pars, dados["duracao"])
    conferir = sum(1 for s in segs if s.get("baixa_confianca"))   # por frase, como no player
    trechos = trechos_conferencia(pars, segs)                      # frases consecutivas viram um trecho só
    ids_duvidosos = {id(p) for p in pars if any(segs[i].get("baixa_confianca") for i in p["segs"])}
    palavras = sum(len(s["txt"].split()) for s in segs)

    origem = dados["origem"]
    if dados.get("url"):
        origem = f"{origem} — <{dados['url']}>"

    L: list[str] = []
    L += [f"# Degravação — {titulo}", ""]
    L += [
        "> Transcrição automática integral, gerada localmente com Whisper. "
        "Antes de usar em peça ou juntar aos autos, confira os trechos sinalizados com ⚠️ "
        "diretamente na mídia (abra o `player.html`).",
        "",
    ]

    L += ["## Ficha técnica", "", "| Campo | Informação |", "|---|---|"]
    L += [
        f"| Arquivo | `{dados['arquivo']}` |",
        f"| Origem | {origem} |",
        f"| Duração | {minutagem(dados['duracao'])} ({duracao_por_extenso(dados['duracao'])}) |",
        f"| Idioma detectado | {dados['idioma']} ({dados['prob_idioma'] * 100:.0f}%) |",
        f"| Modelo | Whisper `{dados['modelo']}` ({dados['dispositivo']}) |",
        f"| Volume | {len(segs)} frases · {len(pars)} parágrafos · {palavras} palavras |",
        f"| Trechos para conferência | {conferir} frase{'s' if conferir != 1 else ''}"
        f"{f' em {len(trechos)} trechos' if len(trechos) != conferir else ''} |",
        *([f"| Falantes | {len(dados['falantes'])} identificados pela voz · "
           f"{sum(1 for x in segs if x.get('falante_incerto'))} frases com falante a conferir |"]
          if dados.get("falantes") else []),
        f"| Degravado em | {datetime.fromisoformat(dados['gerado_em']).strftime('%d/%m/%Y %H:%M')} |",
        *([f"| Revisão | {resumo_revisao(dados)} |"] if dados.get("revisoes") else []),
        "| Reproduzir | [abrir player com transcrição sincronizada](player.html) |",
        "",
    ]

    L += [
        MARCA_CLAUDE_INI,
        TITULO_ESTRUTURA,
        "",
        f"{MARCA_PENDENTE} **\"estruture a degravação "
        f"{dados['slug']}\"** — o Claude preenche resumo executivo, tópicos, falantes e "
        "pontos de atenção sem alterar a transcrição integral._",
        MARCA_CLAUDE_FIM,
        "",
    ]

    if dados.get("falantes"):
        L += ["## Falantes", "",
              "Separação automática pela voz (aproximada). **(?)** = falante a conferir "
              "(frase curta ou troca rápida); **✎** = atribuição revista depois da separação automática.", "",
              "| Rótulo | Identificação | Tempo de fala |", "|---|---|---|"]
        for rot, info in dados["falantes"].items():
            L.append(f"| {rot} | {info.get('nome') or '—'} | {minutagem(info['tempo'])} |")
        L.append("")

    L += ["## Índice por minutagem", ""]
    for n, g in enumerate(grupos, 1):
        previa = _texto(g[0], segs)[:90].rstrip() + "…"
        L.append(f"- [Bloco {n} — {minutagem(g[0]['ini'])} a {minutagem(g[-1]['fim'])}](#bloco-{n}) — {previa}")
    L.append("")

    if trechos:
        L += ["## Trechos para conferência", "",
              "Frases em que o modelo teve baixa confiança (ruído, fala sobreposta, termos raros). "
              "Clique na minutagem para ouvir.", ""]
        for ini, texto in trechos:
            L.append(f"- {_link(ini)} {texto[:140].rstrip()}{'…' if len(texto) > 140 else ''}")
        L.append("")

    marcacoes = marcacoes_validas(dados)
    if marcacoes:
        L += ["## Marcações", "", "Trechos marcados na revisão, pela ordem da gravação.", ""]
        for m in marcacoes:
            quem = nome_falante(dados, segs[m["de"]].get("falante"))
            nota = f" — _{m['nota']}_" if m["nota"] else ""
            L.append(f"- {_link(m['ini'])} **{CATEGORIAS[m['cat']]}** — {quem + ': ' if quem else ''}“{m['texto']}”{nota}")
        L.append("")

    L += ["## Transcrição integral", ""]
    for n, g in enumerate(grupos, 1):
        L += [f'<a id="bloco-{n}"></a>', "", f"### Bloco {n} — {minutagem(g[0]['ini'])} a {minutagem(g[-1]['fim'])}", ""]
        for p in g:
            alerta = " ⚠️" if id(p) in ids_duvidosos else ""
            L += [f"{_link(p['ini'])}{alerta} {_rotulo(p, segs, dados)}{_texto(p, segs)}", ""]

    L += ["---", "", f"_Gerado por degravacao-claude-advogados em {dados['gerado_em'][:10]}._", ""]
    return "\n".join(L)


def palavras_validas(s: dict) -> list[dict]:
    """Tempos por palavra da frase, ou [] se o texto foi corrigido depois da transcrição."""
    ws = s.get("palavras") or []
    return ws if "".join(w["txt"] for w in ws).strip() == s["txt"].strip() else []


def _duas_linhas(txt: str) -> str:
    if len(txt) <= LEGENDA_LINHA:
        return txt
    espacos = [i for i, c in enumerate(txt) if c == " "]
    if not espacos:
        return txt
    i = min(espacos, key=lambda k: max(k, len(txt) - k - 1))   # a linha mais longa, a menor possível
    return txt[:i] + "\n" + txt[i + 1:]


def _cabe_em_duas_linhas(texto: str) -> bool:
    return all(len(linha) <= LEGENDA_LINHA for linha in _duas_linhas(texto).split("\n"))


def _agrupar(tokens: list[tuple], prefixo: int) -> list[list[tuple]]:
    """Reparte os pedaços (texto, ini, fim) em legendas de tamanho parecido, nenhuma acima de duas linhas
    de LEGENDA_LINHA caracteres (contando o prefixo do falante na primeira)."""
    total = prefixo + sum(len(t) for t, _, _ in tokens)
    partes = -(-total // (2 * LEGENDA_LINHA))   # sem sobra órfã no fim
    grupos: list[list[tuple]] = []
    atual: list[tuple] = []
    feito = prefixo
    texto = "x" * prefixo                        # o prefixo "[Nome] " ocupa espaço só na primeira legenda
    for tok in tokens:
        candidato = texto + tok[0]
        estoura = bool(atual) and not _cabe_em_duas_linhas(candidato.strip())
        equilibrado = len(grupos) < partes - 1 and feito >= total * (len(grupos) + 1) / partes
        if atual and (estoura or equilibrado):
            grupos.append(atual)
            atual, feito = [], 0
            candidato = tok[0]
        atual.append(tok)
        feito += len(tok[0])
        texto = candidato
    if atual:
        grupos.append(atual)
    return grupos


def partes_legenda(dados: dict) -> list[tuple[float, float, str | None, str, bool, int]]:
    """Legendas de até duas linhas, cortadas pelos tempos das palavras.

    Cada parte: (início, fim, rótulo do falante, texto, se abre a frase, índice da frase).
    Frase sem tempos por palavra (texto corrigido) é repartida nos espaços, com o tempo
    distribuído na proporção dos caracteres.
    """
    saida: list[tuple[float, float, str | None, str, bool, int]] = []
    for n_s, s in enumerate(dados["segmentos"]):
        i = s.get("i", n_s)
        rot = s.get("falante")
        txt = " ".join(s["txt"].split())
        prefixo = len(f"[{nome_falante(dados, rot)}] ") if rot else 0
        ws = palavras_validas(s)
        if ws:
            tokens = [(w["txt"], w["ini"], w["fim"]) for w in ws]
        else:
            tokens = [((" " if k else "") + w, None, None) for k, w in enumerate(txt.split())]
        grupos = _agrupar(tokens, prefixo)
        if len(grupos) <= 1:
            saida.append((s["ini"], s["fim"], rot, txt, True, i))
            continue
        textos = ["".join(t for t, _, _ in g).strip() for g in grupos]
        if ws:
            for n, g in enumerate(grupos):
                ini = s["ini"] if n == 0 else g[0][1]
                fim = s["fim"] if n == len(grupos) - 1 else g[-1][2]
                saida.append((ini, fim, rot, textos[n], n == 0, i))
        else:
            total, acumulado, duracao = sum(len(t) for t in textos) or 1, 0, s["fim"] - s["ini"]
            for n, texto in enumerate(textos):
                ini = s["ini"] if n == 0 else round(s["ini"] + duracao * acumulado / total, 2)
                acumulado += len(texto)
                fim = s["fim"] if n == len(textos) - 1 else round(s["ini"] + duracao * acumulado / total, 2)
                saida.append((ini, fim, rot, texto, n == 0, i))
    return saida


def legendas(dados: dict) -> list[tuple[float, float, str]]:
    """Legendas de arquivo (.srt/.vtt): o nome de quem fala abre cada frase."""
    return [(ini, fim, _duas_linhas((f"[{nome_falante(dados, rot)}] " if rot and abre else "") + txt))
            for ini, fim, rot, txt, abre, _ in partes_legenda(dados)]


def gerar_srt(dados: dict) -> str:
    linhas = []
    for n, (ini, fim, txt) in enumerate(legendas(dados), 1):
        linhas += [str(n), f"{minutagem(ini, True, ',')} --> {minutagem(fim, True, ',')}", txt, ""]
    return "\n".join(linhas)


def gerar_vtt(dados: dict) -> str:
    linhas = ["WEBVTT", ""]
    for ini, fim, txt in legendas(dados):   # no VTT, & e < são marcação: precisam de escape
        linhas += [f"{minutagem(ini, True)} --> {minutagem(fim, True)}", html.escape(txt, quote=False), ""]
    return "\n".join(linhas)


def gerar_txt(dados: dict) -> str:
    segs = dados["segmentos"]
    pars = paragrafos(segs)
    return "\n\n".join(
        (f"{nome_falante(dados, p['falante'])}{marcas_falante(p, segs)}: " if p.get("falante") else "") + _texto(p, segs)
        for p in pars
    ) + "\n"


# ---------------------------------------------------------------- seção estruturada pelo Claude

_LINK_TS = re.compile(r"\[\[(\d{2}:\d{2}:\d{2})\]\]\(player\.html#t=(\d+)\)")
_ITEM_TS = re.compile(r"^\s*[-*]\s+\[\[\d{2}:\d{2}:\d{2}\]\]\(player\.html#t=(\d+)\)\s*(.*)$")


def secao_estruturada(md_doc: str) -> str | None:
    """Conteúdo da seção do Claude, ou None se o documento ainda traz só o aviso de pendente."""
    ini, fim = md_doc.find(MARCA_CLAUDE_INI), md_doc.find(MARCA_CLAUDE_FIM)
    if not (0 <= ini < fim):
        return None
    trecho = md_doc[ini + len(MARCA_CLAUDE_INI):fim]
    return None if estrutura_pendente(trecho) else trecho


def marcos(estrutura: str | None) -> dict:
    """Tópicos e pontos de atenção com minutagem, para a linha do tempo do player."""
    saida: dict[str, list] = {"topicos": [], "pontos": []}
    secao = None
    for ln in (estrutura or "").splitlines():
        if ln.startswith("## "):
            nome = ln[3:].strip().lower()
            secao = "topicos" if "tópicos" in nome or "topicos" in nome else (
                "pontos" if "atenção" in nome or "atencao" in nome else None)
            continue
        m = _ITEM_TS.match(ln)
        if secao and m:
            resto = _LINK_TS.sub(r"\1", m.group(2))
            negrito = re.search(r"\*\*(.+?)\*\*", resto)
            texto = negrito.group(1) if secao == "topicos" and negrito else re.sub(r"[*_`]", "", resto)
            saida[secao].append({"t": int(m.group(1)), "txt": texto.strip(" —–-")[:160]})
    return saida


_ITEM_NUMERADO = re.compile(r"^\d{1,3}[.)]\s+")


def eh_item_lista(linha: str) -> bool:
    """Linha (já sem espaços nas pontas) que é item de lista: "- texto", "* texto" ou o marcador sozinho."""
    return linha.startswith(("- ", "* ")) or linha in ("-", "*")


def eh_item_numerado(linha: str) -> bool:
    """Item de lista numerada: "1. texto" ou "2) texto"."""
    return bool(_ITEM_NUMERADO.match(linha))


def _inline(txt: str) -> str:
    txt = html.escape(txt, quote=False)
    txt = _LINK_TS.sub(r'<button class="ts" data-t="\2">\1</button>', txt)
    txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
    txt = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<i>\1</i>", txt)
    txt = re.sub(r"`([^`]+)`", r"<code>\1</code>", txt)
    return txt


def _tipo_linha(linha: str) -> str:
    """Classifica a linha já normalizada (strip): vazia, comentário, título, item, tabela ou texto."""
    if not linha:
        return "vazia"
    if linha.startswith("<!--"):
        return "comentario"
    if linha.startswith("#"):
        return "titulo"
    if eh_item_lista(linha):
        return "item"
    if eh_item_numerado(linha):
        return "numerado"
    if linha.startswith("|"):
        return "tabela"
    return "texto"


def md_para_html(md: str) -> str:
    """Converte o subconjunto de Markdown usado na seção estruturada (títulos, parágrafos,
    listas, tabelas, negrito e links de minutagem). O texto é escapado antes.

    Toda linha é classificada uma vez só, pelo mesmo critério em todos os ramos, e cada
    volta do laço consome pelo menos uma linha: título indentado ou marcador solto não travam."""
    saida: list[str] = []
    linhas = [ln.strip() for ln in md.splitlines()]
    i = 0
    while i < len(linhas):
        ln = linhas[i]
        tipo = _tipo_linha(ln)
        if tipo in ("vazia", "comentario"):
            i += 1
        elif tipo == "titulo":
            nivel = min(len(ln) - len(ln.lstrip("#")) + 1, 4)
            saida.append(f"<h{nivel}>{_inline(ln.lstrip('#').strip())}</h{nivel}>")
            i += 1
        elif tipo == "item":
            itens = []
            while i < len(linhas) and _tipo_linha(linhas[i]) == "item":
                texto = linhas[i][2:].strip()
                if texto:
                    itens.append(f"<li>{_inline(texto)}</li>")
                i += 1
            if itens:
                saida.append("<ul>" + "".join(itens) + "</ul>")
        elif tipo == "numerado":
            itens = []
            while i < len(linhas) and _tipo_linha(linhas[i]) == "numerado":
                texto = _ITEM_NUMERADO.sub("", linhas[i]).strip()
                if texto:
                    itens.append(f"<li>{_inline(texto)}</li>")
                i += 1
            if itens:
                saida.append("<ol>" + "".join(itens) + "</ol>")
        elif tipo == "tabela":
            bloco = []
            while i < len(linhas) and _tipo_linha(linhas[i]) == "tabela":
                bloco.append([c.strip() for c in linhas[i].strip("|").split("|")])
                i += 1
            if not any(c for r in bloco for c in r):   # "|" solto: não há tabela
                continue
            corpo = [r for r in bloco[1:] if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            cab = "".join(f"<th>{_inline(c)}</th>" for c in bloco[0])
            linhas_t = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in corpo)
            saida.append(f'<div class="tabela"><table><thead><tr>{cab}</tr></thead><tbody>{linhas_t}</tbody></table></div>')
        else:
            par = []
            while i < len(linhas) and _tipo_linha(linhas[i]) == "texto":
                par.append(linhas[i])
                i += 1
            saida.append(f"<p>{_inline(' '.join(par))}</p>")
    return "\n".join(saida)


def salvar_tudo(pasta: Path, dados: dict, titulo: str) -> Path:
    slug = dados["slug"]
    md = pasta / f"{slug}.md"
    # errors="replace": um substituto solto vindo de uma revisão malformada não pode derrubar a gravação.
    md.write_text(gerar_markdown(dados, titulo), encoding="utf-8", errors="replace")
    (pasta / f"{slug}.srt").write_text(gerar_srt(dados), encoding="utf-8", errors="replace")
    (pasta / f"{slug}.vtt").write_text(gerar_vtt(dados), encoding="utf-8", errors="replace")
    (pasta / f"{slug}.txt").write_text(gerar_txt(dados), encoding="utf-8", errors="replace")
    return md
