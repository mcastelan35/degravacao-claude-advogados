"use strict";
/* Player da degravação: mídia sincronizada com a transcrição, legendas, forma de onda por falante,
   marcações jurídicas e revisão do texto. Os dados (D) vêm embutidos pela ferramenta. */

/* ================= utilidades ================= */
const $ = id => document.getElementById(id);
const local = D.modo === "local";
const video = $("video"), tela = $("tela"), lt = $("lt");
// A .tela (vídeo, legenda, palco do áudio, botão de play) vai inteira para a janela flutuante: referências fixas,
// porque lá document.getElementById não a encontra mais.
const legendaTela = $("legenda-tela"), palcoAudio = $("palco-audio"), palcoFalante = $("palco-falante"),
      palcoTexto = $("palco-texto"), telaPlay = $("tela-play");
const segs = D.segmentos, pars = D.paragrafos;
const temMidia = D.midia.tipo !== "nenhuma", ehVideo = D.midia.tipo === "video";
const reduzir = matchMedia("(prefers-reduced-motion: reduce)").matches;
const pad = n => String(n).padStart(2, "0");
const hms = t => { t = Math.max(0, Math.floor(t || 0)); return `${pad(Math.floor(t / 3600))}:${pad(Math.floor(t % 3600 / 60))}:${pad(t % 60)}`; };
const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const rank = rot => rot ? Number(String(rot).slice(1)) || 0 : 0;
const cor = r => r ? `var(--f${(r - 1) % 6 + 1})` : "var(--caneta)";
const corLegenda = r => r ? `var(--fc${(r - 1) % 6 + 1})` : "#cfe0ff";
const corMarca = cat => `var(--m-${cat})`;
const duracao = () => D.duracao || video.duration || 1;
const CATS = D.categorias;
const nomeCat = id => (CATS.find(c => c[0] === id) || CATS[0])[1];

function busca(lista, t) {   // último índice com lista[i] <= t (lista em ordem)
  let lo = 0, hi = lista.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (lista[m] <= t) { r = m; lo = m + 1; } else hi = m - 1; }
  return r;
}
function el(tag, props, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k === "html") e.innerHTML = v;
    else if (k === "value") e.value = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k.startsWith("--")) e.style.setProperty(k, v);
    else if (k === "style") {   // declaração a declaração: não apaga as variáveis --cor/--mc já aplicadas
      for (const decl of String(v).split(";")) {
        const p = decl.indexOf(":");
        if (p > 0) e.style.setProperty(decl.slice(0, p).trim(), decl.slice(p + 1).trim());
      }
    } else e.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos) if (f != null && f !== false) e.append(f);
  return e;
}
const SVG = "http://www.w3.org/2000/svg";
function icone(nome) {
  const s = document.createElementNS(SVG, "svg"); s.setAttribute("class", "ic"); s.setAttribute("aria-hidden", "true");
  const u = document.createElementNS(SVG, "use"); u.setAttribute("href", "#i-" + nome); s.append(u);
  return s;
}
const trocarIcone = (botao, nome) => botao.querySelector("use")?.setAttribute("href", "#i-" + nome);

const loja = {   // localStorage pode falhar (janela anônima, artefato em prévia): tudo funciona sem ele
  ler(chave, padrao) { try { const v = localStorage.getItem(chave); return v == null ? padrao : JSON.parse(v); } catch { return padrao; } },
  gravar(chave, valor) { try { localStorage.setItem(chave, JSON.stringify(valor)); } catch { /* sem armazenamento */ } },
};
const CHAVE = "degravacao:" + D.id;
const prefs = Object.assign({ tema: "auto", layout: "lado", fonte: 16, legenda: "m", legendas: true, pularSilencio: false,
                              retroceder: false, volume: 1, mudo: false, velocidade: 1 }, loja.ler("degravacao:prefs", {}));
const salvarPrefs = () => loja.gravar("degravacao:prefs", prefs);

let tToast = 0;
function aviso(msg, acao, rotuloAcao) {
  $("toast-texto").textContent = msg;
  const b = $("toast-acao");
  b.hidden = !acao;
  if (acao) { b.textContent = rotuloAcao; b.onclick = () => { $("toast").hidden = true; acao(); }; }
  $("toast").hidden = false;
  clearTimeout(tToast);
  tToast = setTimeout(() => { $("toast").hidden = true; }, acao ? 9000 : 2800);
}
async function copiar(texto, msg = "Copiado") {
  try { await navigator.clipboard.writeText(texto); aviso(msg); return; } catch { /* tenta o método antigo */ }
  const area = el("textarea", { style: "position:fixed;opacity:0;top:0" });
  area.value = texto; document.body.append(area); area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  area.remove();
  aviso(ok ? msg : "Não foi possível copiar. Selecione o texto e use Ctrl+C.");
}
function baixar(nome, conteudo, tipo = "application/json") {
  const url = URL.createObjectURL(new Blob([conteudo], { type: tipo }));
  const a = el("a", { href: url, download: nome });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/* ================= estado ================= */
const inicios = Float64Array.from(segs, s => s.ini);
const cues = D.cues, iniCues = Float64Array.from(cues, c => c[0]);
const elems = [], parEls = [], parDeSeg = [];
const conferir = segs.map((s, i) => s.b ? i : -1).filter(i => i >= 0);
pars.forEach((p, k) => p.segs.forEach(i => { parDeSeg[i] = k; }));
let atual = -1, palavraAtiva = null, repetir = -1, pausaSeguir = 0, ultimoSegundo = -1, ultimoSalvo = 0, cueAtual = -2;
let buscaAtiva = false, revisando = false, filtro = null, pausadoEm = 0, janelaPip = null, selecao = null, pularSuave = 0;
let pendentesLocais = 0, descartadasLocais = 0, migrouLocal = false;   // o que ficou deste navegador quando o documento mudou
let marcas = carregarMarcas();
const revisao = carregarRevisao();

/* O que o usuário faz no player fica neste navegador, com a "base" (data da última revisão aplicada ao
   documento). Quando o documento é regerado com outra base, nada é descartado: o que ainda não está no
   documento continua pendente, e um aviso pede para exportar. */
function carregarMarcas() {
  const salvo = loja.ler(CHAVE + ":marcas", null);
  const doc = (D.marcacoes || []).map(m => ({ ...m }));   // o que já foi aplicado ao documento
  if (!salvo || !Array.isArray(salvo.itens)) return doc;
  if (salvo.base === D.revisaoEm) return salvo.itens.filter(m => m && segs[m.de] && segs[m.ate]);
  const noDoc = new Map(doc.map(m => [m.id, m]));
  const iguais = (a, b) => a.de === b.de && a.ate === b.ate && a.cat === b.cat && (a.nota || "") === (b.nota || "");
  // Fica o que o documento não tem: marcação nova, ou uma já exportada que foi editada depois (nota, categoria, trecho).
  const pendentes = salvo.itens.filter(m => m && m.id && segs[m.de] && segs[m.ate] && (!noDoc.has(m.id) || !iguais(m, noDoc.get(m.id))));
  pendentesLocais += pendentes.length; migrouLocal = true;
  const vistos = new Set(pendentes.map(m => m.id));
  return [...doc.filter(m => !vistos.has(m.id)), ...pendentes].sort((a, b) => a.ini - b.ini);
}
function normalizarRevisao(r) {   // aceita os formatos antigos (texto como string; falante por índice do parágrafo)
  const textos = {}, falantes = {};
  let descartadas = 0;
  for (const [i, v] of Object.entries(r.textos || {})) {
    if (!segs[i]) continue;
    if (typeof v === "string") textos[i] = { t: v, o: segs[i].t };
    else if (v && typeof v.t === "string") textos[i] = { t: v.t, o: typeof v.o === "string" ? v.o : segs[i].t };
  }
  for (const [chave, v] of Object.entries(r.falantes || {})) {
    if (typeof v === "string") {   // antigo: chave = número do parágrafo
      const p = pars[chave];
      if (p) falantes[p.segs[0]] = { rot: v, segs: [...p.segs] }; else descartadas++;
      continue;
    }
    if (!v || typeof v.rot !== "string") continue;
    const k = parDeSeg[chave];   // atual: chave = primeira frase do parágrafo
    const vistas = Array.isArray(v.segs) ? v.segs.map(Number).filter(i => segs[i]) : [];
    if (k != null && pars[k].segs[0] === Number(chave))
      // o parágrafo que o usuário vê agora é o que a exportação leva (se ele cresceu, as frases novas entram)
      falantes[chave] = { rot: v.rot, segs: [...pars[k].segs] };
    else if (vistas.length && vistas.every(i => pars[parDeSeg[i]]?.rot === v.rot))
      continue;   // o documento já traz essa troca (os parágrafos se fundiram por causa dela): nada a avisar
    else descartadas++;
  }
  return { textos, falantes, nomes: Object.assign({}, r.nomes || {}), descartadas };
}
function carregarRevisao() {
  const vazia = { base: D.revisaoEm, textos: {}, falantes: {}, nomes: {} };
  const salvo = loja.ler(CHAVE + ":revisao", null);
  if (!salvo) return vazia;
  const n = normalizarRevisao(salvo);
  descartadasLocais += n.descartadas;
  if (salvo.base === D.revisaoEm) return { base: D.revisaoEm, textos: n.textos, falantes: n.falantes, nomes: n.nomes };
  // o documento mudou: fica só o que ainda não está nele
  const r = { base: D.revisaoEm, textos: {}, falantes: {}, nomes: {} };
  for (const [i, e] of Object.entries(n.textos)) if (e.t !== segs[i].t) r.textos[i] = e;
  for (const [c, e] of Object.entries(n.falantes)) if (e.rot !== pars[parDeSeg[c]].rot) r.falantes[c] = e;
  for (const [rot, nome] of Object.entries(n.nomes)) {
    const f = D.falantes.find(x => x.rot === rot);
    if (!f || (f.nome || "") !== nome) r.nomes[rot] = nome;
  }
  pendentesLocais += Object.keys(r.textos).length + Object.keys(r.falantes).length + Object.keys(r.nomes).length;
  migrouLocal = true;
  return r;
}
const trocaDoPar = k => revisao.falantes[pars[k].segs[0]];   // {rot, segs} trocado na revisão, ou undefined
const rotDoPar = k => trocaDoPar(k)?.rot ?? pars[k].rot;
const rotDoSeg = i => i >= 0 && parDeSeg[i] != null ? rotDoPar(parDeSeg[i]) : null;
const textoSeg = i => revisao.textos[i]?.t ?? segs[i].t;
const textoPar = p => p.segs.map(textoSeg).join(" ");
function nomeFalante(rot) {
  if (!rot) return "";
  return revisao.nomes[rot] || (D.falantes.find(f => f.rot === rot) || {}).nome || `Falante ${rank(rot)}`;
}
function falantesDisponiveis() {
  const rots = new Set([...D.falantes.map(f => f.rot), ...Object.values(revisao.falantes).map(e => e.rot)]);
  return [...rots].sort((a, b) => rank(a) - rank(b)).map(rot => ({ rot, nome: nomeFalante(rot) }));
}
function topicoEm(t) { let r = null; for (const x of D.topicos) { if (x.t <= t) r = x; else break; } return r; }

/* ================= preferências ================= */
function aplicarPrefs() {
  if (local) {
    if (prefs.tema === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.dataset.theme = prefs.tema;
  }
  $("app").dataset.layout = temMidia ? prefs.layout : "lado";
  document.documentElement.style.setProperty("--tam-texto", prefs.fonte + "px");
  $("aj-fonte-v").textContent = prefs.fonte;
  tela.classList.remove("leg-p", "leg-m", "leg-g");
  tela.classList.add("leg-" + prefs.legenda);
  for (const [grupo, valor] of [["aj-tema", prefs.tema], ["aj-layout", prefs.layout], ["aj-legenda", prefs.legenda]])
    $(grupo).querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === valor)));
  $("aj-pular").checked = prefs.pularSilencio;
  $("aj-retroceder").checked = prefs.retroceder;
  $("btn-legendas").setAttribute("aria-pressed", String(prefs.legendas));
}
$("aj-tema-linha").hidden = !local;                       // no artefato, o tema é o do Claude
if (!temMidia) ["aj-layout-linha", "aj-legenda-linha"].forEach(id => { $(id).hidden = true; });
$("aj-tema").onclick = e => { const b = e.target.closest("button"); if (!b) return; prefs.tema = b.dataset.v; salvarPrefs(); aplicarPrefs(); requestAnimationFrame(desenharOnda); };
$("aj-layout").onclick = e => { const b = e.target.closest("button"); if (!b) return; prefs.layout = b.dataset.v; salvarPrefs(); aplicarPrefs(); requestAnimationFrame(desenharOnda); };
$("aj-legenda").onclick = e => { const b = e.target.closest("button"); if (!b) return; prefs.legenda = b.dataset.v; salvarPrefs(); aplicarPrefs(); };
$("aj-fonte").onclick = e => {
  const b = e.target.closest("button[data-d]"); if (!b) return;
  prefs.fonte = Math.min(22, Math.max(13, prefs.fonte + Number(b.dataset.d))); salvarPrefs(); aplicarPrefs();
};
$("aj-pular").onchange = e => { prefs.pularSilencio = e.target.checked; salvarPrefs(); };
$("aj-retroceder").onchange = e => { prefs.retroceder = e.target.checked; salvarPrefs(); };
aplicarPrefs();

