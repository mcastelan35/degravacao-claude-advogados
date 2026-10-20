"""Página do player: mídia + transcrição sincronizada, legendas, forma de onda, marcações e revisão.

O modelo fica em degravacao/pagina/ (player.html, player.css, player.js) e vira uma página única,
com os dados embutidos. Serve ao player.html local (abre com dois cliques, sem internet) e à página
publicada como artefato no claude.ai (ver artefato.py); muda só o que cada ambiente permite: no
local há impressão, arquivos para baixar e revisão do texto; no artefato, as fontes da web.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import re

from .documento import (CATEGORIAS, falante_revisto, marcacoes_validas, marcos, md_para_html, palavras_validas,
                        paragrafos, partes_legenda, resumo_revisao, secao_estruturada, legendas)
from .falantes import nome as nome_falante
from .fontes import EXT_AUDIO
from .transcricao import LIMIAR_PALAVRA
from .util import duracao_por_extenso, minutagem

MODELO = Path(__file__).parent / "pagina"


def _rank(rotulo: str | None) -> int:
    return int(rotulo[1:]) if rotulo else 0


def montar_dados(dados: dict, md_doc: str | None, titulo: str, src: str, tipo: str, modo: str,
                 ficha_extra: list | None = None, motivo: str = "") -> dict:
    """Dados compactos que a página embute.

    `motivo` (artefato) diz por que a mídia não é a gravação completa: "sem_video" (escolha de quem
    publicou), "ausente" (original não encontrado) ou "tamanho" (não coube no limite do artefato).
    """
    segs = dados["segmentos"]
    artefato = modo == "artefato"   # a página publicada não leva o que é só de trabalho interno
    estrutura = secao_estruturada(md_doc or "")
    gerado = datetime.fromisoformat(dados["gerado_em"])
    conferir = sum(1 for s in segs if s["baixa_confianca"])
    falantes = [{"rot": r, "nome": nome_falante(dados, r), "tempo": minutagem(i["tempo"]), "seg": i["tempo"], "r": _rank(r)}
                for r, i in (dados.get("falantes") or {}).items()]

    frases = []
    for s in segs:
        item: dict = {"ini": s["ini"], "fim": s["fim"], "t": s["txt"]}
        if s["baixa_confianca"]:
            item["b"] = 1
        if s.get("corrigido"):
            item["c"] = 1
            if not artefato:   # o texto original do Whisper fica só no player local
                item["o"] = s.get("txt_whisper", "")
        ws = palavras_validas(s)
        if ws:
            item["w"] = [[w["ini"], w["fim"], w["txt"]] for w in ws]
            duvidas = [n for n, w in enumerate(ws) if w.get("p", 1) < LIMIAR_PALAVRA]
            if s["baixa_confianca"] and duvidas:
                item["d"] = duvidas   # sublinha só as palavras duvidosas, não a frase toda
        frases.append(item)

    pars = [{"ini": p["ini"], "segs": p["segs"], "rot": p.get("falante"),
             "inc": all(segs[i].get("falante_incerto") for i in p["segs"]),
             "rev": any(falante_revisto(segs[i]) for i in p["segs"]),
             "b": any(segs[i]["baixa_confianca"] for i in p["segs"])}
            for p in paragrafos(segs)]

    # No artefato, o link do Drive daria a quem recebe a página acesso à gravação inteira.
    origem = dados["origem"] + (f" — {dados['url']}" if dados.get("url") and not artefato else "")
    ficha = [
        ["Arquivo original", dados["arquivo"] + (f" ({dados['formato']})" if dados.get("formato") else "")],
        ["Origem", origem],
        ["Duração", f"{minutagem(dados['duracao'])} ({duracao_por_extenso(dados['duracao'])})"],
        ["Transcrição", f"Whisper {dados['modelo']}, local ({dados['dispositivo']}) · idioma {dados['idioma']} "
                        f"({dados['prob_idioma'] * 100:.0f}%)"],
        ["Volume", f"{len(segs)} frases · {len(pars)} parágrafos · {sum(len(s['txt'].split()) for s in segs)} palavras"],
        ["Trechos a conferir", str(conferir)],
        *([["Falantes", f"{len(falantes)} separados pela voz · "
                        f"{sum(1 for s in segs if s.get('falante_incerto'))} frases com falante a conferir"]]
          if falantes else []),
        *([["Revisão", resumo_revisao(dados)]] if dados.get("revisoes") else []),
        ["Degravado em", gerado.strftime("%d/%m/%Y %H:%M")],
        *(ficha_extra or []),
    ]
    chips = [[minutagem(dados["duracao"]), False]]
    if falantes:
        chips.append([f"{len(falantes)} falante{'s' if len(falantes) != 1 else ''}", False])
    if conferir:
        chips.append([f"{conferir} a conferir", True])
    chips += [[f"Whisper {dados['modelo']}", False], [gerado.strftime("%d/%m/%Y"), False]]

    m = marcos(estrutura)
    slug = dados["slug"]
    cues = []
    for parte in partes_legenda(dados):   # (ini, fim, rótulo, texto, abre, índice da frase); o índice pode faltar
        a, b, rot, txt, _abre, *resto = parte
        cues.append([a, b, rot, txt, resto[0] if resto else None])
    arquivos = []
    if modo == "local":
        arquivos = [["Word (.docx)", f"{slug}.docx", "documento", "baixa uma cópia"],
                    ["Documento (.md)", f"{slug}.md", "documento", "Markdown"],
                    ["Texto corrido (.txt)", f"{slug}.txt", "documento", "para colar"],
                    ["Legendas (.srt)", f"{slug}.srt", "legenda", "VLC, editores"],
                    ["Legendas (.vtt)", f"{slug}.vtt", "legenda", "web"]]
    return {
        "modo": modo,
        "id": f"{slug}|{dados['gerado_em']}",
        "titulo": titulo,
        "slug": slug,
        "geradoEm": dados["gerado_em"],
        "duracao": dados["duracao"],
        "chips": chips,
        "midia": {"tipo": tipo, "src": src, "nome": unquote(src.rsplit("/", 1)[-1]) if src else "",
                  "soAudio": dados.get("tipo_midia") == "audio",   # a gravação já era só áudio
                  "motivo": motivo},
        "segmentos": frases,
        "paragrafos": pars,
        "cues": cues,
        "legendas": [[a, b, t] for a, b, t in legendas(dados)],
        "picos": dados.get("picos") or [],
        "falantes": falantes,
        "ficha": ficha,
        "estrutura": md_para_html(estrutura) if estrutura else "",
        "topicos": sorted(m["topicos"], key=lambda x: x["t"]),
        "pontos": sorted(m["pontos"], key=lambda x: x["t"]),
        "marcacoes": marcacoes_validas(dados),   # saneadas como no .md e no Word
        "revisaoEm": dados.get("revisao_em") or "",
        "arquivos": arquivos,
        "categorias": [[k, v] for k, v in CATEGORIAS.items()],
    }


def gerar_html(dados: dict, md_doc: str | None, titulo: str, src: str, tipo: str, modo: str,
               ficha_extra: list | None = None, motivo: str = "") -> str:
    d = montar_dados(dados, md_doc, titulo, src, tipo, modo, ficha_extra, motivo)
    # "<" vira <: nenhum texto transcrito consegue fechar o <script> nem abrir comentário.
    js_dados = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    modelo = (MODELO / "player.html").read_text(encoding="utf-8")
    # Uma passada só: o que entra (título, dados, código) nunca é varrido de novo, então um título ou uma
    # frase que contenha um dos marcadores do modelo sai como texto.
    partes = {"__TITULO__": html.escape(titulo), "__FONTES__": FONTES if modo == "artefato" else "",
              "/*__CSS__*/": (MODELO / "player.css").read_text(encoding="utf-8"),
              "/*__JS__*/": (MODELO / "player.js").read_text(encoding="utf-8"), "__DADOS__": js_dados}
    pagina = re.sub("|".join(re.escape(k) for k in partes), lambda m: partes[m.group(0)], modelo)
    return CABECALHO_LOCAL + pagina if modo == "local" else pagina


def gerar_player(pasta: Path, dados: dict, titulo: str, src: str, md_doc: str | None = None) -> Path:
    # Pelo conteúdo (gravado na degravação); degravações antigas caem na extensão.
    tipo = dados.get("tipo_midia") or ("audio" if Path(unquote(src)).suffix.lower() in EXT_AUDIO else "video")
    destino = pasta / "player.html"
    destino.write_text(gerar_html(dados, md_doc, titulo, src, tipo, "local"), encoding="utf-8")
    return destino


# O artefato recebe o esqueleto <html>/<head> na publicação; o arquivo local precisa do seu.
CABECALHO_LOCAL = """<!doctype html>
<html lang="pt-BR">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
"""

# Só no artefato: o player local não faz nenhuma requisição externa (usa as fontes do sistema).
FONTES = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">"""
