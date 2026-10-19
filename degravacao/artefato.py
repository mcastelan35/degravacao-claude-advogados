"""Gera uma página para publicar como artefato no claude.ai (vídeo + transcrição + estrutura).

O artefato aceita arquivos de até 15 MB, então a mídia é recomprimida para caber:
vídeo quando sobra taxa suficiente, só o áudio em gravações longas e, no limite,
apenas a transcrição. A publicação em si é feita pelo Claude (ferramenta de artefatos).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from pathlib import Path

from .documento import MARCA_CLAUDE_FIM, MARCA_CLAUDE_INI, paragrafos
from .falantes import nome as nome_falante
from .util import duracao_por_extenso, minutagem

LIMITE_MB = 14.0              # margem sob o teto de 15 MB por arquivo do artefato
VIDEO_MIN_KBPS = 180          # abaixo disso o vídeo fica ruim demais: publica só o áudio
AUDIO_MIN_KBPS = 24
EXT_AUDIO_WEB = {".m4a", ".mp3"}
EXT_WEB = {".mp4", ".m4v", ".webm"} | EXT_AUDIO_WEB    # formatos que os navegadores tocam


def obter_ffmpeg() -> str:
    """ffmpeg do sistema ou o que vem no pacote imageio-ffmpeg (instalado com a ferramenta)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _dimensoes(midia: Path) -> tuple[int, int] | None:
    import av
    with av.open(str(midia)) as c:
        v = next((s for s in c.streams if s.type == "video"), None)
        return (v.codec_context.width, v.codec_context.height) if v else None


def _par(n: float) -> int:
    return max(2, int(round(n / 2)) * 2)


def preparar_midia(origem: Path, destino: Path, duracao: float, sem_video: bool = False,
                   limite_mb: float = LIMITE_MB) -> tuple[Path | None, str]:
    """Recomprime a mídia para caber no limite. Devolve (arquivo, "video" | "audio" | "nenhuma")."""
    destino.mkdir(parents=True, exist_ok=True)
    for antigo in destino.glob("midia.*"):
        antigo.unlink()
    orcamento = limite_mb * 8000 / max(duracao, 1)   # kbit/s disponíveis para a mídia inteira
    if origem.exists():
        # Nunca gastar mais que o original: se ele já cabe e o navegador toca, vai como está.
        orcamento = min(orcamento, origem.stat().st_size * 8 / 1000 / max(duracao, 1) * 1.05)
        tipo = "audio" if origem.suffix.lower() in EXT_AUDIO_WEB else "video"
        if (origem.suffix.lower() in EXT_WEB and origem.stat().st_size <= limite_mb * 1e6
                and not (sem_video and tipo == "video")):
            copia = destino / f"midia{origem.suffix.lower()}"
            shutil.copy2(origem, copia)
            return copia, tipo
    ffmpeg = obter_ffmpeg()
    dims = None if sem_video else _dimensoes(origem)

    if dims and orcamento >= VIDEO_MIN_KBPS:
        audio_k = 64
        video_k = int(orcamento * 0.9) - audio_k
        lado = 720 if video_k >= 1000 else 480 if video_k >= 450 else 360
        w, h = dims
        escala = min(1.0, lado / min(w, h))           # o lado menor vira 720/480/360, sem ampliar
        saida = destino / "midia.mp4"
        for tentativa in (1.0, 0.8):
            vk = int(video_k * tentativa)
            cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(origem),
                   "-vf", f"scale={_par(w * escala)}:{_par(h * escala)}",
                   "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{vk}k",
                   "-maxrate", f"{int(vk * 1.3)}k", "-bufsize", f"{vk * 2}k",
                   "-c:a", "aac", "-b:a", f"{audio_k}k", "-ac", "1", "-movflags", "+faststart", str(saida)]
            if subprocess.call(cmd) == 0 and saida.stat().st_size <= limite_mb * 1e6:
                return saida, "video"
        saida.unlink(missing_ok=True)

    if orcamento >= AUDIO_MIN_KBPS:
        saida = destino / "midia.m4a"
        ak = min(96, int(orcamento * 0.9))
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(origem), "-vn",
               "-c:a", "aac", "-b:a", f"{ak}k", "-ac", "1", "-movflags", "+faststart", str(saida)]
        if subprocess.call(cmd) == 0 and saida.stat().st_size <= limite_mb * 1e6:
            return saida, "audio"
        saida.unlink(missing_ok=True)
    return None, "nenhuma"