/* ================= cabeçalho e menus ================= */
$("titulo").textContent = D.titulo;
for (const [texto, alerta] of D.chips) $("chips").append(el("span", { class: alerta ? "alerta" : null, text: texto }));

function fecharMenus() {
  for (const [b, m] of [["btn-exportar", "menu-exportar"], ["btn-ajustes", "ajustes"]]) {
    $(m).hidden = true; $(b).setAttribute("aria-expanded", "false");
  }
}
function alternarMenu(botao, menu) {
  const abrir = $(menu).hidden;
  fecharMenus();
  $(menu).hidden = !abrir; $(botao).setAttribute("aria-expanded", String(abrir));
}
$("btn-exportar").onclick = () => alternarMenu("btn-exportar", "menu-exportar");
$("btn-ajustes").onclick = () => alternarMenu("btn-ajustes", "ajustes");
document.addEventListener("pointerdown", e => {
  if (!e.target.closest(".ancora")) fecharMenus();
  if (!e.target.closest("#selecao")) esconderSelecao();
});

(function montarExportar() {
  $("ancora-exportar").hidden = false;
  const menu = $("menu-exportar"), item = (ic, rotulo, acao, nota) =>
    el("button", { class: "item", onclick: () => { fecharMenus(); acao(); } }, icone(ic), rotulo, nota ? el("small", { text: nota }) : null);
  if (local) {
    for (const [rotulo, nome, ic, nota] of D.arquivos)
      menu.append(el("a", { href: encodeURI(nome), download: nome.endsWith(".docx") ? nome : null }, icone(ic), rotulo, el("small", { text: nota })));
    menu.append(item("imprimir", "Imprimir ou salvar PDF", () => window.print(), "Ctrl+P"));
  }
  const transcricaoInteira = () => pars.map((p, k) => `[${hms(p.ini)}] ${rotDoPar(k) ? nomeFalante(rotDoPar(k)) + ": " : ""}${textoPar(p)}`).join("\n\n");
  menu.append(item("copiar", "Copiar a transcrição", () => copiar(transcricaoInteira(), "Transcrição copiada"), "com minutagem"));
  menu.append(item("marcar", "Copiar as marcações", () => copiarMarcas()));
  if (local) menu.append(item("editar", "Exportar revisão e marcações", () => exportarRevisao(), ".json"));
})();

/* ================= mídia ================= */
function avisoMidia(texto) { const a = $("aviso-midia"); a.hidden = false; a.textContent = texto; return a; }
// Por que a página não traz a gravação inteira: nunca atribuir ao limite de tamanho o que foi escolha.
const MOTIVOS = {
  sem_video: "Esta página foi publicada sem a gravação, por escolha de quem a preparou.",
  ausente: "A gravação original não foi encontrada ao preparar esta página: só a transcrição está disponível.",
  tamanho: "Esta página traz só o áudio: o vídeo não cabe no limite de tamanho do artefato.",
};
const MOTIVOS_SEM_MIDIA = { ...MOTIVOS, tamanho: "Esta página não traz a gravação: longa demais para o limite de tamanho do artefato." };
if (!temMidia) {
  $("midia").hidden = true; $("mesa").classList.add("sem-midia");
  $("dados").before(el("p", { class: "aviso", text: MOTIVOS_SEM_MIDIA[D.midia.motivo] || "Esta página não traz a gravação." }));
} else {
  video.src = D.midia.src;
  if (!ehVideo) {
    tela.classList.add("audio"); palcoAudio.hidden = false; $("btn-tela-cheia").hidden = true;
    if (!local && !D.midia.soAudio) avisoMidia(MOTIVOS[D.midia.motivo] || MOTIVOS.tamanho);
  }
}
video.addEventListener("error", () => {
  if (!local) { avisoMidia("Não foi possível carregar a mídia. A transcrição continua disponível ao lado."); return; }
  let dica = "";
  try {   // no Windows, o navegador não abre arquivos cujo caminho completo passa de 260 caracteres
    if (/^Win/.test(navigator.platform) && decodeURIComponent(location.pathname).length + decodeURIComponent(D.midia.src).length > 240)
      dica = " O caminho deste arquivo passa de 260 caracteres, o limite do Windows: mova a pasta das degravações para um caminho mais curto (ex.: C:\\Degravacoes) e rode `regerar`.";
  } catch { /* caminho fora do padrão */ }
  const a = avisoMidia(`Não foi possível abrir ${D.midia.nome} (o arquivo foi movido ou renomeado).${dica} Selecione-o para assistir: `);
  const entrada = el("input", { type: "file", id: "arquivo", accept: "video/*,audio/*" });
  entrada.onchange = () => { const f = entrada.files[0]; if (f) { video.src = URL.createObjectURL(f); a.hidden = true; } };
  a.append(el("br"), entrada);
});

