#!/usr/bin/env python3
"""Degravação de vídeos e áudios para advogados — ponto de entrada único.

Uso rápido:
    python degravar.py instalar                     # 1ª vez: cria .venv e instala dependências
    python degravar.py "https://drive.google.com/file/d/…/view"
    python degravar.py "C:\\Audiencias\\audiencia.mp4"
    python degravar.py                              # processa tudo que estiver em entrada/
    python degravar.py transcrever --monitorar      # vigia entrada/ e degrava o que chegar
    python degravar.py assistir                     # abre o player da última degravação
    python degravar.py listar
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VENV = RAIZ / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

# Acentos e símbolos no terminal do Windows.
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _dentro_da_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def instalar(baixar_modelo: str | None) -> int:
    if not VENV_PY.exists():
        print(f"• criando ambiente virtual em {VENV} …")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    print("• instalando dependências (faster-whisper, gdown)…")
    subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip", "-q"])
    subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")])
    if baixar_modelo:
        print(f"• baixando modelo Whisper '{baixar_modelo}' (pode levar alguns minutos)…")
        subprocess.check_call([str(VENV_PY), str(RAIZ / "degravar.py"), "_baixar_modelo", baixar_modelo])
    print("\n✓ Instalação concluída. Coloque vídeos em entrada/ e rode: python degravar.py")
    return 0


# Se a .venv existe e não estamos nela, reexecuta o script com o Python da .venv.
if __name__ == "__main__" and VENV_PY.exists() and not _dentro_da_venv() and "instalar" not in sys.argv[1:2]:
    sys.exit(subprocess.call([str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]]))

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402
import webbrowser  # noqa: E402
from datetime import datetime  # noqa: E402

from degravacao import documento, fontes  # noqa: E402
from degravacao.util import minutagem, slugify, src_relativo  # noqa: E402

ENTRADA = RAIZ / "entrada"
SAIDA = RAIZ / "saida"
DOWNLOADS = SAIDA / ".baixando"
VOCABULARIO = RAIZ / "config" / "vocabulario.txt"

# Formatos que o navegador não reproduz: convertidos para o player se houver ffmpeg.
NAO_REPRODUZIVEIS = {".mkv", ".avi", ".wmv", ".flv", ".mpg", ".mpeg", ".3gp", ".ts", ".wma", ".amr"}


# ---------------------------------------------------------------- utilidades

def processados() -> dict[str, Path]:
    """Mapa chave-da-fonte → pasta, a partir das degravações já existentes."""
    mapa: dict[str, Path] = {}
    for j in SAIDA.glob("*/transcricao.json"):
        try:
            mapa[json.loads(j.read_text(encoding="utf-8"))["chave"]] = j.parent
        except Exception:  # noqa: BLE001
            continue
    return mapa


def pasta_destino(slug: str, chave: str, mapa: dict[str, Path]) -> Path:
    if chave in mapa:
        return mapa[chave]
    pasta, n = SAIDA / slug, 2
    while pasta.exists():
        pasta, n = SAIDA / f"{slug}-{n}", n + 1
    return pasta


def carregar_vocabulario(extra: str | None) -> str:
    termos: list[str] = []
    if extra:
        termos += [t.strip() for t in extra.split(",") if t.strip()]
    if VOCABULARIO.exists():
        for linha in VOCABULARIO.read_text(encoding="utf-8").splitlines():
            linha = linha.split("#", 1)[0].strip()
            if linha:
                termos += [t.strip() for t in linha.split(",") if t.strip()]
    vistos, unicos = set(), []
    for t in termos:
        if t.lower() not in vistos:
            vistos.add(t.lower())
            unicos.append(t)
    return ", ".join(unicos)


def preparar_video_player(midia: Path, pasta: Path, converter: bool) -> Path:
    if midia.suffix.lower() not in NAO_REPRODUZIVEIS or not converter:
        return midia
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print(f"  ⚠ o navegador não reproduz {midia.suffix}; instale o ffmpeg para conversão automática.")
        return midia
    eh_audio = midia.suffix.lower() in fontes.EXT_AUDIO
    destino = pasta / (midia.stem + (".m4a" if eh_audio else ".mp4"))
    print(f"  ⚙ convertendo para {destino.suffix} (compatível com o navegador)…")
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(midia)]
    cmd += (["-vn"] if eh_audio else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"])
    cmd += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(destino)]
    if subprocess.call(cmd) == 0:
        return destino
    print("  ⚠ conversão falhou; o player usará o arquivo original.")
    return midia


def regravar_documentos(pasta: Path, dados: dict) -> Path:
    """(Re)gera .md, legendas e player preservando a seção já estruturada pelo Claude."""
    from degravacao.player import gerar_player

    titulo = dados["titulo"]
    md = pasta / f"{dados['slug']}.md"
    estrutura_antiga = None
    if md.exists():
        atual = md.read_text(encoding="utf-8")
        ini, fim = atual.find(documento.MARCA_CLAUDE_INI), atual.find(documento.MARCA_CLAUDE_FIM)
        if 0 <= ini < fim and "_Pendente." not in atual[ini:fim]:
            estrutura_antiga = atual[ini:fim]
    md = documento.salvar_tudo(pasta, dados, titulo)
    if estrutura_antiga:
        novo = md.read_text(encoding="utf-8")
        ini, fim = novo.find(documento.MARCA_CLAUDE_INI), novo.find(documento.MARCA_CLAUDE_FIM)
        md.write_text(novo[:ini] + estrutura_antiga + novo[fim:], encoding="utf-8")
    gerar_player(pasta, dados, titulo, src_relativo(Path(dados["caminho_video"]), pasta))
    return md


# ---------------------------------------------------------------- transcrição

def degravar_uma(midia: fontes.Midia, modelo_ref: dict, args, vocab: str, mapa: dict[str, Path]) -> Path:
    from degravacao import transcricao

    titulo = midia.caminho.stem
    slug = slugify(titulo)
    pasta = pasta_destino(slug, midia.chave, mapa)
    slug = pasta.name
    print(f"\n■ {midia.caminho.name}  →  saida/{slug}/")

    if modelo_ref.get("modelo") is None:
        modelo_ref["modelo"] = transcricao.carregar_modelo(args.modelo, args.dispositivo)
    try:
        dados = transcricao.transcrever(modelo_ref["modelo"], midia.caminho, args.idioma, vocab)
    except RuntimeError as e:
        if getattr(modelo_ref["modelo"], "_degravacao_info", {}).get("dispositivo") != "cuda":
            raise
        print(f"\n  ⚠ falha na GPU ({e}); repetindo na CPU.")
        modelo_ref["modelo"] = transcricao.carregar_modelo(args.modelo, "cpu")
        dados = transcricao.transcrever(modelo_ref["modelo"], midia.caminho, args.idioma, vocab)

    pasta.mkdir(parents=True, exist_ok=True)
    # Destino final da mídia; mover/copiar só acontece depois que tudo foi gravado.
    levar = midia.mover or args.copiar_video
    arquivo = pasta / midia.caminho.name if levar else midia.caminho

    chave = midia.chave
    if midia.mover and midia.origem == "Arquivo local":
        chave = f"arquivo:{arquivo.resolve()}"  # o arquivo passa a morar na pasta de saída

    video = preparar_video_player(midia.caminho, pasta, not args.sem_converter)
    if video == midia.caminho:
        video = arquivo
    dados.update({
        "titulo": titulo,
        "slug": slug,
        "arquivo": midia.caminho.name,
        "origem": midia.origem,
        "url": midia.url,
        "chave": chave,
        "caminho_midia": str(arquivo.resolve()),
        "caminho_video": str(video.resolve()),
        "vocabulario": vocab,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    })
    (pasta / "transcricao.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    md = regravar_documentos(pasta, dados)
    if levar and midia.caminho.resolve() != arquivo.resolve():
        (shutil.move if midia.mover else shutil.copy2)(str(midia.caminho), str(arquivo))
    mapa[chave] = pasta

    duvidas = sum(1 for s in dados["segmentos"] if s["baixa_confianca"])
    print(f"  ✓ {minutagem(dados['duracao'])} degravados em {dados['tempo_processamento'] / 60:.1f} min "
          f"· {len(dados['segmentos'])} segmentos · {duvidas} para conferência")
    print(f"  ✓ documento: {md.relative_to(RAIZ)}")
    print(f"  ✓ player:    {(pasta / 'player.html').relative_to(RAIZ)}")
    return pasta


def cmd_transcrever(args) -> int:
    SAIDA.mkdir(exist_ok=True)
    ENTRADA.mkdir(exist_ok=True)
    vocab = carregar_vocabulario(args.vocabulario)
    modelo_ref: dict = {}

    if args.monitorar:
        return monitorar(args, vocab, modelo_ref)

    mapa = processados()
    try:
        midias = fontes.resolver(args.entradas, ENTRADA, DOWNLOADS, set() if args.refazer else set(mapa))
    except fontes.ErroEntrada as e:
        print(f"✗ {e}")
        return 1
    if not midias:
        print("Nada a degravar. Coloque vídeos/áudios em entrada/ ou informe um link/caminho.")
        return 0

    print(f"{len(midias)} mídia(s) para degravar · modelo {args.modelo} · idioma {args.idioma or 'automático'}")
    falhas = 0
    for m in midias:
        try:
            degravar_uma(m, modelo_ref, args, vocab, mapa)
        except KeyboardInterrupt:
            print("\nInterrompido.")
            return 130
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"\n  ✗ falha ao degravar {m.caminho.name}: {e}")
    if DOWNLOADS.exists() and not any(DOWNLOADS.iterdir()):
        DOWNLOADS.rmdir()
    return 1 if falhas else 0


def monitorar(args, vocab: str, modelo_ref: dict) -> int:
    print(f"Vigiando {ENTRADA} a cada {args.intervalo}s. Ctrl+C para sair.")
    tamanhos: dict[Path, int] = {}
    try:
        while True:
            for arq in fontes.listar_pasta(ENTRADA):
                tam = arq.stat().st_size
                if tamanhos.get(arq) != tam:  # ainda copiando: espera o tamanho estabilizar
                    tamanhos[arq] = tam
                    continue
                midia = fontes.Midia(arq, "Arquivo local", f"arquivo:{arq.resolve()}", mover=True)
                try:
                    degravar_uma(midia, modelo_ref, args, vocab, processados())
                except Exception as e:  # noqa: BLE001
                    print(f"  ✗ falha: {e} — movendo para entrada/_falhas/")
                    (ENTRADA / "_falhas").mkdir(exist_ok=True)
                    shutil.move(str(arq), str(ENTRADA / "_falhas" / arq.name))
                tamanhos.pop(arq, None)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")
        return 0


# ---------------------------------------------------------------- outros comandos

def localizar(nome: str | None) -> Path | None:
    pastas = sorted((j.parent for j in SAIDA.glob("*/transcricao.json")), key=lambda p: p.stat().st_mtime)
    if not nome:
        return pastas[-1] if pastas else None
    p = Path(nome)
    if p.is_file():
        p = p.parent
    if (p / "transcricao.json").exists():
        return p
    alvo = slugify(nome)
    for pasta in reversed(pastas):
        if pasta.name == nome or pasta.name == alvo:
            return pasta
    for pasta in reversed(pastas):
        if alvo in pasta.name:
            return pasta
    return None


def cmd_assistir(args) -> int:
    pasta = localizar(args.nome)
    if not pasta:
        print("Degravação não encontrada. Use: python degravar.py listar")
        return 1
    player = pasta / "player.html"
    print(f"Abrindo {player}")
    webbrowser.open(player.resolve().as_uri() + (f"#t={args.em}" if args.em else ""))
    return 0


def cmd_listar(_args) -> int:
    pastas = sorted(SAIDA.glob("*/transcricao.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pastas:
        print("Nenhuma degravação ainda.")
        return 0
    for j in pastas:
        d = json.loads(j.read_text(encoding="utf-8"))
        md = j.parent / f"{d['slug']}.md"
        estruturado = "estruturado" if "_Pendente." not in md.read_text(encoding="utf-8") else "sem estrutura"
        print(f"{d['slug']:<45} {minutagem(d['duracao'])}  {d['gerado_em'][:10]}  {d['origem']:<14} {estruturado}")
    return 0


def cmd_regerar(args) -> int:
    pasta = localizar(args.nome)
    if not pasta:
        print("Degravação não encontrada.")
        return 1
    dados = json.loads((pasta / "transcricao.json").read_text(encoding="utf-8"))
    md = regravar_documentos(pasta, dados)
    print(f"✓ regerados: {md.name}, legendas e player.html (seção estruturada preservada)")
    return 0


def _baixar_modelo(nome: str) -> int:
    from degravacao.transcricao import carregar_modelo
    carregar_modelo(nome, "cpu")
    print("✓ modelo disponível.")
    return 0


# ---------------------------------------------------------------- argparse

COMANDOS = {"instalar", "transcrever", "assistir", "listar", "regerar", "_baixar_modelo"}


def main(argv: list[str]) -> int:
    if not argv or (argv[0] not in COMANDOS and argv[0] not in {"-h", "--help"}):
        argv = ["transcrever", *argv]

    ap = argparse.ArgumentParser(prog="degravar", description="Degravação integral de vídeos/áudios.")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("instalar", help="cria .venv e instala dependências")
    p.add_argument("--baixar-modelo", metavar="MODELO", help="já baixa o modelo (ex.: large-v3, turbo)")

    p = sub.add_parser("transcrever", help="degrava links do Drive, arquivos ou pastas (padrão: entrada/)")
    p.add_argument("entradas", nargs="*", help="link do Google Drive, arquivo ou pasta")
    p.add_argument("--modelo", default=os.environ.get("DEGRAVAR_MODELO", "large-v3"),
                   help="large-v3 (padrão, mais preciso) · turbo (bem mais rápido) · medium · small")
    p.add_argument("--idioma", default="pt", help="código do idioma (padrão pt; use '' para detectar)")
    p.add_argument("--dispositivo", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--vocabulario", help="termos extras separados por vírgula (nomes das partes, termos técnicos)")
    p.add_argument("--refazer", action="store_true", help="degrava de novo mesmo se já processado")
    p.add_argument("--copiar-video", action="store_true", help="copia o arquivo local para a pasta de saída")
    p.add_argument("--sem-converter", action="store_true", help="não converte formatos que o navegador não abre")
    p.add_argument("--monitorar", action="store_true", help="vigia entrada/ continuamente")
    p.add_argument("--intervalo", type=int, default=20, help="segundos entre verificações no modo monitor")

    p = sub.add_parser("assistir", help="abre o player com transcrição sincronizada")
    p.add_argument("nome", nargs="?", help="nome/slug da degravação (padrão: a mais recente)")
    p.add_argument("--em", type=int, help="abre já na minutagem (segundos)")

    sub.add_parser("listar", help="lista as degravações feitas")

    p = sub.add_parser("regerar", help="regera .md, legendas e player a partir do transcricao.json")
    p.add_argument("nome", nargs="?")

    p = sub.add_parser("_baixar_modelo")
    p.add_argument("nome")

    args = ap.parse_args(argv)
    if args.comando == "instalar":
        return instalar(args.baixar_modelo)
    if args.comando in {"transcrever", "_baixar_modelo"}:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            print("Dependências ausentes. Rode primeiro:  python degravar.py instalar")
            return 1
    if args.comando == "_baixar_modelo":
        return _baixar_modelo(args.nome)
    return {"transcrever": cmd_transcrever, "assistir": cmd_assistir,
            "listar": cmd_listar, "regerar": cmd_regerar}[args.comando](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
