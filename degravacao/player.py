"""Gera o player.html: vídeo + transcrição sincronizada, busca e minutagem clicável."""

from __future__ import annotations

import json
from pathlib import Path

from .documento import paragrafos
from .util import minutagem

MODELO = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITULO__ — Degravação</title>
<style>
  :root {
    --fundo: #f6f5f2; --painel: #ffffff; --texto: #1d1d1b; --suave: #6b6a65;
    --borda: #e3e1db; --destaque: #fff1c2; --acento: #b4532a; --alerta: #b7791f;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --fundo: #161614; --painel: #1f1f1c; --texto: #ecebe6; --suave: #9c9a92;
      --borda: #33322e; --destaque: #4a3d14; --acento: #e0895f; --alerta: #e0b04f;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--fundo); color: var(--texto);
         font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { padding: 14px 20px; border-bottom: 1px solid var(--borda); display: flex;
           gap: 16px; align-items: baseline; flex-wrap: wrap; }
  header h1 { font-size: 18px; margin: 0; }
  header span { color: var(--suave); font-size: 14px; }
  main { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 20px;
         padding: 20px; height: calc(100vh - 56px); }
  @media (max-width: 900px) { main { grid-template-columns: 1fr; height: auto; } #transcricao { max-height: 70vh; } }
  .coluna { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
  video { width: 100%; max-height: 62vh; background: #000; border-radius: 10px; }
  #legenda { min-height: 3.4em; padding: 10px 14px; background: var(--painel); border: 1px solid var(--borda);
             border-radius: 10px; font-size: 18px; }
  .controles { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  button, select, input[type=search] { font: inherit; font-size: 14px; color: var(--texto);
      background: var(--painel); border: 1px solid var(--borda); border-radius: 8px; padding: 6px 10px; }
  button { cursor: pointer; } button:hover { border-color: var(--acento); }
  label { font-size: 14px; color: var(--suave); display: flex; gap: 6px; align-items: center; }
  #erro { display: none; padding: 12px 14px; border: 1px solid var(--alerta); border-radius: 10px; font-size: 14px; }
  #transcricao { overflow-y: auto; background: var(--painel); border: 1px solid var(--borda);
                 border-radius: 10px; padding: 8px 18px; flex: 1; }
  .par { margin: 12px 0; }
  .ts { font: 13px ui-monospace, Consolas, monospace; color: var(--acento); cursor: pointer;
        margin-right: 6px; border: 0; background: none; padding: 0; }
  .seg { cursor: pointer; border-radius: 3px; }
  .seg:hover { text-decoration: underline dotted; }
  .seg.atual { background: var(--destaque); }
  .seg.baixa { text-decoration: underline wavy var(--alerta); text-underline-offset: 3px; }
  mark { background: #ffd54f; color: #000; }
  .info { font-size: 13px; color: var(--suave); }
</style>
</head>
<body>
<header>
  <h1>__TITULO__</h1>
  <span>__DURACAO__ · __PARAGRAFOS__ parágrafos · <span style="text-decoration: underline wavy var(--alerta)">sublinhado ondulado</span> = conferir na mídia</span>
</header>
<main>
  <section class="coluna">
    <video id="video" controls preload="metadata" src="__SRC__"></video>
    <div id="erro">
      Não foi possível abrir a mídia em <code>__SRC_TEXTO__</code> (arquivo movido ou formato não suportado pelo navegador).
      Selecione o arquivo manualmente: <input type="file" id="arquivo" accept="video/*,audio/*">
    </div>
    <div id="legenda" aria-live="polite"></div>
    <div class="controles">
      <button data-pular="-10">⟲ 10s</button>
      <button data-pular="-5">− 5s</button>
      <button id="play">▶ / ❚❚</button>
      <button data-pular="5">+ 5s</button>
      <button data-pular="10">10s ⟳</button>
      <label>Velocidade
        <select id="velocidade">
          <option>0.5</option><option>0.75</option><option selected>1</option>
          <option>1.25</option><option>1.5</option><option>1.75</option><option>2</option>
        </select>
      </label>
      <button id="copiar" title="Copia a minutagem atual">Copiar minutagem</button>
    </div>
    <p class="info">Atalhos: <b>espaço</b> play/pausa · <b>← →</b> 5 s · <b>J / L</b> 10 s · clique em qualquer frase para ir ao trecho.</p>
  </section>
  <section class="coluna">
    <div class="controles">
      <input type="search" id="busca" placeholder="Buscar na transcrição…" style="flex:1">
      <span id="contagem" class="info"></span>
      <label><input type="checkbox" id="seguir" checked> acompanhar</label>
    </div>
    <div id="transcricao"></div>
  </section>
</main>
<script>
const DADOS = __DADOS__;
const video = document.getElementById("video");
const caixa = document.getElementById("transcricao");
const legenda = document.getElementById("legenda");
const seguir = document.getElementById("seguir");
const segs = DADOS.segmentos;
const elems = [];

function hms(t) {
  t = Math.max(0, Math.floor(t));
  const h = String(Math.floor(t / 3600)).padStart(2, "0");
  const m = String(Math.floor(t % 3600 / 60)).padStart(2, "0");
  const s = String(t % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}
function ir(t) { video.currentTime = t; video.play().catch(() => {}); }

for (const p of DADOS.paragrafos) {
  const div = document.createElement("p");
  div.className = "par";
  const b = document.createElement("button");
  b.className = "ts"; b.textContent = "[" + hms(p.ini) + "]";
  b.onclick = () => ir(p.ini);
  div.appendChild(b);
  for (const i of p.segs) {
    const s = segs[i];
    const span = document.createElement("span");
    span.className = "seg" + (s.b ? " baixa" : "");
    span.textContent = s.t + " ";
    span.dataset.t = s.t;
    span.onclick = () => ir(s.ini);
    elems[i] = span;
    div.appendChild(span);
  }
  caixa.appendChild(div);
}

let atual = -1;
function indicePara(t) {
  let lo = 0, hi = segs.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (segs[m].ini <= t) { r = m; lo = m + 1; } else hi = m - 1; }
  return r;
}
video.addEventListener("timeupdate", () => {
  const i = indicePara(video.currentTime);
  if (i === atual) return;
  if (atual >= 0 && elems[atual]) elems[atual].classList.remove("atual");
  atual = i;
  if (i >= 0) {
    elems[i].classList.add("atual");
    legenda.textContent = video.currentTime <= segs[i].fim + 1 ? segs[i].t : "";
    if (seguir.checked) elems[i].scrollIntoView({ block: "center", behavior: "smooth" });
  }
});

document.querySelectorAll("[data-pular]").forEach(b =>
  b.onclick = () => { video.currentTime += Number(b.dataset.pular); });
document.getElementById("play").onclick = () => video.paused ? video.play() : video.pause();
document.getElementById("velocidade").onchange = e => { video.playbackRate = Number(e.target.value); };
document.getElementById("copiar").onclick = () =>
  navigator.clipboard.writeText(hms(video.currentTime)).catch(() => {});

document.addEventListener("keydown", e => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  const k = e.key.toLowerCase();
  if (k === " ") { e.preventDefault(); video.paused ? video.play() : video.pause(); }
  else if (k === "arrowleft") video.currentTime -= 5;
  else if (k === "arrowright") video.currentTime += 5;
  else if (k === "j") video.currentTime -= 10;
  else if (k === "l") video.currentTime += 10;
});

function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
function escapar(s) { return s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
document.getElementById("busca").addEventListener("input", e => {
  const q = norm(e.target.value.trim());
  let n = 0, primeiro = null;
  elems.forEach(el => {
    const txt = el.dataset.t + " ";
    if (!q) { el.textContent = txt; return; }
    const alvo = norm(txt);
    let out = "", pos = 0, idx;
    while ((idx = alvo.indexOf(q, pos)) !== -1) {
      out += escapar(txt.slice(pos, idx)) + "<mark>" + escapar(txt.slice(idx, idx + q.length)) + "</mark>";
      pos = idx + q.length; n++; primeiro = primeiro || el;
    }
    if (pos === 0) el.textContent = txt; else el.innerHTML = out + escapar(txt.slice(pos));
  });
  document.getElementById("contagem").textContent = q ? `${n} ocorrência(s)` : "";
  if (primeiro) { seguir.checked = false; primeiro.scrollIntoView({ block: "center" }); }
});

video.addEventListener("error", () => { document.getElementById("erro").style.display = "block"; });
document.getElementById("arquivo").addEventListener("change", e => {
  const f = e.target.files[0];
  if (f) { video.src = URL.createObjectURL(f); document.getElementById("erro").style.display = "none"; }
});

const m = location.hash.match(/t=(\d+(?:\.\d+)?)/);
if (m) video.addEventListener("loadedmetadata", () => { video.currentTime = Number(m[1]); }, { once: true });
</script>
</body>
</html>
"""


def gerar_player(pasta: Path, dados: dict, titulo: str, src: str) -> Path:
    segs = dados["segmentos"]
    compacto = {
        "segmentos": [{"ini": s["ini"], "fim": s["fim"], "t": s["txt"], "b": s["baixa_confianca"]} for s in segs],
        "paragrafos": [{"ini": p["ini"], "segs": p["segs"]} for p in paragrafos(segs)],
    }
    json_seguro = json.dumps(compacto, ensure_ascii=False).replace("</", "<\\/")
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")  # noqa: E731
    html = (
        MODELO.replace("__TITULO__", esc(titulo))
        .replace("__SRC_TEXTO__", esc(src))
        .replace("__SRC__", esc(src))
        .replace("__DURACAO__", minutagem(dados["duracao"]))
        .replace("__PARAGRAFOS__", str(len(compacto["paragrafos"])))
        .replace("__DADOS__", json_seguro)  # por último: o texto transcrito não passa por outras trocas
    )
    destino = pasta / "player.html"
    destino.write_text(html, encoding="utf-8")
    return destino