/* Legenda própria sobre o vídeo (estilizada, com quem fala); a faixa nativa só aparece na tela cheia do iPhone. */
let trilha = null;
if (ehVideo && typeof VTTCue === "function" && video.addTextTrack) {
  trilha = video.addTextTrack("captions", "Legendas", "pt-BR");
  trilha.mode = "hidden";
  for (const [a, b, t] of D.legendas) trilha.addCue(new VTTCue(a, b, t.replace(/&/g, "&amp;").replace(/</g, "&lt;")));
  video.addEventListener("webkitbeginfullscreen", () => { trilha.mode = prefs.legendas ? "showing" : "hidden"; });
  video.addEventListener("webkitendfullscreen", () => { trilha.mode = "hidden"; });
}
function mostrarLegenda(t) {
  let i = busca(iniCues, t);
  if (i >= 0 && t > cues[i][1] + 0.6) i = -1;
  if (!prefs.legendas || !ehVideo) i = -1;
  if (i === cueAtual) return;
  cueAtual = i;
  legendaTela.textContent = "";
  if (i < 0) return;
  const [, , rotCue, textoCue, seg] = cues[i];
  // A legenda segue a revisão feita neste navegador: falante trocado e, se a frase foi editada, o texto novo inteiro.
  const rot = seg != null ? rotDoSeg(seg) : rotCue, quem = nomeFalante(rot);
  const texto = seg != null && textoSeg(seg) !== segs[seg].t ? textoSeg(seg) : textoCue;
  legendaTela.append(el("div", { class: "cue", "--cor": corLegenda(rank(rot)) }, quem ? el("b", { text: quem }) : null, texto));
}

/* ================= transcrição ================= */
const editavel = (() => { try { const d = document.createElement("div"); d.contentEditable = "plaintext-only"; return "plaintext-only"; } catch { return "true"; } })();

function pintar(i, comPalavras) {   // texto da frase; separa as palavras para o destaque ou para sublinhar as duvidosas
  const s = segs[i], e = elems[i];
  if (!e) return;
  e._w = null;
  const ed = revisao.textos[i], texto = textoSeg(i), editado = texto !== s.t, conflito = editado && ed.o !== s.t;
  if (editado) e.title = conflito ? "Corrigido neste navegador, mas a frase mudou no documento depois disso: confira antes de exportar"
    : "Corrigido neste navegador; ainda não aplicado ao documento";
  else if (s.c) e.title = "Corrigido na revisão." + (s.o ? ` Transcrição original: “${s.o}”` : "");
  else e.removeAttribute("title");
  e.classList.toggle("conflito", conflito);
  if (s.w && !editado && !revisando && (comPalavras || s.d)) {
    const duvidas = new Set(s.d || []);
    e.textContent = "";
    e._w = s.w.map((w, n) => {
      const p = el("span", { class: duvidas.has(n) ? "duvida" : null, text: w[2].trimStart() });
      if (n && /^\s/.test(w[2])) e.append(" ");
      e.append(p);
      return p;
    });
  } else e.textContent = texto;
  e.classList.toggle("editada", editado);
}
function rotuloFalante(p, k) {
  const rot = rotDoPar(k), nome = nomeFalante(rot);
  if (!rot) return null;
  if (revisando) {
    const sel = el("select", { class: "falante", "--cor": cor(rank(rot)), "data-k": k, "aria-label": "Falante deste parágrafo", title: nome });
    for (const f of falantesDisponiveis()) sel.append(el("option", { value: f.rot, text: f.nome, selected: f.rot === rot }));
    sel.append(el("option", { value: "__novo", text: "+ Novo falante" }));
    return sel;
  }
  const troca = trocaDoPar(k), trocado = troca != null && troca.rot !== p.rot;
  const situacao = trocado ? "falante trocado nesta revisão" : p.rev ? "atribuição revista depois da separação automática"
    : p.inc ? "falante a conferir (frase curta ou troca rápida)" : "separação automática pela voz";
  return el("span", {
    class: "falante" + (p.inc && !trocado ? " incerto" : "") + (p.rev || trocado ? " revisto" : ""), "--cor": cor(rank(rot)),
    text: nome, title: `${nome} · ${situacao}`,
  });
}
function montarParagrafo(p, k) {
  const fala = el("p", { class: "fala" }, rotuloFalante(p, k));
  for (const i of p.segs) {
    const s = segs[i];
    const span = el("span", { class: "seg" + (s.b && !s.d ? " baixa" : "") + (s.c ? " corrigida" : ""), "data-i": i });
    if (revisando) { span.setAttribute("contenteditable", editavel); span.spellcheck = true; span.lang = "pt-BR"; }
    elems[i] = span;
    pintar(i);
    fala.append(span, " ");
  }
  const linha = el("div", { class: "par", "data-k": k },
    el("button", { class: "ts", "data-t": p.ini, title: "Ouvir a partir daqui", text: hms(p.ini) }), fala,
    el("div", { class: "acoes-par" },
      el("button", { class: "acao", "data-acao": "marcar", title: "Marcar o parágrafo", "aria-label": "Marcar o parágrafo" }, icone("marcar")),
      el("button", { class: "acao", "data-acao": "copiar", title: "Copiar com minutagem e falante", "aria-label": "Copiar o parágrafo" }, icone("copiar"))));
  parEls[k] = linha;
  return linha;
}
function renderTranscricao() {
  const lista = document.createDocumentFragment();
  pars.forEach((p, k) => lista.append(montarParagrafo(p, k)));
  $("transcricao").replaceChildren(lista);
  if (!pars.length) $("transcricao").append(el("p", { class: "vazio", text: "Nenhuma fala foi detectada nesta gravação." }));
  atual = -1; palavraAtiva = null;
  aplicarMarcasNoTexto();
  aplicarFiltro(filtro);
  if ($("busca").value.trim()) buscar();
}
function refazerParagrafo(k) {
  parEls[k].replaceWith(montarParagrafo(pars[k], k));
  aplicarMarcasNoTexto();
  if (atual >= 0 && parDeSeg[atual] === k) elems[atual].classList.add("atual");
}

const citacaoPar = (p, k) => `[${hms(p.ini)}] ${rotDoPar(k) ? nomeFalante(rotDoPar(k)) + ": " : ""}“${textoPar(p)}”`;
document.addEventListener("click", e => {   // um só ouvinte: minutagens (em qualquer aba), ações dos parágrafos, frases
  const ts = e.target.closest("button.ts[data-t]");
  if (ts) { ir(Number(ts.dataset.t)); ts.blur(); return; }   // sem foco no botão, Espaço volta a reproduzir/pausar
  const acao = e.target.closest(".acao[data-acao]");
  if (acao) {
    const k = Number(acao.closest(".par").dataset.k), p = pars[k];
    if (acao.dataset.acao === "copiar") copiar(citacaoPar(p, k), "Parágrafo copiado com minutagem");
    else criarMarca(p.segs[0], p.segs[p.segs.length - 1], textoPar(p));
    acao.blur();
    return;
  }
  if (revisando) return;
  const s = e.target.closest("#transcricao .seg");
  if (s && getSelection().isCollapsed) ir(segs[s.dataset.i].ini, true, Number(s.dataset.i));
});
document.addEventListener("dblclick", e => {   // dois cliques numa palavra: o instante exato em que ela é dita
  const s = e.target.closest("#transcricao .seg");
  if (!s || revisando || !temMidia) return;
  const i = Number(s.dataset.i), w = segs[i].w, sel = getSelection();
  if (!w || textoSeg(i) !== segs[i].t || !sel.rangeCount) return;
  if (!s.contains(sel.anchorNode)) return;
  const r = document.createRange();
  r.setStart(s, 0); r.setEnd(sel.anchorNode, sel.anchorOffset);
  const pos = r.toString().length;
  let acum = 0, n = 0;
  for (; n < w.length; n++) { acum += (n ? w[n][2] : w[n][2].trimStart()).length; if (acum > pos) break; }
  sel.removeAllRanges();
  ir(w[Math.min(n, w.length - 1)][0], true, i);
});