# ---------------------------------------------------------------- markdown da seção estruturada

_LINK_TS = re.compile(r"\[\[(\d{2}:\d{2}:\d{2})\]\]\(player\.html#t=(\d+)\)")


def _inline(txt: str) -> str:
    txt = html.escape(txt, quote=False)
    txt = _LINK_TS.sub(r'<button class="ts" data-t="\2">\1</button>', txt)
    txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
    txt = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<i>\1</i>", txt)
    txt = re.sub(r"`([^`]+)`", r"<code>\1</code>", txt)
    return txt


def md_para_html(md: str) -> str:
    """Converte o subconjunto de Markdown usado na seção estruturada (títulos, parágrafos,
    listas, tabelas, negrito e links de minutagem). O texto é escapado antes."""
    saida: list[str] = []
    linhas = md.splitlines()
    i = 0
    while i < len(linhas):
        ln = linhas[i].rstrip()
        if not ln.strip() or ln.strip().startswith("<!--"):
            i += 1
        elif ln.startswith("#"):
            nivel = min(len(ln) - len(ln.lstrip("#")) + 1, 4)
            saida.append(f"<h{nivel}>{_inline(ln.lstrip('#').strip())}</h{nivel}>")
            i += 1
        elif ln.lstrip().startswith(("- ", "* ")):
            itens = []
            while i < len(linhas) and linhas[i].lstrip().startswith(("- ", "* ")):
                itens.append(f"<li>{_inline(linhas[i].lstrip()[2:])}</li>")
                i += 1
            saida.append("<ul>" + "".join(itens) + "</ul>")
        elif ln.lstrip().startswith("|"):
            bloco = []
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                bloco.append([c.strip() for c in linhas[i].strip().strip("|").split("|")])
                i += 1
            corpo = [r for r in bloco[1:] if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            cab = "".join(f"<th>{_inline(c)}</th>" for c in bloco[0])
            linhas_t = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in corpo)
            saida.append(f'<div class="tabela"><table><thead><tr>{cab}</tr></thead><tbody>{linhas_t}</tbody></table></div>')
        else:
            par = []
            while i < len(linhas) and linhas[i].strip() and not linhas[i].lstrip().startswith(("#", "- ", "* ", "|", "<!--")):
                par.append(linhas[i].strip())
                i += 1
            saida.append(f"<p>{_inline(' '.join(par))}</p>")
    return "\n".join(saida)


def secao_estruturada(md_doc: str) -> str | None:
    ini, fim = md_doc.find(MARCA_CLAUDE_INI), md_doc.find(MARCA_CLAUDE_FIM)
    if not (0 <= ini < fim):
        return None
    trecho = md_doc[ini + len(MARCA_CLAUDE_INI):fim]
    return None if "_Pendente." in trecho else trecho


# ---------------------------------------------------------------- página

