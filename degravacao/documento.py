"""Gera o documento .md estruturado e as legendas (.srt/.vtt)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .util import duracao_por_extenso, minutagem

PAUSA_NOVO_PARAGRAFO = 2.0     # segundos de silêncio que abrem novo parágrafo
TAMANHO_PARAGRAFO = 550        # caracteres a partir dos quais o parágrafo fecha no fim da frase
TAMANHO_MAXIMO = 1200

MARCA_CLAUDE_INI = "<!-- CLAUDE:ESTRUTURA:INICIO -->"
MARCA_CLAUDE_FIM = "<!-- CLAUDE:ESTRUTURA:FIM -->"


def paragrafos(segmentos: list[dict]) -> list[dict]:
    """Agrupa segmentos do Whisper em parágrafos legíveis, sem alterar o texto."""
    saida: list[dict] = []
    atual: dict | None = None
    for s in segmentos:
        if atual is not None:
            pausa = s["ini"] - atual["fim"]
            tamanho = sum(len(segmentos[i]["txt"]) for i in atual["segs"])
            fim_frase = segmentos[atual["segs"][-1]]["txt"].rstrip().endswith((".", "?", "!", "…"))
            if pausa >= PAUSA_NOVO_PARAGRAFO or (tamanho >= TAMANHO_PARAGRAFO and fim_frase) or tamanho >= TAMANHO_MAXIMO:
                saida.append(atual)
                atual = None
        if atual is None:
            atual = {"ini": s["ini"], "fim": s["fim"], "segs": []}
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


def gerar_markdown(dados: dict, titulo: str) -> str:
    segs = dados["segmentos"]
    pars = paragrafos(segs)
    grupos = blocos(pars, dados["duracao"])
    duvidosos = [p for p in pars if any(segs[i]["baixa_confianca"] for i in p["segs"])]
    ids_duvidosos = {id(p) for p in duvidosos}
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
        f"| Volume | {len(segs)} segmentos · {len(pars)} parágrafos · {palavras} palavras |",
        f"| Trechos para conferência | {len(duvidosos)} |",
        f"| Degravado em | {datetime.fromisoformat(dados['gerado_em']).strftime('%d/%m/%Y %H:%M')} |",
        "| Reproduzir | [abrir player com transcrição sincronizada](player.html) |",
        "",
    ]

    L += [
        MARCA_CLAUDE_INI,
        "## Resumo e estrutura",
        "",
        "_Pendente. No Claude Code, peça: **\"estruture a degravação "
        f"{dados['slug']}\"** — o Claude preenche resumo executivo, tópicos, falantes e "
        "pontos de atenção sem alterar a transcrição integral._",
        MARCA_CLAUDE_FIM,
        "",
    ]

    L += ["## Índice por minutagem", ""]
    for n, g in enumerate(grupos, 1):
        previa = _texto(g[0], segs)[:90].rstrip() + "…"
        L.append(f"- [Bloco {n} — {minutagem(g[0]['ini'])} a {minutagem(g[-1]['fim'])}](#bloco-{n}) — {previa}")
    L.append("")

    if duvidosos:
        L += ["## Trechos para conferência", "",
              "Trechos em que o modelo teve baixa confiança (ruído, fala sobreposta, termos raros). "
              "Clique na minutagem para ouvir.", ""]
        for p in duvidosos:
            L.append(f"- {_link(p['ini'])} {_texto(p, segs)[:140].rstrip()}…")
        L.append("")

    L += ["## Transcrição integral", ""]
    for n, g in enumerate(grupos, 1):
        L += [f'<a id="bloco-{n}"></a>', "", f"### Bloco {n} — {minutagem(g[0]['ini'])} a {minutagem(g[-1]['fim'])}", ""]
        for p in g:
            alerta = " ⚠️" if id(p) in ids_duvidosos else ""
            L += [f"{_link(p['ini'])}{alerta} {_texto(p, segs)}", ""]

    L += ["---", "", f"_Gerado por degravacao-claude-advogados em {dados['gerado_em'][:10]}._", ""]
    return "\n".join(L)


def gerar_srt(segmentos: list[dict]) -> str:
    linhas = []
    for n, s in enumerate(segmentos, 1):
        linhas += [str(n), f"{minutagem(s['ini'], True, ',')} --> {minutagem(s['fim'], True, ',')}", s["txt"], ""]
    return "\n".join(linhas)


def gerar_vtt(segmentos: list[dict]) -> str:
    linhas = ["WEBVTT", ""]
    for s in segmentos:
        linhas += [f"{minutagem(s['ini'], True)} --> {minutagem(s['fim'], True)}", s["txt"], ""]
    return "\n".join(linhas)


def gerar_txt(segmentos: list[dict]) -> str:
    pars = paragrafos(segmentos)
    return "\n\n".join(_texto(p, segmentos) for p in pars) + "\n"


def salvar_tudo(pasta: Path, dados: dict, titulo: str) -> Path:
    slug = dados["slug"]
    md = pasta / f"{slug}.md"
    md.write_text(gerar_markdown(dados, titulo), encoding="utf-8")
    (pasta / f"{slug}.srt").write_text(gerar_srt(dados["segmentos"]), encoding="utf-8")
    (pasta / f"{slug}.vtt").write_text(gerar_vtt(dados["segmentos"]), encoding="utf-8")
    (pasta / f"{slug}.txt").write_text(gerar_txt(dados["segmentos"]), encoding="utf-8")
    return md