/* ================= sincronia ================= */
function marcarPalavra(p) { if (p === palavraAtiva) return; palavraAtiva?.classList.remove("palavra"); p?.classList.add("palavra"); palavraAtiva = p; }
function palavraEm(i, t) {
  const w = segs[i].w;
  if (!elems[i]._w) pintar(i, true);
  if (!elems[i]._w) return;
  let lo = 0, hi = w.length - 1, n = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (w[m][0] <= t) { n = m; lo = m + 1; } else hi = m - 1; }
  marcarPalavra(n >= 0 ? elems[i]._w[n] : null);
}
function mostrarAgora(i, t) {
  const top = topicoEm(t), rot = rotDoSeg(i), quem = nomeFalante(rot), r = rank(rot);
  $("agora-topico").textContent = top ? top.txt : "";
  const a = $("agora-texto");
  a.textContent = "";
  a.style.setProperty("--cor", cor(r));
  if (quem) a.append(el("b", { text: quem + ": " }));
  a.append(textoSeg(i));
  if (!ehVideo) {
    palcoFalante.textContent = quem;
    palcoFalante.style.setProperty("--cor", cor(r));
    palcoTexto.textContent = textoSeg(i);
  }
  marcarTopico(top);
}
function rolarAte(e, forcar) {
  // Os parágrafos usam content-visibility:auto, com altura estimada enquanto não são desenhados: numa rolagem suave
  // para longe, o navegador mira a estimativa e para no lugar errado. Salto longo (ou logo depois de um seek) vai sem animação.
  const r = e.getBoundingClientRect(), longe = r.bottom < -innerHeight * 1.5 || r.top > innerHeight * 2.5;
  e.scrollIntoView({ block: "center", behavior: reduzir || forcar || longe ? "auto" : "smooth" });
}
function atualizarTempo(t) {
  const pct = Math.min(100, 100 * t / duracao()) + "%";
  $("cabeca").style.left = pct;
  $("lt-tocado").style.width = pct;
  if (Math.floor(t) !== ultimoSegundo) {
    ultimoSegundo = Math.floor(t);
    $("tempo-atual").textContent = hms(t);
    lt.setAttribute("aria-valuenow", ultimoSegundo);
    lt.setAttribute("aria-valuetext", hms(t));
  }
}
function sincronizar() {
  const t = video.currentTime;
  if (repetir >= 0 && segs[repetir] && t >= segs[repetir].fim + 0.12) { video.currentTime = segs[repetir].ini; return; }
  if (prefs.pularSilencio && !video.paused && repetir < 0 && segs.length) {   // salta pausas longas entre falas
    const j = busca(inicios, t), prox = j + 1 < segs.length ? segs[j + 1].ini : null;
    const fora = j < 0 || t > segs[j].fim + 0.4;
    if (prox != null && fora && prox - t > 1.5) { video.currentTime = prox - 0.35; return; }
  }
  atualizarTempo(t);
  mostrarLegenda(t);
  const i = busca(inicios, t);
  if (i !== atual) {
    if (atual >= 0 && elems[atual]) elems[atual].classList.remove("atual");
    marcarPalavra(null);
    atual = i;
    if (i >= 0 && elems[i]) {
      elems[i].classList.add("atual");
      mostrarAgora(i, t);
      if ($("seguir").checked && Date.now() > pausaSeguir && !$("p-transcricao").hidden && !parEls[parDeSeg[i]].hidden && !revisando)
        rolarAte(elems[i], Date.now() < pularSuave);
    }
  }
  if (i >= 0 && !buscaAtiva && !revisando && segs[i].w && textoSeg(i) === segs[i].t) palavraEm(i, t);
  if (Math.abs(t - ultimoSalvo) > 5) { ultimoSalvo = t; loja.gravar(CHAVE + ":posicao", t); }
}
let laco = 0;
const quadro = () => { sincronizar(); laco = requestAnimationFrame(quadro); };
function estadoPlay(tocando) {
  trocarIcone($("btn-play"), tocando ? "pause" : "play");
  $("btn-play").setAttribute("aria-label", tocando ? "Pausar" : "Reproduzir");
  $("btn-play").title = (tocando ? "Pausar" : "Reproduzir") + " (espaço)";
}
video.addEventListener("play", () => {
  if (prefs.retroceder && pausadoEm && Date.now() - pausadoEm > 1500 && video.currentTime > 3) video.currentTime -= 2;
  pausadoEm = 0;
  telaPlay.hidden = true;
  estadoPlay(true);
  cancelAnimationFrame(laco); laco = requestAnimationFrame(quadro);
});
video.addEventListener("pause", () => {
  pausadoEm = Date.now(); estadoPlay(false); cancelAnimationFrame(laco);
  loja.gravar(CHAVE + ":posicao", video.currentTime);
});
video.addEventListener("timeupdate", sincronizar);
video.addEventListener("seeked", () => { pularSuave = Date.now() + 800; sincronizar(); });
for (const ev of ["wheel", "touchmove"])   // rolar à mão pausa o acompanhamento por alguns segundos
  $("p-transcricao").addEventListener(ev, () => { pausaSeguir = Date.now() + 5000; }, { passive: true });

/* ================= controles ================= */
function ir(t, tocar = true, seg) {
  if (!temMidia) return;
  if (repetir >= 0) definirRepetir(seg ?? Math.max(0, busca(inicios, t + 0.05)));
  pularSuave = Date.now() + 1000;   // a transcrição salta junto, sem animação
  video.currentTime = Math.max(0, Math.min(t, duracao() - 0.05));
  if (tocar) video.play().catch(() => {});
}
const alternar = () => (video.paused ? video.play().catch(() => {}) : video.pause());
const pular = d => { video.currentTime = Math.max(0, Math.min(video.currentTime + d, duracao())); };
$("btn-play").onclick = alternar;
telaPlay.onclick = alternar;
video.addEventListener("click", alternar);
video.addEventListener("dblclick", () => telaCheia());
$("btn-voltar").onclick = () => pular(-5);
$("btn-avancar").onclick = () => pular(5);

const velocidades = [...$("velocidade").options].map(o => Number(o.value));
function definirVelocidade(v) {
  video.playbackRate = v; prefs.velocidade = v; salvarPrefs();
  $("velocidade").value = String(v);
}
function mudarVelocidade(d) {
  const i = velocidades.indexOf(video.playbackRate);
  const v = velocidades[Math.min(velocidades.length - 1, Math.max(0, (i < 0 ? 2 : i) + d))];
  definirVelocidade(v); aviso(`Velocidade ${String(v).replace(".", ",")}×`);
}
$("velocidade").onchange = e => { definirVelocidade(Number(e.target.value)); e.target.blur(); };

function definirVolume(v, mudo) {
  video.volume = v; video.muted = mudo; prefs.volume = v; prefs.mudo = mudo; salvarPrefs();
  $("volume").value = String(mudo ? 0 : v);
  trocarIcone($("btn-som"), mudo || v === 0 ? "mudo" : "som");
  $("btn-som").setAttribute("aria-label", mudo ? "Ativar o som" : "Silenciar");
}
$("volume").oninput = e => definirVolume(Number(e.target.value), Number(e.target.value) === 0);
$("btn-som").onclick = () => definirVolume(prefs.volume || 1, !video.muted);

function alternarLegendas() {
  prefs.legendas = !prefs.legendas; salvarPrefs(); cueAtual = -2; aplicarPrefs();
  sincronizar();
  aviso(prefs.legendas ? "Legendas ligadas" : "Legendas desligadas");
}
$("btn-legendas").onclick = alternarLegendas;
if (!ehVideo) $("btn-legendas").hidden = true;

async function telaCheia() {
  if (!ehVideo) return;
  if (document.fullscreenElement) { await document.exitFullscreen().catch(() => {}); return; }
  const midia = $("midia");
  if (midia.requestFullscreen) { try { await midia.requestFullscreen(); return; } catch { /* tenta o nativo */ } }
  if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();   // iPhone
}
$("btn-tela-cheia").onclick = telaCheia;
document.addEventListener("fullscreenchange", () => {
  const em = !!document.fullscreenElement;
  trocarIcone($("btn-tela-cheia"), em ? "sair-tela" : "tela-cheia");
  $("btn-tela-cheia").setAttribute("aria-label", em ? "Sair da tela cheia" : "Tela cheia");
  requestAnimationFrame(desenharOnda);
});

/* Janela flutuante: com Document Picture-in-Picture, leva o vídeo e a legenda (dá para assistir enquanto escreve). */
const pipDocumento = "documentPictureInPicture" in window;
if (!pipDocumento && !(ehVideo && document.pictureInPictureEnabled)) $("btn-pip").hidden = true;
async function abrirPip() {
  if (janelaPip) { janelaPip.close(); return; }
  if (pipDocumento) {
    try {
      const w = await documentPictureInPicture.requestWindow({ width: ehVideo ? 560 : 440, height: ehVideo ? 330 : 190 });
      document.querySelectorAll("style, link[rel=stylesheet]").forEach(n => w.document.head.append(n.cloneNode(true)));
      const raiz = w.document.documentElement;
      if (document.documentElement.dataset.theme) raiz.dataset.theme = document.documentElement.dataset.theme;
      raiz.style.cssText = document.documentElement.style.cssText;
      w.document.title = D.titulo;
      w.document.body.className = "pip";
      const lugar = document.createComment("tela");
      tela.before(lugar);
      w.document.body.append(tela);
      w.document.addEventListener("keydown", e => { if (e.key === " ") { e.preventDefault(); alternar(); } });
      janelaPip = w;
      $("btn-pip").setAttribute("aria-pressed", "true");
      w.addEventListener("pagehide", () => {
        lugar.replaceWith(tela); janelaPip = null;
        $("btn-pip").setAttribute("aria-pressed", "false");
      });
      return;
    } catch { /* cai na janela flutuante só do vídeo */ }
  }
  if (ehVideo && document.pictureInPictureEnabled) {
    try {
      if (document.pictureInPictureElement) await document.exitPictureInPicture();
      else await video.requestPictureInPicture();
    } catch { aviso("O navegador não abriu a janela flutuante."); }
  }
}
$("btn-pip").onclick = abrirPip;