def gerar_pagina(dados: dict, md_doc: str, titulo: str, midia: Path | None, tipo: str) -> str:
    from datetime import datetime

    segs = dados["segmentos"]
    estrutura = secao_estruturada(md_doc)
    falantes = [{"rot": r, "nome": nome_falante(dados, r), "tempo": minutagem(i["tempo"])}
                for r, i in (dados.get("falantes") or {}).items()]
    gerado = datetime.fromisoformat(dados["gerado_em"])
    ficha = [
        ["Arquivo original", dados["arquivo"]],
        ["Origem", dados["origem"]],
        ["Duração", f"{minutagem(dados['duracao'])} ({duracao_por_extenso(dados['duracao'])})"],
        ["Transcrição", f"Whisper {dados['modelo']}, local · idioma {dados['idioma']} ({dados['prob_idioma'] * 100:.0f}%)"],
        ["Volume", f"{len(segs)} frases · {sum(len(s['txt'].split()) for s in segs)} palavras"],
        ["Trechos a conferir", str(sum(1 for s in segs if s["baixa_confianca"]))],
        ["Degravado em", gerado.strftime("%d/%m/%Y %H:%M")],
        ["Mídia nesta página", {"video": "vídeo recomprimido para o artefato",
                               "audio": "só o áudio (gravação longa para o limite do artefato)",
                               "nenhuma": "sem mídia (gravação longa demais para o limite do artefato)"}[tipo]],
    ]
    d = {
        "titulo": titulo,
        "duracao": dados["duracao"],
        "chips": [minutagem(dados["duracao"]),
                  f"{len(falantes)} falante{'s' if len(falantes) != 1 else ''}" if falantes else "falantes não separados",
                  f"Whisper {dados['modelo']}", gerado.strftime("%d/%m/%Y")],
        "segmentos": [{"ini": s["ini"], "fim": s["fim"], "t": s["txt"], "b": s["baixa_confianca"],
                       "f": nome_falante(dados, s.get("falante"))} for s in segs],
        "paragrafos": [{"ini": p["ini"], "segs": p["segs"], "f": nome_falante(dados, p.get("falante"))}
                       for p in paragrafos(segs)],
        "falantes": falantes,
        "ficha": ficha,
        "estrutura": md_para_html(estrutura) if estrutura else "",
        "slug": dados["slug"],
        "midia": {"tipo": tipo, "src": f"midia/{midia.name}" if midia else ""},
    }
    js = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    return (PAGINA.replace("__TITULO__", html.escape(titulo))
            .replace("__DADOS__", js))