function definirRepetir(v) { repetir = v; $("btn-repetir").setAttribute("aria-pressed", String(v >= 0)); }
function alternarRepetir() {
  if (!segs.length) return;
  definirRepetir(repetir >= 0 ? -1 : Math.max(0, atual >= 0 ? atual : busca(inicios, video.currentTime)));
  if (repetir >= 0) { ir(segs[repetir].ini, true, repetir); aviso("Repetindo a frase. Tecle R para parar."); }
}
$("btn-repetir").onclick = alternarRepetir;
function proximoConferir() {
  if (!conferir.length) return;
  const i = conferir.find(j => segs[j].ini > video.currentTime + 1.5) ?? conferir[0];
  abrirAba("transcricao");
  if (parEls[parDeSeg[i]].hidden) aplicarFiltro(null);
  pausaSeguir = Date.now() + 1500;
  elems[i].scrollIntoView({ block: "center" });
  ir(Math.max(0, segs[i].ini - 1), true, i);
}
if (conferir.length) {
  $("txt-proximo").textContent = `A conferir (${conferir.length})`;
  $("btn-proximo").onclick = proximoConferir;
} else $("btn-proximo").hidden = true;
function marcarAtual() {
  if (!segs.length) return;
  const i = atual >= 0 ? atual : busca(inicios, video.currentTime);
  if (i >= 0) criarMarca(i, i, textoSeg(i));
}
$("btn-marcar-atual").onclick = marcarAtual;
if (!segs.length) $("btn-repetir").hidden = $("btn-marcar-atual").hidden = true;
$("btn-copiar-ts").onclick = () => copiar(hms(video.currentTime), `Minutagem ${hms(video.currentTime)} copiada`);

/* ================= linha do tempo: forma de onda colorida por falante ================= */
const picos = D.picos.length ? D.picos : (() => {   // degravação antiga, sem forma de onda: blocos onde há fala
  const n = 600, a = new Array(n).fill(3);
  for (const s of segs) for (let x = Math.floor(s.ini / duracao() * n); x < Math.min(n, Math.ceil(s.fim / duracao() * n)); x++) a[x] = 45;
  return a;
})();
function falanteEm(t) {
  const i = busca(inicios, t);
  return i < 0 || t > segs[i].fim + 1 ? -1 : rank(rotDoSeg(i));
}
let tOnda = 0;
function desenharOnda() {
  const w = lt.clientWidth, h = lt.clientHeight, dpr = window.devicePixelRatio || 1;
  if (!w || !h) return;
  lt.style.setProperty("--largura-lt", w + "px");
  const estilo = getComputedStyle(lt), tok = n => estilo.getPropertyValue(n).trim();
  const cores = [tok("--caneta"), 1, 2, 3, 4, 5, 6].map((c, n) => n ? tok("--f" + c) : c);
  const base = tok("--onda-base");
  const barras = Math.max(60, Math.floor(w / 3)), passo = w / barras, meio = h / 2, alt = h - 16;
  const colunas = [];
  for (let b = 0; b < barras; b++) {
    const i0 = Math.floor(b / barras * picos.length), i1 = Math.max(i0 + 1, Math.floor((b + 1) / barras * picos.length));
    let v = 0;
    for (let i = i0; i < i1; i++) v = Math.max(v, picos[i]);
    colunas.push([Math.max(2, v / 100 * alt), falanteEm((b + 0.5) / barras * duracao())]);
  }
  for (const [canvas, tocado] of [[$("onda"), false], [$("onda-tocada"), true]]) {
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    canvas.style.width = w + "px"; canvas.style.height = h + "px";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    colunas.forEach(([a, r], b) => {
      const corBarra = r > 0 ? cores[(r - 1) % 6 + 1] : r === 0 ? cores[0] : base;
      ctx.fillStyle = tocado ? corBarra : (r >= 0 ? corBarra : base);
      ctx.globalAlpha = tocado ? 1 : (r >= 0 ? 0.3 : 0.55);
      const x = b * passo + 0.5, larg = Math.max(1, passo - 1.2);
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, meio - a / 2, larg, a, Math.min(1.5, larg / 2)); else ctx.rect(x, meio - a / 2, larg, a);
      ctx.fill();
    });
  }
}
const pedirOnda = () => { cancelAnimationFrame(tOnda); tOnda = requestAnimationFrame(desenharOnda); };
if ("ResizeObserver" in window) {
  new ResizeObserver(pedirOnda).observe(lt);
  // Em telas estreitas a mídia fica fixa no alto: a rolagem até a frase precisa descontar a altura dela.
  new ResizeObserver(() => document.documentElement.style.setProperty("--altura-midia", $("midia").offsetHeight + "px")).observe($("midia"));
} else window.addEventListener("resize", pedirOnda);
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", pedirOnda);
// O claude.ai troca o tema pelo atributo data-theme da página: as cores da onda são lidas na hora de desenhar.
new MutationObserver(pedirOnda).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class", "style"] });

function desenharMarcos() {
  const camada = $("lt-marcos"), pct = t => Math.min(100, 100 * t / duracao()) + "%";
  camada.textContent = "";
  for (const x of D.topicos) camada.append(el("div", { class: "m-topico", style: `left:${pct(x.t)}` }));
  for (const i of conferir) camada.append(el("div", { class: "m-conferir", style: `left:${pct(segs[i].ini)}` }));
  for (const m of marcas)
    camada.append(el("div", { class: "m-marca", "--mc": corMarca(m.cat), style: `left:${pct(m.ini)};width:${Math.max(0.4, 100 * (m.fim - m.ini) / duracao())}%` }));
  for (const x of D.pontos) camada.append(el("div", { class: "m-ponto", style: `left:${pct(x.t)}` }));
}
const tempoNo = e => { const r = lt.getBoundingClientRect(); return Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * duracao(); };
function mostrarDica(e) {
  const r = lt.getBoundingClientRect(), t = tempoNo(e), tol = duracao() * 7 / r.width;
  const ponto = D.pontos.find(x => Math.abs(x.t - t) <= tol), marca = marcas.find(m => t >= m.ini - tol && t <= m.fim + tol);
  const i = busca(inicios, t), top = topicoEm(t);
  const d = $("dica");
  d.hidden = false; d.textContent = "";
  d.append(el("b", { text: hms(t) + (top ? " · " + top.txt : "") }));
  let texto = "";
  if (ponto) texto = "Ponto de atenção: " + ponto.txt;
  else if (marca) texto = `${nomeCat(marca.cat)}: “${marca.texto}”`;
  else if (i >= 0 && t <= segs[i].fim + 1) texto = (rotDoSeg(i) ? nomeFalante(rotDoSeg(i)) + ": " : "") + textoSeg(i);
  if (texto) d.append(el("span", { text: texto }));
  const w = d.offsetWidth, x = e.clientX - r.left;
  d.style.left = Math.min(Math.max(x, w / 2), r.width - w / 2) + "px";
}
let arrastando = false;
lt.addEventListener("pointerdown", e => { arrastando = true; lt.setPointerCapture(e.pointerId); ir(tempoNo(e), false); });
lt.addEventListener("pointermove", e => { mostrarDica(e); if (arrastando) ir(tempoNo(e), false); });
lt.addEventListener("pointerup", () => { arrastando = false; });
lt.addEventListener("pointerleave", () => { $("dica").hidden = true; });

function montarLegendaLt() {
  const L = $("legenda-lt"), item = (classe, texto, r) => {
    const a = el("i", { class: "amostra " + classe, "--cor": r != null ? cor(r) : null });
    L.append(el("span", {}, a, texto));
  };
  L.textContent = "";
  for (const f of falantesDisponiveis()) item("", f.nome, rank(f.rot));
  if (D.topicos.length) item("topico", "tópico");
  if (D.pontos.length) item("ponto", "ponto de atenção");
  if (conferir.length) item("conferir", "a conferir");
}

/* ================= busca, filtros e sumário ================= */
let achados = [], pos = -1, tBusca = 0, buscaPendente = false;
function buscar() {
  buscaPendente = false;
  const q = norm($("busca").value.trim());
  achados = []; pos = -1; buscaAtiva = !!q; marcarPalavra(null);
  const marcasLt = document.createDocumentFragment();
  elems.forEach((e, i) => {
    if (!q) { pintar(i); return; }
    const t = textoSeg(i), alvo = norm(t);
    let saida = "", k = 0, idx;
    while ((idx = alvo.indexOf(q, k)) !== -1) { saida += esc(t.slice(k, idx)) + "<mark>" + esc(t.slice(idx, idx + q.length)) + "</mark>"; k = idx + q.length; }
    e._w = null;
    if (k === 0) { e.textContent = t; return; }
    e.innerHTML = saida + esc(t.slice(k));
    if (parEls[parDeSeg[i]].hidden) return;
    achados.push(...e.querySelectorAll("mark"));
    marcasLt.append(el("div", { class: "m-busca", style: `left:${Math.min(100, 100 * segs[i].ini / duracao())}%` }));
  });
  $("lt-busca").replaceChildren(marcasLt);
  $("contagem").textContent = q ? (achados.length ? `${achados.length}` : "0") : "";
  $("contagem").title = q ? `${achados.length} ocorrência(s)` : "";
  if (achados.length) { $("seguir").checked = false; irAchado(1); }
}
function irAchado(d) {
  if (buscaPendente) { clearTimeout(tBusca); buscar(); return; }
  if (!achados.length) return;
  achados[pos]?.classList.remove("foco");
  pos = pos < 0 ? 0 : (pos + d + achados.length) % achados.length;
  achados[pos].classList.add("foco");
  achados[pos].scrollIntoView({ block: "center" });
  $("contagem").textContent = `${pos + 1}/${achados.length}`;
}
function limparBusca() { if ($("busca").value) { $("busca").value = ""; buscar(); } }
$("busca").addEventListener("input", () => { buscaPendente = true; clearTimeout(tBusca); tBusca = setTimeout(buscar, 160); });
$("busca").addEventListener("keydown", e => {
  if (e.key === "Enter") { e.preventDefault(); irAchado(e.shiftKey ? -1 : 1); }
  else if (e.key === "Escape") { limparBusca(); $("busca").blur(); }
});
$("busca-prox").onclick = () => irAchado(1);
$("busca-ant").onclick = () => irAchado(-1);

function montarFiltros() {
  const caixa = $("filtros"), opcoes = [[null, "Tudo"]];
  const falantes = falantesDisponiveis();
  if (falantes.length > 1) for (const f of falantes) opcoes.push([f.rot, f.nome]);
  if (conferir.length) opcoes.push(["conferir", `A conferir (${conferir.length})`]);
  if (marcas.length) opcoes.push(["marcados", `Marcados (${marcas.length})`]);
  caixa.textContent = "";
  caixa.hidden = opcoes.length < 2;
  for (const [v, nome] of opcoes) {
    const b = el("button", { class: "filtro", "data-v": String(v), "aria-pressed": String(v === filtro), title: nome,
                             onclick: () => { aplicarFiltro(v); b.blur(); } });
    if (v && v.startsWith?.("F")) b.append(el("i", { class: "amostra", "--cor": cor(rank(v)) }));
    b.append(el("span", { text: nome }));
    caixa.append(b);
  }
  if (filtro !== null && !opcoes.some(o => o[0] === filtro)) aplicarFiltro(null);
}
function aplicarFiltro(v) {
  filtro = v;
  pars.forEach((p, k) => {
    let mostrar = true;
    if (v === "conferir") mostrar = p.b;
    else if (v === "marcados") mostrar = p.segs.some(i => elems[i]?.classList.contains("marcada"));
    else if (v !== null) mostrar = rotDoPar(k) === v;
    if (parEls[k]) parEls[k].hidden = !mostrar;
  });
  $("filtros").querySelectorAll(".filtro").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === String(v))));
  if (buscaAtiva) buscar();
}

let topicoAtual = null;
function montarSumario() {
  if (!D.topicos.length) return;
  const nav = $("sumario");
  nav.hidden = false;
  D.topicos.forEach((x, n) => nav.append(el("button", { "data-n": n, title: x.txt, onclick: e => { ir(x.t); e.currentTarget.blur(); } },
                                            el("i", { text: hms(x.t) }), el("span", { text: x.txt }))));
}
function marcarTopico(top) {
  if (top === topicoAtual || !D.topicos.length) return;
  topicoAtual = top;
  const n = top ? D.topicos.indexOf(top) : -1, nav = $("sumario");
  nav.querySelectorAll("button").forEach(b => {
    const ativo = Number(b.dataset.n) === n;
    b.classList.toggle("atual", ativo);
    if (ativo) {   // só o sumário rola, na horizontal: a página (celular) fica onde o usuário a deixou
      const x = b.getBoundingClientRect().left - nav.getBoundingClientRect().left + nav.scrollLeft;
      nav.scrollTo({ left: x - nav.clientWidth / 2 + b.offsetWidth / 2, behavior: reduzir ? "auto" : "smooth" });
    }
  });
}

/* ================= seleção: citar ou marcar ================= */
function lerSelecao() {
  const sel = getSelection();
  if (!sel.rangeCount || sel.isCollapsed) return null;
  const r = sel.getRangeAt(0);
  if (!$("transcricao").contains(r.commonAncestorContainer)) return null;
  const partes = [];
  let de = -1, ate = -1;
  for (const linha of parEls) {
    if (!linha || linha.hidden || !r.intersectsNode(linha)) continue;
    const fala = linha.querySelector(".fala"), x = document.createRange();
    x.selectNodeContents(fala);
    if (r.compareBoundaryPoints(Range.START_TO_START, x) > 0) x.setStart(r.startContainer, r.startOffset);
    if (r.compareBoundaryPoints(Range.END_TO_END, x) < 0) x.setEnd(r.endContainer, r.endOffset);
    const copia = x.cloneContents();
    copia.querySelectorAll(".falante").forEach(n => n.remove());
    const texto = copia.textContent.replace(/\s+/g, " ").trim();
    const its = [...fala.querySelectorAll(".seg")].filter(s => r.intersectsNode(s)).map(s => Number(s.dataset.i));
    if (!texto || !its.length) continue;
    const k = Number(linha.dataset.k);
    partes.push({ k, texto, ini: segs[its[0]].ini, fim: segs[its[its.length - 1]].fim });
    if (de < 0) de = its[0];
    ate = its[its.length - 1];
  }
  return partes.length ? { partes, de, ate } : null;
}
function citacaoSelecao({ partes }) {
  const ini = hms(partes[0].ini), fim = hms(partes[partes.length - 1].fim), quando = ini === fim ? ini : `${ini}–${fim}`;
  const nomes = [...new Set(partes.map(x => nomeFalante(rotDoPar(x.k))).filter(Boolean))];
  if (nomes.length <= 1) return `“${partes.map(x => x.texto).join(" ")}” (${nomes.length ? nomes[0] + ", " : ""}${quando})`;
  return `Trecho de ${quando}:\n` + partes.map(x => `${nomeFalante(rotDoPar(x.k)) || "—"}: “${x.texto}”`).join("\n");
}
function esconderSelecao() { $("selecao").hidden = true; }
function mostrarSelecao() {
  if (revisando) { esconderSelecao(); return; }
  selecao = lerSelecao();
  if (!selecao) { esconderSelecao(); return; }
  const r = getSelection().getRangeAt(0).getBoundingClientRect(), caixa = $("selecao");
  caixa.hidden = false;
  const w = caixa.offsetWidth, h = caixa.offsetHeight;
  caixa.style.left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), innerWidth - w - 8) + "px";
  caixa.style.top = (r.top > h + 18 ? r.top - h - 10 : Math.min(r.bottom + 10, innerHeight - h - 8)) + "px";
}
let tSelecao = 0;
document.addEventListener("selectionchange", () => { clearTimeout(tSelecao); tSelecao = setTimeout(mostrarSelecao, 220); });
$("selecao").addEventListener("mousedown", e => e.preventDefault());   // clicar não desfaz a seleção
$("sel-citar").onclick = () => { if (selecao) copiar(citacaoSelecao(selecao), "Citação copiada com minutagem"); esconderSelecao(); };
for (const [id, nome] of CATS) {
  $("sel-cats").append(el("button", {
    "--mc": corMarca(id), title: nome, "aria-label": "Marcar como " + nome,
    onclick: () => {
      if (!selecao) return;
      criarMarca(selecao.de, selecao.ate, selecao.partes.map(x => x.texto).join(" "), id);
      getSelection().removeAllRanges(); esconderSelecao();
    },
  }));
}
for (const alvo of [window, $("p-transcricao")]) alvo.addEventListener("scroll", esconderSelecao, { passive: true });