PAGINA = r"""<title>__TITULO__</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
  /* Layout: mesa de degravação — mídia fixa à esquerda, folha de transcrição à direita; empilha no celular. */
  :root {
    --fundo: #f5f5f2; --folha: #ffffff; --tinta: #1b1a17; --suave: #69665e; --linha: #e2e0da;
    --caneta: #2c4f86; --marca: #ffe98a; --marca-tinta: #1b1a17; --achado: #ffd166; --conferir: #b7791f;
    --chip: #e9eef7; --tela: #0d0d0c;
    --f-titulo: "Fraunces", Georgia, "Times New Roman", serif;
    --f-texto: "Hanken Grotesk", system-ui, -apple-system, "Segoe UI", sans-serif;
    --f-mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --fundo: #121211; --folha: #1b1b19; --tinta: #ebe9e3; --suave: #9b988f; --linha: #2e2d2a;
      --caneta: #9bb9ec; --marca: #5b4a10; --marca-tinta: #fff6d6; --achado: #8a6a12; --conferir: #e0b04f;
      --chip: #23304a; --tela: #000000; color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --fundo: #121211; --folha: #1b1b19; --tinta: #ebe9e3; --suave: #9b988f; --linha: #2e2d2a;
    --caneta: #9bb9ec; --marca: #5b4a10; --marca-tinta: #fff6d6; --achado: #8a6a12; --conferir: #e0b04f;
    --chip: #23304a; --tela: #000000; color-scheme: dark;
  }
  html, body { height: 100%; }
  body { background: var(--fundo); color: var(--tinta); font: 15px/1.6 var(--f-texto); }
  .app { height: 100%; display: grid; grid-template-rows: auto minmax(0, 1fr);
         padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
  header { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 8px 24px;
           padding-block: 18px 14px; border-bottom: 1px solid var(--linha); }
  .rotulo { font: 500 11px/1 var(--f-mono); letter-spacing: .12em; text-transform: uppercase; color: var(--suave); }
  h1 { font: 600 clamp(20px, 2.4vw, 28px)/1.15 var(--f-titulo); margin: 6px 0 0; text-wrap: balance; }
  .ficha-chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .ficha-chips span { font: 12px/1 var(--f-mono); padding: 6px 9px; border: 1px solid var(--linha); border-radius: 6px;
                      color: var(--suave); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .mesa { display: grid; grid-template-columns: minmax(260px, 380px) minmax(0, 1fr); gap: 24px; padding-block: 18px; min-height: 0; }
  .mesa.sem-midia { grid-template-columns: minmax(0, 1fr); }
  .midia { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
  .tela { background: var(--tela); border-radius: 10px; overflow: hidden; display: flex; justify-content: center; min-height: 0; flex: 1; }
  .tela.audio { flex: none; background: none; }
  video { display: block; width: 100%; height: 100%; max-height: 100%; object-fit: contain; background: var(--tela); }
  .tela.audio video { height: 54px; background: none; }
  .agora { font-size: 14px; color: var(--suave); min-height: 3.2em; }
  .agora b { color: var(--tinta); font-weight: 600; }
  .controles { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  button, select, input { font: inherit; color: var(--tinta); }
  .btn { font: 500 13px/1 var(--f-texto); padding: 8px 11px; border-radius: 7px; border: 1px solid var(--linha);
         background: var(--folha); cursor: pointer; font-variant-numeric: tabular-nums; }
  .btn:hover { border-color: var(--caneta); }
  .btn.principal { background: var(--tinta); color: var(--folha); border-color: var(--tinta); min-width: 76px; }
  :focus-visible { outline: 2px solid var(--caneta); outline-offset: 2px; }
  .aviso { font-size: 13px; color: var(--suave); border-left: 3px solid var(--conferir); padding: 4px 0 4px 12px; margin: 0; }
  .folha { background: var(--folha); border: 1px solid var(--linha); border-radius: 10px; display: grid;
           grid-template-rows: auto minmax(0, 1fr); min-height: 0; min-width: 0; }
  .abas { display: flex; gap: 2px; padding: 6px 8px 0; border-bottom: 1px solid var(--linha); overflow-x: auto; }
  .aba { border: 0; background: none; padding: 10px 12px; font: 600 13px/1 var(--f-texto); color: var(--suave);
         border-bottom: 2px solid transparent; cursor: pointer; white-space: nowrap; }
  .aba[aria-selected="true"] { color: var(--tinta); border-bottom-color: var(--caneta); }
  .painel { overflow-y: auto; min-height: 0; padding: 4px 22px 22px; }
  .busca { position: sticky; top: 0; z-index: 2; background: var(--folha); display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
           padding-block: 12px; border-bottom: 1px solid var(--linha); }
  .busca input[type=search] { flex: 1; min-width: 160px; padding: 8px 10px; border: 1px solid var(--linha); border-radius: 7px; background: var(--fundo); }
  .busca small, .nota { font-size: 12px; color: var(--suave); }
  .busca label { font-size: 13px; color: var(--suave); display: flex; gap: 6px; align-items: center; }
  .par { display: grid; grid-template-columns: 74px minmax(0, 1fr); gap: 4px 14px; padding-block: 14px; border-bottom: 1px dashed var(--linha); }
  .par:last-child { border-bottom: 0; }
  .ts { font: 500 12px/1.9 var(--f-mono); color: var(--caneta); background: none; border: 0; padding: 0; cursor: pointer;
        text-align: left; font-variant-numeric: tabular-nums; }
  .ts:hover { text-decoration: underline; }
  .par > .ts { align-self: start; }
  .falante { display: inline-block; font: 600 11px/1 var(--f-texto); letter-spacing: .04em; text-transform: uppercase;
             padding: 4px 7px; border-radius: 4px; background: var(--chip); color: var(--caneta); margin-right: 8px; vertical-align: 2px; }
  .seg { cursor: pointer; border-radius: 3px; padding: 1px 0; transition: background-color .15s; }
  .seg:hover { text-decoration: underline dotted var(--suave); text-underline-offset: 3px; }
  .seg.atual { background: var(--marca); color: var(--marca-tinta); box-shadow: 0 0 0 2px var(--marca); }
  .seg.baixa { text-decoration: underline wavy var(--conferir); text-underline-offset: 4px; }
  mark { background: var(--achado); color: var(--marca-tinta); border-radius: 2px; }
  .estrutura { max-width: 72ch; padding-block: 8px; }
  .estrutura h2, .estrutura h3 { font: 600 18px/1.3 var(--f-titulo); margin: 22px 0 8px; text-wrap: balance; }
  .estrutura h3 { font-size: 16px; }
  .estrutura p { margin: 0 0 12px; }
  .estrutura ul { margin: 0 0 12px; padding-left: 18px; display: grid; gap: 6px; }
  .estrutura .ts { line-height: inherit; margin-right: 4px; }
  .tabela { overflow-x: auto; margin: 0 0 12px; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--linha); vertical-align: top; }
  th { font-weight: 600; color: var(--suave); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
  dl.dados { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 8px 18px; margin: 16px 0; }
  dl.dados dt { color: var(--suave); font-size: 13px; }
  dl.dados dd { margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
  .vazio { padding: 24px 0; color: var(--suave); max-width: 60ch; }
  @media (max-width: 820px) {
    .app { height: auto; display: block; }
    .mesa { grid-template-columns: minmax(0, 1fr); gap: 14px; }
    .midia { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--fundo); padding-block: 8px; }
    .tela { height: 36vh; flex: none; }
    .tela.audio { height: auto; }
    .agora { display: none; }
    .folha { display: block; }
    .painel { overflow: visible; padding: 4px 16px 18px; }
    .busca { position: static; }
    .par { grid-template-columns: minmax(0, 1fr); gap: 2px; }
    dl.dados { grid-template-columns: minmax(0, 1fr); gap: 2px 0; }
    dl.dados dd { margin-bottom: 8px; }
  }
  @media (prefers-reduced-motion: reduce) { .seg { transition: none; } }
</style>

<div class="app">
  <header>
    <div>
      <div class="rotulo">Degravação</div>
      <h1 id="titulo"></h1>
    </div>
    <div class="ficha-chips" id="chips"></div>
  </header>
  <div class="mesa" id="mesa">
    <section class="midia" id="midia" aria-label="Mídia">
      <div class="tela" id="tela"><video id="video" controls playsinline preload="metadata"></video></div>
      <div class="agora" id="agora" aria-live="polite"></div>
      <div class="controles">
        <button class="btn" data-pular="-5" title="Voltar 5 s (←)">− 5 s</button>
        <button class="btn principal" id="play">Reproduzir</button>
        <button class="btn" data-pular="5" title="Avançar 5 s (→)">+ 5 s</button>
        <select class="btn" id="velocidade" aria-label="Velocidade">
          <option value="0.75">0,75×</option><option value="1" selected>1×</option><option value="1.25">1,25×</option>
          <option value="1.5">1,5×</option><option value="2">2×</option>
        </select>
        <button class="btn" id="copiar-ts">Copiar minutagem</button>
      </div>
      <p class="aviso" id="aviso-midia" hidden></p>
    </section>
    <section class="folha" aria-label="Conteúdo da degravação">
      <div class="abas" role="tablist">
        <button class="aba" role="tab" id="aba-transcricao" aria-selected="true" aria-controls="p-transcricao">Transcrição integral</button>
        <button class="aba" role="tab" id="aba-estrutura" aria-selected="false" aria-controls="p-estrutura">Resumo e estrutura</button>
        <button class="aba" role="tab" id="aba-ficha" aria-selected="false" aria-controls="p-ficha">Ficha técnica</button>
      </div>
      <div class="painel" id="p-transcricao" role="tabpanel" aria-labelledby="aba-transcricao">
        <div class="busca">
          <input type="search" id="busca" placeholder="Buscar na transcrição (Enter vai para a próxima)" aria-label="Buscar na transcrição">
          <small id="contagem"></small>
          <label><input type="checkbox" id="seguir" checked> acompanhar a mídia</label>
          <button class="btn" id="copiar-texto">Copiar texto</button>
        </div>
        <div id="transcricao"></div>
        <p class="nota"><span class="seg baixa">sublinhado ondulado</span> = trecho a conferir na mídia · clique em qualquer frase para ouvir.</p>
      </div>
      <div class="painel" id="p-estrutura" role="tabpanel" aria-labelledby="aba-estrutura" hidden>
        <div class="estrutura" id="estrutura"></div>
      </div>
      <div class="painel" id="p-ficha" role="tabpanel" aria-labelledby="aba-ficha" hidden>
        <dl class="dados" id="dados"></dl>
        <div class="estrutura" id="falantes"></div>
        <p class="aviso">Transcrição automática integral, gerada localmente com Whisper. Antes de citar em peça ou material, confira os trechos sinalizados ouvindo a gravação.</p>
      </div>
    </section>
  </div>
</div>

<script>
const D = __DADOS__;
const $ = id => document.getElementById(id);
const video = $("video"), segs = D.segmentos, elems = [];
const hms = t => { t = Math.max(0, Math.floor(t)); const p = n => String(n).padStart(2, "0");
  return `${p(Math.floor(t / 3600))}:${p(Math.floor(t % 3600 / 60))}:${p(t % 60)}`; };
const temMidia = D.midia.tipo !== "nenhuma";
function ir(t) { if (!temMidia) return; video.currentTime = t; video.play().catch(() => {}); }
async function copiar(txt, btn) {
  const orig = btn.textContent;
  try { await navigator.clipboard.writeText(txt); btn.textContent = "Copiado"; }
  catch { btn.textContent = "Selecione e copie"; }
  setTimeout(() => btn.textContent = orig, 1600);
}

$("titulo").textContent = D.titulo;
for (const c of D.chips) { const s = document.createElement("span"); s.textContent = c; $("chips").appendChild(s); }

/* Mídia */
if (D.midia.tipo === "nenhuma") {
  $("midia").hidden = true; $("mesa").classList.add("sem-midia");
} else {
  video.src = D.midia.src;
  if (D.midia.tipo === "audio") {
    $("tela").classList.add("audio");
    const a = $("aviso-midia"); a.hidden = false;
    a.textContent = "Esta página traz só o áudio: o vídeo não cabe no limite de tamanho do artefato.";
  }
}
video.addEventListener("error", () => { const a = $("aviso-midia"); a.hidden = false;
  a.textContent = "Não foi possível carregar a mídia. A transcrição continua disponível ao lado."; });

/* Transcrição */
for (const p of D.paragrafos) {
  const linha = document.createElement("div"); linha.className = "par";
  const b = document.createElement("button"); b.className = "ts"; b.textContent = hms(p.ini); b.dataset.t = p.ini;
  linha.appendChild(b);
  const txt = document.createElement("p"); txt.style.margin = "0";
  if (p.f) { const c = document.createElement("span"); c.className = "falante"; c.textContent = p.f; txt.appendChild(c); }
  for (const i of p.segs) {
    const s = segs[i], span = document.createElement("span");
    span.className = "seg" + (s.b ? " baixa" : ""); span.textContent = s.t; span.dataset.t = s.t;
    span.onclick = () => ir(s.ini); elems[i] = span;
    txt.appendChild(span); txt.appendChild(document.createTextNode(" "));
  }
  linha.appendChild(txt); $("transcricao").appendChild(linha);
}
document.addEventListener("click", e => {          // minutagens clicáveis em qualquer aba
  const b = e.target.closest("button.ts[data-t]"); if (b) ir(Number(b.dataset.t));
});

/* Sincronia */
let atual = -1;
function indice(t) { let lo = 0, hi = segs.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (segs[m].ini <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; }
const reduzir = matchMedia("(prefers-reduced-motion: reduce)").matches;
video.addEventListener("timeupdate", () => {
  const i = indice(video.currentTime);
  if (i === atual) return;
  if (atual >= 0) elems[atual].classList.remove("atual");
  atual = i; if (i < 0) return;
  elems[i].classList.add("atual");
  $("agora").innerHTML = "";
  const b = document.createElement("b"); b.textContent = (segs[i].f || "Agora") + ": ";
  $("agora").append(b, segs[i].t);
  if ($("seguir").checked && !$("p-transcricao").hidden)
    elems[i].scrollIntoView({ block: "center", behavior: reduzir ? "auto" : "smooth" });
});
video.addEventListener("play", () => $("play").textContent = "Pausar");
video.addEventListener("pause", () => $("play").textContent = "Reproduzir");
$("play").onclick = () => video.paused ? video.play() : video.pause();
document.querySelectorAll("[data-pular]").forEach(b => b.onclick = () => { video.currentTime += Number(b.dataset.pular); });
$("velocidade").onchange = e => { video.playbackRate = Number(e.target.value); };
$("copiar-ts").onclick = e => copiar(hms(video.currentTime), e.currentTarget);
$("copiar-texto").onclick = e => copiar(D.paragrafos.map(p => (p.f ? p.f + ": " : "") + p.segs.map(i => segs[i].t).join(" ")).join("\n\n"), e.currentTarget);
document.addEventListener("keydown", e => {
  if (!temMidia || ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(document.activeElement.tagName)) return;
  if (e.key === " ") { e.preventDefault(); video.paused ? video.play() : video.pause(); }
  else if (e.key === "ArrowLeft") video.currentTime -= 5;
  else if (e.key === "ArrowRight") video.currentTime += 5;
});

/* Busca (ignora acentos e maiúsculas) */
const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const esc = s => s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
let achados = [], pos = -1;
$("busca").addEventListener("input", e => {
  const q = norm(e.target.value.trim()); achados = []; pos = -1;
  elems.forEach(el => {
    const t = el.dataset.t;
    if (!q) { el.textContent = t; return; }
    const alvo = norm(t); let out = "", k = 0, idx;
    while ((idx = alvo.indexOf(q, k)) !== -1) {
      out += esc(t.slice(k, idx)) + "<mark>" + esc(t.slice(idx, idx + q.length)) + "</mark>"; k = idx + q.length;
    }
    if (k === 0) el.textContent = t; else { el.innerHTML = out + esc(t.slice(k)); achados.push(...el.querySelectorAll("mark")); }
  });
  $("contagem").textContent = q ? (achados.length ? `${achados.length} ocorrência(s)` : "Nenhuma ocorrência") : "";
  if (achados.length) { $("seguir").checked = false; pos = 0; achados[0].scrollIntoView({ block: "center" }); }
});
$("busca").addEventListener("keydown", e => {
  if (e.key !== "Enter" || !achados.length) return;
  pos = (pos + 1) % achados.length; achados[pos].scrollIntoView({ block: "center" });
  $("contagem").textContent = `${pos + 1} de ${achados.length}`;
});

/* Estrutura (escrita pelo Claude no .md), ficha e falantes */
if (D.estrutura) $("estrutura").innerHTML = D.estrutura;
else $("estrutura").innerHTML = '<p class="vazio">O resumo e a estrutura ainda não foram gerados. No Claude Code, peça: <b>“estruture a degravação ' + esc(D.slug) + '”</b> e gere o artefato de novo.</p>';
for (const [k, v] of D.ficha) { const dt = document.createElement("dt"), dd = document.createElement("dd");
  dt.textContent = k; dd.textContent = v; $("dados").append(dt, dd); }
if (D.falantes.length) {
  $("falantes").innerHTML = '<h3>Falantes</h3><div class="tabela"><table><thead><tr><th>Rótulo</th><th>Identificação</th><th>Tempo de fala</th></tr></thead><tbody>'
    + D.falantes.map(f => `<tr><td>${esc(f.rot)}</td><td>${esc(f.nome)}</td><td>${esc(f.tempo)}</td></tr>`).join("") + "</tbody></table></div>";
}

/* Abas */
const abas = [["aba-transcricao", "p-transcricao"], ["aba-estrutura", "p-estrutura"], ["aba-ficha", "p-ficha"]];
abas.forEach(([a, p]) => $(a).onclick = () => abas.forEach(([a2, p2]) => {
  $(a2).setAttribute("aria-selected", a2 === a); $(p2).hidden = p2 !== p; }));

/* Link direto para um momento: #t75 */
const m = location.hash.match(/^#t(\d+)$/);
if (m && temMidia) video.addEventListener("loadedmetadata", () => { video.currentTime = Number(m[1]); }, { once: true });
</script>
"""