/* ================= marcações ================= */
const quemDe = m => nomeFalante(rotDoSeg(m.de));
const quandoDe = m => hms(m.ini) + (Math.floor(m.fim) > Math.floor(m.ini) ? "–" + hms(m.fim) : "");
const citacaoMarca = m => `“${m.texto}” (${quemDe(m) ? quemDe(m) + ", " : ""}${quandoDe(m)})${m.nota ? `\nNota: ${m.nota}` : ""}`;
function salvarMarcas(rerender = true) {
  loja.gravar(CHAVE + ":marcas", { base: D.revisaoEm, itens: marcas });
  if (rerender) atualizarMarcas();
}
function criarMarca(de, ate, texto, cat = "relevante") {
  if (de > ate) [de, ate] = [ate, de];
  const m = { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), de, ate, ini: segs[de].ini, fim: segs[ate].fim,
              cat, nota: "", texto: texto.replace(/\s+/g, " ").trim() };
  marcas.push(m);
  marcas.sort((a, b) => a.ini - b.ini);
  salvarMarcas();
  aviso(`Marcado como ${nomeCat(cat)} (${hms(m.ini)})`, () => abrirAba("marcacoes"), "Ver marcações");
}
function removerMarca(m) {
  const n = marcas.indexOf(m);
  marcas.splice(n, 1);
  salvarMarcas();
  aviso("Marcação removida", () => { marcas.splice(n, 0, m); salvarMarcas(); }, "Desfazer");
}
function copiarMarcas() {
  if (!marcas.length) { aviso("Ainda não há marcações."); return; }
  copiar(marcas.map(m => `[${quandoDe(m)}] ${nomeCat(m.cat)} — ${quemDe(m) ? quemDe(m) + ": " : ""}“${m.texto}”${m.nota ? ` — ${m.nota}` : ""}`).join("\n"),
         `${marcas.length} marcaç${marcas.length > 1 ? "ões copiadas" : "ão copiada"}`);
}
$("marcas-copiar").onclick = copiarMarcas;
function aplicarMarcasNoTexto() {
  for (const e of elems) if (e) { e.classList.remove("marcada"); e.style.removeProperty("--mc"); }
  for (const m of marcas) for (let i = m.de; i <= m.ate; i++) {
    if (!elems[i]) continue;
    elems[i].classList.add("marcada");
    elems[i].style.setProperty("--mc", corMarca(m.cat));
  }
}
function renderListaMarcas() {
  const lista = $("lista-marcas"), n = marcas.length;
  lista.textContent = "";
  $("cont-marcas").hidden = !n;
  $("cont-marcas").textContent = n;
  $("p-marcacoes").classList.toggle("vazio", !n);
  $("marcas-copiar").disabled = !n;
  $("marcas-ajuda").textContent = n ? `${n} marcaç${n > 1 ? "ões" : "ão"}, pela ordem da gravação.` + (local ? " Ficam guardadas neste navegador; exporte para levá-las ao documento e ao Word." : "")
    : "Marque os trechos que vão para a peça: confissões, contradições, datas, valores.";
  if (!n) {
    lista.append(el("div", { class: "vazio", html: "Nenhuma marcação ainda. <b>Selecione um trecho</b> na transcrição e escolha uma cor, use o marcador ao lado de cada parágrafo ou tecle <kbd>M</kbd> durante a reprodução para marcar a frase atual." }));
    return;
  }
  for (const m of marcas) {
    const sel = el("select", { class: "marca-cat", "aria-label": "Categoria da marcação" });
    for (const [id, nome] of CATS) sel.append(el("option", { value: id, text: nome, selected: id === m.cat }));
    const nota = el("textarea", { rows: 1, placeholder: "Nota (ex.: usar nas razões finais)", "aria-label": "Nota", value: m.nota || "" });
    const cartao = el("article", { class: "marca", "--mc": corMarca(m.cat) },
      el("div", { class: "marca-cab" }, sel,
        el("button", { class: "ts", "data-t": m.ini, text: quandoDe(m) }),
        quemDe(m) ? el("span", { class: "marca-quem", text: quemDe(m) }) : null,
        el("div", { class: "marca-acoes" },
          el("button", { class: "acao", title: "Copiar como citação", "aria-label": "Copiar como citação", onclick: () => copiar(citacaoMarca(m), "Citação copiada") }, icone("copiar")),
          el("button", { class: "acao", title: "Remover a marcação", "aria-label": "Remover a marcação", onclick: () => removerMarca(m) }, icone("lixo")))),
      el("blockquote", { text: `“${m.texto}”` }), nota);
    sel.onchange = () => { m.cat = sel.value; cartao.style.setProperty("--mc", corMarca(m.cat)); salvarMarcas(false); aplicarMarcasNoTexto(); desenharMarcos(); };
    nota.oninput = () => { m.nota = nota.value; clearTimeout(nota._t); nota._t = setTimeout(() => salvarMarcas(false), 400); };
    lista.append(cartao);
  }
}
function atualizarMarcas() { aplicarMarcasNoTexto(); desenharMarcos(); renderListaMarcas(); montarFiltros(); }

/* ================= revisão (só no player local): texto, falantes e nomes ================= */
function salvarRevisao() { loja.gravar(CHAVE + ":revisao", revisao); contarRevisao(); }
function contarRevisao() {
  const n = Object.keys(revisao.textos).length + Object.keys(revisao.falantes).length + Object.keys(revisao.nomes).length;
  $("cont-revisao").hidden = !n;
  $("cont-revisao").textContent = n;
  return n;
}
let filtroGuardado = null;   // a revisão mostra a transcrição inteira; o filtro volta ao concluir
function alternarRevisao(ligar) {
  revisando = ligar;
  document.body.classList.toggle("revisando", ligar);
  $("faixa-revisao").hidden = !ligar;
  $("barra-busca").hidden = ligar;
  $("btn-revisar").setAttribute("aria-pressed", String(ligar));
  if (ligar) { limparBusca(); abrirAba("transcricao"); definirRepetir(-1); filtroGuardado = filtro; filtro = null; }
  renderTranscricao();
  renderFicha();
  if (!ligar && filtroGuardado) { aplicarFiltro(filtroGuardado); filtroGuardado = null; }
  if (!ligar && contarRevisao()) aviso("Revisão guardada neste navegador.", exportarRevisao, "Exportar agora");
}
$("btn-revisar").onclick = () => alternarRevisao(!revisando);
$("rev-concluir").onclick = () => alternarRevisao(false);
$("rev-exportar").onclick = () => exportarRevisao();
$("marcas-exportar").onclick = () => exportarRevisao();
let confirmandoDesfazer = 0;
$("rev-desfazer").onclick = () => {
  const rotulo = $("rev-desfazer").querySelector("span");
  if (Date.now() - confirmandoDesfazer > 3000) {
    confirmandoDesfazer = Date.now();
    rotulo.textContent = "Clique de novo para desfazer";
    setTimeout(() => { rotulo.textContent = "Desfazer tudo"; }, 3000);
    return;
  }
  revisao.textos = {}; revisao.falantes = {}; revisao.nomes = {};
  salvarRevisao(); renderTranscricao(); renderFicha(); montarFiltros(); montarLegendaLt(); pedirOnda();
  rotulo.textContent = "Desfazer tudo";
  aviso("Revisão desfeita");
};
const transcricao = $("transcricao");
transcricao.addEventListener("input", e => {
  const s = e.target.closest(".seg");
  if (!s || !revisando) return;
  const i = Number(s.dataset.i), texto = s.textContent.replace(/\s+/g, " ").trim();
  // `o` é o texto que a frase tinha na primeira edição: é o "original" que a exportação envia, para o CLI detectar conflito.
  if (texto && texto !== segs[i].t) revisao.textos[i] = { t: texto, o: revisao.textos[i]?.o ?? segs[i].t }; else delete revisao.textos[i];
  s.classList.toggle("editada", i in revisao.textos);
  salvarRevisao();
});
transcricao.addEventListener("keydown", e => {
  if (!revisando || !e.target.closest(".seg")) return;
  if (e.key === "Enter") { e.preventDefault(); e.target.blur(); }
  if (e.key === "Escape") { const i = Number(e.target.dataset.i); delete revisao.textos[i]; salvarRevisao(); pintar(i); e.target.blur(); }
});
transcricao.addEventListener("paste", e => {   // cola só texto, sem formatação
  if (!revisando || !e.target.closest(".seg")) return;
  e.preventDefault();
  document.execCommand("insertText", false, (e.clipboardData?.getData("text/plain") || "").replace(/\s+/g, " "));
});
transcricao.addEventListener("focusout", e => { const s = e.target.closest?.(".seg"); if (s && revisando) pintar(Number(s.dataset.i)); });
transcricao.addEventListener("change", e => {
  const sel = e.target.closest("select.falante");
  if (!sel) return;
  const k = Number(sel.dataset.k), p = pars[k], chave = p.segs[0];
  let rot = sel.value, novo = false;
  if (rot === "__novo") { rot = "F" + (Math.max(0, ...falantesDisponiveis().map(f => rank(f.rot))) + 1); novo = true; }
  // Guardado pela primeira frase, com as frases vistas agora: os parágrafos mudam quando os falantes mudam.
  if (rot === p.rot) delete revisao.falantes[chave]; else revisao.falantes[chave] = { rot, segs: [...p.segs] };
  salvarRevisao(); refazerParagrafo(k); montarFiltros(); montarLegendaLt(); pedirOnda();
  if (novo) { renderFicha(); aviso(`${nomeFalante(rot)} criado. Dê um nome a ele na aba Ficha.`, () => abrirAba("ficha"), "Abrir a Ficha"); }
});
function exportarRevisao() {
  const dados = {
    tipo: "degravacao-revisao", versao: 1, slug: D.slug, gerado_em: D.geradoEm, exportado_em: new Date().toISOString(),
    correcoes: Object.entries(revisao.textos).map(([i, e]) => ({ i: Number(i), original: e.o, texto: e.t })),
    falantes: Object.values(revisao.falantes).flatMap(e => e.segs.map(i => ({ i, falante: e.rot }))),
    nomes: revisao.nomes,
    marcacoes: marcas.map(({ id, de, ate, ini, fim, cat, nota, texto }) => ({ id, de, ate, ini, fim, cat, nota, texto })),
  };
  baixar(`revisao-${D.slug}.json`, JSON.stringify(dados, null, 1));
  aviso(`Arquivo revisao-${D.slug}.json salvo em Downloads. No Claude, peça: “aplique a revisão da degravação ${D.slug}”.`);
}

/* ================= resumo e ficha ================= */
if (D.estrutura) $("estrutura").innerHTML = D.estrutura;
else {
  $("p-resumo").classList.add("vazio");
  $("estrutura").innerHTML = '<p class="vazio">O resumo ainda não foi feito. No Claude Code, peça: <b>“estruture a degravação '
    + esc(D.slug) + '”</b>. Ele preenche resumo executivo, participantes, tópicos e pontos de atenção, que também aparecem na linha do tempo.</p>';
}
function renderFicha() {
  const dl = $("dados");
  dl.textContent = "";
  for (const [k, v] of D.ficha) dl.append(el("dt", { text: k }), el("dd", { text: v }));
  const falas = $("falas");
  falas.textContent = "";
  // Na revisão, também os falantes criados por "+ Novo falante", para receberem nome.
  const lista = revisando
    ? falantesDisponiveis().map(x => D.falantes.find(f => f.rot === x.rot) || { rot: x.rot, nome: null, tempo: "—", seg: 0, r: rank(x.rot) })
    : D.falantes;
  if (lista.length) {
    const total = lista.reduce((s, f) => s + f.seg, 0) || 1;
    falas.append(el("h3", { class: "secao-titulo", text: "Tempo de fala" }));
    const grade = el("div", { class: "falas" });
    for (const f of lista) {
      const nome = revisando
        ? el("input", { value: nomeFalante(f.rot), "aria-label": `Nome de ${f.rot}`, placeholder: `Falante ${rank(f.rot)}` })
        : el("span", { text: nomeFalante(f.rot) });
      if (revisando) nome.oninput = () => {
        const v = nome.value.trim();
        if (v && v !== f.nome) revisao.nomes[f.rot] = v; else delete revisao.nomes[f.rot];
        salvarRevisao(); clearTimeout(nome._t);
        nome._t = setTimeout(() => { renderTranscricao(); montarFiltros(); montarLegendaLt(); }, 350);
      };
      grade.append(el("div", { class: "fala-linha" },
        el("div", { class: "fala-nome" }, el("i", { class: "amostra", "--cor": cor(f.r) }), nome),
        el("div", { class: "fala-barra", title: Math.round(100 * f.seg / total) + "% do tempo de fala" },
          el("i", { "--cor": cor(f.r), style: `width:${(100 * f.seg / total).toFixed(1)}%` })),
        el("span", { class: "fala-tempo", text: f.tempo })));
    }
    falas.append(grade);
    if (revisando) falas.append(el("p", { class: "nota", text: "Dê nome a cada falante (ex.: Juiz(a), Testemunha — Maria). O nome vai para o documento quando a revisão for aplicada." }));
  }
  const arq = $("arquivos");
  arq.textContent = "";
  if (local && D.arquivos.length) {
    arq.append(el("h3", { class: "secao-titulo", text: "Arquivos desta degravação" }));
    const lista = el("div", { class: "arquivos" });
    for (const [rotulo, nome, ic] of D.arquivos) lista.append(el("a", { class: "btn", href: encodeURI(nome), download: nome.endsWith(".docx") ? nome : null }, icone(ic), rotulo));
    lista.append(el("button", { class: "btn", onclick: () => window.print() }, icone("imprimir"), "Imprimir ou salvar PDF"));
    arq.append(lista);
  }
}

/* ================= abas, diálogo e teclado ================= */
const ABAS = { transcricao: "p-transcricao", resumo: "p-resumo", marcacoes: "p-marcacoes", ficha: "p-ficha" };
function abrirAba(nome) {
  for (const [n, painel] of Object.entries(ABAS)) {
    $("aba-" + n).setAttribute("aria-selected", String(n === nome));
    $(painel).hidden = n !== nome;
  }
}
for (const n of Object.keys(ABAS)) $("aba-" + n).onclick = e => { abrirAba(n); e.currentTarget.blur(); };
for (const id of ["seguir", "aj-pular", "aj-retroceder"]) $(id).addEventListener("change", e => e.target.blur());

const dialogo = $("dlg-atalhos");
function abrirAtalhos() { if (dialogo.showModal) dialogo.showModal(); else dialogo.setAttribute("open", ""); }
function fecharAtalhos() { if (dialogo.close) dialogo.close(); else dialogo.removeAttribute("open"); }
$("btn-atalhos").onclick = abrirAtalhos;
dialogo.addEventListener("click", e => {
  if (e.target.closest("[data-fechar]")) { fecharAtalhos(); return; }
  if (e.target !== dialogo) return;
  const r = dialogo.getBoundingClientRect();   // o próprio <dialog> é o alvo também no espaçamento interno: só fecha fora da caixa
  if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) fecharAtalhos();
});

document.addEventListener("keydown", e => {
  if (e.key === "Escape") { fecharMenus(); esconderSelecao(); limparBusca(); }
  const alvo = document.activeElement;
  if (alvo && (["INPUT", "SELECT", "TEXTAREA"].includes(alvo.tagName) || alvo.isContentEditable)) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "/") { e.preventDefault(); abrirAba("transcricao"); $("busca").focus(); return; }
  if (e.key === "?") { e.preventDefault(); abrirAtalhos(); return; }
  if (!temMidia) return;
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase();
  if (alvo?.tagName === "BUTTON" && (k === " " || k === "enter")) return;   // o botão focado age sozinho
  const acoes = {
    " ": alternar, k: alternar, arrowleft: () => pular(-5), arrowright: () => pular(5), j: () => pular(-10), l: () => pular(10),
    "<": () => mudarVelocidade(-1), ">": () => mudarVelocidade(1), c: alternarLegendas, m: marcarAtual, r: alternarRepetir,
    n: proximoConferir, f: telaCheia, p: abrirPip,
  };
  if (acoes[k]) { e.preventDefault(); acoes[k](); }
});

/* ================= início ================= */
if (local) { $("btn-revisar").hidden = false; $("marcas-exportar").hidden = false; }
renderTranscricao();
montarFiltros();
montarSumario();
montarLegendaLt();
desenharMarcos();
renderListaMarcas();
renderFicha();
contarRevisao();
if (migrouLocal) { loja.gravar(CHAVE + ":marcas", { base: D.revisaoEm, itens: marcas }); loja.gravar(CHAVE + ":revisao", revisao); }
if (pendentesLocais || descartadasLocais) setTimeout(() => {   // depois do aviso "Você parou em…", que tem seu tempo de ser lido
  const n = pendentesLocais, partes = [];
  if (n) partes.push(`${n} alteraç${n > 1 ? "ões feitas" : "ão feita"} neste navegador ainda não ${n > 1 ? "foram aplicadas" : "foi aplicada"} ao documento — exporte a revisão para aplicá-las.`);
  if (descartadasLocais) partes.push(`${descartadasLocais} troca(s) de falante deste navegador não valem mais: os parágrafos mudaram.`);
  aviso(partes.join(" "), n && local ? exportarRevisao : null, "Exportar");
}, 7000);
if (segs.length) mostrarAgora(0, segs[0].ini);   // antes do play, a primeira fala já aparece
$("tempo-total").textContent = " / " + hms(duracao());
lt.setAttribute("aria-valuemax", Math.floor(duracao()));
estadoPlay(false);
if (temMidia) {
  definirVolume(prefs.volume, prefs.mudo);
  if (velocidades.includes(prefs.velocidade)) definirVelocidade(prefs.velocidade);
  video.addEventListener("loadedmetadata", () => {
    if (prefs.velocidade !== 1) video.playbackRate = prefs.velocidade;
    pedirOnda();
    const h = location.hash.match(/^#t=?(\d+(?:\.\d+)?)$/);
    if (h) { video.currentTime = Number(h[1]); return; }
    const salvo = loja.ler(CHAVE + ":posicao", 0);
    if (salvo > 15 && salvo < duracao() - 10) aviso(`Você parou em ${hms(salvo)}.`, () => ir(salvo), "Continuar de lá");
  }, { once: true });
}
pedirOnda();
if (ABAS[location.hash.slice(1)]) abrirAba(location.hash.slice(1));
